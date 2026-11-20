# MicroProfile REST Client Patterns

Detailed patterns for integrating external HTTP services using MicroProfile REST Client in Quarkus with Kotlin coroutines.

## Architecture

```
@RegisterRestClient interface (type-safe)
  └── ClientHeadersFactory / @ClientHeaderParam (auth, tracing)
       └── External HTTP Service
```

## Dependencies

```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-rest-client-jackson</artifactId>
</dependency>
```

## Declaring a REST Client Interface

```kotlin
@RegisterRestClient(configKey = "my-api")
@Path("/api/v1")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
interface MyApiClient {

    @GET
    @Path("/resources/{id}")
    suspend fun getResource(@PathParam("id") id: String): ResourceDto

    @POST
    @Path("/resources")
    suspend fun createResource(request: CreateResourceRequest): ResourceDto

    @GET
    @Path("/resources")
    suspend fun listResources(
        @QueryParam("page") page: Int = 0,
        @QueryParam("size") size: Int = 20,
    ): List<ResourceDto>

    @PUT
    @Path("/resources/{id}")
    suspend fun updateResource(
        @PathParam("id") id: String,
        body: UpdateResourceRequest,
    ): ResourceDto

    @DELETE
    @Path("/resources/{id}")
    suspend fun deleteResource(@PathParam("id") id: String): Response
}
```

## Injecting and Using the Client

```kotlin
@ApplicationScoped
class MyExternalService(
    @RestClient private val apiClient: MyApiClient,
) {
    companion object {
        private val log = LoggerFactory.getLogger(MyExternalService::class.java)
    }

    suspend fun fetchResource(id: String): ResourceDto {
        return apiClient.getResource(id)
    }

    suspend fun fetchResourceOrNull(id: String): ResourceDto? {
        return try {
            apiClient.getResource(id)
        } catch (e: WebApplicationException) {
            if (e.response.status == 404) {
                log.warn("Resource $id not found upstream")
                null
            } else {
                log.error("Upstream error: ${e.response.status}", e)
                throw UpstreamServiceException("Failed to fetch resource", e)
            }
        }
    }
}
```

## Authentication — ClientHeadersFactory

Use `ClientHeadersFactory` to inject auth headers into every outbound request:

```kotlin
@ApplicationScoped
class BearerTokenHeaderFactory(
    private val identity: SecurityIdentity,
) : ClientHeadersFactory {

    override fun update(
        incomingHeaders: MultivaluedMap<String, String>,
        outgoingHeaders: MultivaluedMap<String, String>,
    ): MultivaluedMap<String, String> {
        val token = (identity.credential(TokenCredential::class.java))?.token
        if (token != null) {
            outgoingHeaders.putSingle(HttpHeaders.AUTHORIZATION, "Bearer $token")
        }
        return outgoingHeaders
    }
}
```

Register it on the client:

```kotlin
@RegisterRestClient(configKey = "my-api")
@RegisterClientHeaders(BearerTokenHeaderFactory::class)
@Path("/api/v1")
interface MyApiClient { /* ... */ }
```

### Static API Key Header

```kotlin
@RegisterRestClient(configKey = "my-api")
@Path("/api/v1")
interface MyApiClient {

    @GET
    @Path("/resources/{id}")
    @ClientHeaderParam(name = "X-Api-Key", value = ["\${my-api.api-key}"])
    suspend fun getResource(@PathParam("id") id: String): ResourceDto
}
```

## Configuration Properties

```properties
# Base URL
quarkus.rest-client.my-api.url=https://api.example.com

# Scope (default: @Dependent — use @Singleton for shared clients)
quarkus.rest-client.my-api.scope=jakarta.inject.Singleton

# Timeouts
quarkus.rest-client.my-api.connect-timeout=5000
quarkus.rest-client.my-api.read-timeout=30000

# TLS trust store (if the upstream uses a private CA)
quarkus.rest-client.my-api.trust-store=classpath:truststore.p12
quarkus.rest-client.my-api.trust-store-password=${TRUSTSTORE_PASSWORD}
quarkus.rest-client.my-api.trust-store-type=PKCS12

# Hostname verification
quarkus.rest-client.my-api.hostname-verifier=io.quarkus.restclient.runtime.NoopHostnameVerifier

# Per-environment overrides
%dev.quarkus.rest-client.my-api.url=http://localhost:8081
%test.quarkus.rest-client.my-api.url=http://localhost:${quarkus.http.test-port}
```

## Timeout and Retry with SmallRye Fault Tolerance

```kotlin
@ApplicationScoped
class ResilientService(
    @RestClient private val apiClient: MyApiClient,
) {
    @Timeout(value = 10, unit = ChronoUnit.SECONDS)
    @Retry(maxRetries = 3, delay = 500, delayUnit = ChronoUnit.MILLIS)
    @CircuitBreaker(requestVolumeThreshold = 10, failureRatio = 0.5, delay = 10000)
    @Fallback(fallbackMethod = "fallbackResource")
    suspend fun fetchResourceResilient(id: String): ResourceDto {
        return apiClient.getResource(id)
    }

    private suspend fun fallbackResource(id: String): ResourceDto {
        return ResourceDto(id = id, status = "UNAVAILABLE")
    }
}
```

Add the dependency:
```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-smallrye-fault-tolerance</artifactId>
</dependency>
```

## Error Handling with ResponseExceptionMapper

Map upstream HTTP errors to domain exceptions globally:

```kotlin
class MyApiExceptionMapper : ResponseExceptionMapper<RuntimeException> {

    override fun toThrowable(response: Response): RuntimeException {
        return when (response.status) {
            400 -> BadRequestException("Upstream returned 400: ${response.readEntity(String::class.java)}")
            401, 403 -> AuthenticationException("Upstream auth failure: ${response.status}")
            404 -> NotFoundException("Upstream resource not found")
            429 -> RateLimitException("Upstream rate limit exceeded")
            in 500..599 -> UpstreamServiceException("Upstream error: ${response.status}")
            else -> RuntimeException("Unexpected upstream status: ${response.status}")
        }
    }

    override fun getPriority(): Int = 50
}
```

Register via `@RegisterProvider`:

```kotlin
@RegisterRestClient(configKey = "my-api")
@RegisterProvider(MyApiExceptionMapper::class)
@Path("/api/v1")
interface MyApiClient { /* ... */ }
```

## Testing

```kotlin
@QuarkusTest
class MyExternalServiceTest {

    @InjectMock
    @RestClient
    lateinit var apiClient: MyApiClient

    @Inject
    lateinit var service: MyExternalService

    @Test
    fun `should return resource from upstream`() = runTest {
        val expected = ResourceDto(id = "123", name = "test")
        Mockito.`when`(apiClient.getResource("123")).thenReturn(expected)

        val result = service.fetchResource("123")
        assertEquals(expected, result)
    }

    @Test
    fun `should return null when not found`() = runTest {
        Mockito.`when`(apiClient.getResource("missing"))
            .thenThrow(WebApplicationException(Response.status(404).build()))

        val result = service.fetchResourceOrNull("missing")
        assertNull(result)
    }
}
```

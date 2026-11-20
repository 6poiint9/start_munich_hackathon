# WebClient HTTP Integration Patterns

Detailed patterns for integrating external HTTP services using Spring WebClient with Kotlin coroutines.

## Architecture

```
CoWebClient (coroutine wrapper)  ──or──  WebClient (reactive)
  └── ExchangeFilterFunction (auth, logging, tracing)
       └── External HTTP Service
```

## Creating a WebClient Bean

```kotlin
@Configuration
class MyServiceConfig {

    @Bean
    @Qualifier("webClientMyService")
    fun webClientMyService(
        builder: WebClient.Builder,
        @Value("\${my-service.host}") host: String,
    ): WebClient = builder
        .baseUrl(host)
        .filter(authFilter())
        .filter(loggingFilter())
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .codecs { it.defaultCodecs().maxInMemorySize(2 * 1024 * 1024) }
        .build()
}
```

## Using WebClient with Coroutines

```kotlin
@Service
class MyExternalService(
    @Qualifier("webClientMyService") private val webClient: WebClient,
) {
    companion object {
        private val log = LoggerFactory.getLogger(MyExternalService::class.java)
    }

    // GET request
    suspend fun fetchData(id: String): MyResponse {
        return webClient.get()
            .uri("/api/v1/resources/{id}", id)
            .retrieve()
            .awaitBody<MyResponse>()
    }

    // POST request
    suspend fun createResource(request: CreateRequest): CreateResponse {
        return webClient.post()
            .uri("/api/v1/resources")
            .bodyValue(request)
            .retrieve()
            .awaitBody<CreateResponse>()
    }

    // Streaming response
    fun streamData(): Flow<DataItem> {
        return webClient.get()
            .uri("/api/v1/stream")
            .retrieve()
            .bodyToFlow<DataItem>()
    }

    // Handle errors
    suspend fun fetchWithErrorHandling(id: String): MyResponse? {
        return try {
            webClient.get()
                .uri("/api/v1/resources/{id}", id)
                .retrieve()
                .awaitBody<MyResponse>()
        } catch (e: WebClientResponseException.NotFound) {
            log.warn("Resource $id not found")
            null
        } catch (e: WebClientResponseException) {
            log.error("Upstream error: ${e.statusCode}", e)
            throw UpstreamServiceException("Failed to fetch resource", e)
        }
    }
}
```

## Authentication Filters

Use `ExchangeFilterFunction` to add auth headers per-request:

```kotlin
// Bearer token forwarding
class BearerTokenFilter : ExchangeFilterFunction {
    override fun filter(request: ClientRequest, next: ExchangeFunction): Mono<ClientResponse> {
        val token = ReactiveSecurityContextHolder.getContext()
            .map { it.authentication.credentials as String }

        return token.flatMap { bearerToken ->
            val filtered = ClientRequest.from(request)
                .header(HttpHeaders.AUTHORIZATION, "Bearer $bearerToken")
                .build()
            next.exchange(filtered)
        }
    }
}

// Static API key
class ApiKeyFilter(private val apiKey: String) : ExchangeFilterFunction {
    override fun filter(request: ClientRequest, next: ExchangeFunction): Mono<ClientResponse> {
        val filtered = ClientRequest.from(request)
            .header("X-Api-Key", apiKey)
            .build()
        return next.exchange(filtered)
    }
}

```

## Request/Response Logging Filter

```kotlin
class LoggingFilter : ExchangeFilterFunction {
    private val log = LoggerFactory.getLogger(LoggingFilter::class.java)

    override fun filter(request: ClientRequest, next: ExchangeFunction): Mono<ClientResponse> {
        log.debug("Request: ${request.method()} ${request.url()}")
        return next.exchange(request).doOnNext { response ->
            log.debug("Response: ${response.statusCode()} for ${request.url()}")
        }
    }
}
```

## Configuration Properties

```yaml
my-service:
  host: ${MY_SERVICE_HOST:http://localhost:8080}
  timeout: 30s
  max-retries: 3
  api-key: ${MY_SERVICE_API_KEY}
```

## Timeout and Retry Configuration

```kotlin
@Bean
fun webClientWithTimeout(
    builder: WebClient.Builder,
    @Value("\${my-service.host}") host: String,
    @Value("\${my-service.timeout:30s}") timeout: Duration,
): WebClient = builder
    .baseUrl(host)
    .clientConnector(
        ReactorClientHttpConnector(
            HttpClient.create()
                .responseTimeout(timeout)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, timeout.toMillis().toInt())
        )
    )
    .build()
```

## Polling Pattern (for async commands)

```kotlin
suspend fun pollForResult(
    requestId: String,
    intervalSeconds: Long = 2,
    maxRetries: Int = 35,
): CommandResult {
    repeat(maxRetries) { attempt ->
        val status = fetchCommandStatus(requestId)
        if (status.isTerminal()) return status
        delay(intervalSeconds * 1000)
    }
    throw TimeoutException("Command $requestId did not complete within $maxRetries retries")
}
```

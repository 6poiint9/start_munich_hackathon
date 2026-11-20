# GraphQL Client Integration Patterns

Detailed patterns for integrating GraphQL services using Spring's `HttpGraphQlClient` with Kotlin coroutines.

## Setup

```kotlin
@Configuration
class MyGraphQlClientConfig {

    @Bean
    fun graphQlClient(
        @Qualifier("webClientGraphQl") webClient: WebClient,
    ): HttpGraphQlClient = HttpGraphQlClient.builder(webClient)
        .url("/graphql")
        .build()
}
```

## Using the Client

```kotlin
@Service
class MyGraphQlService(
    private val graphQlClient: HttpGraphQlClient,
) {
    suspend fun fetchData(id: String): MyData {
        return graphQlClient.documentName("getMyData")  // references .graphql file
            .variable("id", id)
            .retrieve("myData")
            .toEntity(MyData::class.java)
            .awaitSingle()
    }
}
```

## GraphQL Document Files

Place in `src/main/resources/graphql-documents/getMyData.graphql`:

```graphql
query GetMyData($id: String!) {
  myData(id: $id) {
    id
    name
    items {
      itemId
      description
    }
  }
}
```

## Error Handling

```kotlin
suspend fun fetchWithErrorHandling(id: String): MyData? {
    return try {
        graphQlClient.documentName("getMyData")
            .variable("id", id)
            .retrieve("myData")
            .toEntity(MyData::class.java)
            .awaitSingle()
    } catch (e: FieldAccessException) {
        val errors = e.response.errors
        log.error("GraphQL errors: ${errors.map { it.message }}")
        null
    }
}
```

## Multiple Operations

```kotlin
suspend fun fetchComplexData(id: String): ComplexResponse {
    val response = graphQlClient.documentName("getComplexData")
        .variable("id", id)
        .execute()
        .awaitSingle()

    val partA = response.field("partA").toEntity(PartA::class.java)
    val partB = response.field("partB").toEntityList(PartB::class.java)
    return ComplexResponse(partA, partB)
}
```

## Authentication

GraphQL client inherits authentication from the underlying WebClient. Configure auth filters on the `webClientGraphQl` bean:

```kotlin
@Bean
@Qualifier("webClientGraphQl")
fun webClientGraphQl(
    builder: WebClient.Builder,
    @Value("\${graphql.host}") host: String,
): WebClient = builder
    .baseUrl(host)
    .filter(bearerTokenFilter())
    .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
    .build()
```

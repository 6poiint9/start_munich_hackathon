# spring-boot-service-integration — code examples

Examples moved out of SKILL.md (Layer 3). Section titles match SKILL.md headings.


## Decision Tree — Which Protocol?

```
Need to call an external REST/HTTP API?
  Yes → WebClient with coroutines
        See: references/webclient-patterns.md

Need to call a gRPC/Protobuf service?
  Yes → gRPC with Kotlin coroutine stubs
        See: references/grpc-integration.md

Need to consume events from a message broker?
  Yes → Spring Kafka with Avro schemas
        See: references/kafka-consumers.md

Need to query a GraphQL API?
  Yes → Spring HttpGraphQlClient
        See: references/graphql-client.md
```


## Common Architecture

```
Controller (REST endpoint)
  └── BFF Service (orchestration, coroutines)
       ├── WebClient → External HTTP API
       ├── gRPC Stub → External gRPC Service
       ├── KafkaListener → Event Stream
       └── GraphQlClient → External GraphQL API
```


## WebClient — Quick Start

```kotlin
@Bean
@Qualifier("webClientMyService")
fun webClientMyService(
    builder: WebClient.Builder,
    @Value("\${my-service.host}") host: String,
): WebClient = builder
    .baseUrl(host)
    .filter(authFilter())
    .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
    .build()

// Usage in service
suspend fun fetchData(id: String): MyResponse {
    return webClient.get()
        .uri("/api/v1/resources/{id}", id)
        .retrieve()
        .awaitBody<MyResponse>()
}
```


## gRPC — Quick Start

```kotlin
@Bean
fun myServiceStub(channel: ManagedChannel): MyServiceGrpcKt.MyServiceCoroutineStub =
    MyServiceGrpcKt.MyServiceCoroutineStub(channel)

// Usage in service
suspend fun getData(id: String): DataResponse {
    val request = getDataRequest { this.id = id }
    return stub.getData(request)
}
```


## Kafka — Quick Start

```kotlin
@KafkaListener(
    topics = ["\${kafka.topics.my-events}"],
    containerFactory = "myKafkaListenerContainerFactory",
)
fun onMessage(record: ConsumerRecord<String, ByteArray>, ack: Acknowledgment) {
    val event = deserialize(record.value())
    eventProcessor.process(event)
    ack.acknowledge()
}
```


## GraphQL — Quick Start

```kotlin
suspend fun fetchData(id: String): MyData {
    return graphQlClient.documentName("getMyData")
        .variable("id", id)
        .retrieve("myData")
        .toEntity(MyData::class.java)
        .awaitSingle()
}
```

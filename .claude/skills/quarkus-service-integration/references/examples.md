# quarkus-service-integration — code examples

Examples moved out of SKILL.md (Layer 3). Section titles match SKILL.md headings.


## Decision Tree — Which Integration?

```
Need to call an external REST/HTTP API?
  Yes → MicroProfile REST Client with @RegisterRestClient
        See: references/rest-client-patterns.md

Need to consume or produce events from Kafka?
  Yes → SmallRye Reactive Messaging with @Incoming / @Outgoing
        See: references/kafka-smallrye-patterns.md

Need in-process async communication between CDI beans?
  Yes → Vert.x Event Bus with @ConsumeEvent
        See: references/vertx-eventbus-patterns.md

Need a document database (Azure)?
  Yes → Azure Cosmos DB with custom client + repository pattern
        See: references/cosmos-redis-patterns.md

Need caching or fast key-value lookups?
  Yes → Quarkus Redis client
        See: references/cosmos-redis-patterns.md
```


## Common Architecture

```
REST Resource (JAX-RS endpoint)
  └── Service (orchestration, CDI @ApplicationScoped)
       ├── @RestClient     → External HTTP API
       ├── @Incoming        → Kafka Event Stream
       ├── EventBus.send()  → In-process async
       ├── CosmosRepository → Azure Cosmos DB
       └── RedisDataSource  → Cache layer
```


## MicroProfile REST Client — Quick Start

```kotlin
@RegisterRestClient(configKey = "my-api")
@Path("/api/v1")
interface MyApiClient {

    @GET
    @Path("/resources/{id}")
    suspend fun getResource(@PathParam("id") id: String): ResourceDto
}

// Usage in service
@ApplicationScoped
class MyService(
    @RestClient private val apiClient: MyApiClient,
) {
    suspend fun fetchResource(id: String): ResourceDto =
        apiClient.getResource(id)
}
```


## SmallRye Kafka — Quick Start

```kotlin
@IfBuildProfile("emea-kafka")
@ApplicationScoped
class KafkaConsumerEmea(
    private val core: KafkaMessageConsumer,
) {
    @Incoming("channel-name")
    @Acknowledgment(Acknowledgment.Strategy.POST_PROCESSING)
    suspend fun consume(record: ConsumerRecord<String, GenericRecord>) {
        core.processRecord(record)
    }
}
```


## Vert.x Event Bus — Quick Start

```kotlin
// Sending
@ApplicationScoped
class OrderService(private val eventBus: EventBus) {
    fun notifyOrderCreated(orderId: String) {
        eventBus.send("order.created", orderId)
    }
}

// Consuming
@ApplicationScoped
class OrderNotifier {
    @ConsumeEvent("order.created", ordered = true, blocking = true)
    fun onOrderCreated(orderId: String) {
        // handle event
    }
}
```


## Cosmos DB & Redis — Quick Start

```kotlin
// Cosmos DB repository
@ApplicationScoped
class VehicleRepository(private val cosmosClient: CosmosClient) {
    suspend fun findById(id: String): Vehicle? =
        withContext(Dispatchers.IO) {
            container.readItem(id, PartitionKey(id), Vehicle::class.java)
                .item
        }
}

// Redis caching
@ApplicationScoped
class CacheService(private val redis: RedisDataSource) {
    fun <T> get(key: String, clazz: Class<T>): T? =
        redis.value(clazz).get(key)

    fun <T : Any> put(key: String, value: T, ttl: Duration) {
        redis.value(value.javaClass as Class<T>).setex(key, ttl.seconds, value)
    }
}
```

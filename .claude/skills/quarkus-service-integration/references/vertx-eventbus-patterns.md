# Vert.x Event Bus Patterns

Patterns for in-process asynchronous communication between CDI beans using the Vert.x Event Bus in Quarkus.

## When to Use the Event Bus

| Use Case | Event Bus? | Alternative |
|----------|-----------|-------------|
| Decouple CDI beans within the same JVM | ✅ Yes | — |
| Ordered sequential processing | ✅ Yes (`ordered = true`) | — |
| Fire-and-forget notifications | ✅ Yes | CDI `@Observes` events |
| Cross-service communication | ❌ No | Kafka / HTTP |
| Durable / persistent messaging | ❌ No | Kafka |
| Request-reply across services | ❌ No | REST client / gRPC |

> **Rule of thumb**: Use the Event Bus only for in-process async. For anything that crosses JVM boundaries, use Kafka (durable events) or REST clients (request/reply).

## Dependencies

The Event Bus is built into Quarkus via Vert.x — no extra dependency needed beyond the base Quarkus BOM.

## Sending Events

### Fire-and-Forget (send)

```kotlin
@ApplicationScoped
class OrderService(
    private val eventBus: EventBus,
) {
    suspend fun createOrder(request: CreateOrderRequest): Order {
        val order = persistOrder(request)

        // Fire-and-forget: deliver to exactly one consumer
        eventBus.send("order.created", order.id)

        return order
    }
}
```

### Publish to All Consumers

```kotlin
// Deliver to ALL consumers registered on this address
eventBus.publish("order.status-changed", JsonObject.mapFrom(statusUpdate))
```

### Request-Reply (within JVM)

```kotlin
suspend fun enrichOrder(orderId: String): EnrichedOrder {
    val reply = eventBus.request<JsonObject>("order.enrich", orderId)
        .coAwait()
    return reply.body().mapTo(EnrichedOrder::class.java)
}
```

## Consuming Events

### Basic Consumer

```kotlin
@ApplicationScoped
class OrderNotificationHandler {

    companion object {
        private val log = LoggerFactory.getLogger(OrderNotificationHandler::class.java)
    }

    @ConsumeEvent("order.created")
    fun onOrderCreated(orderId: String) {
        log.info("Order created: $orderId")
        // Send email, push notification, etc.
    }
}
```

### Ordered Processing

When events must be processed in the order they arrive:

```kotlin
@ConsumeEvent("order.created", ordered = true)
fun onOrderCreatedOrdered(orderId: String) {
    // Events are delivered one at a time, in order
}
```

### Blocking Consumer

When the handler performs blocking I/O (JDBC, file I/O):

```kotlin
@ConsumeEvent("order.created", blocking = true)
fun onOrderCreatedBlocking(orderId: String) {
    // Runs on a worker thread instead of the event loop
    jdbcRepository.insertAuditLog(orderId)
}
```

### Combined: Ordered + Blocking

```kotlin
@ConsumeEvent("order.created", ordered = true, blocking = true)
fun onOrderCreatedOrderedBlocking(orderId: String) {
    // Ordered delivery + worker thread
}
```

### Handling Complex Payloads

Use `JsonObject` for structured data:

```kotlin
// Sending
eventBus.send("vehicle.updated", JsonObject().apply {
    put("vin", vin)
    put("field", "status")
    put("newValue", newStatus.name)
})

// Consuming
@ConsumeEvent("vehicle.updated")
fun onVehicleUpdated(payload: JsonObject) {
    val vin = payload.getString("vin")
    val field = payload.getString("field")
    val newValue = payload.getString("newValue")
    // ...
}
```

### Request-Reply Consumer

```kotlin
@ConsumeEvent("order.enrich")
fun enrichOrder(orderId: String): JsonObject {
    val enriched = enrichmentService.enrich(orderId)
    return JsonObject.mapFrom(enriched)
}
```

## Custom Codec (for typed objects)

To send/receive custom Kotlin types without `JsonObject`:

```kotlin
class OrderEventCodec : MessageCodec<OrderEvent, OrderEvent> {
    private val mapper = ObjectMapper().registerKotlinModule()

    override fun encodeToWire(buffer: Buffer, event: OrderEvent) {
        val json = mapper.writeValueAsString(event)
        buffer.appendInt(json.length)
        buffer.appendString(json)
    }

    override fun decodeFromWire(pos: Int, buffer: Buffer): OrderEvent {
        val length = buffer.getInt(pos)
        val json = buffer.getString(pos + 4, pos + 4 + length)
        return mapper.readValue(json, OrderEvent::class.java)
    }

    override fun transform(event: OrderEvent): OrderEvent = event // local delivery, no copy needed
    override fun name(): String = "order-event-codec"
    override fun systemCodecID(): Byte = -1
}
```

Register in a startup observer:

```kotlin
@ApplicationScoped
class CodecRegistrar {
    fun onStart(@Observes ev: StartupEvent, vertx: Vertx) {
        vertx.eventBus().registerCodec(OrderEventCodec())
    }
}
```

## Error Handling

```kotlin
@ConsumeEvent("order.created")
fun onOrderCreated(orderId: String) {
    try {
        notificationService.notifyOrderCreated(orderId)
    } catch (e: Exception) {
        log.error("Failed to handle order.created for $orderId", e)
        // Event Bus has no built-in retry — implement your own if needed
        retryQueue.enqueue("order.created", orderId)
    }
}
```

> **Important**: The Event Bus is in-memory and non-durable. If the application crashes, unprocessed events are lost. For durable event processing, use Kafka.

## Testing

```kotlin
@QuarkusTest
class OrderNotificationHandlerTest {

    @Inject
    lateinit var eventBus: EventBus

    @Inject
    lateinit var notificationHandler: OrderNotificationHandler

    @Test
    fun `should process order created event`() {
        eventBus.send("order.created", "order-123")

        // Allow async processing time
        Thread.sleep(500)

        // Assert side effects (e.g., notification sent)
    }
}
```

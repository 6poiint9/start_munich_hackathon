# SmallRye Reactive Messaging — Kafka + Avro Patterns

Detailed patterns for consuming and producing Kafka messages in Quarkus using SmallRye Reactive Messaging with Confluent Avro schema support.

## Architecture

```
SmallRye Reactive Messaging connector
  └── @Incoming / @Outgoing channel
       ├── Confluent Schema Registry (Avro)
       ├── Profile-gated consumers (@IfBuildProfile)
       └── Core KafkaMessageConsumer (shared logic)
```

## Dependencies

```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-smallrye-reactive-messaging-kafka</artifactId>
</dependency>
<!-- Avro + Schema Registry -->
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-confluent-schema-registry-avro</artifactId>
</dependency>
<dependency>
    <groupId>org.apache.avro</groupId>
    <artifactId>avro</artifactId>
</dependency>
```

## Profile-Gated Consumer Pattern (PPA Style)

In PPA, different Kafka clusters (e.g., EMEA vs China) are activated via Quarkus build profiles. Each profile has its own thin consumer class that delegates to a shared core processor.

### Core Consumer (shared logic)

```kotlin
@ApplicationScoped
class KafkaMessageConsumer(
    private val vehicleService: VehicleService,
) {
    companion object {
        private val log = LoggerFactory.getLogger(KafkaMessageConsumer::class.java)
    }

    suspend fun processRecord(record: ConsumerRecord<String, GenericRecord>) {
        val key = record.key()
        val avroRecord = record.value()

        log.info("Processing Kafka record: key=$key, topic=${record.topic()}, partition=${record.partition()}")

        try {
            val vin = avroRecord.get("vin")?.toString()
                ?: throw IllegalArgumentException("Missing VIN in record key=$key")

            val event = mapToVehicleEvent(avroRecord)
            vehicleService.handleEvent(vin, event)
        } catch (e: Exception) {
            log.error("Failed to process record key=$key from topic=${record.topic()}", e)
            throw e // let SmallRye handle retry / dead-letter
        }
    }

    private fun mapToVehicleEvent(record: GenericRecord): VehicleEvent {
        return VehicleEvent(
            vin = record.get("vin").toString(),
            eventType = record.get("eventType").toString(),
            timestamp = record.get("timestamp") as Long,
            payload = record.get("payload")?.toString(),
        )
    }
}
```

### EMEA Kafka Consumer

```kotlin
@IfBuildProfile("emea-kafka")
@ApplicationScoped
class KafkaConsumerEmea(
    private val core: KafkaMessageConsumer,
) {
    companion object {
        private val log = LoggerFactory.getLogger(KafkaConsumerEmea::class.java)
    }

    @Incoming("vehicle-events-emea")
    @Acknowledgment(Acknowledgment.Strategy.POST_PROCESSING)
    suspend fun consume(record: ConsumerRecord<String, GenericRecord>) {
        log.debug("EMEA consumer received: key=${record.key()}")
        core.processRecord(record)
    }
}
```

### China Kafka Consumer

```kotlin
@IfBuildProfile("china-kafka")
@ApplicationScoped
class KafkaConsumerChina(
    private val core: KafkaMessageConsumer,
) {
    @Incoming("vehicle-events-china")
    @Acknowledgment(Acknowledgment.Strategy.POST_PROCESSING)
    suspend fun consume(record: ConsumerRecord<String, GenericRecord>) {
        core.processRecord(record)
    }
}
```

### Why This Pattern?

- **Profile isolation**: Only the consumer matching the active build profile is instantiated — no connection attempts to absent brokers.
- **DRY**: All business logic lives in `KafkaMessageConsumer`; thin wrappers only bind the channel.
- **Testability**: Test `KafkaMessageConsumer` directly without Kafka infrastructure.

## Configuration

```properties
# ── EMEA Kafka channel ──
mp.messaging.incoming.vehicle-events-emea.connector=smallrye-kafka
mp.messaging.incoming.vehicle-events-emea.topic=${KAFKA_EMEA_TOPIC:vehicle-events}
mp.messaging.incoming.vehicle-events-emea.bootstrap.servers=${KAFKA_EMEA_BROKERS:localhost:9092}
mp.messaging.incoming.vehicle-events-emea.group.id=${KAFKA_EMEA_GROUP:ppa-vehicle-group}
mp.messaging.incoming.vehicle-events-emea.auto.offset.reset=earliest
mp.messaging.incoming.vehicle-events-emea.enable.auto.commit=false
mp.messaging.incoming.vehicle-events-emea.value.deserializer=io.confluent.kafka.serializers.KafkaAvroDeserializer
mp.messaging.incoming.vehicle-events-emea.schema.registry.url=${SCHEMA_REGISTRY_EMEA_URL:http://localhost:8081}
mp.messaging.incoming.vehicle-events-emea.specific.avro.reader=false

# ── China Kafka channel ──
mp.messaging.incoming.vehicle-events-china.connector=smallrye-kafka
mp.messaging.incoming.vehicle-events-china.topic=${KAFKA_CHINA_TOPIC:vehicle-events}
mp.messaging.incoming.vehicle-events-china.bootstrap.servers=${KAFKA_CHINA_BROKERS:localhost:9093}
mp.messaging.incoming.vehicle-events-china.group.id=${KAFKA_CHINA_GROUP:ppa-vehicle-group}
mp.messaging.incoming.vehicle-events-china.auto.offset.reset=earliest
mp.messaging.incoming.vehicle-events-china.enable.auto.commit=false
mp.messaging.incoming.vehicle-events-china.value.deserializer=io.confluent.kafka.serializers.KafkaAvroDeserializer
mp.messaging.incoming.vehicle-events-china.schema.registry.url=${SCHEMA_REGISTRY_CHINA_URL:http://localhost:8082}
mp.messaging.incoming.vehicle-events-china.specific.avro.reader=false
```

## Avro Schema Definition

Place `.avsc` files in `src/main/avro/`:

```json
{
  "type": "record",
  "name": "VehicleEvent",
  "namespace": "com.porsche.ppa.kafka.model",
  "fields": [
    {"name": "vin", "type": "string"},
    {"name": "eventType", "type": "string"},
    {"name": "timestamp", "type": "long"},
    {"name": "payload", "type": ["null", "string"], "default": null}
  ]
}
```

Generate classes: `./mvnw generate-sources` (or use `GenericRecord` as shown above).

## Confluent Schema Registry Authentication

When the registry requires credentials:

```properties
mp.messaging.incoming.vehicle-events-emea.schema.registry.url=${SCHEMA_REGISTRY_URL}
mp.messaging.incoming.vehicle-events-emea.basic.auth.credentials.source=USER_INFO
mp.messaging.incoming.vehicle-events-emea.basic.auth.user.info=${SCHEMA_REGISTRY_USER}:${SCHEMA_REGISTRY_PASSWORD}
```

## Producing Messages

```kotlin
@ApplicationScoped
class VehicleEventProducer(
    @Channel("vehicle-events-out") private val emitter: Emitter<VehicleEvent>,
) {
    fun sendEvent(event: VehicleEvent) {
        emitter.send(
            Message.of(event)
                .withMetadata(
                    OutgoingKafkaRecordMetadata.builder<String>()
                        .withKey(event.vin)
                        .withTopic("vehicle-events")
                        .build()
                )
        )
    }
}
```

```properties
mp.messaging.outgoing.vehicle-events-out.connector=smallrye-kafka
mp.messaging.outgoing.vehicle-events-out.topic=vehicle-events
mp.messaging.outgoing.vehicle-events-out.value.serializer=io.confluent.kafka.serializers.KafkaAvroSerializer
mp.messaging.outgoing.vehicle-events-out.schema.registry.url=${SCHEMA_REGISTRY_URL}
```

## Error and Deserialization Failure Handling

### Dead-Letter Topic

```properties
mp.messaging.incoming.vehicle-events-emea.failure-strategy=dead-letter-queue
mp.messaging.incoming.vehicle-events-emea.dead-letter-queue.topic=vehicle-events-dlq
mp.messaging.incoming.vehicle-events-emea.dead-letter-queue.key.serializer=org.apache.kafka.common.serialization.StringSerializer
mp.messaging.incoming.vehicle-events-emea.dead-letter-queue.value.serializer=org.apache.kafka.common.serialization.ByteArraySerializer
```

### Deserialization Failure Handler

Register a custom handler for poison pills (messages that cannot be deserialized):

```kotlin
@ApplicationScoped
@Identifier("vehicle-events-deser-handler")
class VehicleDeserializationFailureHandler : DeserializationFailureHandler<GenericRecord> {

    companion object {
        private val log = LoggerFactory.getLogger(VehicleDeserializationFailureHandler::class.java)
    }

    override fun handleDeserializationFailure(
        topic: String,
        isKey: Boolean,
        deserializer: String,
        data: ByteArray?,
        exception: Exception?,
        headers: Headers?,
    ): GenericRecord? {
        log.error("Deserialization failure on topic=$topic, isKey=$isKey", exception)
        // Return null to skip the record, or throw to trigger failure-strategy
        return null
    }
}
```

```properties
mp.messaging.incoming.vehicle-events-emea.value-deserialization-failure-handler=vehicle-events-deser-handler
```

## Health Checks

SmallRye Reactive Messaging automatically registers readiness health checks for Kafka channels. Verify at `/q/health/ready`.

To disable for a channel:
```properties
mp.messaging.incoming.vehicle-events-emea.health-readiness-enabled=false
```

## Testing with Testcontainers

```kotlin
@QuarkusTest
@TestProfile(EmeaKafkaTestProfile::class)
class KafkaConsumerEmeaTest {

    companion object {
        @Container
        val kafka = KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.5.0"))
    }

    @Inject
    lateinit var vehicleService: VehicleService

    @InjectMock
    lateinit var vehicleRepository: VehicleRepository

    @Test
    fun `should consume vehicle event and update service`() {
        // Send test Avro message to embedded Kafka
        // Assert vehicleService processed it
    }
}

class EmeaKafkaTestProfile : QuarkusTestProfile {
    override fun getEnabledAlternatives() = emptySet<Class<*>>()
    override fun getConfigProfile() = "emea-kafka"
}
```

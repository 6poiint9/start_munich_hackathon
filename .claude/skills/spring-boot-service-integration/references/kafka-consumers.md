# Kafka Consumer Integration Patterns

Detailed patterns for setting up Kafka consumers with Avro schema support in Spring Boot.

## Consumer Setup

### 1. Add Dependencies

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-kafka</artifactId>
</dependency>
<!-- Avro support (optional) -->
<dependency>
    <groupId>org.apache.avro</groupId>
    <artifactId>avro</artifactId>
</dependency>
<dependency>
    <groupId>io.confluent</groupId>
    <artifactId>kafka-avro-serializer</artifactId>
</dependency>
```

### 2. Define Avro Schema (optional)

Place `.avsc` files in `src/main/avro/`:

```json
{
  "type": "record",
  "name": "MyEvent",
  "namespace": "com.example.kafka.model",
  "fields": [
    {"name": "id", "type": "string"},
    {"name": "eventType", "type": "string"},
    {"name": "timestamp", "type": "long"},
    {"name": "payload", "type": ["null", "string"], "default": null}
  ]
}
```

Generate classes: `./mvnw generate-sources`

### 3. Create Kafka Configuration

```kotlin
@Configuration
@Profile("kafka-enabled")  // Activate via Spring profile
class MyKafkaConfig {

    @Bean
    fun myConsumerFactory(
        @Value("\${kafka.broker-url}") brokerUrl: String,
        @Value("\${kafka.group-id}") groupId: String,
    ): ConsumerFactory<String, ByteArray> {
        val props = mapOf(
            ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG to brokerUrl,
            ConsumerConfig.GROUP_ID_CONFIG to groupId,
            ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG to StringDeserializer::class.java,
            ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG to ByteArrayDeserializer::class.java,
            ConsumerConfig.AUTO_OFFSET_RESET_CONFIG to "earliest",
            ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG to false,
        )
        return DefaultKafkaConsumerFactory(props)
    }

    @Bean
    fun myKafkaListenerContainerFactory(
        consumerFactory: ConsumerFactory<String, ByteArray>,
    ): ConcurrentKafkaListenerContainerFactory<String, ByteArray> {
        val factory = ConcurrentKafkaListenerContainerFactory<String, ByteArray>()
        factory.consumerFactory = consumerFactory
        factory.containerProperties.ackMode = ContainerProperties.AckMode.MANUAL_IMMEDIATE
        return factory
    }
}
```

### 4. Create Kafka Listener

```kotlin
@Component
@Profile("kafka-enabled")
class MyEventListener(
    private val eventProcessor: EventProcessor,
) {
    companion object {
        private val log = LoggerFactory.getLogger(MyEventListener::class.java)
    }

    @KafkaListener(
        topics = ["\${kafka.topics.my-events}"],
        containerFactory = "myKafkaListenerContainerFactory",
    )
    fun onMessage(
        record: ConsumerRecord<String, ByteArray>,
        acknowledgment: Acknowledgment,
    ) {
        try {
            log.info("Received event: key=${record.key()}, partition=${record.partition()}")
            val event = deserialize(record.value())
            eventProcessor.process(event)
            acknowledgment.acknowledge()
        } catch (e: Exception) {
            log.error("Failed to process event: key=${record.key()}", e)
            // Dead letter queue, retry, or skip based on error type
        }
    }

    private fun deserialize(bytes: ByteArray): MyEvent {
        val reader = SpecificDatumReader<MyEvent>(MyEvent.getClassSchema())
        val decoder = DecoderFactory.get().binaryDecoder(bytes, null)
        return reader.read(null, decoder)
    }
}
```

## Configuration

```yaml
kafka:
  broker-url: ${KAFKA_BROKER_URL:localhost:9092}
  group-id: ${KAFKA_GROUP_ID:my-app-group}
  topics:
    my-events: my-event-topic
  schema-registry-url: ${SCHEMA_REGISTRY_URL:http://localhost:8081}
```

## Local Kafka (Docker Compose)

```yaml
services:
  kafka:
    image: apache/kafka:latest
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9094
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9094
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: true
    ports:
      - '9092:9092'
```

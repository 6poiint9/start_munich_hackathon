---
name: quarkus-service-integration
description: >-
  Integrates external systems into Quarkus services: MicroProfile REST Client, SmallRye
  Reactive Messaging with Kafka and Avro, Vert.x event bus, Azure Cosmos DB, and Redis.
  Use when adding or fixing a REST client, Kafka consumer or producer, event-bus handler,
  or Cosmos/Redis access, only when pom.xml contains quarkus-bom. Don't use in Spring Boot
  projects (use spring-boot-service-integration).
---

# Quarkus Service Integration

> **Layer 3:** full code examples live in [references/examples.md](references/examples.md). Read only the section you are implementing.

Patterns for integrating external services in Quarkus applications with Kotlin coroutines and CDI.

> **Repo-first:** Inspect the existing service integrations in the repository before applying these patterns. Match the local approach for REST client configuration, error handling, and profile gating. Use these patterns as defaults only when the repo does not already establish another approach.
>
> **Shared conventions:** For constructor injection and blocking-call avoidance, see `_shared/kotlin-conventions.md`.

> **Progressive disclosure**: This SKILL.md provides the decision tree and overview. Detailed patterns for each protocol are in `references/`.

---

## Decision Tree — Which Integration?

→ Example: [references/examples.md § Decision Tree — Which Integration?](references/examples.md#decision-tree--which-integration)

## Quick Reference

| Protocol | Quarkus Component | Kotlin Pattern | Config Key |
|----------|-------------------|----------------|------------|
| HTTP/REST | MicroProfile `@RegisterRestClient` | `suspend fun getResource(): Dto` | `quarkus.rest-client.<configKey>.url` |
| Kafka | SmallRye `@Incoming` / `@Outgoing` | `suspend fun consume(record: ConsumerRecord<K, V>)` | `mp.messaging.incoming.<channel>.*` |
| Event Bus | Vert.x `EventBus` / `@ConsumeEvent` | `eventBus.send("address", payload)` | n/a (in-process only) |
| Cosmos DB | Custom Azure SDK client | `suspend fun findById(id: String): Entity?` | `azure.cosmos.*` |
| Redis | `io.quarkus.redis.datasource.RedisDataSource` | `redis.hash(Entity::class.java)` | `quarkus.redis.*` |

## Common Architecture

→ Example: [references/examples.md § Common Architecture](references/examples.md#common-architecture)

## MicroProfile REST Client — Quick Start

→ Example: [references/examples.md § MicroProfile REST Client — Quick Start](references/examples.md#microprofile-rest-client--quick-start)

Configuration:
```properties
quarkus.rest-client.my-api.url=https://api.example.com
quarkus.rest-client.my-api.scope=jakarta.inject.Singleton
```

→ Full details: `references/rest-client-patterns.md`

## SmallRye Kafka — Quick Start

→ Example: [references/examples.md § SmallRye Kafka — Quick Start](references/examples.md#smallrye-kafka--quick-start)

Configuration:
```properties
mp.messaging.incoming.channel-name.connector=smallrye-kafka
mp.messaging.incoming.channel-name.topic=my-topic
mp.messaging.incoming.channel-name.group.id=my-group
```

→ Full details: `references/kafka-smallrye-patterns.md`

## Vert.x Event Bus — Quick Start

→ Example: [references/examples.md § Vert.x Event Bus — Quick Start](references/examples.md#vertx-event-bus--quick-start)

→ Full details: `references/vertx-eventbus-patterns.md`

## Cosmos DB & Redis — Quick Start

→ Example: [references/examples.md § Cosmos DB & Redis — Quick Start](references/examples.md#cosmos-db--redis--quick-start)

→ Full details: `references/cosmos-redis-patterns.md`

---

## Best Practices (Preferred in This Codebase)

1. **Use `@Qualifier`** (or distinct `configKey`) when multiple REST client beans exist for different services
2. **Profile-gate optional integrations** — use `@IfBuildProfile` for Kafka consumers so they don't block startup when the broker is absent
3. **Centralize error handling** — map upstream errors to domain exceptions via `ResponseExceptionMapper`
4. **Add timeouts** — configure `quarkus.rest-client.<key>.connect-timeout` and `read-timeout`; avoid relying on defaults
5. **Use SmallRye Fault Tolerance** — `@Retry`, `@Timeout`, `@CircuitBreaker`, `@Fallback` for resilient outbound calls
6. **Encrypt secrets** — use `${VAULT_*}` or Kubernetes secrets; avoid hardcoded API keys
7. **Test with mocks** — use `@QuarkusTest` + `@InjectMock` / `@RestClientTest`, and Testcontainers for Kafka

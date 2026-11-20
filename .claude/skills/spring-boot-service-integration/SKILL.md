---
name: spring-boot-service-integration
description: >-
  Integrates external systems into Spring Boot WebFlux services: WebClient HTTP calls with
  auth filters, retries and timeouts, gRPC protobuf clients, Kafka consumers with Avro
  schemas, GraphQL clients, and polling. Use when adding or fixing a WebClient, gRPC,
  Kafka, or GraphQL integration, only in Spring Boot WebFlux projects
  (spring-boot-starter-webflux, e.g. ppa-connect-bff). Don't use when pom.xml contains
  quarkus-bom (use quarkus-service-integration).
---

# Spring Boot Service Integration

> **Layer 3:** full code examples live in [references/examples.md](references/examples.md). Read only the section you are implementing.

Patterns for integrating external services in Spring Boot WebFlux (reactive) applications with Kotlin coroutines.

> **Repo-first:** Inspect the existing service integrations in the repository before applying these patterns. Match the local approach for WebClient configuration, error handling, and authentication filters. Use these patterns as defaults only when the repo does not already establish another approach.
>
> **Shared conventions:** For constructor injection, `@Qualifier` usage, and blocking-call avoidance, see `_shared/kotlin-conventions.md`.

> **Progressive disclosure**: This SKILL.md provides the decision tree and overview. Detailed patterns for each protocol are in `references/`.

---

## Decision Tree — Which Protocol?

→ Example: [references/examples.md § Decision Tree — Which Protocol?](references/examples.md#decision-tree--which-protocol)

## Quick Reference

| Protocol | Spring Component | Kotlin Pattern | Config Key |
|----------|-----------------|----------------|------------|
| HTTP/REST | `WebClient` | `awaitBody<T>()`, `bodyToFlow<T>()` | `my-service.host` |
| gRPC | `ManagedChannel` + Kotlin stub | `stub.getData(request)` | `grpc.my-service.host/port` |
| Kafka | `@KafkaListener` | `ConsumerRecord<K,V>` + `Acknowledgment` | `kafka.broker-url` |
| GraphQL | `HttpGraphQlClient` | `.retrieve("field").toEntity(T::class.java).awaitSingle()` | `graphql.host` |

## Common Architecture

→ Example: [references/examples.md § Common Architecture](references/examples.md#common-architecture)

## WebClient — Quick Start

→ Example: [references/examples.md § WebClient — Quick Start](references/examples.md#webclient--quick-start)

→ Full details: `references/webclient-patterns.md`

## gRPC — Quick Start

→ Example: [references/examples.md § gRPC — Quick Start](references/examples.md#grpc--quick-start)

→ Full details: `references/grpc-integration.md`

## Kafka — Quick Start

→ Example: [references/examples.md § Kafka — Quick Start](references/examples.md#kafka--quick-start)

→ Full details: `references/kafka-consumers.md`

## GraphQL — Quick Start

→ Example: [references/examples.md § GraphQL — Quick Start](references/examples.md#graphql--quick-start)

→ Full details: `references/graphql-client.md`

---

## Best Practices (Preferred in This Codebase)

1. **Use `@Qualifier`** when multiple WebClient beans exist (see `_shared/kotlin-conventions.md`)
2. **Profile-gate** optional integrations (Kafka, WebSocket) so they don't block startup
3. **Centralize error handling** — map upstream errors to domain exceptions
4. **Add timeouts** — avoid relying on defaults for external calls
5. **Use circuit breakers** (Resilience4j) for fault tolerance
6. **Log correlation IDs** — propagate trace context through all outbound calls
7. **Encrypt secrets** — use vault or config encryption; avoid hardcoded API keys
8. **Test with mocks** — use MockWebServer for WebClient, embedded Kafka for consumers

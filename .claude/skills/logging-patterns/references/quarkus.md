# Quarkus Logging Patterns

Logging patterns for Kotlin Quarkus applications using JBoss Logging and quarkus-logging-json.

## Logger Declaration

Quarkus injects `org.jboss.logging.Logger` via CDI:

```kotlin
// GOOD: CDI-injected logger (Quarkus pattern)
@ApplicationScoped
class MyService(
    private val logger: Logger,  // org.jboss.logging.Logger
) {
    suspend fun process(id: String) {
        logger.info("Processing request for $id")
    }
}

// BAD: SLF4J LoggerFactory (Spring pattern — don't use in Quarkus)
companion object {
    private val log = LoggerFactory.getLogger(MyService::class.java)
}
```

## JSON Logging Configuration

```yaml
# application.yaml
quarkus:
  log:
    min-level: INFO
    level: INFO
    category:
      "de.porsche.app.myservice":
        min-level: INFO
        level: INFO
    console:
      json:
        enabled: true  # JSON format for deployed environments
      format: "%d{HH:mm:ss} %-5p [%X{traceId},%X{parentId},%X{spanId}] [%c{2.}] (%t) %s%e%n"
```

## Profile-Based Log Configuration

```yaml
# Base (deployed): JSON enabled
quarkus:
  log:
    console:
      json:
        enabled: true

# Local development override
"%local":
  quarkus:
    log:
      console:
        json:
          enabled: false
      category:
        "de.porsche.app":
          level: TRACE

# Test override
"%test":
  quarkus:
    log:
      console:
        json:
          enabled: false
      category:
        "de.porsche.app":
          level: TRACE
```

| Profile | Format | Level |
|---------|--------|-------|
| base/prod | JSON | INFO |
| local | Human-readable | TRACE |
| test | Human-readable | TRACE |

## OpenTelemetry Trace Context

When `quarkus-opentelemetry` extension is active, trace IDs are automatically injected:

| Field | Description |
|-------|-------------|
| `traceId` | Distributed trace ID |
| `parentId` | Parent span ID |
| `spanId` | Current span ID |

These appear automatically in the log format pattern `%X{traceId}`.

## Log Levels Guide

Same as Spring Boot — use ERROR for unexpected failures, WARN for unusual but expected conditions, INFO for business events, DEBUG for diagnostics, TRACE for fine-grained detail.

## Anti-Patterns

- **SLF4J LoggerFactory.getLogger()** — Use CDI-injected JBoss Logger instead
- **logback-spring.xml** — Quarkus doesn't use Logback; configure via `application.yaml`
- **MDCContext() from kotlinx-coroutines-slf4j** — Quarkus propagates context automatically via SmallRye Context Propagation
- **String concatenation in log calls** — Use parameterized logging: `logger.infof("Processing %s items", count)` or template strings at INFO+ only
- **Logging sensitive data** — Never log tokens, passwords, PII

## Suppressing Noisy Loggers

```yaml
quarkus:
  log:
    category:
      "org.jboss.resteasy.reactive":
        level: WARN
      "io.quarkus.oidc":
        level: WARN
      "org.apache.kafka":
        level: WARN
```

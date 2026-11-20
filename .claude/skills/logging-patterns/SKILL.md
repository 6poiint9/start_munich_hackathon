---
name: logging-patterns
description: >-
  Configures structured logging for Kotlin Spring Boot (SLF4J, Logback,
  logstash-logback-encoder) and Quarkus (JBoss Logging, quarkus-logging-json) services:
  JSON log format, MDC and trace or correlation-ID propagation, log levels, and
  profile-based format switching. Use when adding or fixing logging, MDC, correlation IDs,
  logback-spring.xml, or quarkus.log.* settings in a backend service. Don't use for
  Android, Flutter, or frontend logging.
---

# Structured Logging Patterns

> **Layer 3:** full code examples live in [references/examples.md](references/examples.md). Read only the section you are implementing.

> **Framework detection**: Check `pom.xml` for `spring-boot-starter` vs `quarkus-bom` to determine which framework applies, then see the corresponding reference file for framework-specific setup.
> **Shared conventions:** For MDC propagation through coroutines and blocking-call avoidance, see `_shared/kotlin-conventions.md`.
>
> **Important**: Our Spring Boot projects do **not** use `logback-spring.xml`. Logback config lives in separate XML files under `src/main/resources/logging/` (e.g. `logging-default.xml`, `logging-cn.xml`), selected at runtime via `logging.config` in `application.yml`.

Best practices for structured logging in Kotlin applications.

## Why Structured (JSON) Logging?

- **Machine-parseable**: Log aggregation tools (Splunk, ELK, Datadog) can index fields directly
- **AI-friendly**: AI agents can parse structured logs more reliably than free-form text
- **Searchable**: Query by `vin`, `requestId`, `userId` across millions of log lines
- **Consistent**: Enforces a schema; no more ad-hoc log message formats

## MDC (Mapped Diagnostic Context)

MDC adds contextual key-value pairs to every log line within a scope.

### Coroutine MDC Propagation

MDC is thread-local, but coroutines may switch threads. See `_shared/kotlin-conventions.md` for the canonical MDC propagation pattern. Quick reference:

→ Example: [references/examples.md § MDC (Mapped Diagnostic Context) › Coroutine MDC Propagation](references/examples.md#mdc-mapped-diagnostic-context--coroutine-mdc-propagation)

## Log Levels Guide

| Level | When to use | Example |
|-------|------------|---------|
| `ERROR` | Unexpected failures requiring attention | Unhandled exception, external service down |
| `WARN` | Expected but unusual conditions | Retry succeeded, fallback triggered, deprecated API called |
| `INFO` | Business-significant events | Request received, command executed, feature toggled |
| `DEBUG` | Diagnostic details for troubleshooting | Request/response payloads, cache hits/misses |
| `TRACE` | Very fine-grained (rarely used) | Loop iterations, internal state transitions |

### Anti-Patterns

→ Example: [references/examples.md § Log Levels Guide › Anti-Patterns](references/examples.md#log-levels-guide--anti-patterns)

## OpenTelemetry Integration

When using OTEL Java agent, trace context is automatically injected into MDC:

| MDC Key | Source | Description |
|---------|--------|-------------|
| `trace_id` | OTEL | Distributed trace ID |
| `span_id` | OTEL | Current span ID |
| `trace_flags` | OTEL | Sampling flags |

These appear automatically in JSON log output when the OTEL agent is attached.

---

## Spring Boot Logging

For Spring Boot–specific logging patterns (SLF4J, logstash-logback-encoder, file-based logback configuration under `logging/`, WebClient filters, region-based format switching), see `references/spring.md`.

---

## Quarkus Logging

For Quarkus-specific logging patterns (JBoss Logging, quarkus-logging-json, application.yaml config), see `references/quarkus.md`.

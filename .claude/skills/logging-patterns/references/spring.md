# Spring Boot Logging Patterns

Spring Boot–specific logging setup and patterns using SLF4J + Logback.
Apply these when `spring-boot-starter` is detected in `pom.xml` or `build.gradle.kts`.

> **Important**: Our projects do **not** use `logback-spring.xml`. Instead, logback configuration lives in separate XML files under `src/main/resources/logging/`, selected at runtime via the `logging.config` property in `application.yml`.

---

## 1. Setup: logstash-logback-encoder

### Dependencies

```xml
<dependency>
    <groupId>ch.qos.logback</groupId>
    <artifactId>logback-classic</artifactId>
    <version>${logback.version}</version>
</dependency>
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>${logback-encoder.version}</version>
</dependency>
```

> Check the project's `pom.xml` for the actual version properties (`logback.version`, `logback-encoder.version`).

### Logback Configuration (file-based, not `logback-spring.xml`)

Our projects use a `logging/` directory under `src/main/resources/` containing separate XML files for each logging mode. The active file is selected via `logging.config` in `application.yml` (typically set in the config-repo).

#### `src/main/resources/logging/override-patterns.xml` (shared pattern include)

Overrides the default Spring Boot log pattern to include OTEL trace context and CIAM ID:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<included>
  <include resource="org/springframework/boot/logging/logback/defaults.xml"/>

  <property name="LOG_LEVEL_PATTERN" value="%5p [%X{trace_id:-},%X{span_id:-},%X{X-CIAM-ID:-}]"/>
  <property name="CONSOLE_LOG_PATTERN"
    value="%clr(%d{yyyy-MM-dd HH:mm:ss.SSS}){faint} %clr(${LOG_LEVEL_PATTERN:-%5p}) %clr(${PID:- }){magenta} %clr(---){faint} %clr([%15.15t]){faint} %clr(%-40.40logger{39}){cyan} %clr(:){faint} %m%n${LOG_EXCEPTION_CONVERSION_WORD:-%wEx}"/>
</included>
```

#### `src/main/resources/logging/logging-default.xml` (human-readable — EMEA / local dev)

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE configuration>
<configuration>
  <include resource="logging/override-patterns.xml"/>
  <include resource="org/springframework/boot/logging/logback/console-appender.xml"/>

  <root>
    <appender-ref ref="CONSOLE"/>
  </root>
</configuration>
```

#### `src/main/resources/logging/logging-cn.xml` (JSON — CN deployed environments)

```xml
<configuration>
  <include resource="org/springframework/boot/logging/logback/defaults.xml"/>
  <include resource="org/springframework/boot/logging/logback/console-appender.xml"/>

  <property name="LOG_LEVEL_PATTERN" value="%5p [%X{traceId:-},%X{spanId:-},%X{X-CIAM-ID:-}]"/>
  <property name="CONSOLE_LOG_PATTERN"
            value="%clr(%d{yyyy-MM-dd HH:mm:ss.SSS}){faint} %clr(${LOG_LEVEL_PATTERN:-%5p}) %clr(${PID:- }){magenta} %clr(---){faint} %clr([%15.15t]){faint} %clr(%-40.40logger{39}){cyan} %clr(:){faint} %m%n${LOG_EXCEPTION_CONVERSION_WORD:-%wEx}"/>

  <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <pattern>${CONSOLE_LOG_PATTERN}</pattern>
      <charset>UTF-8</charset>
    </encoder>
  </appender>

  <logger name="de.porsche.app" level="debug" additivity="false">
    <appender-ref ref="STDOUT"/>
    <filter class="ch.qos.logback.classic.filter.ThresholdFilter">
      <level>debug</level>
    </filter>
  </logger>

  <root>
    <level value="info"/>
    <appender-ref ref="STDOUT"/>
  </root>
</configuration>
```

### Selecting the Logging Config via `application.yml`

The active logback config is set with `logging.config`, typically in the config-repo or region-specific `application-*.yml`:

```yaml
# Default / EMEA — human-readable output
logging:
  config: classpath:logging/logging-default.xml
  level:
    root: INFO
    de.porsche.app.myservice: TRACE

# CN deployed — JSON output (in a CN-specific profile section)
logging:
  config: classpath:logging/logging-cn.xml
  exception-conversion-word: "%replace(%wEx){'\n','\u2028'}%nopex"
```

> **CN note**: `exception-conversion-word` replaces newlines with Unicode line separators so stack traces don't break JSON log lines.

---

## 2. Logger Bean & Injection

Define a prototype-scoped `Logger` bean that auto-resolves the owning class:

```kotlin
@Configuration
class LoggingConfig {

    @Bean
    @Scope("prototype")
    fun logger(injectionPoint: InjectionPoint): Logger =
        LoggerFactory.getLogger(
            injectionPoint.methodParameter?.containingClass // constructor injection
                ?: injectionPoint.field?.declaringClass,    // field injection fallback
        )
}
```

Then inject the logger via constructor (preferred) or field injection:

```kotlin
@Service
class MyService(
    private val logger: Logger,
) {

    suspend fun process(vin: String) {
        logger.info("Processing request for vehicle")
        // MDC fields (trace_id, span_id, X-CIAM-ID) are automatically included
    }
}
```

> **Do not** use `LoggerFactory.getLogger(...)` directly or companion-object loggers.
> Always inject the `Logger` so the declaring class is resolved automatically.

---

## 3. MDC & Observation Context in WebFilters

MDC context (trace IDs, CIAM ID) is propagated via `WebFilter` beans. The OTEL Java agent injects `trace_id` and `span_id` automatically; custom context like `X-CIAM-ID` is set in filters:

```kotlin
@Bean
fun getLoggingContext(): WebFilter =
    object : WebFilter, Ordered {
        override fun filter(exchange: ServerWebExchange, chain: WebFilterChain): Mono<Void> =
            chain.filter(exchange).contextWrite {
                // Extract headers and populate Reactor context / MDC
                getUpdatedContext(context = it, headers = exchange.request.headers)
            }
        override fun getOrder() = ORDER_CONTEXT
    }
```

---

## 4. Region & Profile-Based Log Configuration

Logging format is determined by **region** (EMEA vs CN) and **environment**, not by a single `logback-spring.xml` with `<springProfile>` blocks.

| Region / Profile | Format | Config file | Level |
|------------------|--------|-------------|-------|
| EMEA (all envs) | Human-readable (pattern) | `logging/logging-default.xml` | INFO (app: TRACE) |
| CN (deployed) | JSON (LogstashEncoder) | `logging/logging-cn.xml` | INFO (app: DEBUG) |
| CN (dev/local) | Human-readable (pattern) | `logging/logging-default.xml` | INFO (app: TRACE) |
| `local` | Human-readable | `logging/logging-default.xml` | TRACE |

**Profile naming convention**: `{region}`, `{region}-{env}`, e.g. `emea`, `emea-staging`, `emea-prod`, `cn`, `cn-staging`, `cn-prod`, `cn-dev`.

### OTEL Agent Configuration

OTEL instrumentation for logback is configured via separate property files in `src/main/resources/otel/`:

```properties
# otel/otel-agent-config-{env}.properties
otel.instrumentation.logback-mdc.enabled=true
otel.instrumentation.logback-appender.experimental.capture-mdc-attributes=vwg.*,ppa.*,po.*
```

### Suppressing Noisy Loggers

Set log levels in `application.yml` (not in XML):

```yaml
logging:
  level:
    org.springframework.web: WARN
    io.netty: WARN
    reactor.netty: WARN
    org.apache.kafka.clients: WARN
```

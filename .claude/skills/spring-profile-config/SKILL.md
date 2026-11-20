---
name: spring-profile-config
description: >-
  Explains and changes Spring profiles and configuration in ppa-connect-bff: EMEA (Spring
  Cloud Config Server) vs CN (bundled) profiles, feature-toggle and local profiles,
  application-*.yml, @ConfigurationProperties, environment variables, encrypted values,
  OTEL settings, and local Docker services. Use when adding or debugging config
  properties, profiles, or env vars, only in ppa-connect-bff or another Spring Boot
  project. Don't use when pom.xml contains quarkus-bom (use quarkus-profile-config).
---

# Spring Profiles & Configuration — ppa-connect-bff

> **Layer 3:** full code examples live in [references/examples.md](references/examples.md). Read only the section you are implementing.

## Profile Hierarchy

### EMEA Region

→ Example: [references/examples.md § Profile Hierarchy › EMEA Region](references/examples.md#profile-hierarchy--emea-region)

### China Region

→ Example: [references/examples.md § Profile Hierarchy › China Region](references/examples.md#profile-hierarchy--china-region)

### Key Difference: EMEA uses external Spring Cloud Config Server; CN config is bundled locally.

## Feature Toggle Profiles

| Profile | Purpose |
|---------|---------|
| `emea-cache-l2` | Enable Redis L2 caching |
| `emea-logging-business` | Enable Splunk business event logging |
| `websocket` | Enable WebSocket/PubSub functionality |
| `vcf-eventhub` | Enable VCF Kafka event consumption |
| `vcf-eventhub-nar` | Enable VCF events for North America Region |
| `kafka-streamzilla` | Enable Streamzilla Kafka consumption |

## Local Development Profiles

| Profile Combination | Purpose |
|--------------------|---------|
| `emea, emea-staging` | Local dev against EMEA staging backends |
| `cn` | Local dev with China config |
| `local, msgp-local` | Use local MSG proxy instance |
| `local, gravityp-local` | Use local Gravity proxy instance |
| `test-no-cache` | Unit tests (no cache, no config server) |

## Configuration Files

### `application.yml` (Base)

→ Example: [references/examples.md § Configuration Files › `application.yml` (Base)](references/examples.md#configuration-files--applicationyml-base)

### Key Configuration Areas

#### Server Settings
→ Example: [references/examples.md § Configuration Files › Key Configuration Areas](references/examples.md#configuration-files--key-configuration-areas)

#### Remote Service Hosts (EMEA example)

#### Polling Configuration

#### Kafka Configuration

#### Redis Cache

#### Observability

#### Keep-Alive

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `PPA_ENCRYPT_KEY` | Spring property encryption key | Yes |
| `PPA_CONFIG_SERVER_PASSWORD` | Config server auth (EMEA only) | EMEA only |
| `SPRING_PROFILES_ACTIVE` | Active profiles | Yes |
| `REDIS_HOST`, `REDIS_PORT` | Redis connection | When using cache |
| `GRAVITY_PROXY_HOST` | Gravity proxy override | Optional |
| `VEHICLES_DATA_API_KEY` | VDS API key | Yes |
| `SPLUNK_TOKEN` | Splunk logging token | EMEA prod |
| `ENVIRONMENT` | Environment name (staging/pre/prod) | Yes |

## Test Profile: `test-no-cache`

Located at `src/test/resources/application-test-no-cache.yml`:

→ Example: [references/examples.md § Test Profile: `test-no-cache`](references/examples.md#test-profile-test-no-cache)

Usage in tests:
```kotlin
@SpringBootTest
@ActiveProfiles(ProfileConstants.PROFILE_TEST_NO_CACHE)
class MyTest { ... }
```

## Adding New Configuration

### 1. Add property to `application-<profile>.yml`

For EMEA, properties are managed in the external config server repository (`ppa-config-server`). For CN, add directly to `application-cn*.yml`.

### 2. Create a `@ConfigurationProperties` class

→ Example: [references/examples.md § Adding New Configuration › 2. Create a `@ConfigurationProperties` class](references/examples.md#adding-new-configuration--2-create-a-configurationproperties-class)

### 3. Register with `@EnableConfigurationProperties`

```kotlin
@Configuration
@EnableConfigurationProperties(MyFeatureProperties::class)
class MyFeatureConfig { ... }
```

### 4. Encrypt sensitive values

Sensitive properties use Spring Cloud Config encryption:
```yaml
my-feature:
  api-key: '{cipher}encrypted-value-here'
```

Encryption is done with the `PPA_ENCRYPT_KEY` environment variable.

## OTEL Configuration

Per-environment OpenTelemetry agent configs at `src/main/resources/otel/`:
- `otel-agent-config-local.properties`
- `otel-agent-config-staging.properties`
- `otel-agent-config-pre.properties`
- `otel-agent-config-prod.properties`

Used in the Dockerfile:
```dockerfile
CMD ["sh", "-c", "java -javaagent:/otel/opentelemetry-javaagent.jar \
  -Dotel.javaagent.configuration-file=/otel/otel-agent-config-${ENVIRONMENT}.properties \
  ..."]
```

## Docker / Local Services

→ Example: [references/examples.md § Docker / Local Services](references/examples.md#docker--local-services)

Then activate profile `emea-cache-l2` for Redis and `vcf-eventhub` / `kafka-streamzilla` for Kafka.

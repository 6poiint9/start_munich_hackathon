---
name: quarkus-profile-config
description: >-
  Explains and changes Quarkus configuration for PPA services: %profile prefixes, EMEA vs
  CN profiles, application.yaml/properties, @ConfigMapping, environment variables,
  encrypted values, and local dev setup. Use when adding or debugging config properties,
  profiles, or env vars, only when pom.xml contains quarkus-bom (ppa-ppns,
  ppa-static-documents-generator, ppa-version-checker). Don't use in ppa-connect-bff or
  other Spring projects (use spring-profile-config).
---

# Quarkus Profiles & Configuration — PPA Quarkus Services

> **Layer 3:** full code examples live in [references/examples.md](references/examples.md). Read only the section you are implementing.

Applies to: **ppa-ppns**, **ppa-static-documents-generator**, **ppa-version-checker**

## Build-Time vs Runtime Profiles (CRITICAL)

**Spring profiles are runtime; Quarkus profiles are BUILD-TIME.** This is the single most important difference. Quarkus evaluates profiles at build (compile/package) time, producing a **different JAR for EMEA vs CN**.

| Concept | Spring | Quarkus |
|---------|--------|---------|
| Profile activation | `SPRING_PROFILES_ACTIVE` at runtime | `quarkus.profile` at **build** time via Maven |
| Conditional beans | `@Profile("emea")` (runtime) | `@IfBuildProfile("emea")` (compile-time) |
| Excluding beans | `@Profile("!cn")` | `@UnlessBuildProfile("cn")` |
| Result | One JAR, multiple profiles | **Separate JARs** per region |

### How It Works

1. Maven profile sets `quarkus.profile` based on `PPA_REGION` env var.
2. Quarkus includes/excludes classes annotated with `@IfBuildProfile` / `@UnlessBuildProfile`.
3. Only matching `application-<profile>.yaml` files are baked into the JAR.
4. The resulting artifact is region-specific — you **cannot** switch profiles at runtime.

## Profile Hierarchy

### EMEA Region

→ Example: [references/examples.md § Profile Hierarchy › EMEA Region](references/examples.md#profile-hierarchy--emea-region)

### China Region

→ Example: [references/examples.md § Profile Hierarchy › China Region](references/examples.md#profile-hierarchy--china-region)

### Key Difference: EMEA has a `pre` environment; CN does not.

## Feature / Component Profiles

Used in **ppa-ppns** and selectively in other services:

| Profile | Purpose | Service(s) |
|---------|---------|------------|
| `emea-kafka` | Enable Kafka consumers (EMEA brokers) | ppa-ppns |
| `cn-kafka` | Enable Kafka consumers (CN brokers) | ppa-ppns |
| `otel` | Enable OpenTelemetry metrics/tracing | all |
| `local` | Local development (mock endpoints) | all |
| `local-e2e` | Local end-to-end with real deps | ppa-ppns |
| `test` | Unit test profile | all |
| `inttest` | Integration test profile | all |

Activate feature profiles alongside the region profile:

```bash
# Build with EMEA + Kafka
PPA_REGION=emea mvn package -Dquarkus.profile=emea,emea-kafka
```

## Maven Profile Activation

Each service's `pom.xml` contains Maven profiles gated on `PPA_REGION`:

→ Example: [references/examples.md § Maven Profile Activation](references/examples.md#maven-profile-activation)

**CI/CD sets `PPA_REGION` before `mvn package`**, producing region-locked artifacts.

## Configuration Keys (Quarkus-Specific)

### Server & Security

→ Example: [references/examples.md § Configuration Keys (Quarkus-Specific) › Server & Security](references/examples.md#configuration-keys-quarkus-specific--server--security)

### Observability

→ Example: [references/examples.md § Configuration Keys (Quarkus-Specific) › Observability](references/examples.md#configuration-keys-quarkus-specific--observability)

### REST Clients

→ Example: [references/examples.md § Configuration Keys (Quarkus-Specific) › REST Clients](references/examples.md#configuration-keys-quarkus-specific--rest-clients)

## Config Encryption (SmallRye Crypto)

Sensitive values are encrypted with AES-GCM using SmallRye Config Crypto:

```yaml
my-secret: ${aes-gcm-nopadding::encryptedBase64Value}
```

### Encrypting a Value

```bash
jbang https://raw.githubusercontent.com/smallrye/smallrye-config/main/documentation/src/main/docs/config/secret-handlers/encryptor.java \
  -s="<plaintext-secret>" \
  -k="<encryption-key>"
```

The encryption key is provided at runtime via `PPA_ENCRYPT_KEY` (mapped to `smallrye.config.secret-handler.aes-gcm-nopadding.encryption-key`).

## Adding New Configuration

### Step 1 — Add the property

Add to the appropriate `application-<profile>.yaml`:

→ Example: [references/examples.md § Adding New Configuration › Step 1 — Add the property](references/examples.md#adding-new-configuration--step-1--add-the-property)

### Step 2 — Inject in code

**Option A: `@ConfigProperty`**

→ Example: [references/examples.md § Adding New Configuration › Step 2 — Inject in code](references/examples.md#adding-new-configuration--step-2--inject-in-code)

**Option B: `@ConfigMapping` (preferred for groups)**


### Step 3 — Encrypt sensitive values

```yaml
my-feature:
  api-key: ${aes-gcm-nopadding::BASE64_ENCRYPTED_VALUE}
```

### Step 4 — Ensure `PPA_ENCRYPT_KEY` is set

The env var must be present in the deployment environment and in local `.env` files.

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `PPA_REGION` | Region for Maven build (`emea` / `cn`) | Yes (build time) |
| `PPA_ENCRYPT_KEY` | SmallRye config encryption key | Yes |
| `PORT` | HTTP listen port (default `8089`) | No |
| `QUARKUS_PROFILE` | Override active profile at runtime | Rare |
| `QUARKUS_OIDC_AUTH_SERVER_URL` | OIDC provider URL | Yes |
| `QUARKUS_OTEL_ENABLED` | Enable/disable OpenTelemetry | No |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | When Kafka enabled |
| `KAFKA_SCHEMA_REGISTRY_URL` | Schema registry URL | When Kafka enabled |
| `ENVIRONMENT` | Deployment env name (staging/pre/prod) | Yes |

## Local Development Setup

### 1. Set region env var

```bash
export PPA_REGION=emea
```

### 2. Start dependencies

```bash
docker-compose up -d   # Kafka, mock services, etc.
```

### 3. Run with local profile

```bash
mvn quarkus:dev -Dquarkus.profile=emea,local
```

### 4. IntelliJ Run Configuration

| Field | Value |
|-------|-------|
| Main class | (use Quarkus Dev Mode plugin) |
| VM options | `-Dquarkus.profile=emea,local` |
| Environment variables | `PPA_REGION=emea;PPA_ENCRYPT_KEY=<key>` |
| Working directory | Service root (e.g., `ppa-ppns/`) |

### 5. Dev UI

Quarkus Dev UI is available at `http://localhost:8089/q/dev-ui` during `quarkus:dev`.

## Key Differences from Spring Profile Config

| Aspect | Spring (ppa-connect-bff) | Quarkus (PPA services) |
|--------|--------------------------|------------------------|
| Profile timing | Runtime (`SPRING_PROFILES_ACTIVE`) | **Build-time** (`quarkus.profile` in Maven) |
| Conditional beans | `@Profile("emea")` | `@IfBuildProfile("emea")` |
| Config prefix | `spring.*` | `quarkus.*` |
| Encryption | `{cipher}encryptedValue` | `${aes-gcm-nopadding::encryptedValue}` |
| Encryption key | `PPA_ENCRYPT_KEY` (Spring Cloud) | `PPA_ENCRYPT_KEY` (SmallRye Crypto) |
| Health endpoint | `/actuator/health` | `/service/health/ready` |
| Security config | Spring Security Java config | `quarkus.http.auth.permission.*` in YAML |
| Config server | Spring Cloud Config Server (EMEA) | All config bundled in JAR |
| Config binding | `@ConfigurationProperties` | `@ConfigMapping` / `@ConfigProperty` |
| Dev mode | `spring-boot:run` | `quarkus:dev` (with live reload) |
| Artifact output | One JAR, any profile | **Separate JAR per region** |

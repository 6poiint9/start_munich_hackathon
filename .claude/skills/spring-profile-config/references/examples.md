# spring-profile-config — code examples

Examples moved out of SKILL.md (Layer 3). Section titles match SKILL.md headings.


## Profile Hierarchy › EMEA Region

```
application.yml                  # Base (all environments)
  └── application-emea.yml       # EMEA shared config (loaded from config server)
       ├── emea-staging          # Staging env (config server endpoint)
       ├── emea-pre              # Pre-production env
       └── emea-prod             # Production env
```


## Profile Hierarchy › China Region

```
application.yml                  # Base (all environments)
  └── application-cn.yml         # CN shared config (bundled in JAR)
       ├── application-cn-dev.yml     # CN development
       ├── application-cn-staging.yml # CN staging
       └── application-cn-prod.yml    # CN production
```


## Configuration Files › `application.yml` (Base)

```yaml
encrypt:
  key: ${PPA_ENCRYPT_KEY:fakeKey}    # Encryption for sensitive properties

spring:
  data:
    redis:
      timeout: 5000ms
      lettuce:
        shutdown-timeout: 2000ms
```


## Configuration Files › Key Configuration Areas

```yaml
server:
  port: ${PORT:8081}
  max-http-request-header-size: 16192
  compression:
    enabled: true
    mime-types: text/html,text/xml,text/plain,application/json
    min-response-size: 1024
```

```yaml
ppa-msg-proxy.host: http://ppa-msg-proxy:8083
ppa-vcf-proxy.host: http://ppa-vcf-proxy:8088
ppa-gravity-proxy.host: ${GRAVITY_PROXY_HOST:http://ppa-gravity-proxy:8080}
my-porsche.host: https://api.porsche-preview.com
```

```yaml
polling:
  vf:
    interval-seconds: 8
    max-retries: 10
  mbb:
    interval-seconds: 2
    max-retries: 35
    async-max-retries: 110
  odp:
    interval-seconds: 3
    max-retries: 35
  vcf:
    interval-seconds: 1
    max-retries: 100
```

```yaml
kafka:
  client-id: <service-name>
  group-id: <consumer-group>
  broker-url: <kafka-broker>
  schema-registry-url: <registry>
  schema-registry-username: <user>
  schema-registry-password: <password>
```

```yaml
spring:
  data:
    redis:
      host: ${REDIS_HOST}
      port: ${REDIS_PORT}
```

```yaml
management:
  tracing:
    baggage:
      correlation:
        fields: [X-CIAM-ID]
    sampling:
      probability: 0    # OTEL agent handles sampling
  otlp:
    metrics:
      export:
        enabled: false

tracing:
  tags:
    cloud.provider: aws
    service.name: ${spring.application.name}
```

```yaml
keep-alive:
  duration:
    vf: 120 seconds
    msg: 300 seconds
  delay: 15000 ms
```


## Test Profile: `test-no-cache`

```yaml
spring:
  cloud:
    config:
      enabled: false       # No config server

polling:
  mbb:
    interval-seconds: 1    # Fast polling for tests
    max-retries: 2
  vf:
    interval-seconds: 1
    max-retries: 2

# All mock endpoints point to localhost:52454
```


## Adding New Configuration › 2. Create a `@ConfigurationProperties` class

```kotlin
@ConfigurationProperties(prefix = "my-feature")
data class MyFeatureProperties(
    val enabled: Boolean = false,
    val timeout: Duration = Duration.ofSeconds(30),
    val host: String = "http://default-host"
)
```


## Docker / Local Services

```bash
# Start Redis and Kafka locally
docker-compose up -d

# Redis: localhost:6379
# Kafka: localhost:9092 (internal), localhost:9093 (SASL_PLAINTEXT)
```

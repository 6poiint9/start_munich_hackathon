# quarkus-profile-config — code examples

Examples moved out of SKILL.md (Layer 3). Section titles match SKILL.md headings.


## Profile Hierarchy › EMEA Region

```
application.yaml                      # Base (all environments)
  └── application-emea.yaml           # EMEA shared config
       ├── application-emea-staging.yaml
       ├── application-emea-pre.yaml
       └── application-emea-prod.yaml
```


## Profile Hierarchy › China Region

```
application.yaml                      # Base (all environments)
  └── application-cn.yaml             # CN shared config
       ├── application-cn-staging.yaml
       └── application-cn-prod.yaml
```


## Maven Profile Activation

```xml
<profile>
  <id>emea</id>
  <activation>
    <property>
      <name>env.PPA_REGION</name>
      <value>emea</value>
    </property>
  </activation>
  <properties>
    <quarkus.profile>emea</quarkus.profile>
  </properties>
  <!-- Excludes CN-specific config files and classes -->
</profile>

<profile>
  <id>cn</id>
  <activation>
    <property>
      <name>env.PPA_REGION</name>
      <value>cn</value>
    </property>
  </activation>
  <properties>
    <quarkus.profile>cn</quarkus.profile>
  </properties>
  <!-- Excludes EMEA-specific config files and classes -->
</profile>
```


## Configuration Keys (Quarkus-Specific) › Server & Security

```yaml
quarkus:
  http:
    port: ${PORT:8089}
    non-application-root-path: /service
    auth:
      permission:
        permitHealthReady:
          paths: /service/health/ready
          policy: permit
          methods: GET
        denyAllOthers:
          paths: /*
          policy: deny
  oidc:
    tenant-enabled: true
    auth-server-url: ${porsche-id.auth-server-url}
```


## Configuration Keys (Quarkus-Specific) › Observability

```yaml
quarkus:
  otel:
    enabled: false           # Overridden in otel profile
  log:
    console:
      json:
        enabled: true        # Structured JSON logging
```


## Configuration Keys (Quarkus-Specific) › REST Clients

```yaml
quarkus:
  rest-client:
    my-api:
      url: ${MY_API_URL}
      connect-timeout: 5000
      read-timeout: 30000
```


## Adding New Configuration › Step 1 — Add the property

```yaml
# application-emea.yaml
my-feature:
  api-url: https://emea-api.example.com
  timeout: 30s
```


## Adding New Configuration › Step 2 — Inject in code

```java
@ConfigProperty(name = "my-feature.api-url")
String apiUrl;

@ConfigProperty(name = "my-feature.timeout", defaultValue = "30s")
Duration timeout;
```

```java
@ConfigMapping(prefix = "my-feature")
public interface MyFeatureConfig {
    String apiUrl();
    Duration timeout();
}
```

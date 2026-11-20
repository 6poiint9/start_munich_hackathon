# gRPC / Protobuf Integration Patterns

Detailed patterns for integrating gRPC services with Kotlin coroutines in Spring Boot.

## Setup

### 1. Add Dependencies

```xml
<dependency>
    <groupId>io.grpc</groupId>
    <artifactId>grpc-netty</artifactId>
    <version>${grpc.version}</version>
</dependency>
<dependency>
    <groupId>io.grpc</groupId>
    <artifactId>grpc-protobuf</artifactId>
    <version>${grpc.version}</version>
</dependency>
<dependency>
    <groupId>io.grpc</groupId>
    <artifactId>grpc-kotlin-stub</artifactId>
    <version>${grpc-kotlin.version}</version>
</dependency>
<dependency>
    <groupId>com.google.protobuf</groupId>
    <artifactId>protobuf-kotlin</artifactId>
    <version>${protobuf.version}</version>
</dependency>
```

### 2. Define Proto Files

Place `.proto` files in `src/main/proto/`:

```protobuf
syntax = "proto3";
package myservice.v1;

option java_package = "com.example.myservice.v1";
option java_multiple_files = true;

service MyService {
  rpc GetData (GetDataRequest) returns (GetDataResponse);
  rpc StreamData (StreamRequest) returns (stream DataItem);
}

message GetDataRequest {
  string id = 1;
}

message GetDataResponse {
  string id = 1;
  string name = 2;
  int64 timestamp = 3;
}
```

### 3. Generate Stubs

```bash
./mvnw generate-sources
# Stubs generated in target/generated-sources/protobuf/
```

### 4. Create Channel and Stub Configuration

```kotlin
@Configuration
class MyGrpcServiceConfig {

    @Bean
    fun myServiceChannel(
        @Value("\${grpc.my-service.host}") host: String,
        @Value("\${grpc.my-service.port}") port: Int,
    ): ManagedChannel = ManagedChannelBuilder
        .forAddress(host, port)
        .defaultServiceConfig(loadRetryConfig())
        .enableRetry()
        .usePlaintext()  // or .useTransportSecurity() for TLS
        .build()

    @Bean
    fun myServiceStub(
        @Qualifier("myServiceChannel") channel: ManagedChannel,
    ): MyServiceGrpcKt.MyServiceCoroutineStub =
        MyServiceGrpcKt.MyServiceCoroutineStub(channel)

    private fun loadRetryConfig(): Map<String, Any> {
        val json = ClassPathResource("grpc/retry-service-config.json").inputStream
            .bufferedReader().readText()
        return ObjectMapper().readValue(json, Map::class.java) as Map<String, Any>
    }
}
```

### 5. Use in Service

```kotlin
@Service
class MyGrpcService(
    private val stub: MyServiceGrpcKt.MyServiceCoroutineStub,
) {
    suspend fun getData(id: String): DataResponse {
        val request = getDataRequest { this.id = id }
        return stub.getData(request)
    }

    fun streamData(request: StreamRequest): Flow<DataItem> {
        return stub.streamData(request).asFlow()
    }
}
```

## gRPC Client Interceptors

```kotlin
class AuthInterceptor(private val tokenProvider: TokenProvider) : ClientInterceptor {
    override fun <ReqT, RespT> interceptCall(
        method: MethodDescriptor<ReqT, RespT>,
        callOptions: CallOptions,
        next: Channel,
    ): ClientCall<ReqT, RespT> {
        return next.newCall(method, callOptions.withCallCredentials(
            BearerTokenCallCredentials(tokenProvider.getToken())
        ))
    }
}

class BearerTokenCallCredentials(private val token: String) : CallCredentials() {
    override fun applyRequestMetadata(
        requestInfo: RequestInfo,
        executor: Executor,
        applier: MetadataApplier,
    ) {
        val metadata = Metadata()
        metadata.put(
            Metadata.Key.of("Authorization", Metadata.ASCII_STRING_MARSHALLER),
            "Bearer $token"
        )
        applier.apply(metadata)
    }
}
```

## Retry Configuration

Place at `src/main/resources/grpc/retry-service-config.json`:

```json
{
  "methodConfig": [{
    "name": [{"service": "myservice.v1.MyService"}],
    "retryPolicy": {
      "maxAttempts": 3,
      "initialBackoff": "0.5s",
      "maxBackoff": "5s",
      "backoffMultiplier": 2,
      "retryableStatusCodes": ["UNAVAILABLE", "DEADLINE_EXCEEDED"]
    }
  }]
}
```

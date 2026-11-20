# Azure Cosmos DB & Redis Patterns

Patterns for Azure Cosmos DB (document database) and Redis (caching) integration in Quarkus with Kotlin coroutines.

---

## Part 1 — Azure Cosmos DB

### Architecture

```
Service (CDI @ApplicationScoped)
  └── CosmosRepository (suspend functions)
       └── CosmosClient (Azure SDK)
            └── Azure Cosmos DB
```

### Dependencies

```xml
<dependency>
    <groupId>com.azure</groupId>
    <artifactId>azure-cosmos</artifactId>
</dependency>
<!-- Jackson module for Kotlin data classes -->
<dependency>
    <groupId>com.fasterxml.jackson.module</groupId>
    <artifactId>jackson-module-kotlin</artifactId>
</dependency>
```

### Cosmos Client Configuration

```kotlin
@ApplicationScoped
class CosmosClientProducer {

    @ConfigProperty(name = "azure.cosmos.endpoint")
    lateinit var endpoint: String

    @ConfigProperty(name = "azure.cosmos.key")
    lateinit var key: String

    @ConfigProperty(name = "azure.cosmos.database")
    lateinit var database: String

    @Produces
    @ApplicationScoped
    fun cosmosClient(): CosmosClient {
        return CosmosClientBuilder()
            .endpoint(endpoint)
            .key(key)
            .consistencyLevel(ConsistencyLevel.SESSION)
            .contentResponseOnWriteEnabled(true)
            .buildClient()
    }

    @Produces
    @ApplicationScoped
    fun cosmosDatabase(client: CosmosClient): CosmosDatabase {
        return client.getDatabase(database)
    }
}
```

### Configuration

```properties
azure.cosmos.endpoint=${COSMOS_ENDPOINT:https://localhost:8081}
azure.cosmos.key=${COSMOS_KEY:local-key}
azure.cosmos.database=${COSMOS_DATABASE:ppa-db}

# Per-environment
%dev.azure.cosmos.endpoint=https://localhost:8081
%dev.azure.cosmos.key=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
```

### Repository Pattern

```kotlin
@ApplicationScoped
class VehicleRepository(
    private val database: CosmosDatabase,
) {
    companion object {
        private val log = LoggerFactory.getLogger(VehicleRepository::class.java)
        private const val CONTAINER_NAME = "vehicles"
    }

    private val container: CosmosContainer by lazy {
        database.getContainer(CONTAINER_NAME)
    }

    suspend fun findById(id: String, partitionKey: String): Vehicle? =
        withContext(Dispatchers.IO) {
            try {
                container.readItem(id, PartitionKey(partitionKey), Vehicle::class.java).item
            } catch (e: CosmosException) {
                if (e.statusCode == 404) null
                else throw e
            }
        }

    suspend fun findByVin(vin: String): List<Vehicle> =
        withContext(Dispatchers.IO) {
            val query = "SELECT * FROM c WHERE c.vin = @vin"
            val options = CosmosQueryRequestOptions()
            val querySpec = SqlQuerySpec(query, SqlParameter("@vin", vin))

            container.queryItems(querySpec, options, Vehicle::class.java)
                .stream()
                .toList()
        }

    suspend fun upsert(vehicle: Vehicle): Vehicle =
        withContext(Dispatchers.IO) {
            container.upsertItem(vehicle).item
        }

    suspend fun delete(id: String, partitionKey: String) =
        withContext(Dispatchers.IO) {
            try {
                container.deleteItem(id, PartitionKey(partitionKey), CosmosItemRequestOptions())
            } catch (e: CosmosException) {
                if (e.statusCode != 404) throw e
                log.warn("Attempted to delete non-existent item: $id")
            }
        }

    suspend fun findAll(partitionKey: String, limit: Int = 100): List<Vehicle> =
        withContext(Dispatchers.IO) {
            val query = "SELECT TOP $limit * FROM c"
            val options = CosmosQueryRequestOptions().apply {
                setPartitionKey(PartitionKey(partitionKey))
            }
            container.queryItems(query, options, Vehicle::class.java)
                .stream()
                .toList()
        }
}
```

### Entity Model

```kotlin
data class Vehicle(
    val id: String,
    val vin: String,
    val model: String,
    val status: VehicleStatus,
    val region: String,
    @JsonProperty("_etag") val etag: String? = null,
    @JsonProperty("_ts") val timestamp: Long? = null,
)
```

### Optimistic Concurrency (ETag)

```kotlin
suspend fun updateWithEtag(vehicle: Vehicle): Vehicle =
    withContext(Dispatchers.IO) {
        val options = CosmosItemRequestOptions().apply {
            setIfMatchETag(vehicle.etag)
        }
        try {
            container.replaceItem(vehicle, vehicle.id, PartitionKey(vehicle.vin), options).item
        } catch (e: CosmosException) {
            if (e.statusCode == 412) {
                throw OptimisticLockException("Vehicle ${vehicle.id} was modified concurrently")
            }
            throw e
        }
    }
```

### Cosmos DB Health Check

```kotlin
@Liveness
@ApplicationScoped
class CosmosHealthCheck(
    private val cosmosClient: CosmosClient,
    @ConfigProperty(name = "azure.cosmos.database") val database: String,
) : HealthCheck {

    override fun call(): HealthCheckResponse {
        return try {
            cosmosClient.getDatabase(database).read()
            HealthCheckResponse.up("cosmos-db")
        } catch (e: Exception) {
            HealthCheckResponse.down("cosmos-db")
        }
    }
}
```

---

## Part 2 — Redis

### Architecture

```
Service (CDI @ApplicationScoped)
  └── CacheService (typed wrappers)
       └── RedisDataSource (Quarkus managed)
            └── Redis server
```

### Dependencies

```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-redis</artifactId>
</dependency>
```

### Configuration

```properties
quarkus.redis.hosts=${REDIS_URL:redis://localhost:6379}
quarkus.redis.timeout=5s

# TLS (production)
%prod.quarkus.redis.hosts=${REDIS_TLS_URL}
%prod.quarkus.redis.tls.enabled=true

# Connection pool
quarkus.redis.max-pool-size=16
quarkus.redis.max-pool-waiting=32
```

### Cache Service Pattern

```kotlin
@ApplicationScoped
class CacheService(
    private val redis: RedisDataSource,
) {
    companion object {
        private val log = LoggerFactory.getLogger(CacheService::class.java)
        private val mapper = ObjectMapper().registerKotlinModule()
    }

    fun <T : Any> get(key: String, clazz: Class<T>): T? {
        return try {
            val json = redis.value(String::class.java).get(key)
            json?.let { mapper.readValue(it, clazz) }
        } catch (e: Exception) {
            log.warn("Redis GET failed for key=$key", e)
            null
        }
    }

    fun <T : Any> put(key: String, value: T, ttl: Duration = Duration.ofMinutes(15)) {
        try {
            val json = mapper.writeValueAsString(value)
            redis.value(String::class.java).setex(key, ttl.seconds, json)
        } catch (e: Exception) {
            log.warn("Redis SET failed for key=$key", e)
        }
    }

    fun delete(key: String) {
        try {
            redis.key().del(key)
        } catch (e: Exception) {
            log.warn("Redis DEL failed for key=$key", e)
        }
    }

    fun exists(key: String): Boolean {
        return try {
            redis.key().exists(key) > 0
        } catch (e: Exception) {
            log.warn("Redis EXISTS failed for key=$key", e)
            false
        }
    }
}
```

### Typed Cache Wrapper

```kotlin
@ApplicationScoped
class VehicleCache(
    private val cache: CacheService,
) {
    companion object {
        private const val PREFIX = "vehicle:"
        private val TTL = Duration.ofMinutes(30)
    }

    fun get(vin: String): Vehicle? =
        cache.get("$PREFIX$vin", Vehicle::class.java)

    fun put(vehicle: Vehicle) =
        cache.put("$PREFIX${vehicle.vin}", vehicle, TTL)

    fun evict(vin: String) =
        cache.delete("$PREFIX$vin")
}
```

### Cache-Aside Pattern

```kotlin
@ApplicationScoped
class VehicleService(
    private val repository: VehicleRepository,
    private val vehicleCache: VehicleCache,
) {
    suspend fun getVehicle(vin: String): Vehicle? {
        // Check cache first
        vehicleCache.get(vin)?.let { return it }

        // Cache miss — fetch from Cosmos DB
        val vehicle = repository.findByVin(vin).firstOrNull() ?: return null

        // Populate cache
        vehicleCache.put(vehicle)

        return vehicle
    }

    suspend fun updateVehicle(vehicle: Vehicle): Vehicle {
        val updated = repository.upsert(vehicle)
        vehicleCache.put(updated) // update cache
        return updated
    }

    suspend fun deleteVehicle(vin: String, id: String) {
        repository.delete(id, vin)
        vehicleCache.evict(vin) // invalidate cache
    }
}
```

### Redis Hash Operations

For structured cache entries:

```kotlin
@ApplicationScoped
class SessionStore(private val redis: RedisDataSource) {

    fun setSessionField(sessionId: String, field: String, value: String) {
        redis.hash(String::class.java).hset("session:$sessionId", field, value)
    }

    fun getSessionField(sessionId: String, field: String): String? {
        return redis.hash(String::class.java).hget("session:$sessionId", field)
    }

    fun getFullSession(sessionId: String): Map<String, String> {
        return redis.hash(String::class.java).hgetall("session:$sessionId")
    }

    fun expireSession(sessionId: String, ttl: Duration) {
        redis.key().expire("session:$sessionId", ttl.seconds)
    }
}
```

### Redis Health Check

Quarkus Redis automatically registers a health check. Verify at `/q/health/ready`.

To add a custom one:

```kotlin
@Readiness
@ApplicationScoped
class RedisHealthCheck(
    private val redis: RedisDataSource,
) : HealthCheck {

    override fun call(): HealthCheckResponse {
        return try {
            redis.key().exists("health-check-ping")
            HealthCheckResponse.up("redis")
        } catch (e: Exception) {
            HealthCheckResponse.named("redis")
                .down()
                .withData("error", e.message ?: "unknown")
                .build()
        }
    }
}
```

## Testing

### Cosmos DB — Unit Test

```kotlin
@QuarkusTest
class VehicleRepositoryTest {

    @Inject
    lateinit var repository: VehicleRepository

    @Test
    fun `should upsert and read vehicle`() = runTest {
        val vehicle = Vehicle(
            id = "test-1",
            vin = "WP0ZZZ99ZTS392124",
            model = "Taycan",
            status = VehicleStatus.ACTIVE,
            region = "EMEA",
        )

        val saved = repository.upsert(vehicle)
        assertNotNull(saved.etag)

        val found = repository.findById("test-1", "WP0ZZZ99ZTS392124")
        assertEquals("Taycan", found?.model)
    }
}
```

### Redis — Unit Test with Testcontainers

```kotlin
@QuarkusTest
class CacheServiceTest {

    companion object {
        @Container
        val redis = GenericContainer("redis:7-alpine").withExposedPorts(6379)
    }

    @Inject
    lateinit var cache: CacheService

    @Test
    fun `should store and retrieve from cache`() {
        val vehicle = Vehicle(id = "1", vin = "VIN123", model = "911", status = VehicleStatus.ACTIVE, region = "EMEA")

        cache.put("vehicle:VIN123", vehicle)
        val cached = cache.get("vehicle:VIN123", Vehicle::class.java)

        assertNotNull(cached)
        assertEquals("911", cached?.model)
    }

    @Test
    fun `should return null for missing key`() {
        val result = cache.get("nonexistent", Vehicle::class.java)
        assertNull(result)
    }
}
```

# logging-patterns — code examples

Examples moved out of SKILL.md (Layer 3). Section titles match SKILL.md headings.


## MDC (Mapped Diagnostic Context) › Coroutine MDC Propagation

```kotlin
import kotlinx.coroutines.slf4j.MDCContext

// GOOD: MDC is propagated to child coroutines
suspend fun orchestrate(vin: String) = withContext(MDCContext()) {
    MDC.put("vin", vin)
    coroutineScope {
        val a = async { serviceA.call() }  // MDC available here
        val b = async { serviceB.call() }  // MDC available here
        combine(a.await(), b.await())
    }
}

// BAD: MDC is lost when switching coroutine context
suspend fun orchestrate(vin: String) {
    MDC.put("vin", vin)
    coroutineScope {
        launch { serviceA.call() }  // MDC may be lost!
    }
}
```


## Log Levels Guide › Anti-Patterns

```kotlin
// BAD: Logging sensitive data
log.info("User authenticated with token: $bearerToken")

// GOOD: Log identifiers only
log.info("User authenticated: ciamId=$ciamId")

// BAD: String concatenation (evaluated even when level is disabled)
log.debug("Processing " + items.size + " items for " + vin)

// GOOD: Parameterized logging (lazy evaluation)
log.debug("Processing {} items for vehicle", items.size)

// BAD: Logging in tight loops
items.forEach { item ->
    log.debug("Processing item: $item")  // Thousands of log lines!
}

// GOOD: Log aggregate
log.debug("Processing {} items", items.size)

// BAD: Logging and re-throwing (causes duplicate log entries)
try { call() } catch (e: Exception) {
    log.error("Failed", e)
    throw e  // Caller will also log this!
}

// GOOD: Log at the boundary, not at every layer
// Let the top-level error handler log the error
throw ServiceException("External call failed", e)
```

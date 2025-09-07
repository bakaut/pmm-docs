# Enhanced Cache Debug Guide - What to Look For

## Debug Message Patterns by Scenario

### 1. 🎯 Successful Cache Hit (Best Case)

```
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST START =====
[CACHE_DEBUG] fetch_history called: session=abc12345..., limit=40, cache_available=True
[CACHE_DEBUG] Cache condition analysis:
[CACHE_DEBUG]   - cache_manager available: True
[CACHE_DEBUG]   - limit_count provided: True (value: 40)
[CACHE_DEBUG]   - limit matches CACHE_N: True (expected: 40)
[CACHE_DEBUG]   - all conditions met: True
[CACHE_DEBUG] DECISION: Attempting incremental cache (all conditions satisfied)
[CACHE_DEBUG] Cache strategy: N-2 incremental (N=40, stable=38, dynamic=2)
[CACHE_DEBUG] Starting incremental cache fetch for session abc12345
[CACHE_DEBUG] Total messages in session: 50 (query took 2.34ms)
[CACHE_DEBUG] CASE 3: Valid caching scenario - proceeding with incremental cache
[CACHE_DEBUG] Cache efficiency potential: 95.0% (stable=38, total=40)
[CACHE_DEBUG] Cache lookup: tenant=history_stable, signature=stable:abc123def456
[CACHE_DEBUG] CASE C4: Cache hit! Retrieved 38 valid messages (age: 0.5 hours, parse: 0.89ms)
[CACHE_DEBUG] CASE 3b: Cache HIT for stable messages: 38 messages (took 1.23ms)
[CACHE_DEBUG] CASE A: Dynamic query successful - fetched 2 rows in 0.67ms
[CACHE_DEBUG] Final result: 40 total messages, cache hit rate: 95.0%, total time: 4.56ms
[CACHE_DEBUG] CASE 5c: Result integrity verified - correct message count
[CACHE_DEBUG] RESULT: Incremental cache completed in 4.56ms, returned 40 messages
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST END (CACHED) =====
```

**Key Indicators:**
- ✅ All cache conditions met
- ✅ Cache hit rate: 95.0%
- ✅ Total time: <10ms
- ✅ Case 3b and Case C4 (successful cache operations)

---

### 2. 📥 Cache Miss - First Request (Normal)

```
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST START =====
[CACHE_DEBUG] DECISION: Attempting incremental cache (all conditions satisfied)
[CACHE_DEBUG] CASE 3: Valid caching scenario - proceeding with incremental cache
[CACHE_DEBUG] CASE A: Cache miss - no data found for signature stable:xyz789abc123
[CACHE_DEBUG] CASE 3a: Cache MISS for stable messages (took 1.45ms to check)
[CACHE_DEBUG] CASE A: DB query successful - fetched 38 rows in 12.34ms
[CACHE_DEBUG] CASE C: Successfully cached 38 stable messages in 2.67ms (key: cache:history_stable:...)
[CACHE_DEBUG] Final result: 40 total messages, cache hit rate: 95.0%, total time: 18.92ms
[CACHE_DEBUG] RESULT: Incremental cache completed in 18.92ms, returned 40 messages
```

**Key Indicators:**
- ✅ Cache miss expected for new data
- ✅ Successfully cached for future requests
- ✅ Slower time (~15-20ms) due to DB query + caching
- ✅ Case 3a and Case A (cache miss scenarios)

---

### 3. 🚫 Cache Bypass - Wrong Limit

```
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST START =====
[CACHE_DEBUG] fetch_history called: session=abc12345..., limit=20, cache_available=True
[CACHE_DEBUG] Cache condition analysis:
[CACHE_DEBUG]   - cache_manager available: True
[CACHE_DEBUG]   - limit_count provided: True (value: 20)
[CACHE_DEBUG]   - limit matches CACHE_N: False (expected: 40)
[CACHE_DEBUG]   - all conditions met: False
[CACHE_DEBUG] DECISION: Cache bypass - limit mismatch (got 20, need 40 for caching)
[CACHE_DEBUG] DECISION: Using direct database query for session abc12345...
[CACHE_DEBUG] RESULT: Direct DB query completed in 8.45ms, returned 20 messages
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST END (DIRECT) =====
```

**Key Indicators:**
- ⚠️ Cache bypass due to limit mismatch
- ✅ System works correctly without cache
- ✅ Direct DB query performance

---

### 4. 🔧 Cache Manager Not Available

```
[CACHE_DEBUG] ===== FETCH_HISTORY REQUEST START =====
[CACHE_DEBUG] Cache condition analysis:
[CACHE_DEBUG]   - cache_manager available: False
[CACHE_DEBUG] DECISION: Cache bypass - no cache manager configured
[CACHE_DEBUG] DECISION: Using direct database query
[CACHE_DEBUG] RESULT: Direct DB query completed in 9.12ms, returned 40 messages
```

**Key Indicators:**
- ⚠️ No cache manager available
- ✅ Graceful fallback to direct queries

---

### 5. 📊 Too Few Messages for Caching

```
[CACHE_DEBUG] CASE 1: Too few messages (2 <= 2) for caching, using direct fetch
[CACHE_DEBUG] Reason: Cannot split into stable+dynamic when total <= dynamic count
[CACHE_DEBUG] CASE A: No messages in session - returning empty list
```

**Key Indicators:**
- ⚠️ Edge case: insufficient messages for caching strategy
- ✅ Appropriate fallback behavior

---

### 6. 💾 Cache Invalidation

```
[CACHE_DEBUG] New message saved, triggering cache invalidation for session abc12345
[CACHE_DEBUG] Starting cache invalidation for session abc12345... (tenant: history_stable)
[CACHE_DEBUG] Pre-invalidation: 5 cache entries exist
[CACHE_DEBUG] CASE B: Cache invalidation successful - cleared 5 entries in 3.21ms
[CACHE_DEBUG] Invalidation efficiency: 100.0% (5/5 entries)
[CACHE_DEBUG] Post-invalidation: 0 cache entries remain
```

**Key Indicators:**
- ✅ Automatic invalidation on new messages
- ✅ Efficient clearing of stale cache
- ✅ Performance impact minimal (<5ms)

---

### 7. ❌ Cache Error (Fault Tolerance)

```
[CACHE_DEBUG] CASE D: Cache retrieval failed with exception: ConnectionError('Redis unavailable')
[CACHE_DEBUG] FALLBACK: Incremental cache failed, falling back to database: ConnectionError
[CACHE_DEBUG] DECISION: Using direct database query
[CACHE_DEBUG] RESULT: Direct DB query completed in 12.45ms, returned 40 messages
```

**Key Indicators:**
- ❌ Cache failure (Redis down, network issues)
- ✅ Automatic fallback to database
- ✅ System continues working normally

---

## 🔍 Debug Commands You Can Use

### 1. Check Cache Status
```python
# Get comprehensive cache status
status = db.get_cache_status()
print(json.dumps(status, indent=2, default=str))

# Log cache summary
db.log_cache_summary("your-session-id")
```

### 2. Monitor Cache Performance
```python
# Before your operation
import time
start = time.time()

# Your fetch_history call
messages = db.fetch_history(session_uuid, 40)

# Check timing
elapsed = (time.time() - start) * 1000
print(f"Operation took {elapsed:.2f}ms")
```

### 3. Test Cache Scenarios
```python
# Test 1: Cache miss (first request)
messages1 = db.fetch_history("new-session", 40)  # Should miss

# Test 2: Cache hit (repeat request)  
messages2 = db.fetch_history("new-session", 40)  # Should hit

# Test 3: Cache bypass (wrong limit)
messages3 = db.fetch_history("new-session", 20)  # Should bypass
```

## 📈 Performance Expectations

| Scenario | Expected Time | Cache Hit Rate | Log Pattern |
|----------|---------------|----------------|-------------|
| **Cache Hit** | 2-5ms | 95% | Case 3b + Case C4 |
| **Cache Miss** | 15-25ms | 95% (after caching) | Case 3a + Case A |
| **Direct Query** | 8-15ms | 0% | Direct DB patterns |
| **Cache Error** | 10-20ms | 0% (fallback) | Case D + FALLBACK |

## 🚨 Red Flags to Watch For

1. **Frequent Cache Misses**: If you see many Case A messages for the same session
2. **Cache Corruption**: Case C1, C2, C3, C5 messages indicate data issues
3. **Performance Regression**: Direct queries consistently >20ms
4. **Frequent Invalidation**: Time since last invalidation <60 seconds
5. **Cache Errors**: Persistent Case D errors indicate Redis issues

## 🔧 Troubleshooting Steps

1. **No Cache Debug Messages?**
   - Check logging level: `logging.basicConfig(level=logging.INFO)`
   - Verify cache_manager injection in DatabaseManager

2. **Always Cache Miss?**
   - Check Redis connectivity: `redis-cli ping`
   - Verify cache signatures are consistent
   - Check TTL settings

3. **Poor Performance?**
   - Monitor cache hit rates
   - Check if limit_count equals 40
   - Verify Redis latency

4. **Cache Not Invalidating?**
   - Check save_message() calls trigger invalidation
   - Monitor clear_tenant_cache() results

Run the debug script to test your setup:
```bash
python3 debug_cache.py
```
# Cache Debug Usage Examples

## How to Monitor Cache Operations

### 1. Enable Debug Logging

Add this to your application startup (e.g., in `index.py`):

```python
import logging

# Set logging level to INFO to see cache debug messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or set specific logger level
logger = logging.getLogger("mindset.database")
logger.setLevel(logging.INFO)
```

### 2. Check Cache Status

```python
# Get comprehensive cache status
status = db.get_cache_status()
print(json.dumps(status, indent=2, default=str))

# Log cache summary for monitoring
db.log_cache_summary("session-123")
```

### 3. Monitor Cache Operations in Real-Time

When you call `fetch_history()`, you'll see debug logs like:

```
[CACHE_DEBUG] fetch_history called: session=abc-123, limit=40, cache_available=True
[CACHE_DEBUG] Attempting incremental cache for session abc-123 (N=40)
[CACHE_DEBUG] Total messages in session: 50 (query took 2.34ms)
[CACHE_DEBUG] Cache strategy: stable=38, dynamic=2, total_requested=40
[CACHE_DEBUG] Cache HIT for stable messages: 38 messages (took 1.23ms)
[CACHE_DEBUG] Fetched 2 dynamic messages from DB (took 0.89ms)
[CACHE_DEBUG] Final result: 40 total messages, cache hit rate: 95.0%
[CACHE_DEBUG] Incremental cache completed in 4.56ms, returned 40 messages
```

### 4. Cache Miss Scenario

```
[CACHE_DEBUG] Cache MISS for stable messages (took 1.45ms to check)
[CACHE_DEBUG] Fetched and cached 38 stable messages from DB (took 12.34ms)
[CACHE_DEBUG] Successfully cached 38 stable messages in 2.67ms (key: cache:history_stable:abc123def)
```

### 5. Cache Invalidation

```
[CACHE_DEBUG] New message saved, triggering cache invalidation for session abc-123
[CACHE_DEBUG] Starting cache invalidation for session abc-123 (tenant: history_stable)
[CACHE_DEBUG] Cache invalidation completed: cleared 5 entries in 3.21ms
```

### 6. Performance Monitoring

Key metrics to watch:

- **Cache Hit Rate**: Should be ~95% for sessions with >40 messages
- **Cache Response Time**: Should be <5ms for cache hits
- **Database Query Time**: Should be much higher (10-50ms) for cache misses
- **Invalidation Frequency**: Should be rare (only when message boundaries shift)

### 7. Troubleshooting

#### No Cache Debug Messages?
1. Check if cache_manager is properly injected in DatabaseManager
2. Verify Redis is running and accessible
3. Ensure logging level is set to INFO or DEBUG

#### Cache Always Missing?
1. Check cache signature generation
2. Verify Redis index exists
3. Check TTL settings

#### Poor Performance?
1. Monitor cache hit/miss ratios
2. Check if limit_count equals HISTORY_CACHE_N (40)
3. Verify Redis connection latency

### 8. Testing Cache Functionality

Run the debug script:

```bash
cd /path/to/flow
python3 debug_cache.py
```

This will test cache connectivity and show you what to expect in the logs.

### 9. Example Log Analysis

**Good Performance (Cache Hit):**
```
[CACHE_DEBUG] Cache HIT for stable messages: 38 messages (took 1.2ms)
[CACHE_DEBUG] Final result: 40 total messages, cache hit rate: 95.0%
[CACHE_DEBUG] Incremental cache completed in 3.4ms
```

**Cache Miss (First Request):**
```
[CACHE_DEBUG] Cache MISS for stable messages (took 1.5ms to check)
[CACHE_DEBUG] Fetched and cached 38 stable messages from DB (took 15.6ms)
[CACHE_DEBUG] Successfully cached 38 stable messages in 2.1ms
```

**Cache Bypass (Non-optimal conditions):**
```
[CACHE_DEBUG] Cache conditions not met - cache_available=True, limit=20, expected_limit=40
[CACHE_DEBUG] Using direct database query for session abc-123
[CACHE_DEBUG] Direct DB query completed in 8.9ms, returned 20 messages
```

### 10. Production Monitoring

For production, consider:

1. **Log aggregation**: Collect cache metrics for analysis
2. **Alerting**: Alert on high cache miss rates or errors
3. **Dashboards**: Visualize cache performance over time
4. **Health checks**: Regular cache connectivity tests

Remember: The cache only activates when `limit_count` equals `HISTORY_CACHE_N` (40), so ensure your application requests exactly 40 messages to benefit from incremental caching.
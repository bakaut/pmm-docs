# Redis Cache System for ПойМойМир Bot

## Overview

This document describes the Redis-based caching system implemented for the ПойМойМир Telegram bot. The cache system provides high-performance storage for embeddings, LLM responses, and semantic search capabilities using Redis with RedisSearch (FT module).

## Architecture

### Key Components

1. **CacheManager** (`cache_manager.py`) - Core cache operations
2. **CacheConfig** (in `config.py`) - Configuration management
3. **Enhanced LLMManager** - LLM operations with cache integration
4. **Cache Examples** (`cache_examples.py`) - Integration patterns
5. **Usage Examples** (`cache_usage_example.py`) - Practical implementation

### Cache Schema

**Redis Key Pattern:**
```
cache:{tenant}:{qhash}
```

**Hash Fields:**
- `text` - Cached text content (TEXT)
- `tenant` - Environment/organization identifier (TAG)
- `user` - User identifier (TAG)
- `created_at` - Unix timestamp (NUMERIC, SORTABLE)
- `embedding` - Binary float32 vector (VECTOR)

**RedisSearch Index:**
- **Text Search**: Full-text search on cached content
- **Vector Search**: KNN similarity search using cosine distance
- **Filtering**: By tenant, user, and creation time
- **TTL**: Per-key automatic expiration

## Installation & Setup

### 1. Install Dependencies

```bash
# Install Redis Python client
pip install redis>=5.0.0

# Or use the provided requirements file
pip install -r flow/cache_requirements.txt
```

### 2. Redis Server Setup

#### Option A: Local Redis
```bash
# Install Redis (macOS)
brew install redis

# Start Redis server
redis-server

# Verify RedisSearch module (required for vector search)
redis-cli MODULE LIST
```

#### Option B: Redis Cloud
```bash
# Use Redis Cloud or other Redis service with RedisSearch support
# Update CACHE_REDIS_URL accordingly
```

### 3. Environment Configuration

Add these variables to your `.env` file:

```bash
# Cache Configuration
CACHE_REDIS_URL=redis://localhost:6379/0
CACHE_INDEX_NAME=idx:cache
CACHE_KEY_PREFIX=cache:
CACHE_EMBEDDING_DIMENSIONS=1536
CACHE_DEFAULT_TTL=3600
CACHE_ENABLE_EMBEDDINGS=true
CACHE_MAX_TEXT_LENGTH=10000
CACHE_BATCH_SIZE=100
```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CACHE_INDEX_NAME` | `idx:cache` | RedisSearch index name |
| `CACHE_KEY_PREFIX` | `cache:` | Redis key prefix |
| `CACHE_EMBEDDING_DIMENSIONS` | `1536` | Embedding vector size |
| `CACHE_DEFAULT_TTL` | `3600` | Default cache TTL (seconds) |
| `CACHE_ENABLE_EMBEDDINGS` | `true` | Enable embedding storage/search |
| `CACHE_MAX_TEXT_LENGTH` | `10000` | Max text length for caching |
| `CACHE_BATCH_SIZE` | `100` | Batch size for bulk operations |

## Usage Examples

### Basic Integration

```python
from mindset.config import Config
from mindset.cache_manager import CacheManager
from mindset.llm_manager import LLMManager
from mindset.utils import Utils

# Load configuration (includes cache settings)
config = Config.from_env()
logger = get_logger()
utils = Utils(config, logger)

# Initialize LLM manager first (required for embedding generation)
llm_manager = LLMManager(config, utils, logger)

# Initialize cache manager with LLM manager
cache_manager = CacheManager(config, llm_manager, logger)
```

### Caching Embeddings

### Caching with Auto-Generated Embeddings

```python
# Store text with automatically generated embedding
cache_manager.put_cache(
    tenant="pmm_bot",
    user="user123", 
    key_signature="conversation:greeting",
    text="Привет! Как дела?",
    ttl_seconds=3600
)  # Embedding is generated internally from text

# Retrieve cache entry
cached = cache_manager.get_cache_by_signature(
    tenant="pmm_bot",
    key_signature="conversation:greeting"
)

# Semantic search with text (embedding generated internally)
results = cache_manager.semantic_search(
    tenant="pmm_bot",
    query_text="Привет, как поживаешь?",
    k=10,
    user="user123"
)
```

### Caching LLM Responses

```python
# Cached LLM call
response = llm_manager.cached_llm_call(
    messages=openai_messages,
    user_id="user123",
    use_cache=True,
    cache_ttl=86400  # 24 hours
)
```

### Direct Cache Operations

### Direct Cache Operations

```python
# Store cache entry with auto-generated embedding
cache_manager.put_cache(
    tenant="pmm_bot",
    user="user123", 
    key_signature="conversation:greeting",
    text="Привет! Как дела?",
    ttl_seconds=3600
)

# Retrieve cache entry
cached = cache_manager.get_cache_by_signature(
    tenant="pmm_bot",
    key_signature="conversation:greeting"
)

# Semantic search with text query
results = cache_manager.semantic_search(
    tenant="pmm_bot",
    query_text="Привет, как поживаешь?",
    k=10,
    user="user123"
)

# KNN search with pre-generated embedding vector
results = cache_manager.knn_search(
    tenant="pmm_bot",
    query_vector=query_embedding,
    k=10,
    user="user123"
)
```

## Cache Tenants

The system uses tenant-based isolation:

- **`pmm_llm`** - LLM responses and embeddings
- **`pmm_db`** - Database query caching
- **`pmm_embeddings`** - Pure embedding storage
- **`pmm_bot`** - Bot-specific cache data

## Performance Considerations

### TTL Strategy
- **Embeddings**: 7 days (rarely change)
- **LLM Responses**: 24 hours (context-dependent)
- **Database Queries**: 1 hour (may update)

### Memory Usage
- **Embedding Size**: 1536 dimensions × 4 bytes = ~6KB per embedding
- **Index Overhead**: ~20% additional memory
- **Recommended RAM**: 4GB+ for production use

### Optimization Tips

1. **Batch Operations**: Use batch processing for multiple embeddings
2. **Text Length**: Limit cached text to essential content
3. **Selective Caching**: Don't cache everything, focus on frequent operations
4. **Monitor Usage**: Use cache statistics for optimization

## Monitoring & Maintenance

### Health Checks

```python
# Check cache health
health = cache_manager.health_check()
print(f"Redis connected: {health['redis_connected']}")
print(f"Index exists: {health['index_exists']}")
```

### Statistics

```python
# Get cache statistics
stats = cache_manager.get_cache_stats()
print(f"Total documents: {stats['total_documents']}")
print(f"Index size: {stats['index_size']} bytes")

# Tenant-specific stats
llm_stats = cache_manager.get_cache_stats(tenant="pmm_llm")
print(f"LLM cached items: {llm_stats.get('tenant_documents', 0)}")
```

### Cleanup Operations

```python
# Clear tenant cache
cleared = cache_manager.clear_tenant_cache("old_tenant")
print(f"Cleared {cleared} entries")

# TTL handles automatic expiration
# Manual cleanup only needed for specific scenarios
```

## Integration with Existing Code

### 1. Update index.py

```python
# Add cache manager initialization with LLM manager
llm = LLMManager(config, utils, logger)
cache_manager = CacheManager(config, llm, logger)
```

### 2. Update Message Handling

```python
# Enhanced embedding generation
user_embedding = llm.embd_text(text, user_id=tg_user_id_str, use_cache=True)

# Cached LLM responses  
ai_answer = llm.cached_llm_call(
    messages=openai_msgs,
    user_id=tg_user_id_str,
    use_cache=True
)

# Similarity search for related conversations
similar = llm.find_similar_embeddings(text, user_id=tg_user_id_str)
```

### 3. Database Integration

```python
# Save messages with embeddings (existing database schema)
db.save_message(session_uuid, user_uuid, "user", text, user_embedding, tg_msg_id)
```

## Error Handling

The cache system is designed with graceful degradation:

1. **Redis Connection Failure**: Falls back to direct API calls
2. **Cache Miss**: Generates new content and caches result
3. **Index Issues**: Attempts to recreate index automatically
4. **Memory Limits**: Uses TTL for automatic cleanup

## Security Considerations

1. **Network Security**: Use `rediss://` for encrypted connections in production
2. **Access Control**: Configure Redis AUTH if exposed
3. **Data Isolation**: Tenant-based separation prevents cross-contamination
4. **PII Handling**: Avoid caching sensitive personal information

## Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Check Redis server status
redis-cli ping

# Verify connection URL
redis-cli -u redis://localhost:6379/0 ping
```

**RedisSearch Module Missing**
```bash
# Check if module is loaded
redis-cli MODULE LIST

# Load module (if available)
redis-cli MODULE LOAD /path/to/redisearch.so
```

**Index Creation Failed**
```python
# Manually recreate index
cache_manager.ensure_index()

# Check index status
health = cache_manager.health_check()
```

**Performance Issues**
```python
# Monitor cache hit rates
stats = cache_manager.get_cache_stats()

# Adjust TTL settings in configuration
# Reduce embedding dimensions if needed
```

### Logging

Enable debug logging to troubleshoot cache operations:

```python
import logging
logging.getLogger('mindset.cache_manager').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Cache Warming**: Pre-populate frequently accessed embeddings
2. **Compression**: Compress large text content before caching
3. **Metrics**: Add detailed performance metrics and dashboards  
4. **Clustering**: Support Redis Cluster for scalability
5. **Backup**: Implement cache backup and restore procedures

## API Reference

See the following files for detailed API documentation:

- `cache_manager.py` - Core cache operations
- `cache_examples.py` - Integration patterns
- `cache_usage_example.py` - Complete usage examples
- `config.py` - Configuration options

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the example files for implementation patterns
3. Enable debug logging for detailed error information
4. Verify Redis server and RedisSearch module availability
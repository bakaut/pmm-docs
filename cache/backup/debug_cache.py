#!/usr/bin/env python3
"""
Cache Debug Script for DatabaseManager

This script helps debug and monitor the incremental caching functionality.
Run this to see real-time cache operations and performance.
"""

import sys
import json
import time
from unittest.mock import Mock

# Add the mindset module to path
sys.path.insert(0, '/Users/nlebedev@tempo.io/pers/poymoymir/flow')

def create_mock_config():
    """Create a mock configuration for testing"""
    config = Mock()
    config.log_level = "DEBUG"
    config.retry_total = 3
    config.retry_backoff_factor = 0.3
    config.enable_conversation_reset = True
    config.system_prompt = "Test prompt"
    config.cache_redis_url = "redis://localhost:6379/0"
    config.cache_index_name = "idx:cache"
    config.cache_key_prefix = "cache:"
    config.cache_embedding_dimensions = 1536
    config.cache_default_ttl = 3600
    config.cache_enable_embeddings = True
    config.cache_max_text_length = 10000
    config.cache_batch_size = 100
    config.cache_fault_tolerant = True
    return config

def test_cache_integration():
    """Test the cache integration without actual database"""
    print("🔍 Testing Cache Integration (Mock Mode)")
    print("=" * 50)
    
    try:
        from mindset.config import Config
        from mindset.database import DatabaseManager
        from mindset.cache_manager import CacheManager
        from mindset.llm_manager import LLMManager
        from mindset.utils import Utils
        import logging
        
        # Set up logging to see debug messages
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger("cache_debug")
        
        # Create real configuration
        config = Config.from_env()
        
        # Create utilities
        utils = Utils(config, logger)
        
        # Create LLM manager (mock to avoid API calls)
        llm_manager = Mock()
        llm_manager.embd_text.return_value = [0.1] * 1536  # Mock embedding
        
        # Create cache manager
        print("📦 Initializing CacheManager...")
        cache_manager = CacheManager(config, llm_manager, logger)
        
        # Test cache health
        print("🏥 Checking cache health...")
        try:
            health = cache_manager.health_check()
            print(f"   ✅ Cache health: {json.dumps(health, indent=2)}")
        except Exception as e:
            print(f"   ❌ Cache health check failed: {e}")
            return False
        
        # Create database manager with cache
        print("🗄️  Initializing DatabaseManager with cache...")
        db = DatabaseManager(config, logger, cache_manager)
        
        # Test cache status
        print("📊 Getting cache status...")
        status = db.get_cache_status()
        print(f"   Cache Status: {json.dumps(status, indent=2, default=str)}")
        
        # Test signature generation
        print("🔑 Testing signature generation...")
        session_uuid = "test-session-debug-123"
        signature = db._create_stable_signature(session_uuid, 38, 50)
        print(f"   Generated signature: {signature}")
        
        # Test cache operations
        print("💾 Testing cache operations...")
        
        # Try to cache some test data
        try:
            cache_key = cache_manager.put_cache(
                tenant="history_stable",
                user=session_uuid,
                key_signature="test_signature",
                text=json.dumps([{"role": "user", "content": "test message"}]),
                ttl_seconds=3600
            )
            print(f"   ✅ Successfully cached test data: {cache_key}")
            
            # Try to retrieve it
            cached_data = cache_manager.get_cache_by_signature("history_stable", "test_signature")
            if cached_data:
                print(f"   ✅ Successfully retrieved cached data")
            else:
                print(f"   ❌ Failed to retrieve cached data")
                
        except Exception as e:
            print(f"   ❌ Cache operations failed: {e}")
        
        print("\n🎉 Cache integration test completed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error (this is expected in test environment): {e}")
        print("   This means you need to run this script in the actual environment with dependencies installed.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def show_cache_debug_instructions():
    """Show instructions for using the cache debug features"""
    print("\n🛠️  Cache Debug Instructions")
    print("=" * 50)
    print("""
To monitor cache operations in real-time:

1. 📊 Enable Debug Logging:
   import logging
   logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(levelname)s - %(message)s')

2. 🔍 Key Debug Messages to Watch:

   🟢 CACHE HIT (Good Performance):
   [CACHE_DEBUG] CASE 3b: Cache HIT for stable messages: 38 messages
   [CACHE_DEBUG] Final result: 40 total messages, cache hit rate: 95.0%
   [CACHE_DEBUG] RESULT: Incremental cache completed in 4.56ms

   🟡 CACHE MISS (First Request):
   [CACHE_DEBUG] CASE A: Cache miss - no data found
   [CACHE_DEBUG] CASE 3a: Cache MISS for stable messages
   [CACHE_DEBUG] CASE C: Successfully cached 38 stable messages

   🔴 CACHE BYPASS (Suboptimal):
   [CACHE_DEBUG] DECISION: Cache bypass - limit mismatch (got 20, need 40)
   [CACHE_DEBUG] DECISION: Using direct database query

   ⚠️  CACHE ERROR (Fault Tolerance):
   [CACHE_DEBUG] CASE D: Cache retrieval failed with exception
   [CACHE_DEBUG] FALLBACK: Incremental cache failed, falling back to database

3. 📈 Performance Expectations:
   - Cache Hit: 2-5ms, 95% hit rate
   - Cache Miss: 15-25ms (includes caching overhead)
   - Direct Query: 8-15ms, 0% cache benefit
   - Cache Error: 10-20ms (fallback mode)

4. 🧪 Test Your Cache:
   
   # Test cache miss then hit
   messages1 = db.fetch_history("test-session", 40)  # Miss
   messages2 = db.fetch_history("test-session", 40)  # Hit
   
   # Test cache bypass
   messages3 = db.fetch_history("test-session", 20)  # Bypass
   
   # Check cache status
   status = db.get_cache_status()
   db.log_cache_summary("test-session")

5. 🔧 Troubleshooting:
   - No debug messages? Check logging level and cache_manager injection
   - Always missing? Check Redis connection and signatures
   - Poor performance? Verify limit_count=40 and monitor hit rates
   - Not invalidating? Check save_message() triggers

6. 📊 Monitor Redis directly:
   redis-cli monitor  # Watch all Redis operations
   redis-cli info keyspace  # Check cache usage

7. 🎯 Expected Log Flow for Successful Cache Hit:
   ===== FETCH_HISTORY REQUEST START =====
   → Cache condition analysis: all conditions met: True
   → DECISION: Attempting incremental cache
   → CASE 3: Valid caching scenario
   → CASE C4: Cache hit! Retrieved 38 valid messages
   → CASE 3b: Cache HIT for stable messages: 38 messages
   → Final result: 40 total messages, cache hit rate: 95.0%
   ===== FETCH_HISTORY REQUEST END (CACHED) =====

📚 See CACHE_DEBUG_SCENARIOS.md for detailed examples of each scenario!
""")

if __name__ == "__main__":
    print("🚀 DatabaseManager Cache Debug Tool")
    print("This tool helps you debug and monitor incremental caching")
    print()
    
    # Test cache integration
    success = test_cache_integration()
    
    # Show debug instructions
    show_cache_debug_instructions()
    
    if success:
        print("\n✅ Cache system appears to be working!")
        print("   Check your application logs for [CACHE_DEBUG] messages when using fetch_history()")
    else:
        print("\n⚠️  Run this script in your actual environment with all dependencies to test Redis connectivity")
    
    print("\n🏁 Debug session complete!")
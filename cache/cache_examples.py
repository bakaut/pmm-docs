"""
Cache Integration Examples

This file demonstrates how to integrate the cache system with existing classes
like LLMManager, DatabaseManager, and others in the ПойМойМир project.

The examples show:
1. Caching LLM responses with embeddings
2. Caching database queries
3. Using the cache for embeddings management
4. Similarity search for related content
"""

from typing import List, Dict, Any, Optional
import logging
from .cache_manager import CacheManager
from .config import Config


class CachedLLMManager:
    """
    Example of integrating cache with LLM operations.
    
    This shows how to cache LLM responses and use similarity search
    to find related conversations or responses.
    """
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cache = CacheManager(config, logger)
        
        # Cache configuration for LLM operations
        self.llm_cache_ttl = 86400  # 24 hours for LLM responses
        self.tenant = "pmm_bot"  # Tenant identifier
    
    def cached_llm_call(self, 
                       messages: List[Dict[str, str]], 
                       user_id: str,
                       model: str = None,
                       use_cache: bool = True) -> str:
        """
        Enhanced LLM call with caching support.
        
        Args:
            messages: OpenAI-format messages
            user_id: User identifier
            model: Model to use (optional)
            use_cache: Whether to use caching
            
        Returns:
            LLM response text
        """
        # Generate cache key from messages content
        messages_text = " ".join([msg.get("content", "") for msg in messages])
        cache_key_signature = f"llm_call:{model or self.config.ai_model}:{hash(messages_text)}"
        
        if use_cache:
            # Try to get from cache first
            cached = self.cache.get_cache_by_signature(
                tenant=self.tenant,
                key_signature=cache_key_signature,
                extend_ttl_seconds=self.llm_cache_ttl  # Extend TTL on access
            )
            
            if cached:
                self.logger.debug("LLM response found in cache for user %s", user_id)
                return cached["text"]
        
        # Cache miss - call actual LLM
        try:
            # Here would be your actual LLM API call
            response = self._call_llm_api(messages, model)
            
            # Generate embedding for the response (optional)
            embedding = None
            if self.config.cache_enable_embeddings:
                embedding = self._generate_embedding(response)
            
            # Cache the response
            if use_cache and response:
                self.cache.put_cache(
                    tenant=self.tenant,
                    user=user_id,
                    key_signature=cache_key_signature,
                    text=response,
                    embedding=embedding,
                    ttl_seconds=self.llm_cache_ttl
                )
                self.logger.debug("Cached LLM response for user %s", user_id)
            
            return response
            
        except Exception as e:
            self.logger.error("LLM call failed: %s", e)
            raise
    
    def find_similar_responses(self, 
                             query_text: str, 
                             user_id: Optional[str] = None,
                             k: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar LLM responses using embedding search.
        
        Args:
            query_text: Text to find similar responses for
            user_id: Optional user filter
            k: Number of results to return
            
        Returns:
            List of similar responses with scores
        """
        if not self.config.cache_enable_embeddings:
            return []
        
        try:
            # Generate embedding for query
            query_embedding = self._generate_embedding(query_text)
            
            # Perform similarity search
            results = self.cache.knn_search(
                tenant=self.tenant,
                query_vector=query_embedding,
                k=k,
                user=user_id
            )
            
            return results["hits"]
            
        except Exception as e:
            self.logger.error("Similarity search failed: %s", e)
            return []
    
    def _call_llm_api(self, messages: List[Dict[str, str]], model: str = None) -> str:
        """Placeholder for actual LLM API call"""
        # This would contain your actual LLM calling logic
        return "Mock LLM response"
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Placeholder for embedding generation"""
        # This would contain your actual embedding generation logic
        # For example, calling OpenAI embeddings API
        return [0.1] * self.config.cache_embedding_dimensions


class CachedDatabaseManager:
    """
    Example of integrating cache with database operations.
    
    This shows how to cache frequently accessed database queries
    like user preferences, session data, etc.
    """
    
    def __init__(self, config: Config, db_manager, logger: Optional[logging.Logger] = None):
        self.config = config
        self.db_manager = db_manager
        self.logger = logger or logging.getLogger(__name__)
        self.cache = CacheManager(config, logger)
        
        # Cache configuration for database operations
        self.db_cache_ttl = 3600  # 1 hour for database queries
        self.tenant = "pmm_db"
    
    def cached_get_user_info(self, user_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get user information with caching.
        
        Args:
            user_id: User ID
            use_cache: Whether to use caching
            
        Returns:
            User information dict or None
        """
        cache_key_signature = f"user_info:{user_id}"
        
        if use_cache:
            cached = self.cache.get_cache_by_signature(
                tenant=self.tenant,
                key_signature=cache_key_signature
            )
            
            if cached:
                import json
                try:
                    return json.loads(cached["text"])
                except json.JSONDecodeError:
                    # Cache corrupted, continue to database
                    pass
        
        # Get from database
        user_info = self.db_manager.get_user_by_id(user_id)  # Your actual DB method
        
        if use_cache and user_info:
            import json
            self.cache.put_cache(
                tenant=self.tenant,
                user=user_id,
                key_signature=cache_key_signature,
                text=json.dumps(user_info),
                ttl_seconds=self.db_cache_ttl
            )
        
        return user_info
    
    def invalidate_user_cache(self, user_id: str):
        """Invalidate cached user data when it's updated"""
        cache_key_signature = f"user_info:{user_id}"
        key = self.cache._generate_key(self.tenant, cache_key_signature)
        self.cache.delete_cache(key)
        self.logger.debug("Invalidated cache for user %s", user_id)


class CachedEmbeddingsManager:
    """
    Example of using cache for embeddings management.
    
    This integrates with the embeddings system from the previous session
    to provide caching for generated embeddings.
    """
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cache = CacheManager(config, logger)
        
        # Cache configuration for embeddings
        self.embedding_cache_ttl = 604800  # 1 week for embeddings
        self.tenant = "pmm_embeddings"
    
    def get_or_generate_embedding(self, 
                                text: str, 
                                user_id: str,
                                model: str = "text-embedding-3-small") -> List[float]:
        """
        Get embedding from cache or generate new one.
        
        Args:
            text: Text to embed
            user_id: User identifier
            model: Embedding model
            
        Returns:
            Embedding vector
        """
        # Generate cache key
        text_hash = hash(text)
        cache_key_signature = f"embedding:{model}:{text_hash}"
        
        # Try cache first
        cached = self.cache.get_cache_by_signature(
            tenant=self.tenant,
            key_signature=cache_key_signature
        )
        
        if cached and cached.get("embedding"):
            # Return cached embedding
            embedding = self.cache._unpack_f32(cached["embedding"])
            self.logger.debug("Found cached embedding for text hash %s", text_hash)
            return embedding
        
        # Generate new embedding
        try:
            embedding = self._generate_embedding_api(text, model)
            
            # Cache the embedding
            self.cache.put_cache(
                tenant=self.tenant,
                user=user_id,
                key_signature=cache_key_signature,
                text=text[:100] + "..." if len(text) > 100 else text,  # Store truncated text
                embedding=embedding,
                ttl_seconds=self.embedding_cache_ttl
            )
            
            self.logger.debug("Generated and cached embedding for text hash %s", text_hash)
            return embedding
            
        except Exception as e:
            self.logger.error("Embedding generation failed: %s", e)
            raise
    
    def find_similar_texts(self, 
                          query_text: str, 
                          user_id: Optional[str] = None,
                          k: int = 10,
                          threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Find texts similar to query using embedding search.
        
        Args:
            query_text: Query text
            user_id: Optional user filter
            k: Number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of similar texts with scores
        """
        # Get or generate embedding for query
        query_embedding = self.get_or_generate_embedding(query_text, user_id or "system")
        
        # Search for similar embeddings
        results = self.cache.knn_search(
            tenant=self.tenant,
            query_vector=query_embedding,
            k=k,
            user=user_id
        )
        
        # Filter by threshold
        filtered_hits = []
        for hit in results["hits"]:
            if hit["score"] >= threshold:
                filtered_hits.append(hit)
        
        return filtered_hits
    
    def _generate_embedding_api(self, text: str, model: str) -> List[float]:
        """Placeholder for actual embedding API call"""
        # This would contain your actual OpenAI embeddings API call
        return [0.1] * self.config.cache_embedding_dimensions


class CacheHealthMonitor:
    """
    Utility class for monitoring cache health and performance.
    """
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cache = CacheManager(config, logger)
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        health = self.cache.health_check()
        stats = self.cache.get_cache_stats()
        
        # Get tenant-specific stats
        tenant_stats = {}
        for tenant in ["pmm_bot", "pmm_db", "pmm_embeddings"]:
            tenant_stats[tenant] = self.cache.get_cache_stats(tenant)
        
        return {
            "health": health,
            "overall_stats": stats,
            "tenant_stats": tenant_stats,
            "config": {
                "redis_url": self.config.cache_redis_url,
                "index_name": self.config.cache_index_name,
                "embeddings_enabled": self.config.cache_enable_embeddings,
                "default_ttl": self.config.cache_default_ttl
            }
        }
    
    def cleanup_expired_cache(self, tenant: Optional[str] = None) -> Dict[str, int]:
        """
        Manual cache cleanup (Redis handles TTL automatically, but this can be used for specific cleanup)
        
        Args:
            tenant: Optional specific tenant to clean
            
        Returns:
            Dict with cleanup statistics
        """
        cleaned = {}
        
        if tenant:
            cleaned[tenant] = self.cache.clear_tenant_cache(tenant)
        else:
            # Clean all known tenants
            for t in ["pmm_bot", "pmm_db", "pmm_embeddings"]:
                cleaned[t] = self.cache.clear_tenant_cache(t)
        
        return cleaned


# Example usage patterns:

def example_integration_with_existing_code():
    """
    Example showing how to integrate cache with existing code
    """
    from .config import Config
    
    # Load configuration (cache config will be loaded automatically)
    config = Config.from_env()
    
    # Initialize cached managers
    cached_llm = CachedLLMManager(config)
    cached_db = CachedDatabaseManager(config, db_manager=None)  # Pass your actual DB manager
    cached_embeddings = CachedEmbeddingsManager(config)
    health_monitor = CacheHealthMonitor(config)
    
    # Example usage:
    
    # 1. Cached LLM call
    messages = [{"role": "user", "content": "Hello, how are you?"}]
    response = cached_llm.cached_llm_call(messages, user_id="user123")
    
    # 2. Find similar responses
    similar = cached_llm.find_similar_responses("Hi there", user_id="user123")
    
    # 3. Cached database query
    user_info = cached_db.cached_get_user_info("user123")
    
    # 4. Cached embeddings
    embedding = cached_embeddings.get_or_generate_embedding("Sample text", "user123")
    
    # 5. Similarity search
    similar_texts = cached_embeddings.find_similar_texts("Sample text", k=5)
    
    # 6. Health monitoring
    stats = health_monitor.get_comprehensive_stats()
    print(f"Cache health: {stats['health']['redis_connected']}")
    print(f"Total cached documents: {stats['overall_stats']['total_documents']}")
    
    return {
        "response": response,
        "similar": similar,
        "user_info": user_info,
        "embedding": embedding,
        "similar_texts": similar_texts,
        "stats": stats
    }


if __name__ == "__main__":
    # Example usage
    try:
        result = example_integration_with_existing_code()
        print("Cache integration example completed successfully!")
        print(f"Results keys: {list(result.keys())}")
    except Exception as e:
        print(f"Example failed: {e}")
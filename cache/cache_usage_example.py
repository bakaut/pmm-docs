"""
Usage Example: Integrating Cache with ПойМойМир Bot

This example demonstrates how to update the main index.py to use the new cache system
and how to adapt existing classes to leverage caching capabilities.
"""

from typing import Any, Dict, List, Optional
import logging

# Assuming these imports from the existing code
from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.logger import get_default_logger
from mindset.telegram_bot import TelegramBot
from mindset.utils import Utils
from mindset.llm_manager import LLMManager
from mindset.moderation import ModerationService
from mindset.suno_manager import SunoManager
from mindset.cache_manager import CacheManager


def example_index_with_cache():
    """
    Example of updating the main index.py to integrate caching
    """
    
    # Configuration from environment variables (cache config included automatically)
    config = Config.from_env()
    
    # Create logger with settings from configuration
    log_level = getattr(logging, config.log_level.upper(), logging.DEBUG)
    logger = get_default_logger(config.log_name, log_level)
    
    # Telegram bot
    telegram_bot = TelegramBot(config)
    
    # Database manager 
    db = DatabaseManager(config, logger)
    
    # Utils manager
    utils = Utils(config, logger)
    
    # LLM manager (initialize before cache manager for embedding generation)
    llm = LLMManager(config, utils, logger)
    
    # Initialize cache manager with LLM manager for embedding generation
    cache_manager = None
    if config.cache_enable_embeddings:
        try:
            cache_manager = CacheManager(config, llm, logger)
            logger.info("Cache manager initialized successfully")
            
            # Check cache health
            health = cache_manager.health_check()
            if health["redis_connected"]:
                logger.info("Redis connection healthy")
            else:
                logger.warning("Redis connection issues: %s", health.get("error", "Unknown"))
                
        except Exception as e:
            logger.warning("Failed to initialize cache manager: %s, continuing without cache", e)
    
    # Moderation service
    moderation_service = ModerationService(db, telegram_bot, logger)
    
    # Suno manager
    suno_manager = SunoManager(config, db, telegram_bot, utils, logger)
    
    logger.debug("All managers initialized (cache support: %s)", cache_manager is not None)
    
    return {
        "config": config,
        "logger": logger,
        "cache_manager": cache_manager,
        "telegram_bot": telegram_bot,
        "db": db,
        "utils": utils,
        "llm": llm,
        "moderation_service": moderation_service,
        "suno_manager": suno_manager
    }


def example_enhanced_message_handler(managers: Dict[str, Any], body: Dict[str, Any]):
    """
    Example of enhanced message handler with caching
    """
    
    # Extract managers
    config = managers["config"]
    logger = managers["logger"]
    cache_manager = managers["cache_manager"]
    db = managers["db"]
    llm = managers["llm"]
    telegram_bot = managers["telegram_bot"]
    utils = managers["utils"]
    moderation_service = managers["moderation_service"]
    
    # Extract message data (existing logic)
    message = body.get("message") or body.get("edited_message")
    if not message or not message.get("text"):
        return {"statusCode": 200, "body": ""}
    
    chat_id = message["chat"]["id"]
    text = message["text"]
    tg_msg_id = message["message_id"]
    
    user = message["from"]
    full_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
    tg_user_id = user.get("id")
    
    if not tg_user_id or not isinstance(tg_user_id, int):
        logger.error("Invalid tg_user_id: %s", tg_user_id)
        return {"statusCode": 200, "body": "Invalid user ID"}
    
    tg_user_id_str = str(tg_user_id)
    user_uuid = db.get_or_create_user(chat_id, full_name)
    
    # Session & history (existing logic)
    bot_id = db.get_or_create_bot(config.bot_token)
    session_uuid = db.get_active_session(user_uuid, bot_id, config.session_lifetime)
    history = db.fetch_history(session_uuid)
    
    db.ensure_user_exists(tg_user_id_str, user_uuid)
    
    # Check moderation (existing logic)
    if moderation_service.is_user_blocked(tg_user_id_str):
        return {"statusCode": 200, "body": "banned"}
    
    # Cache user message with auto-generated embedding
    if cache_manager:
        try:
            cache_manager.put_cache(
                tenant="pmm_user_messages",
                user=tg_user_id_str,
                key_signature=f"msg_{tg_msg_id}",
                text=text,
                ttl_seconds=86400  # 24 hours
            )
        except Exception as e:
            logger.warning("Failed to cache user message: %s", e)
    
    # Generate embedding for database (traditional way)
    user_embedding = llm.embd_text(text)
    
    # Save user message with embedding
    msg_id = db.save_message(session_uuid, user_uuid, "user", text, 
                           user_embedding or [], tg_msg_id)
    
    # Prepare message context (existing logic)
    ctx = utils.compute_message_context(history, text)
    openai_msgs = ctx["openai_msgs"]
    
    # Find similar previous conversations using semantic search
    if cache_manager and len(text) > 20:  # Only for substantial messages
        try:
            similar_messages = cache_manager.semantic_search(
                tenant="pmm_user_messages",
                query_text=text,
                k=3,
                user=tg_user_id_str
            )
            
            if similar_messages and similar_messages["hits"]:
                logger.debug("Found %d similar messages for user %s", 
                           len(similar_messages["hits"]), tg_user_id_str)
                # Could use this for context enrichment or suggesting related topics
                
        except Exception as e:
            logger.warning("Similarity search failed: %s", e)
    
    # Generate LLM response
    ai_answer = llm.llm_call(openai_msgs, str(chat_id), tg_user_id_str, moderation_service.moderate_user)
    
    # Cache assistant response with auto-generated embedding
    if ai_answer and ai_answer != config.fallback_answer and cache_manager:
        try:
            cache_manager.put_cache(
                tenant="pmm_assistant_messages",
                user="assistant",
                key_signature=f"response_{tg_msg_id}",
                text=ai_answer,
                ttl_seconds=86400  # 24 hours
            )
        except Exception as e:
            logger.warning("Failed to cache assistant message: %s", e)
        
        # Generate embedding for database
        assistant_embedding = llm.embd_text(ai_answer)
        db.save_message(session_uuid, user_uuid, "assistant", ai_answer, 
                      assistant_embedding or [], tg_msg_id)
    
    # Send response (existing logic)
    try:
        telegram_bot.send_message_chunks(chat_id, ai_answer)
    except Exception as e:
        logger.exception("Failed to send message to Telegram %s", chat_id)
    
    return {"statusCode": 200, "body": ""}


def example_cache_monitoring():
    """
    Example of cache monitoring and maintenance
    """
    config = Config.from_env()
    logger = get_default_logger("cache_monitor")
    
    try:
        # For monitoring, we don't need LLM manager
        cache_manager = CacheManager(config, None, logger)
        
        # Get cache statistics
        stats = cache_manager.get_cache_stats()
        print(f"Total cached documents: {stats['total_documents']}")
        print(f"Index size: {stats['index_size']} bytes")
        
        # Get tenant-specific statistics
        llm_stats = cache_manager.get_cache_stats(tenant="pmm_llm")
        print(f"LLM cached documents: {llm_stats.get('tenant_documents', 0)}")
        
        # Health check
        health = cache_manager.health_check()
        print(f"Redis connected: {health['redis_connected']}")
        print(f"Index exists: {health['index_exists']}")
        
        # Example search
        if health['redis_connected'] and health['index_exists']:
            # Text search example
            text_results = cache_manager.text_search(
                tenant="pmm_llm",
                query="музыка песня",
                limit=5
            )
            print(f"Found {len(text_results['hits'])} text search results")
            
        return {
            "status": "success",
            "stats": stats,
            "health": health
        }
        
    except Exception as e:
        logger.error("Cache monitoring failed: %s", e)
        return {
            "status": "error",
            "error": str(e)
        }


def example_cache_maintenance():
    """
    Example of cache maintenance operations
    """
    config = Config.from_env()
    logger = get_default_logger("cache_maintenance")
    utils = Utils(config, logger)
    
    try:
        # For maintenance operations with embedding generation
        llm = LLMManager(config, utils, logger)
        cache_manager = CacheManager(config, llm, logger)
        
        # Clear old cache entries for a specific tenant
        cleared_llm = cache_manager.clear_tenant_cache("old_tenant")
        logger.info(f"Cleared {cleared_llm} entries for old tenant")
        
        # Performance optimization example
        if config.cache_enable_embeddings:
            # Pre-generate embeddings for common phrases
            common_phrases = [
                "Привет, как дела?",
                "Напиши песню о любви",
                "Хочу послушать музыку"
            ]
            
            for phrase in common_phrases:
                try:
                    # Cache entry with automatically generated embedding
                    cache_manager.put_cache(
                        tenant="pmm_common",
                        user="system",
                        key_signature=f"common_phrase:{hash(phrase)}",
                        text=phrase,
                        ttl_seconds=86400 * 7  # 1 week
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache common phrase '{phrase}': {e}")
        
        return {"status": "maintenance_completed"}
        
    except Exception as e:
        logger.error("Cache maintenance failed: %s", e)
        return {"status": "error", "error": str(e)}


def example_environment_setup():
    """
    Example environment variables for cache configuration
    """
    example_env = {
        # Existing configuration
        "bot_token": "your_bot_token_here",
        "database_url": "postgresql://user:pass@localhost/db",
        "operouter_key": "your_openrouter_key",
        "openai_api_key": "your_openai_key",
        
        # Cache configuration (new)
        "cache_redis_url": "redis://localhost:6379/0",
        "cache_index_name": "idx:cache",
        "cache_key_prefix": "cache:",
        "cache_embedding_dimensions": "1536",
        "cache_default_ttl": "3600",
        "cache_enable_embeddings": "true",
        "cache_max_text_length": "10000",
        "cache_batch_size": "100"
    }
    
    return example_env


if __name__ == "__main__":
    print("=== Cache Integration Examples ===")
    
    # Example 1: Basic setup
    print("\\n1. Setting up managers with cache support...")
    try:
        managers = example_index_with_cache()
        print("✓ Managers initialized successfully")
        print(f"✓ Cache enabled: {managers['cache_manager'] is not None}")
    except Exception as e:
        print(f"✗ Setup failed: {e}")
    
    # Example 2: Environment setup
    print("\\n2. Example environment configuration...")
    env_example = example_environment_setup()
    print("✓ Example environment variables:")
    for key, value in env_example.items():
        if "cache_" in key:
            print(f"  {key}={value}")
    
    # Example 3: Cache monitoring
    print("\\n3. Cache monitoring example...")
    try:
        monitor_result = example_cache_monitoring()
        print(f"✓ Monitoring status: {monitor_result['status']}")
        if monitor_result['status'] == 'success':
            print(f"  Redis connected: {monitor_result['health']['redis_connected']}")
    except Exception as e:
        print(f"✗ Monitoring failed: {e}")
    
    print("\\n=== Integration Examples Complete ===")
    print("\\nNext steps:")
    print("1. Install Redis: pip install redis>=5.0.0")
    print("2. Start Redis server: redis-server")
    print("3. Update your .env file with cache configuration")
    print("4. Replace LLM calls with cached versions in your code")
    print("5. Monitor cache performance and adjust TTL settings")
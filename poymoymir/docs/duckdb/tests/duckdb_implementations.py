#!/usr/bin/env python3
"""
Test script for database implementations

Demonstrates both PostgreSQL and DuckDB implementations of the DatabaseManager.
This script can be used to test functionality and compare performance.

Requirements:
- pip install duckdb
- pip install psycopg2 (for PostgreSQL testing)

Usage:
    python test_database_implementations.py
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add the flow directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent / "flow"))

from mindset.config import Config, DatabaseConfig
from mindset.database_factory import create_database_manager, get_database_info


def setup_logging():
    """Setup basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def create_test_config(db_type: str, db_path: str = None) -> Config:
    """Create a test configuration for the specified database type."""

    # Mock environment variables for Config initialization
    os.environ.update({
        'BOT_TOKEN': 'test_token_1234567890',
        'AI__OPEROUTER_KEY': 'test_openrouter_key',
        'DATABASE__TYPE': db_type,
    })

    if db_type == 'duckdb':
        if db_path:
            os.environ['DATABASE__PATH'] = db_path
        else:
            os.environ['DATABASE__PATH'] = ':memory:'
    else:
        # Mock PostgreSQL settings for testing
        os.environ['DATABASE__URL'] = 'postgresql://test:test@localhost:5432/test'

    try:
        config = Config()
        return config
    except Exception as e:
        print(f"Failed to create config: {e}")
        # Create minimal config manually for testing
        from mindset.config import AIConfig, NetworkConfig, SunoConfig, StorageConfig, MessagesConfig, AudioConfig, CacheConfig, ToolsConfig, PromptsConfig

        if db_type == 'duckdb':
            db_config = DatabaseConfig(type='duckdb', path=db_path or ':memory:')
        else:
            db_config = DatabaseConfig(type='postgresql', url='postgresql://test:test@localhost:5432/test')

        # Create mock config with minimal required fields
        class MockConfig:
            def __init__(self):
                self.database = db_config
                self.ai_model = 'test-model'
                self.bot_token = 'test_token'
                self.session_lifetime = 3600

        return MockConfig()


def test_duckdb_implementation(logger):
    """Test DuckDB implementation."""
    logger.info("=" * 50)
    logger.info("Testing DuckDB Implementation")
    logger.info("=" * 50)

    try:
        # Create temporary file for DuckDB
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as tmp_file:
            db_path = tmp_file.name

        # Create config for DuckDB
        config = create_test_config('duckdb', db_path)

        # Get database info
        db_info = get_database_info(config)
        logger.info(f"Database info: {json.dumps(db_info, indent=2)}")

        # Create database manager
        db_manager = create_database_manager(config, logger)

        # Test basic operations
        logger.info("Testing basic operations...")

        # Test bot creation
        bot_id = db_manager.get_or_create_bot("test_token_hash", "test_bot")
        logger.info(f"Created bot: {bot_id}")

        # Test user creation
        user_id = db_manager.get_or_create_user(12345, "Test User")
        logger.info(f"Created user: {user_id}")

        # Test telegram user
        db_manager.ensure_user_exists("12345", user_id)

        # Test session creation
        session_id = db_manager.get_active_session(user_id, bot_id, 3600)
        logger.info(f"Created session: {session_id}")

        # Test message saving
        test_embedding = [0.1] * 1536  # Mock embedding
        msg_id = db_manager.save_message(
            session_id, user_id, "user", "Hello, world!", test_embedding, 123
        )
        logger.info(f"Saved message: {msg_id}")

        # Test message analysis update
        analysis = {"intent": "greeting", "emotion": "positive"}
        db_manager.update_message_analysis(msg_id, analysis)
        logger.info("Updated message analysis")

        # Test history fetching
        history = db_manager.fetch_history(session_id)
        logger.info(f"Fetched history: {len(history)} messages")

        # Test song operations
        song_id = db_manager.save_song(
            user_id, session_id, "task_123", "Test Song", "A happy song", "pop"
        )
        logger.info(f"Saved song: {song_id}")

        # Test moderation
        mod_result = db_manager.moderate_user("12345", "Test violation")
        logger.info(f"Moderation result: {mod_result}")

        # Test database info
        if hasattr(db_manager, 'get_database_info'):
            db_stats = db_manager.get_database_info()
            logger.info(f"Database statistics: {json.dumps(db_stats, indent=2, default=str)}")

        logger.info("✅ DuckDB implementation test completed successfully!")

        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass

    except Exception as e:
        logger.error(f"❌ DuckDB test failed: {e}", exc_info=True)


def test_postgresql_implementation(logger):
    """Test PostgreSQL implementation (if available)."""
    logger.info("=" * 50)
    logger.info("Testing PostgreSQL Implementation")
    logger.info("=" * 50)

    try:
        # Create config for PostgreSQL
        config = create_test_config('postgresql')

        # Get database info
        db_info = get_database_info(config)
        logger.info(f"Database info: {json.dumps(db_info, indent=2)}")

        # Try to create database manager (will fail if no PostgreSQL available)
        try:
            db_manager = create_database_manager(config, logger)
            logger.info("✅ PostgreSQL database manager created successfully!")
            logger.info("Note: This is just import test - actual database operations would require a running PostgreSQL server")
        except Exception as e:
            logger.warning(f"⚠️  PostgreSQL manager creation failed (expected if no server): {e}")

    except Exception as e:
        logger.error(f"❌ PostgreSQL test setup failed: {e}")


def compare_implementations(logger):
    """Compare key features of both implementations."""
    logger.info("=" * 50)
    logger.info("Implementation Comparison")
    logger.info("=" * 50)

    comparison = {
        "PostgreSQL": {
            "Type": "Client-Server Database",
            "Setup": "Requires PostgreSQL server",
            "Vector Support": "via pgvector extension",
            "JSON Support": "Native JSONB",
            "Scalability": "Excellent for large datasets",
            "Use Cases": "Production, multi-user systems"
        },
        "DuckDB": {
            "Type": "Embedded Database",
            "Setup": "No server required",
            "Vector Support": "via vss extension",
            "JSON Support": "Native JSON",
            "Scalability": "Great for single-user/analytical workloads",
            "Use Cases": "Development, analytics, single-user apps"
        }
    }

    for impl_name, features in comparison.items():
        logger.info(f"\n{impl_name}:")
        for feature, description in features.items():
            logger.info(f"  {feature}: {description}")


def main():
    """Main test function."""
    logger = setup_logging()

    logger.info("🚀 Starting Database Implementation Tests")

    # Test DuckDB implementation
    test_duckdb_implementation(logger)

    # Test PostgreSQL implementation
    test_postgresql_implementation(logger)

    # Compare implementations
    compare_implementations(logger)

    logger.info("\n" + "=" * 50)
    logger.info("All tests completed!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

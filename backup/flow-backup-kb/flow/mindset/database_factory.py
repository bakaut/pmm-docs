"""
Database Factory Module

Provides a factory function to create the appropriate database manager
based on configuration settings. Supports both PostgreSQL and DuckDB backends.

Usage:
    from .database_factory import create_database_manager

    db_manager = create_database_manager(config, logger)
    # Returns either DatabaseManager (PostgreSQL) or DatabaseManagerDuckDB (DuckDB)
"""

import logging
from typing import Optional, Union

from .config import Config


def create_database_manager(config: Config, logger: Optional[logging.Logger] = None) -> Union['DatabaseManager', 'DatabaseManagerDuckDB']:
    """
    Create and return the appropriate database manager based on configuration.

    Args:
        config: Configuration object containing database settings
        logger: Optional logger instance

    Returns:
        DatabaseManager instance (PostgreSQL or DuckDB implementation)

    Raises:
        ValueError: If database type is not supported
        ImportError: If required database driver is not available
    """
    if not logger:
        logger = logging.getLogger(__name__)

    db_type = config.database.type.lower()

    if db_type == 'postgresql':
        try:
            from .database import DatabaseManager
            logger.info("Creating PostgreSQL database manager")
            return DatabaseManager(config, logger)
        except ImportError as e:
            logger.error(f"Failed to import PostgreSQL database manager: {e}")
            logger.error("Make sure psycopg2 is installed: pip install psycopg2")
            raise

    elif db_type == 'duckdb':
        try:
            from .database_duckdb import DatabaseManagerDuckDB
            logger.info("Creating DuckDB database manager")

            # Extract DuckDB path from config
            db_path = getattr(config.database, 'path', None)
            if not db_path:
                db_path = ":memory:"
                logger.warning("No DuckDB path specified, using in-memory database")

            # Create database manager with enhanced error handling
            try:
                return DatabaseManagerDuckDB(config, logger, db_path)
            except Exception as e:
                logger.error(f"Failed to create DuckDB manager: {e}")
                # Try with in-memory fallback for serverless environments
                if db_path != ":memory:":
                    logger.warning("Falling back to in-memory database")
                    return DatabaseManagerDuckDB(config, logger, ":memory:")
                raise

        except ImportError as e:
            logger.error(f"Failed to import DuckDB database manager: {e}")
            logger.error("Make sure duckdb is installed: pip install duckdb")
            raise

    else:
        raise ValueError(f"Unsupported database type: {db_type}. Supported types: postgresql, duckdb")


def get_database_info(config: Config) -> dict:
    """
    Get database configuration information without creating a connection.

    Args:
        config: Configuration object

    Returns:
        Dictionary with database configuration details
    """
    db_config = config.database

    info = {
        "type": db_config.type,
        "connection_params": db_config.connection_params
    }

    if db_config.type == 'postgresql':
        info.update({
            "host": getattr(db_config, 'host', None),
            "port": getattr(db_config, 'port', 5432),
            "database_name": getattr(db_config, 'name', None),
            "user": getattr(db_config, 'user', None),
            "has_url": bool(getattr(db_config, 'url', None))
        })
    elif db_config.type == 'duckdb':
        db_path = getattr(db_config, 'path', ':memory:')
        info.update({
            "database_path": db_path,
            "is_memory": db_path == ":memory:"
        })

    return info


# Compatibility imports - allows importing either implementation directly
try:
    from .database import DatabaseManager as PostgreSQLDatabaseManager
except ImportError:
    PostgreSQLDatabaseManager = None

try:
    from .database_duckdb import DatabaseManagerDuckDB as DuckDBDatabaseManager
except ImportError:
    DuckDBDatabaseManager = None

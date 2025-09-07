#!/usr/bin/env python3
"""
Script to fix database migration issues.
"""

import os
import sys
import psycopg2
from psycopg2 import sql
import logging

def get_db_connection():
    """Get database connection using environment variables."""
    # Try to get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Parse the database URL
        import urllib.parse
        parsed = urllib.parse.urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password
        )
    else:
        # Use individual environment variables
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', 5432),
            database=os.environ.get('DB_NAME', 'poymoymir'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', '')
        )
    
    return conn

def fix_migrations():
    """Fix migration issues in the database."""
    try:
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if the telegraph_pages table has issues
        logger.info("Checking telegraph_pages table...")
        
        # Try to update any NULL values in user_id and chat_id columns
        try:
            cursor.execute(
                "UPDATE telegraph_pages SET user_id = '00000000-0000-0000-0000-000000000000' WHERE user_id IS NULL"
            )
            logger.info("Updated NULL user_id values in telegraph_pages: %s rows affected", cursor.rowcount)
        except Exception as e:
            logger.warning("Could not update user_id in telegraph_pages: %s", e)
        
        try:
            cursor.execute(
                "UPDATE telegraph_pages SET chat_id = 0 WHERE chat_id IS NULL"
            )
            logger.info("Updated NULL chat_id values in telegraph_pages: %s rows affected", cursor.rowcount)
        except Exception as e:
            logger.warning("Could not update chat_id in telegraph_pages: %s", e)
        
        # Commit changes
        conn.commit()
        
        # Check if the payment table exists
        try:
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tg_locked_audio_payments')"
            )
            exists = cursor.fetchone()[0]
            if exists:
                logger.info("Payment table already exists")
            else:
                logger.info("Payment table does not exist yet")
        except Exception as e:
            logger.warning("Could not check payment table existence: %s", e)
            
        # Close connections
        cursor.close()
        conn.close()
        
        logger.info("Migration fix script completed")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = fix_migrations()
    sys.exit(0 if success else 1)
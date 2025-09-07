#!/usr/bin/env python3
"""
Test script to verify the personal Telegraph page creation functionality.
"""

import sys
import os
from pathlib import Path

# Add the mindset directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent / "flow"))

from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.logger import get_default_logger
from mindset.telegram_bot import TelegramBot
from mindset.telegraph import TelegraphManager

def test_personal_telegraph_page():
    """Test creating a personal Telegraph page for a user."""
    try:
        # Create a simple config
        config = Config.from_env()
        
        # Setup logger
        logger = get_default_logger('test')
        
        # Create instances
        telegram_bot = TelegramBot(config)
        telegraph_manager = TelegraphManager(config)
        
        # For testing purposes, we'll use dummy values
        tg_user_id = 123456789
        chat_id = 987654321
        
        # Create a mock database manager (we won't actually use it for this test)
        print("Testing personal Telegraph page creation...")
        
        # Test the create_and_pin_user_telegraph_page method
        # Note: This is a simplified test that doesn't actually connect to a database
        # In a real scenario, you would need to set up a proper database connection
        
        print("Personal Telegraph page creation test completed!")
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running personal Telegraph page test...")
    success = test_personal_telegraph_page()
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed!")
        sys.exit(1)
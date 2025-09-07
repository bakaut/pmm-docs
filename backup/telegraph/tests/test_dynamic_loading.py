#!/usr/bin/env python3
"""
Test script to verify the dynamic loading of telegraph pages.
"""

import os
import sys

def test_dynamic_loading():
    """Test that the telegraph pages are loaded dynamically."""
    
    try:
        # Add the mindset directory to the path so we can import TelegramBot
        mindset_path = os.path.join(os.path.dirname(__file__), '..', 'mindset')
        sys.path.insert(0, mindset_path)
        
        # Import the TelegramBot class
        from telegram_bot import TelegramBot
        
        # Create a mock config class
        class MockConfig:
            def __init__(self):
                self.bot_token = "test_token"
                self.connect_timeout = 10
                self.read_timeout = 30
                self.ai_model = "test_model"
                self.telegraph_api_key = "test_key"
        
        # Create a TelegramBot instance
        config = MockConfig()
        bot = TelegramBot(config)
        
        print("Telegraph pages loaded successfully!")
        print(f"Found {len(bot.telegraph_pages)} telegraph pages:")
        
        for key, filename in bot.telegraph_pages.items():
            print(f"  - {key}: {filename}")
            
        # Check that we have the expected pages
        expected_pages = {"privacy_policy", "discussion_restrictions", "song_creation_journey", "menu"}
        loaded_pages = set(bot.telegraph_pages.keys())
        
        if expected_pages.issubset(loaded_pages):
            print("\n✅ All expected pages are loaded dynamically!")
            return True
        else:
            missing = expected_pages - loaded_pages
            print(f"\n❌ Missing pages: {missing}")
            return False
        
    except Exception as e:
        print(f"Error testing dynamic loading: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dynamic_loading()
    sys.exit(0 if success else 1)
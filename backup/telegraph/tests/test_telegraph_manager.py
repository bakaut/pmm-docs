#!/usr/bin/env python3
"""
Test script to verify the TelegraphManager functionality.
"""

import sys
import os
from pathlib import Path

# Add the mindset directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent / "flow"))

from mindset.config import Config
from mindset.telegraph import TelegraphManager

class SimpleConfig:
    """Simple config class for testing."""
    def __init__(self):
        self.connect_timeout = 5
        self.read_timeout = 30
        self.telegraph_api_key = os.environ.get('TELEGRAPH_API_KEY', '')
        self.telegraph_bot_username = "PoyMoyMirBot"
        self.telegraph_author_name = "PoyMoyMir"

def test_telegraph_manager():
    """Test the TelegraphManager functionality."""
    try:
        # Create a simple config
        config = SimpleConfig()
        
        # Create TelegraphManager
        telegraph_manager = TelegraphManager(config)
        print("TelegraphManager initialized successfully")
        
        # Test content
        test_content = [
            {
                "tag": "h3",
                "children": ["Тестовая страница"]
            },
            {
                "tag": "p",
                "children": ["Это тестовая страница, созданная для проверки функциональности TelegraphManager."]
            }
        ]
        
        # Create a page
        print("Creating test page...")
        page = telegraph_manager.create_page(
            tg_id=123456789,  # Test Telegram user ID
            chat_id=987654321,  # Test chat ID
            title="Тестовая страница ПойМойМир",
            content=test_content
        )
        
        if page:
            print("Page created successfully!")
            print(f"Page URL: {page.get('url', 'N/A')}")
            print(f"Page path: {page.get('path', 'N/A')}")
            return True
        else:
            print("Failed to create page")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running TelegraphManager test...")
    success = test_telegraph_manager()
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed!")
        sys.exit(1)
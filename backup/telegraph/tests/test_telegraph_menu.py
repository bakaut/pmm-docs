#!/usr/bin/env python3
"""
Test script to create a Telegraph page with the menu content.
"""

import sys
import json
from pathlib import Path

# Add the mindset directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent))

import requests
from telegraph import TelegraphManager

# Simple config class to mimic the real config
class SimpleConfig:
    def __init__(self, telegraph_api_key):
        self.telegraph_api_key = telegraph_api_key
        self.telegraph_bot_username = "PoyMoyMirBot"
        self.telegraph_author_name = "PoyMoyMir"
        self.connect_timeout = 1
        self.read_timeout = 5

def test_telegraph_menu():
    """Test creating a page with the menu content."""
    
    try:
        # Create a simple config with the provided API token
        config = SimpleConfig("3e52657449f1054c210291c7a2e5712eff217c8b129d27996a92c6603ad3")
        print("Configuration created successfully")
        
        # Create TelegraphManager
        telegraph_manager = TelegraphManager(config)
        print("TelegraphManager initialized successfully")
        
        # Load the menu content
        menu_file = Path(__file__).parent.parent / "knowledge_bases" / "telegraph" / "menu.json"
        with open(menu_file, 'r', encoding='utf-8') as f:
            menu_content = json.load(f)
        
        print("Loaded menu content")
        
        # Create a page with the menu content
        print("Creating menu page...")
        page = telegraph_manager.create_page(
            tg_id=123456789,  # Test Telegram user ID
            chat_id=987654321,  # Test chat ID
            title="Меню документов",
            content=menu_content
        )
        
        if page:
            print("Menu page created successfully!")
            print(f"Page URL: {page.get('url', 'N/A')}")
            print(f"Page path: {page.get('path', 'N/A')}")
            return True
        else:
            print("Failed to create menu page")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running Telegraph menu test...")
    success = test_telegraph_menu()
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed!")
        sys.exit(1)
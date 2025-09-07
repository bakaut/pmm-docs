#!/usr/bin/env python3
"""
Test script to create a Telegraph page with actual content from our telegraph documents.
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

def test_telegraph_with_song_creation_content():
    """Test creating a page with the song creation journey content."""
    
    try:
        # Create a simple config with the provided API token
        config = SimpleConfig("3e52657449f1054c210291c7a2e5712eff217c8b129d27996a92c6603ad3")
        print("Configuration created successfully")
        
        # Create TelegraphManager
        telegraph_manager = TelegraphManager(config)
        print("TelegraphManager initialized successfully")
        
        # Load the song creation journey content
        song_creation_file = Path(__file__).parent.parent / "knowledge_bases" / "telegraph" / "song_creation_journey.json"
        with open(song_creation_file, 'r', encoding='utf-8') as f:
            song_creation_content = json.load(f)
        
        print("Loaded song creation journey content")
        
        # Create a page with the song creation journey content
        print("Creating song creation journey page...")
        page = telegraph_manager.create_page(
            tg_id=123456789,  # Test Telegram user ID
            chat_id=987654321,  # Test chat ID
            title="Путь создания песни в ПойМойМир",
            content=song_creation_content
        )
        
        if page:
            print("Song creation journey page created successfully!")
            print(f"Page URL: {page.get('url', 'N/A')}")
            print(f"Page path: {page.get('path', 'N/A')}")
        else:
            print("Failed to create song creation journey page")
            return False
            
        # Load the discussion restrictions content
        discussion_restrictions_file = Path(__file__).parent.parent / "knowledge_bases" / "telegraph" / "discussion_restrictions.json"
        with open(discussion_restrictions_file, 'r', encoding='utf-8') as f:
            discussion_restrictions_content = json.load(f)
        
        print("Loaded discussion restrictions content")
        
        # Create a page with the discussion restrictions content
        print("Creating discussion restrictions page...")
        page = telegraph_manager.create_page(
            tg_id=123456789,  # Test Telegram user ID
            chat_id=987654321,  # Test chat ID
            title="Запреты обсуждения",
            content=discussion_restrictions_content
        )
        
        if page:
            print("Discussion restrictions page created successfully!")
            print(f"Page URL: {page.get('url', 'N/A')}")
            print(f"Page path: {page.get('path', 'N/A')}")
            return True
        else:
            print("Failed to create discussion restrictions page")
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running Telegraph test with actual content...")
    success = test_telegraph_with_song_creation_content()
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed!")
        sys.exit(1)
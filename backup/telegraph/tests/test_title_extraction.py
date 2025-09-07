#!/usr/bin/env python3
"""
Test script to verify the title extraction from JSON content.
"""

import os
import sys
import json

def test_title_extraction():
    """Test the _extract_title_from_content method."""
    
    try:
        # Add the mindset directory to the path so we can import TelegramBot
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, script_dir)
        
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
        
        # Test title extraction for each page
        telegraph_dir = os.path.join(script_dir, "..", "knowledge_bases", "telegraph")
        telegraph_dir = os.path.abspath(telegraph_dir)
        
        expected_titles = {
            "privacy_policy": "Политика обработки персональных данных",
            "discussion_restrictions": "Запреты обсуждения",
            "song_creation_journey": "🌟 Путь создания песни в ПойМойМир",
            "menu": "Меню документов"
        }
        
        print("Testing title extraction from JSON content:")
        
        all_passed = True
        for page_key, filename in bot.telegraph_pages.items():
            try:
                file_path = os.path.join(telegraph_dir, filename)
                
                # Load JSON content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                
                # Extract title
                extracted_title = bot._extract_title_from_content(content, page_key)
                
                # Check against expected title
                expected_title = expected_titles.get(page_key, page_key.replace("_", " ").title())
                
                print(f"  {page_key}:")
                print(f"    Extracted: '{extracted_title}'")
                print(f"    Expected:  '{expected_title}'")
                
                if extracted_title == expected_title:
                    print(f"    ✅ PASS")
                else:
                    print(f"    ❌ FAIL")
                    all_passed = False
                    
            except Exception as e:
                print(f"  {page_key}: Error - {e}")
                all_passed = False
        
        if all_passed:
            print("\n✅ All title extractions passed!")
            return True
        else:
            print("\n❌ Some title extractions failed!")
            return False
        
    except Exception as e:
        print(f"Error testing title extraction: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_title_extraction()
    sys.exit(0 if success else 1)
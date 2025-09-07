#!/usr/bin/env python3
"""
Test script for TelegraphManager class demonstrating all formatting tags.
"""

import sys
import os

# Add the mindset module to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'flow'))

from flow.mindset.telegraph import TelegraphManager
from flow.mindset.config import Config

def create_comprehensive_content():
    """Create content with all possible formatting tags."""
    return [
        # Headers
        {"tag": "h3", "children": ["Telegraph Formatting Test"]},
        {"tag": "p", "children": ["This page demonstrates all formatting options supported by Telegraph."]},
        
        # Text formatting
        {"tag": "p", "children": [
            "Text can be ", 
            {"tag": "b", "children": ["bold"]}, 
            ", ", 
            {"tag": "i", "children": ["italic"]}, 
            ", or ", 
            {"tag": "s", "children": ["strikethrough"]}, 
            "."
        ]},
        
        {"tag": "p", "children": [{"tag": "code", "children": ["Inline code example"]}]},
        
        # Blockquote
        {"tag": "blockquote", "children": ["This is a blockquote with ", {"tag": "b", "children": ["bold text"]}, "."]},
        
        # Code block
        {"tag": "pre", "children": [{"tag": "code", "children": ["def example():\n    return 'Hello World'"]}]},
        
        # Lists
        {"tag": "h4", "children": ["Lists"]},
        {"tag": "ul", "children": [
            {"tag": "li", "children": ["Unordered item 1"]},
            {"tag": "li", "children": [{"tag": "b", "children": ["Bold item 2"]}]},
        ]},
        
        {"tag": "ol", "children": [
            {"tag": "li", "children": ["Ordered item 1"]},
            {"tag": "li", "children": ["Ordered item 2"]},
        ]},
        
        # Horizontal rule
        {"tag": "hr"},
        
        # Link
        {"tag": "p", "children": [
            "This is a ", 
            {"tag": "a", "attrs": {"href": "https://telegra.ph"}, "children": ["link to Telegraph"]}, 
            "."
        ]},
        
        # Media (using placeholder URLs)
        {"tag": "h4", "children": ["Media Elements"]},
        {"tag": "figure", "children": [
            {"tag": "img", "attrs": {"src": "https://telegra.ph/images/logo.png"}},
            {"tag": "figcaption", "children": ["Image caption"]}
        ]},
        
        # Final section
        {"tag": "h4", "children": ["Summary"]},
        {"tag": "p", "children": [
            "For more information, see the ",
            {"tag": "a", "attrs": {"href": "https://telegra.ph/api"}, "children": ["Telegraph API documentation"]},
            "."
        ]}
    ]

def main():
    """Main function to test TelegraphManager with all formatting tags."""
    
    # Create a minimal config
    try:
        # Create config using environment variables approach
        config_dict = {
            "bot_token": "dummy_token",
            "database_url": "postgresql://dummy:dummy@localhost/dummy",
            "operouter_key": "dummy_key",
            "suno_api_key": "dummy_suno_key",
            "telegraph_api_key": "3e52657449f1054c210291c7a2e5712eff217c8b129d27996a92c6603ad3",
            "telegraph_bot_username": "test",
            "telegraph_short_name": "test",
            "telegraph_author_name": "sandbox"
        }
        
        config = Config.from_env(config_dict)
        
        # Initialize Telegraph manager
        telegraph = TelegraphManager(config)
        
        # Create content
        content = create_comprehensive_content()
        
        # Create page
        print("Creating Telegraph page with all formatting options...")
        page = telegraph.create_page(
            tg_id=123456789,
            chat_id=987654321,
            title="Telegraph Formatting Test",
            content=content
        )
        
        if page:
            print("✅ Page created successfully!")
            print(f"🔗 URL: https://telegra.ph/{page['path']}")
            print(f"📝 Title: {page['title']}")
            return True
        else:
            print("❌ Failed to create page")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    main()
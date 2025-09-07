#!/usr/bin/env python3
"""
Simple test script to verify the title extraction from JSON content.
"""

import os
import sys
import json

def extract_title_from_content(content, page_key: str) -> str:
    """
    Extract title from JSON content by looking for the first h3 element.
    
    Args:
        content: JSON content as list of nodes
        page_key: Page key for fallback title
        
    Returns:
        Extracted title or fallback title
    """
    try:
        # Look for the first h3 element in the content
        for element in content:
            if isinstance(element, dict) and element.get('tag') == 'h3':
                children = element.get('children', [])
                if children:
                    # Get the first child which should be the title text
                    title_text = children[0] if isinstance(children[0], str) else str(children[0])
                    # Remove any markdown or extra formatting
                    title_text = title_text.strip()
                    if title_text:
                        return title_text
    except Exception as e:
        print(f"Failed to extract title from content for {page_key}: {e}")
    
    # Fallback to default titles or generated title
    titles = {
        "privacy_policy": "Политика обработки персональных данных",
        "discussion_restrictions": "Запреты обсуждения",
        "song_creation_journey": "Путь создания песни в ПойМойМир",
        "menu": "Меню документов"
    }
    return titles.get(page_key, page_key.replace("_", " ").title())

def test_title_extraction():
    """Test the title extraction logic."""
    
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Look for JSON files in the knowledge_bases/telegraph directory
        telegraph_dir = os.path.join(script_dir, "..", "knowledge_bases", "telegraph")
        telegraph_dir = os.path.abspath(telegraph_dir)  # Resolve the relative path
        
        if not os.path.exists(telegraph_dir):
            print(f"Telegraph directory not found: {telegraph_dir}")
            return False
            
        expected_titles = {
            "privacy_policy": "Политика обработки персональных данных",
            "discussion_restrictions": "Запреты обсуждения",
            "song_creation_journey": "🌟 Путь создания песни в ПойМойМир",
            "menu": "Меню документов"
        }
        
        print("Testing title extraction from JSON content:")
        
        all_passed = True
        # Iterate through all JSON files in the directory
        for filename in os.listdir(telegraph_dir):
            if filename.endswith('.json') and not filename.startswith('test_'):
                page_key = filename[:-5]  # Remove .json extension
                file_path = os.path.join(telegraph_dir, filename)
                
                try:
                    # Load JSON content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                    
                    # Extract title
                    extracted_title = extract_title_from_content(content, page_key)
                    
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
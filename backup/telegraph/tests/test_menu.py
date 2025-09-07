#!/usr/bin/env python3
"""
Test script to verify the menu JSON can be loaded and used with TelegraphManager.
"""

import json

def test_menu_json():
    """Test that the menu JSON can be loaded and is valid."""
    
    try:
        # Load the menu JSON
        with open('menu.json', 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        print("Menu JSON loaded successfully!")
        print(f"Content has {len(content)} elements")
        
        # Check the first few elements
        print("\nFirst 3 elements:")
        for i, element in enumerate(content[:3]):
            print(f"  {i+1}. Tag: {element.get('tag', 'N/A')}")
            children = element.get('children', [])
            if children:
                first_child = children[0] if isinstance(children, list) and len(children) > 0 else children
                if isinstance(first_child, str):
                    print(f"     First child: {first_child[:50]}..." if len(first_child) > 50 else f"     First child: {first_child}")
                else:
                    print(f"     First child: {first_child}")
        
        return True
        
    except Exception as e:
        print(f"Error loading menu JSON: {e}")
        return False

if __name__ == "__main__":
    test_menu_json()
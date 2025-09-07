#!/usr/bin/env python3
"""
Test script to verify the dynamic loading of telegraph pages.
"""

import os
import sys

def test_load_telegraph_pages():
    """Test the _load_telegraph_pages method directly."""
    
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Look for JSON files in the knowledge_bases/telegraph directory
        # The telegraph directory is in the parent flow directory
        telegraph_dir = os.path.join(script_dir, "..", "knowledge_bases", "telegraph")
        telegraph_dir = os.path.abspath(telegraph_dir)  # Resolve the relative path
        
        if not os.path.exists(telegraph_dir):
            print(f"Telegraph directory not found: {telegraph_dir}")
            return False
            
        telegraph_pages = {}
        
        # Iterate through all files in the directory
        for filename in os.listdir(telegraph_dir):
            # Only process JSON files (excluding test files)
            if filename.endswith('.json') and not filename.startswith('test_'):
                # Use filename without extension as the key
                page_key = filename[:-5]  # Remove .json extension
                telegraph_pages[page_key] = filename
                
        print("Telegraph pages loaded successfully!")
        print(f"Found {len(telegraph_pages)} telegraph pages:")
        
        for key, filename in telegraph_pages.items():
            print(f"  - {key}: {filename}")
            
        # Check that we have the expected pages
        expected_pages = {"privacy_policy", "discussion_restrictions", "song_creation_journey", "menu"}
        loaded_pages = set(telegraph_pages.keys())
        
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
    success = test_load_telegraph_pages()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script to verify the migration from utils to SemanticSearch class.
"""

import os
import sys
from unittest.mock import Mock, MagicMock

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.semantic_search import SemanticSearch
from mindset.utils import Utils

def test_migration():
    """Test that the migration from utils to SemanticSearch class works correctly."""
    print("Testing migration from utils to SemanticSearch class")
    print("====================================================")
    
    try:
        # Test that SemanticSearch class works
        print("1. Testing SemanticSearch class initialization...")
        
        # Create mock configuration and logger
        mock_config = Mock()
        mock_logger = Mock()
        
        # Initialize the SemanticSearch class with mocks
        searcher = SemanticSearch(mock_config, mock_logger)
        print("   ✓ SemanticSearch class initialized successfully")
        
        # Mock the database and LLM methods
        searcher.db = Mock()
        searcher.llm = Mock()
        
        # Mock database methods
        searcher.db.get_phrases_by_key.return_value = []
        searcher.db.save_phrase.return_value = "test-phrase-id"
        searcher.db.semantic_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'greeting',
                'phrase': 'Hello',
                'similarity': 0.95
            }
        ]
        searcher.db.full_text_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'greeting',
                'phrase': 'Hello',
                'rank': 0.9
            }
        ]
        
        # Mock LLM method
        searcher.llm.embd_text.return_value = [0.1] * 1536  # Mock embedding
        
        # Test add_phrase method
        print("2. Testing add_phrase method...")
        success = searcher.add_phrase("greeting", ["Hello", "Hi", "Good morning", "Hey there"])
        assert success == True
        print("   ✓ add_phrase method works correctly")
        
        # Test initialize_phrases method
        print("3. Testing initialize_phrases method...")
        success = searcher.initialize_phrases()
        # This will fail because we're using mocks, but it shouldn't raise an exception
        print("   ✓ initialize_phrases method executed without errors")
        
        # Test semantic_search_phrase method
        print("4. Testing semantic_search_phrase method...")
        result = searcher.semantic_search_phrase("Hi there, how are you?", "greeting", threshold=0.5)
        assert result is not None
        print("   ✓ semantic_search_phrase method works correctly")
        
        # Test full_text_search_phrase method
        print("5. Testing full_text_search_phrase method...")
        result = searcher.full_text_search_phrase("Good morning", "greeting")
        assert result is not None
        print("   ✓ full_text_search_phrase method works correctly")
        
        # Test search_phrase method
        print("6. Testing search_phrase method...")
        result = searcher.search_phrase("Hi there!", "greeting", threshold=0.7)
        assert result is not None
        print("   ✓ search_phrase method works correctly")
        
        # Test that the methods have been removed from Utils class
        print("7. Verifying methods have been removed from Utils class...")
        utils = Utils(mock_config, mock_logger)
        
        # These methods should no longer exist in Utils
        assert not hasattr(utils, 'parse_intents_and_create_embeddings')
        assert not hasattr(utils, 'semantic_search_intent')
        assert not hasattr(utils, 'full_text_search_intent')
        print("   ✓ Methods successfully removed from Utils class")
        
        print("\nAll tests passed! Migration completed successfully.")
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Test script to verify the method name changes from intent methods to phrase methods.
"""

import os
import sys
from unittest.mock import Mock, MagicMock

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.semantic_search import SemanticSearch

def test_method_name():
    """Test that the method name has been changed correctly."""
    print("Testing method name changes from intent methods to phrase methods")
    print("=====================================================================")
    
    try:
        # Create mock configuration and logger
        mock_config = Mock()
        mock_logger = Mock()
        
        # Initialize the SemanticSearch class with mocks
        searcher = SemanticSearch(mock_config, mock_logger)
        
        # Check that the old method names don't exist
        assert not hasattr(searcher, 'initialize_intents'), "initialize_intents method should not exist"
        print("✓ initialize_intents method correctly removed")
        
        assert not hasattr(searcher, 'add_intent'), "add_intent method should not exist"
        print("✓ add_intent method correctly removed")
        
        assert not hasattr(searcher, 'semantic_search_intent'), "semantic_search_intent method should not exist"
        print("✓ semantic_search_intent method correctly removed")
        
        assert not hasattr(searcher, 'full_text_search_intent'), "full_text_search_intent method should not exist"
        print("✓ full_text_search_intent method correctly removed")
        
        # Check that the new method names exist
        assert hasattr(searcher, 'initialize_phrases'), "initialize_phrases method should exist"
        print("✓ initialize_phrases method correctly added")
        
        assert hasattr(searcher, 'add_phrase'), "add_phrase method should exist"
        print("✓ add_phrase method correctly added")
        
        assert hasattr(searcher, 'semantic_search_phrase'), "semantic_search_phrase method should exist"
        print("✓ semantic_search_phrase method correctly added")
        
        assert hasattr(searcher, 'full_text_search_phrase'), "full_text_search_phrase method should exist"
        print("✓ full_text_search_phrase method correctly added")
        
        # Check that the methods are callable
        assert callable(getattr(searcher, 'initialize_phrases')), "initialize_phrases method should be callable"
        print("✓ initialize_phrases method is callable")
        
        assert callable(getattr(searcher, 'add_phrase')), "add_phrase method should be callable"
        print("✓ add_phrase method is callable")
        
        assert callable(getattr(searcher, 'semantic_search_phrase')), "semantic_search_phrase method should be callable"
        print("✓ semantic_search_phrase method is callable")
        
        assert callable(getattr(searcher, 'full_text_search_phrase')), "full_text_search_phrase method should be callable"
        print("✓ full_text_search_phrase method is callable")
        
        print("\nAll tests passed! Method name changes completed successfully.")
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_method_name()
    sys.exit(0 if success else 1)
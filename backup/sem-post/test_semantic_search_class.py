#!/usr/bin/env python3
"""
Test script for the SemanticSearch class.
"""

import os
import sys
import logging
from unittest.mock import Mock, MagicMock

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.semantic_search import SemanticSearch

def test_semantic_search_class():
    """Test the SemanticSearch class functionality."""
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('test_semantic_search_class')
    
    try:
        # Test initialization
        logger.info("Testing SemanticSearch class initialization")
        
        # Create mock configuration
        mock_config = Mock()
        
        # Create mock logger
        mock_logger = Mock()
        
        # Initialize SemanticSearch with mocks
        searcher = SemanticSearch(mock_config, mock_logger)
        
        # Verify that the components were initialized
        assert searcher.config == mock_config
        assert searcher.logger == mock_logger
        logger.info("SemanticSearch class initialized successfully")
        
        # Test the search_phrase method with mocks
        logger.info("Testing search_phrase method")
        
        # Mock the database and LLM methods
        searcher.db = Mock()
        searcher.llm = Mock()
        
        # Mock semantic search results
        searcher.db.semantic_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'finalize_song',
                'phrase': 'Хочу услышать, как это звучит',
                'similarity': 0.85
            }
        ]
        
        # Mock embedding creation
        searcher.llm.embd_text.return_value = [0.1] * 1536  # Mock embedding
        
        # Test search_phrase with a matching phrase
        result = searcher.search_phrase("Хочу услышать, как это звучит", "finalize_song", threshold=0.7)
        assert result is not None
        assert result['matched'] == True
        assert result['phrase_key'] == 'finalize_song'
        assert result['similarity'] == 0.85
        logger.info("search_phrase method works correctly for matching phrases")
        
        # Test search_phrase with a non-matching phrase (low similarity)
        searcher.db.semantic_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'finalize_song',
                'phrase': 'Хочу услышать, как это звучит',
                'similarity': 0.3  # Below threshold
            }
        ]
        
        # Mock full-text search results
        searcher.db.full_text_search_phrases.return_value = []
        
        result = searcher.search_phrase("Не соответствует", "finalize_song", threshold=0.7)
        assert result is not None
        assert result['matched'] == False
        logger.info("search_phrase method works correctly for non-matching phrases")
        
        logger.info("All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_semantic_search_class()
    sys.exit(0 if success else 1)
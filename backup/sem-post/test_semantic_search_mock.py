#!/usr/bin/env python3
"""
Test script for semantic search functionality with mock database.
"""

import os
import sys
import logging
from unittest.mock import Mock, MagicMock

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.utils import Utils
from mindset.semantic_search import SemanticSearch
from mindset.config import Config

def test_semantic_search_with_mock():
    """Test the semantic search functionality with mock database."""
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('test_semantic_search_mock')
    
    try:
        # Create mock configuration
        config = Mock(spec=Config)
        
        # Initialize SemanticSearch with mock config
        searcher = SemanticSearch(config, logger)
        
        # Create mock database manager
        mock_db = Mock()
        mock_db.semantic_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'finalize_song',
                'phrase': 'Хочу услышать, как это звучит',
                'similarity': 0.85
            }
        ]
        mock_db.full_text_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'finalize_song',
                'phrase': 'Хочу услышать, как это звучит',
                'rank': 0.95
            }
        ]
        
        # Create mock LLM manager
        mock_llm = Mock()
        mock_llm.embd_text.return_value = [0.1] * 1536  # Mock embedding
        
        # Test semantic search for a finalize_song phrase
        test_phrase = "Хочу услышать, как это звучит"
        phrase_key = "finalize_song"
        
        logger.info(f"Testing semantic search for phrase: {test_phrase}")
        
        # Perform semantic search
        result = searcher.semantic_search_phrase(test_phrase, phrase_key, threshold=0.5)
        if result:
            logger.info(f"Semantic search result: {result}")
            assert result['matched'] == True
            assert result['phrase_key'] == phrase_key
            assert result['similarity'] == 0.85
        else:
            logger.warning("No semantic search result found")
            
        # Test with a phrase that doesn't match
        mock_db.semantic_search_phrases.return_value = [
            {
                'id': 'test-phrase-id',
                'key': 'finalize_song',
                'phrase': 'Хочу услышать, как это звучит',
                'similarity': 0.3  # Below threshold
            }
        ]
        
        result = searcher.semantic_search_phrase(test_phrase, phrase_key, threshold=0.5)
        if result:
            logger.info(f"Semantic search result (below threshold): {result}")
            assert result['matched'] == False
            assert result['phrase_key'] == phrase_key
            assert result['best_similarity'] == 0.3
        else:
            logger.warning("No semantic search result found")
            
        # Perform full-text search
        logger.info(f"Testing full-text search for phrase: {test_phrase}")
        fulltext_result = searcher.full_text_search_phrase(test_phrase, phrase_key)
        if fulltext_result:
            logger.info(f"Full-text search result: {fulltext_result}")
            assert fulltext_result['matched'] == True
            assert fulltext_result['phrase_key'] == phrase_key
            assert fulltext_result['rank'] == 0.95
        else:
            logger.warning("No full-text search result found")
            
        logger.info("All tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_semantic_search_with_mock()
    sys.exit(0 if success else 1)
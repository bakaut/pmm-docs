#!/usr/bin/env python3
"""
Test script for semantic search functionality.
"""

import os
import sys
import logging

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.llm_manager import LLMManager
from mindset.utils import Utils
from mindset.semantic_search import SemanticSearch
from mindset.logger import get_default_logger

def test_semantic_search():
    """Test the semantic search functionality."""
    # Setup logging
    logger = get_default_logger('test_semantic_search')
    logger.setLevel(logging.DEBUG)
    
    try:
        # Load configuration
        config = Config.from_env()
        logger.info("Configuration loaded successfully")
        
        # Initialize components
        utils = Utils(config, logger)
        db = DatabaseManager(config, logger)
        llm = LLMManager(config, utils, logger)
        searcher = SemanticSearch(config, logger)
        
        # Test semantic search for a finalize_song phrase
        test_phrase = "Хочу услышать, как это звучит"
        phrase_key = "finalize_song"
        
        logger.info(f"Testing semantic search for phrase: {test_phrase}")
        
        # Perform semantic search
        result = searcher.semantic_search_phrase(test_phrase, phrase_key, threshold=0.5)
        if result:
            logger.info(f"Semantic search result: {result}")
        else:
            logger.warning("No semantic search result found")
            
        # Perform full-text search
        logger.info(f"Testing full-text search for phrase: {test_phrase}")
        fulltext_result = searcher.full_text_search_phrase(test_phrase, phrase_key)
        if fulltext_result:
            logger.info(f"Full-text search result: {fulltext_result}")
        else:
            logger.warning("No full-text search result found")
            
        # Test with a different phrase
        test_phrase2 = "Спой это как песню"
        logger.info(f"Testing with phrase: {test_phrase2}")
        
        result2 = searcher.semantic_search_phrase(test_phrase2, phrase_key, threshold=0.5)
        if result2:
            logger.info(f"Semantic search result: {result2}")
        else:
            logger.warning("No semantic search result found")
            
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_semantic_search()
    sys.exit(0 if success else 1)
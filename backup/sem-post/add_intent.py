#!/usr/bin/env python3
"""
Script to add a new phrase to the phrases table.
"""

import os
import sys

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.semantic_search import SemanticSearch

def add_phrase(phrase_key, phrases):
    """Add a new phrase with its variations to the database.
    
    Args:
        phrase_key (str): The key for the phrase (e.g., 'greeting', 'farewell')
        phrases (list): List of phrase variations for this key
    """
    try:
        # Initialize semantic search
        searcher = SemanticSearch()
        
        # Add the phrase
        return searcher.add_phrase(phrase_key, phrases)
        
    except Exception as e:
        print(f"Error adding phrase: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 add_phrase.py <phrase_key> <phrase1> [phrase2] [phrase3] ...")
        print("Example: python3 add_phrase.py greeting 'Hello' 'Hi there' 'Good morning'")
        sys.exit(1)
        
    phrase_key = sys.argv[1]
    phrases = sys.argv[2:]
    
    success = add_phrase(phrase_key, phrases)
    sys.exit(0 if success else 1)
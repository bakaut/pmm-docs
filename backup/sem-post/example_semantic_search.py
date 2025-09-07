#!/usr/bin/env python3
"""
Example script demonstrating how to use the SemanticSearch class.
"""

import os
import sys

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.semantic_search import SemanticSearch

def main():
    """Example usage of the SemanticSearch class."""
    print("SemanticSearch Example")
    print("=====================")
    
    try:
        # Initialize the SemanticSearch class
        print("Initializing SemanticSearch...")
        searcher = SemanticSearch()
        print("SemanticSearch initialized successfully!")
        
        # Add a new phrase
        print("\nAdding a new phrase...")
        success = searcher.add_phrase("greeting", ["Hello", "Hi", "Good morning", "Hey there"])
        if success:
            print("Phrase 'greeting' added successfully!")
        else:
            print("Failed to add phrase 'greeting'")
            
        # Perform a semantic search
        print("\nPerforming semantic search...")
        result = searcher.search_phrase("Hi there, how are you?", "greeting", threshold=0.5)
        if result:
            if result.get('matched'):
                print(f"Match found! Similarity: {result.get('similarity', 'N/A')}")
                print(f"Matched phrase: {result.get('matched_phrase')}")
            else:
                print(f"No match found. Best similarity: {result.get('best_similarity', 'N/A')}")
        else:
            print("Search failed")
            
        # Perform a full-text search
        print("\nPerforming full-text search...")
        result = searcher.full_text_search_phrase("Good morning", "greeting")
        if result:
            if result.get('matched'):
                print(f"Match found! Rank: {result.get('rank', 'N/A')}")
                print(f"Matched phrase: {result.get('matched_phrase')}")
            else:
                print("No match found")
        else:
            print("Search failed")
            
        print("\nExample completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Semantic Search module for intent detection and phrase matching.

This module provides a unified interface for semantic search functionality,
including initializing phrases from JSON files, adding new phrases, and
performing semantic and full-text searches.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

# Add the mindset directory to the path so we can import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mindset.config import Config
from mindset.database import DatabaseManager
from mindset.llm_manager import LLMManager
from mindset.utils import Utils
from mindset.logger import get_default_logger


class SemanticSearch:
    """A unified class for semantic search functionality."""

    def __init__(self, config: Config = None, logger: logging.Logger = None):
        """
        Initialize the SemanticSearch class.

        Args:
            config: Configuration object. If None, will be loaded from environment.
            logger: Logger instance. If None, a default logger will be created.
        """
        self.logger = logger or get_default_logger('semantic_search')
        self.logger.setLevel(logging.DEBUG)

        try:
            if config is None:
                self.config = Config.from_env()
            else:
                self.config = config

            self.logger.info("Configuration loaded successfully")

            # Initialize components
            self.utils = Utils(self.config, self.logger)
            self.db = DatabaseManager(self.config, self.logger)
            self.llm = LLMManager(self.config, self.utils, self.logger)

        except Exception as e:
            self.logger.error(f"Error initializing SemanticSearch: {e}")
            raise

    def add_phrase(self, phrase_key: str, phrases: List[str], processed: bool = False, force_processed: bool = False) -> bool:
        """
        Add a new phrase with its variations to the database.

        Args:
            phrase_key (str): The key for the phrase (e.g., 'greeting', 'farewell')
            phrases (list): List of phrase variations for this key
            processed (bool): Whether the phrases should be marked as processed
            force_processed (bool): Whether the phrases should be marked as force processed

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"Adding phrase '{phrase_key}' with {len(phrases)} variations")

            # Add each phrase
            added_count = 0
            for phrase in phrases:
                self.logger.info(f"Adding phrase: {phrase}")

                # Check if phrase already exists (regardless of processed status)
                existing_phrases = self.db.get_phrases_by_key(phrase_key, include_processed=True)
                phrase_exists = any(p['phrase'] == phrase for p in existing_phrases)

                if not phrase_exists:
                    # Create embedding for the phrase
                    embedding = self.llm.embd_text(phrase)
                    if embedding:
                        # Save phrase and embedding to database
                        phrase_id = self.db.save_phrase(phrase_key, phrase, embedding, processed, force_processed)
                        self.logger.info(f"Saved phrase '{phrase}' with ID: {phrase_id}")
                        added_count += 1
                    else:
                        self.logger.warning(f"Failed to create embedding for phrase: {phrase}")
                else:
                    # If phrase exists but is not processed and we want to mark it as processed, update it
                    existing_phrase = next((p for p in existing_phrases if p['phrase'] == phrase), None)
                    if existing_phrase and not existing_phrase['processed'] and processed:
                        if self.db.update_phrase_processed_status(existing_phrase['id'], processed):
                            self.logger.info(f"Updated phrase '{phrase}' to processed")
                        else:
                            self.logger.warning(f"Failed to update phrase '{phrase}' to processed")
                    else:
                        self.logger.debug(f"Phrase already exists in database: {phrase}")

            self.logger.info(f"Successfully added {added_count} new phrases for key '{phrase_key}'")
            return True

        except Exception as e:
            self.logger.error(f"Error adding phrase: {e}")
            return False

    def initialize_phrases(self, phrases_dir: str = None, mark_as_processed: bool = True) -> bool:
        """
        Initialize the phrases table with embeddings from phrase JSON files.

        Args:
            phrases_dir (str): Path to the directory containing phrase JSON files.
                              If None, uses the default path.
            mark_as_processed (bool): Whether to mark the phrases as processed during initialization

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Define the phrases directory
            if phrases_dir is None:
                phrases_dir = os.path.join(os.path.dirname(__file__), '..', 'knowledge_bases', 'templates', 'common', 'phrases')
                phrases_dir = os.path.abspath(phrases_dir)

            self.logger.info(f"Looking for phrases in: {phrases_dir}")

            if not os.path.exists(phrases_dir):
                self.logger.error(f"Phrases directory not found: {phrases_dir}")
                return False

            # Process each JSON file in the phrases directory
            processed_files = 0
            for filename in os.listdir(phrases_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(phrases_dir, filename)
                    phrase_key = filename.replace('.json', '')

                    self.logger.info(f"Processing phrase file: {filename} with key: {phrase_key}")

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            phrases = json.load(f)

                        # Process each phrase in the JSON array
                        for i, phrase_obj in enumerate(phrases):
                            for key, phrase in phrase_obj.items():
                                # Use the key from the JSON object if it exists, otherwise use the filename-based key
                                actual_key = key if key else phrase_key

                                self.logger.debug(f"Processing phrase {i+1}: {phrase} with key: {actual_key}")

                                # Check if phrase already exists (regardless of processed status)
                                existing_phrases = self.db.get_phrases_by_key(actual_key, include_processed=False)
                                phrase_exists = any(p['phrase'] == phrase for p in existing_phrases)

                                if not phrase_exists:
                                    # Create embedding for the phrase
                                    embedding = self.llm.embd_text(phrase)
                                    if embedding:
                                        # Save phrase and embedding to database
                                        phrase_id = self.db.save_phrase(actual_key, phrase, embedding, mark_as_processed, False)
                                        self.logger.info(f"Saved phrase '{phrase}' with ID: {phrase_id}")
                                    else:
                                        self.logger.warning(f"Failed to create embedding for phrase: {phrase}")
                                else:
                                    # If phrase exists but is not processed and we want to mark it as processed, update it
                                    existing_phrase = next((p for p in existing_phrases if p['phrase'] == phrase), None)
                                    if existing_phrase and not existing_phrase['processed'] and mark_as_processed:
                                        if self.db.update_phrase_processed_status(existing_phrase['id'], mark_as_processed):
                                            self.logger.info(f"Updated phrase '{phrase}' to processed")
                                        else:
                                            self.logger.warning(f"Failed to update phrase '{phrase}' to processed")
                                    else:
                                        self.logger.debug(f"Phrase already exists in database: {phrase}")

                        processed_files += 1
                    except Exception as e:
                        self.logger.error(f"Error processing phrase file {filename}: {e}")
                        continue

            self.logger.info(f"Phrase initialization completed successfully. Processed {processed_files} files")
            return True

        except Exception as e:
            self.logger.error(f"Error during phrase initialization: {e}")
            return False

    def get_unprocessed_phrases(self) -> List[Dict[str, Any]]:
        """
        Get all unprocessed phrases from the database.

        Returns:
            List of unprocessed phrases
        """
        return self.db.get_unprocessed_phrases()

    def mark_phrase_as_processed(self, phrase_id: str) -> bool:
        """
        Mark a phrase as processed.

        Args:
            phrase_id: The ID of the phrase to mark as processed

        Returns:
            True if successful, False otherwise
        """
        return self.db.update_phrase_processed_status(phrase_id, True)

    def semantic_search_phrase(self, user_text: str, phrase_key: str, threshold: float = 0.7, include_processed: bool = True) -> Optional[Dict[str, Any]]:
        """
        Perform semantic search to determine if user text matches a phrase.

        Args:
            user_text: The user's input text
            phrase_key: The phrase key to match against (e.g., 'finalize_song')
            threshold: Similarity threshold for matching
            include_processed: If False, only search unprocessed phrases

        Returns:
            Dict with match information or None if no match
        """
        try:
            # Create embedding for user text
            user_embedding = self.llm.embd_text(user_text)
            if not user_embedding:
                return None

            # Perform semantic search
            results = self.db.semantic_search_phrases(user_embedding, phrase_key, limit=50, include_processed=include_processed)

            # Check if any results exceed threshold
            if results and results[0]['similarity'] >= threshold:
                return {
                    'matched': True,
                    'phrase_key': phrase_key,
                    'matched_phrase': results[0]['phrase'],
                    'similarity': results[0]['similarity'],
                    'phrase_id': results[0]['id']
                }

            return {
                'matched': False,
                'phrase_key': phrase_key,
                'best_similarity': results[0]['similarity'] if results else 0
            }
        except Exception as e:
            self.logger.error(f"Error in semantic search for phrase {phrase_key}: {e}")
            return None

    def full_text_search_phrase(self, user_text: str, phrase_key: str, include_processed: bool = True) -> Optional[Dict[str, Any]]:
        """
        Perform full-text search to determine if user text matches a phrase.

        Args:
            user_text: The user's input text
            phrase_key: The phrase key to match against
            include_processed: If False, only search unprocessed phrases

        Returns:
            Dict with match information or None if no match
        """
        try:
            # Perform full-text search
            results = self.db.full_text_search_phrases(user_text, phrase_key, limit=1, include_processed=include_processed)

            if results:
                return {
                    'matched': True,
                    'phrase_key': phrase_key,
                    'matched_phrase': results[0]['phrase'],
                    'rank': results[0]['rank'],
                    'phrase_id': results[0]['id']
                }

            return {
                'matched': False,
                'phrase_key': phrase_key
            }
        except Exception as e:
            self.logger.error(f"Error in full-text search for phrase {phrase_key}: {e}")
            return None

    def search_phrase(self, user_text: str, phrase_key: str, threshold: float = 0.7, include_processed: bool = True) -> Optional[Dict[str, Any]]:
        """
        Perform both semantic and full-text search to determine if user text matches a phrase.

        Args:
            user_text: The user's input text
            phrase_key: The phrase key to match against
            threshold: Similarity threshold for semantic matching
            include_processed: If False, only search unprocessed phrases

        Returns:
            Dict with match information or None if no match
        """
        # Try semantic search first
        semantic_result = self.semantic_search_phrase(user_text, phrase_key, threshold, include_processed)
        if semantic_result and semantic_result.get('matched'):
            return semantic_result

        # Fallback to full-text search
        fulltext_result = self.full_text_search_phrase(user_text, phrase_key, include_processed)
        if fulltext_result and fulltext_result.get('matched'):
            return fulltext_result

        # Return the best result (semantic result if it exists, otherwise fulltext)
        return semantic_result or fulltext_result

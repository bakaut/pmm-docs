# Semantic Search for Phrase Detection

This document explains how to use the semantic search functionality for phrase detection in the PoyMoyMir bot.

## Overview

The semantic search system allows the bot to match user input against predefined phrases using both:
1. **Semantic similarity** - Using embeddings and cosine similarity
2. **Full-text search** - Using PostgreSQL's full-text search capabilities

## Components

### 1. Database Schema

A new `phrases` table is created with the following structure:

```sql
CREATE TABLE phrases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    key text NOT NULL,
    phrase text NOT NULL,
    phrase_embd vector(1536),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
```

### 2. Database Methods

The `DatabaseManager` class includes new methods for working with phrases:

- `save_phrase(key, phrase, phrase_embd)` - Save a phrase and its embedding
- `get_phrase_by_id(phrase_id)` - Retrieve a phrase by ID
- `get_phrases_by_key(key)` - Retrieve all phrases for a specific key
- `semantic_search_phrases(query_embd, key, limit)` - Search using cosine similarity
- `full_text_search_phrases(query_text, key, limit)` - Search using full-text search

### 3. SemanticSearch Class

A unified `SemanticSearch` class provides all functionality for semantic search:

- `add_phrase(phrase_key, phrases)` - Add a new phrase with its variations
- `initialize_phrases(phrases_dir)` - Initialize phrases from JSON files
- `semantic_search_phrase(user_text, phrase_key, threshold)` - Perform semantic search
- `full_text_search_phrase(user_text, phrase_key)` - Perform full-text search
- `search_phrase(user_text, phrase_key, threshold)` - Perform both searches (semantic first, then fallback to full-text)

### 4. Deprecated Methods

The following methods have been removed from the `Utils` class and moved to the `SemanticSearch` class:
- `parse_intents_and_create_embeddings()`
- `semantic_search_intent()`
- `full_text_search_intent()`

## Usage

### 1. Initialize Phrases

Run the SemanticSearch class directly:

```bash
cd flow && python3 mindset/semantic_search.py init
```

This script will:
- Read all JSON files from `knowledge_bases/templates/common/phrases/`
- Create embeddings for each phrase using the LLM
- Save phrases and embeddings to the database

### 2. Add New Phrases

Add new phrases using the SemanticSearch class directly:

```bash
cd flow && python3 mindset/semantic_search.py add greeting "Hello" "Hi there" "Good morning"
```

### 3. Semantic Search in Message Processing

In the main message processing flow (`index.py`), semantic search is performed:

```python
from mindset.semantic_search import SemanticSearch

# Initialize semantic search
searcher = SemanticSearch(config, logger)

# Perform both semantic and full-text search
phrase_match = searcher.search_phrase(text, phrase_key, threshold=0.7)
```

## Phrase JSON Format

Phrase files should be stored in `knowledge_bases/templates/common/phrases/` with the following format:

```json
[
  {
    "finalize_song": "Хочу услышать, как это звучит"
  },
  {
    "finalize_song": "А можешь спеть это?"
  }
]
```

Each file represents a single phrase type, with the filename (without .json) used as the phrase key.

## Search Process

1. **Semantic Search**:
   - User text is converted to an embedding
   - Cosine similarity is calculated against stored phrase embeddings
   - Results above the threshold are considered matches

2. **Full-text Search** (fallback):
   - Uses PostgreSQL's full-text search capabilities
   - Provides a backup when semantic search doesn't find a match

## Configuration

The semantic search can be configured through the following parameters:

- `threshold` - Similarity threshold for matching (default: 0.7)
- `limit` - Number of results to return (default: 5)

## Testing

Test the SemanticSearch class:

```bash
cd flow && python3 mindset/test_semantic_search_class.py
```

Or test the migration:

```bash
cd flow && python3 mindset/test_migration.py
```

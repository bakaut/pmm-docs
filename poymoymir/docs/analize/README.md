# Mindset Module

The mindset module contains the core logic for the PoyMoyMir bot.

## Components

- [config.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/config.py) - Configuration management
- [database.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/database.py) - Database operations
- [llm_manager.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/llm_manager.py) - LLM API management
- [telegram_bot.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/telegram_bot.py) - Telegram bot functionality
- [suno_manager.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/suno_manager.py) - Suno API integration
- [moderation.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/moderation.py) - Content moderation
- [semantic_search.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/semantic_search.py) - Semantic search functionality
- [payment_handler.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/payment_handler.py) - Payment processing
- [refund_processor.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/refund_processor.py) - Refund handling
- [utils.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/utils.py) - Utility functions
- [logger.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/logger.py) - Logging configuration
- [analyze.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/analyze.py) - Message analysis for song creation processes (new)

## New Module: analyze.py

The [analyze.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/analyze.py) module provides functionality to identify song creation processes from user messages and group them into JSON objects for further processing. It uses LLM-based classification to detect the start and end of song creation workflows.

### Features

- Reads messages by user UUID from the database
- Uses LLM classification to identify intents in messages
- Detects start and end of song creation processes
- Groups messages into JSON objects with approximately 50 messages each
- Provides metadata for each group including timestamps and process information

### Usage

See [docs/analyze.md](file:///Users/nlebedev@tempo.io/pers/poymoymir/docs/analyze.md) for detailed documentation.

## Example Usage

```python
from mindset.analyze import MessageAnalyzer
from mindset.database import DatabaseManager
from mindset.llm_manager import LLMManager

# Initialize components
db = DatabaseManager(config, logger)
llm = LLMManager(config, utils, logger)
analyzer = MessageAnalyzer(db, llm, logger)

# Group messages into JSONs
user_uuid = "example-user-uuid"
json_groups = analyzer.group_messages_into_jsons(user_uuid, messages_per_json=50)
```
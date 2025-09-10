# Message Analysis Module

## Overview

The `analyze.py` module provides functionality to identify song creation processes from user messages and group them into JSON objects for further processing. It uses LLM-based classification to detect the start and end of song creation workflows.

## Classes

### MessageAnalyzer

Main class for analyzing user messages and identifying song creation processes.

#### Constructor

```python
MessageAnalyzer(db, llm, logger=None)
```

Parameters:
- `db`: DatabaseManager instance for accessing messages
- `llm`: LLMManager instance for classification
- `logger`: Optional logger instance

#### Methods

##### `read_messages_by_user_uuid(user_uuid)`

Reads all messages for a specific user, ordered by creation time.

Parameters:
- `user_uuid`: The UUID of the user

Returns:
- List of messages sorted by creation time

##### `group_messages_into_jsons(user_uuid, messages_per_json=50)`

Reads messages by user UUID and creates JSONs grouped by song creation processes.
Each JSON contains approximately 50 messages from one song creation process.

Parameters:
- `user_uuid`: The UUID of the user
- `messages_per_json`: Target number of messages per JSON (default 50)

Returns:
- List of JSON objects containing grouped messages

## Usage Example

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

## Implementation Details

The MessageAnalyzer works by:

1. Reading all messages for a user from the database
2. Using LLM classification to identify intents in each message
3. Detecting the start of song creation processes (intents: "create_song", "continue_song")
4. Detecting the end of song creation processes (intents: "finalize_song", "song_received", "feedback")
5. Grouping messages between start and end markers into processes
6. Splitting each process into chunks of approximately 50 messages
7. Creating JSON objects for each chunk with metadata

## Dependencies

- `database.py`: For accessing message data
- `llm_manager.py`: For message classification
- Standard Python libraries: json, logging, uuid, datetime, typing
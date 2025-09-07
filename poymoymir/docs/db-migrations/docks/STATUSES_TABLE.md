# Statuses Table Documentation

## Overview

The `statuses` table is designed to store intent and state information for user messages in the system. This separates the status tracking from the main messages table, providing a cleaner data structure and better query performance for status-related operations.

## Table Schema

| Column Name     | Data Type | Constraints           | Description                                  |
|-----------------|-----------|-----------------------|----------------------------------------------|
| id              | VARCHAR   | PRIMARY KEY           | Unique identifier (UUID)                     |
| session_id      | VARCHAR   | NOT NULL, FK          | Foreign key to conversation_sessions table   |
| user_id         | VARCHAR   | NOT NULL, FK          | Foreign key to users table                   |
| message_id      | VARCHAR   | NOT NULL, FK          | Foreign key to messages table                |
| state           | TEXT      | NULLABLE              | Detected state from LLM analysis             |
| state_reason    | TEXT      | NULLABLE              | Reason for the detected state                |
| intent          | TEXT      | NULLABLE              | Detected intent from LLM analysis            |
| intent_reason   | TEXT      | NULLABLE              | Reason for the detected intent               |
| created_at      | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Timestamp when the record was created  |

## Foreign Key Constraints

The table includes the following foreign key constraints:
- `session_id` references `conversation_sessions.id` with CASCADE delete
- `user_id` references `users.id` with CASCADE delete
- `message_id` references `messages.id` with CASCADE delete

## Indexes

The following indexes are created to optimize query performance:

1. `idx_statuses_session_id` - For queries filtering by session
2. `idx_statuses_user_id` - For queries filtering by user
3. `idx_statuses_message_id` - For queries filtering by message
4. `idx_statuses_created_at` - For time-based queries

## Usage

### Saving Status Information

The system automatically saves intent and state information to this table when processing user messages. The information is extracted from the LLM analysis and stored with references to the related session, user, and message.

### Querying Status Information

You can query status information using any of the indexed columns:

```sql
-- Get all statuses for a session
SELECT * FROM statuses WHERE session_id = 'session-uuid' ORDER BY created_at DESC;

-- Get status for a specific message
SELECT * FROM statuses WHERE message_id = 'message-uuid' ORDER BY created_at DESC LIMIT 1;

-- Get recent statuses for a user
SELECT * FROM statuses WHERE user_id = 'user-uuid' ORDER BY created_at DESC LIMIT 10;
```

## Migration

To add this table to an existing database, run the migration script:

```bash
python flow/mindset/migrate_statuses_table.py
```

This script will:
1. Create the `statuses` table if it doesn't exist
2. Create the necessary indexes for optimal performance
3. Establish foreign key relationships with related tables

## Integration with Existing Code

The `DatabaseManager` class has been extended with new methods to work with the statuses table:

- `save_status()` - Save intent and state information
- `get_status_by_message_id()` - Retrieve status by message ID
- `get_statuses_by_session()` - Retrieve statuses for a session

These methods are automatically used in the main message processing flow in `index.py`.

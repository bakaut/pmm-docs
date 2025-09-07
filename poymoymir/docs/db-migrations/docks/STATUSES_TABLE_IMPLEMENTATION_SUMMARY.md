# Statuses Table Implementation Summary

## Overview

This document summarizes the implementation of the new `statuses` table for storing intent and state information separately from the main messages table. This change improves data organization and query performance for status-related operations.

## Changes Made

### 1. Database Schema Changes

**New Table: `statuses`**

| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR (Primary Key) | Unique identifier (UUID) |
| session_id | VARCHAR (NOT NULL, FK) | Reference to conversation_sessions table |
| user_id | VARCHAR (NOT NULL, FK) | Reference to users table |
| message_id | VARCHAR (NOT NULL, FK) | Reference to messages table |
| state | TEXT (Nullable) | Detected state from LLM analysis |
| state_reason | TEXT (Nullable) | Reason for the detected state |
| intent | TEXT (Nullable) | Detected intent from LLM analysis |
| intent_reason | TEXT (Nullable) | Reason for the detected intent |
| created_at | TIMESTAMP | Timestamp when record was created |

### 2. Foreign Key Constraints

- `session_id` references `conversation_sessions.id` with CASCADE delete
- `user_id` references `users.id` with CASCADE delete
- `message_id` references `messages.id` with CASCADE delete

### 3. Indexes Created

- `idx_statuses_session_id` - For session-based queries
- `idx_statuses_user_id` - For user-based queries
- `idx_statuses_message_id` - For message-based queries
- `idx_statuses_created_at` - For time-based queries

### 4. Code Changes

#### Database Layer (Both PostgreSQL and DuckDB)

Added new methods to `DatabaseManager` classes:
- `save_status()` - Save intent and state information
- `get_status_by_message_id()` - Retrieve status by message ID
- `get_statuses_by_session()` - Retrieve statuses for a session

#### Business Logic Layer

Modified `flow/index.py` to save intent and state information to the new table after LLM analysis.

#### Migration Infrastructure

Created migration files and scripts:
- SQL migration file: `flow/mindset/migrations/001_create_statuses_table.sql`
- Python migration script: `flow/mindset/migrate_statuses_table.py`
- Manual SQL script: `docs/database/statuses_table.sql`

### 5. Documentation

Created documentation files:
- `docs/database/STATUSES_TABLE.md` - Detailed documentation
- `docs/database/STATUSES_TABLE_IMPLEMENTATION_SUMMARY.md` - This summary

## Usage

### Automatic Usage

The system automatically saves intent and state information to the new table during normal message processing. No additional configuration is required.

### Manual Migration

To manually create the table in an existing database, you can either:

1. Run the Python migration script:
   ```bash
   python flow/mindset/migrate_statuses_table.py
   ```

2. Execute the SQL script directly in your database:
   ```sql
   CREATE TABLE IF NOT EXISTS statuses (
       id VARCHAR PRIMARY KEY,
       session_id VARCHAR NOT NULL,
       user_id VARCHAR NOT NULL,
       message_id VARCHAR NOT NULL,
       state TEXT,
       state_reason TEXT,
       intent TEXT,
       intent_reason TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

       -- Foreign key constraints
       CONSTRAINT fk_statuses_session_id
           FOREIGN KEY (session_id)
           REFERENCES conversation_sessions(id)
           ON DELETE CASCADE,
       CONSTRAINT fk_statuses_user_id
           FOREIGN KEY (user_id)
           REFERENCES users(id)
           ON DELETE CASCADE,
       CONSTRAINT fk_statuses_message_id
           FOREIGN KEY (message_id)
           REFERENCES messages(id)
           ON DELETE CASCADE
   );
   ```

## Benefits

1. **Separation of Concerns**: Status information is now stored separately from message content
2. **Improved Performance**: Dedicated indexes for status queries
3. **Data Integrity**: Foreign key constraints ensure referential integrity
4. **Better Data Organization**: Cleaner schema structure
5. **Extensibility**: Easy to add more status-related fields in the future
6. **Backward Compatibility**: Existing functionality remains unchanged

## Testing

A test script (`flow/mindset/test_migration.py`) has been created to verify the migration SQL is valid.

## Future Considerations

1. Add data retention policies for the statuses table
2. Consider partitioning for large-scale deployments
3. Add additional indexes based on query patterns
4. Implement data archiving for historical analysis

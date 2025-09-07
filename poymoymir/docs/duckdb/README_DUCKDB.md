# DuckDB Database Implementation

This directory contains a DuckDB implementation of the database layer that provides the same interface as the original PostgreSQL implementation. DuckDB is an in-process analytical database management system that's perfect for development, testing, and single-user applications.

## 🚀 Features

### Core Capabilities
- **Same Interface**: Drop-in replacement for the PostgreSQL `DatabaseManager`
- **Embedded Database**: No server setup required
- **Vector Support**: Embeddings storage via DuckDB's `vss` extension
- **JSON Support**: Native JSON handling for message analysis
- **High Performance**: Optimized for analytical workloads
- **ACID Transactions**: Full transaction support with rollback

### DuckDB Advantages
- **Zero Configuration**: Works out of the box
- **Fast Development**: No database server setup
- **Excellent Analytics**: Built for analytical queries
- **Small Footprint**: Single file or in-memory storage
- **SQL Compatibility**: Familiar PostgreSQL-like syntax

## 📦 Installation

### Requirements
```bash
pip install duckdb>=0.9.0
```

### Optional Extensions
For vector embeddings support:
```bash
# DuckDB will automatically install vss extension when needed
# No manual installation required
```

## 🔧 Configuration

### Environment Variables

Choose your database type in your `.env` file:

```bash
# For DuckDB (file-based)
DATABASE__TYPE=duckdb
DATABASE__PATH=/path/to/your/database.duckdb

# For DuckDB (in-memory) - great for testing
DATABASE__TYPE=duckdb
DATABASE__PATH=:memory:

# For PostgreSQL (original)
DATABASE__TYPE=postgresql
DATABASE__URL=postgresql://user:pass@host:port/dbname
```

### Configuration Examples

See the example configuration files:
- [`.env.duckdb.example`](.env.duckdb.example) - DuckDB configuration
- [`.env.postgresql.example`](.env.postgresql.example) - PostgreSQL configuration

## 🏗️ Usage

### Basic Usage

```python
from mindset.database_factory import create_database_manager
from mindset.config import Config

# Load configuration
config = Config()

# Create database manager (automatically chooses implementation)
db_manager = create_database_manager(config, logger)

# Use the same interface as PostgreSQL version
user_id = db_manager.get_or_create_user(12345, "John Doe")
session_id = db_manager.get_active_session(user_id, bot_id, 3600)
```

### Direct Import

```python
# Direct import for DuckDB
from mindset.database_duckdb import DatabaseManagerDuckDB

db_manager = DatabaseManagerDuckDB(config, logger, "/path/to/db.duckdb")

# Direct import for PostgreSQL
from mindset.database import DatabaseManager

db_manager = DatabaseManager(config, logger)
```

### Factory Pattern (Recommended)

```python
from mindset.database_factory import create_database_manager, get_database_info

# Get database info without connecting
db_info = get_database_info(config)
print(f"Using {db_info['type']} database")

# Create appropriate manager
db_manager = create_database_manager(config, logger)
```

## 🔄 Migration from PostgreSQL

### 1. Update Configuration
Change your database configuration:
```bash
# From PostgreSQL
DATABASE__TYPE=postgresql
DATABASE__URL=postgresql://...

# To DuckDB
DATABASE__TYPE=duckdb
DATABASE__PATH=/path/to/database.duckdb
```

### 2. Update Dependencies
Add DuckDB to your requirements:
```bash
pip install duckdb>=0.9.0
```

### 3. Code Changes
**No code changes required!** The interface is identical:

```python
# This works with both implementations
db_manager = create_database_manager(config, logger)
user_id = db_manager.get_or_create_user(chat_id, full_name)
```

## 🏎️ Performance Comparison

| Feature | PostgreSQL | DuckDB |
|---------|------------|---------|
| **Setup Time** | Minutes (server setup) | Seconds (no setup) |
| **Single User Performance** | Good | Excellent |
| **Multi User Performance** | Excellent | Limited |
| **Analytics Queries** | Good | Excellent |
| **Vector Operations** | Good (pgvector) | Good (vss) |
| **Memory Usage** | Higher (server) | Lower (embedded) |

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_database_implementations.py
```

This will test:
- ✅ DuckDB implementation functionality
- ✅ PostgreSQL import compatibility
- ✅ Performance characteristics
- ✅ Feature comparison

## 📊 Database Schema

The DuckDB implementation creates the same schema as PostgreSQL:

### Tables Created
- `users` - User information
- `bots` - Bot configurations
- `tg_users` - Telegram user moderation data
- `conversation_sessions` - Chat sessions
- `messages` - Chat messages with embeddings
- `songs` - Generated songs

### Key Differences from PostgreSQL
- **Vector Storage**: Uses `FLOAT[1536]` or `TEXT` for embeddings
- **JSON Fields**: Uses `JSON` instead of `JSONB`
- **UUID Generation**: Uses `gen_random_uuid()`
- **Timestamps**: Uses `TIMESTAMPTZ` with `now()`

## 🛠️ Advanced Features

### Vector Embeddings
```python
# Embeddings are stored automatically
embedding = [0.1, 0.2, ...] # 1536-dimensional vector
msg_id = db_manager.save_message(
    session_id, user_id, "user", "Hello!", embedding, tg_msg_id
)
```

### Database Utilities
```python
# Get database statistics
stats = db_manager.get_database_info()

# Optimize database (like PostgreSQL VACUUM)
db_manager.vacuum_database()

# Backup database (file-based only)
db_manager.backup_database("/path/to/backup/")
```

### Custom Queries
```python
# Execute custom queries
results = db_manager.query_all(
    "SELECT COUNT(*) as msg_count FROM messages WHERE role = ?",
    ("user",)
)
```

## 🔍 Troubleshooting

### Common Issues

1. **Import Error**: `ModuleNotFoundError: No module named 'duckdb'`
   ```bash
   pip install duckdb>=0.9.0
   ```

2. **Vector Extension Warning**: `Vector extension not available`
   - This is normal, vectors will be stored as JSON strings
   - For vector similarity search, install: `pip install duckdb[vss]`

3. **Permission Denied**: Database file access issues
   ```python
   # Use in-memory database for testing
   DATABASE__PATH=:memory:
   ```

4. **Database Locked**: File is in use
   - Ensure all connections are properly closed
   - Use connection context managers

### Debugging

Enable debug logging:
```bash
LOG_LEVEL=DEBUG
```

Check database info:
```python
from mindset.database_factory import get_database_info
print(get_database_info(config))
```

## 🎯 Use Cases

### Perfect for DuckDB
- **Development Environment**: Fast setup, no server needed
- **Testing**: In-memory databases for unit tests
- **Single User Applications**: Personal chatbots, analysis tools
- **Data Analysis**: Exploring conversation data
- **Prototyping**: Quick experiments and demos

### Stick with PostgreSQL for
- **Production Systems**: Multiple concurrent users
- **High Availability**: Replication, clustering needs
- **Complex Permissions**: Row-level security requirements
- **Existing Infrastructure**: Already using PostgreSQL

## 📚 Resources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckDB Python API](https://duckdb.org/docs/api/python/overview)
- [DuckDB Extensions](https://duckdb.org/docs/extensions/overview)
- [Vector Search with DuckDB](https://duckdb.org/docs/extensions/vss)

## 🤝 Contributing

When adding new database operations:

1. **Add to both implementations**: PostgreSQL and DuckDB
2. **Maintain interface compatibility**: Same method signatures
3. **Add tests**: Update `test_database_implementations.py`
4. **Document differences**: Note any implementation-specific behavior

## 📝 License

Same license as the main project.

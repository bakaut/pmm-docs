# Telegraph Integration

This document describes the Telegraph integration for the ПойМойМир project.

## Overview

The Telegraph integration allows the bot to create and manage personalized web pages for users on telegra.ph. Each user gets their own page with a unique URL that can be updated with personalized content.

## Components

### 1. Database Table (`telegraph_pages`)

The integration uses a new database table to store information about user pages:

```sql
CREATE TABLE telegraph_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    page_id TEXT UNIQUE,
    page_url TEXT,
    page_title TEXT DEFAULT 'Меню пользователя',
    page_content TEXT DEFAULT '',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2. TelegraphManager Class

The `TelegraphManager` class in [telegraph.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/telegraph.py) handles all interactions with the Telegraph API:

- Creating pages
- Editing pages
- Retrieving page information
- Managing page lists

### 3. Database Integration

The `DatabaseManager` class in [database.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/database.py) has new methods for:

- Getting or creating Telegraph page records
- Updating page information
- Retrieving page data by user

### 4. Telegram Bot Integration

The `TelegramBot` class in [telegram_bot.py](file:///Users/nlebedev@tempo.io/pers/poymoymir/flow/mindset/telegram_bot.py) has a new method `create_or_update_user_telegraph_page` that combines the database and Telegraph API operations.

## Usage

### Creating a User Page

```python
# Initialize components
config = Config.from_env()
db = DatabaseManager(config)
telegraph = TelegraphManager(config)
bot = TelegramBot(config)

# Create or update user's page
page_url = bot.create_or_update_user_telegraph_page(
    db=db,
    telegraph_manager=telegraph,
    tg_user_id=123456789,
    chat_id=987654321,
    page_content="Welcome to your personal page!"
)

print(f"Page URL: {page_url}")
```

### Page Content Format

Telegraph pages use a node-based content format. The integration provides a helper method to convert simple strings to this format:

```python
# Simple string content
content = "Hello, world!"

# Complex content as nodes
content = [
    {"tag": "h2", "children": ["Welcome!"]},
    {"tag": "p", "children": ["This is a paragraph."]},
    {"tag": "ul", "children": [
        {"tag": "li", "children": ["Item 1"]},
        {"tag": "li", "children": ["Item 2"]}
    ]}
]
```

## Page URL Generation

Page URLs are generated using a unique slug based on the user's Telegram ID and chat ID:

```
https://telegra.ph/{md5(tg_id + chat_id)}
```

## Security

- All Telegraph API interactions use HTTPS
- Page content is stored in the database with user association
- Access to pages is controlled through the unique URLs

## Error Handling

The integration includes comprehensive error handling for:

- Network errors
- API errors
- Database errors
- Invalid content formats

## Future Enhancements

Possible future enhancements include:

- Automatic page updates based on user interactions
- Rich media content integration
- Page analytics
- Custom templates


## index.py
from mindset.telegraph import TelegraphManager  # Add TelegraphManager import
# Telegraph manager
telegraph_manager = TelegraphManager(config)  # Initialize TelegraphManager
# Create Telegraph page for the user (if configured to do so)
page_url = telegram_bot.create_or_update_user_telegraph_page(
    db=db,
    telegraph_manager=telegraph_manager,
    tg_user_id=tg_user_id,
    chat_id=chat_id,
    page_content=f"Привет, {full_name}! Это ваша персональная страница в Telegraph."
)

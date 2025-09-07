# Telegraph Documents

This directory contains documents for the "ПойМойМир" Telegram bot in JSON format that can be imported into the TelegraphManager class.

## Files

- `privacy_policy.json` - The privacy policy formatted as JSON nodes for Telegraph API
- `discussion_restrictions.json` - The discussion restrictions policy formatted as JSON nodes for Telegraph API
- `song_creation_journey.json` - The song creation journey guide formatted as JSON nodes for Telegraph API

## Usage

To use these documents with the TelegraphManager class:

```python
import json
from mindset.telegraph import TelegraphManager

# Load the privacy policy content
with open('privacy_policy.json', 'r', encoding='utf-8') as f:
    privacy_policy_content = json.load(f)

# Load the discussion restrictions content
with open('discussion_restrictions.json', 'r', encoding='utf-8') as f:
    discussion_restrictions_content = json.load(f)

# Load the song creation journey content
with open('song_creation_journey.json', 'r', encoding='utf-8') as f:
    song_creation_journey_content = json.load(f)

# Load the menu content
with open('menu.json', 'r', encoding='utf-8') as f:
    menu_content = json.load(f)

# Initialize TelegraphManager
telegraph_manager = TelegraphManager(config)

# Create a new page with the privacy policy
page = telegraph_manager.create_page(
    tg_id=user_tg_id,
    chat_id=user_chat_id,
    title="Политика обработки персональных данных",
    content=privacy_policy_content
)

# Create a new page with the discussion restrictions
page = telegraph_manager.create_page(
    tg_id=user_tg_id,
    chat_id=user_chat_id,
    title="Запреты обсуждения",
    content=discussion_restrictions_content
)

# Create a new page with the song creation journey
page = telegraph_manager.create_page(
    tg_id=user_tg_id,
    chat_id=user_chat_id,
    title="Путь создания песни в ПойМойМир",
    content=song_creation_journey_content
)

# Create a new page with the menu
page = telegraph_manager.create_page(
    tg_id=user_tg_id,
    chat_id=user_chat_id,
    title="Меню документов",
    content=menu_content
)
```

The JSON structure follows the Telegraph API node format with supported tags:
- Headers: h3, h4
- Paragraphs: p
- Lists: ul, ol, li
- Links: a (with href attribute)
- Text formatting: b (bold)
- Horizontal rules: hr

Note: The Telegraph API does not support table tags, so the "Цели и правовые основания обработки" section in the privacy policy has been reformatted using bold text and paragraphs instead of a table.

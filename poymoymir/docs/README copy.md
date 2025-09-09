# Weekly Summary Telegram Workflow

This workflow automatically posts a weekly summary of repository changes to a Telegram chat or group.

## How to Get Chat ID and Thread ID

### Getting the Chat ID

1. **For a private chat with your bot:**
   - Start a conversation with your bot
   - Send any message to the bot
   - Visit this URL in your browser (replace `BOT_TOKEN` with your actual bot token):
     ```
     https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
     ```
   - Look for the `chat.id` field in the response

2. **For a group chat:**
   - Add your bot to the group
   - Send a message in the group
   - Visit the same URL as above
   - Find the `chat.id` for your group (it will be a negative number)

### Getting the Thread ID (for Topics)

1. **Enable topics in your group:**
   - Go to group settings
   - Enable "Topics" feature

2. **Find the thread ID:**
   - Create or identify the topic you want to use
   - Forward a message from that topic to `@username_to_id_bot` on Telegram
   - The bot will reply with the thread ID

3. **Alternative method:**
   - Use a Telegram bot library or API tool to inspect message objects
   - The `message_thread_id` field will be present in messages from topics

## Configuration

Set these secrets in your GitHub repository:

- `OPENAI_API_KEY`: Your OpenAI API key for generating summaries
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: The chat ID where the summary should be posted
- `TELEGRAM_MESSAGE_THREAD_ID` (optional): The thread ID for a specific topic

## Schedule

The workflow runs every Monday at 9:00 AM UTC, or can be triggered manually.

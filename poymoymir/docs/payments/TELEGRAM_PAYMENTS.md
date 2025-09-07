# Telegram Payments with Stars Currency

This document explains how to implement and use Telegram payments with Stars currency (XTR) in your bot.

## Overview

The payment system allows users to unlock content (such as audio files) by paying with Telegram Stars. The flow works as follows:

1. Bot sends a locked message with payment buttons (1⭐, 10⭐, 100⭐)
2. User clicks a payment button
3. Bot sends an invoice for the selected amount
4. User pays the invoice
5. Bot receives a successful payment notification
6. Bot unlocks the content by editing the original message

## Database Schema

A new table `tg_locked_audio_payments` is created to track payment information with references to existing tables:

```sql
CREATE TABLE tg_locked_audio_payments (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  message_id BIGINT NOT NULL,
  payer_user_id BIGINT,
  user_id UUID,
  invoice_payload TEXT NOT NULL UNIQUE,
  amount_stars INTEGER NOT NULL CHECK (amount_stars >= 1),
  currency TEXT NOT NULL DEFAULT 'XTR' CHECK (currency = 'XTR'),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','refunded','failed','canceled')),
  telegram_payment_charge_id TEXT,
  telegram_provider_payment_charge_id TEXT,
  audio_file_id TEXT,
  audio_path TEXT,
  reveal_done BOOLEAN NOT NULL DEFAULT FALSE,
  reveal_attempts INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at TIMESTAMPTZ,
  refunded_at TIMESTAMPTZ,
  extra JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK ((audio_file_id IS NOT NULL) OR (audio_path IS NOT NULL))
);
```

### Foreign Key Relationships

The table includes the following foreign key relationships:
- `payer_user_id` references `tg_users(id)` - Links to the Telegram user who made the payment
- `user_id` references `users(id)` - Links to the main user record

Note: Foreign key constraints should be applied when database access is available, as documented in `docs/DATABASE_FOREIGN_KEY_SETUP.md`.

## Implementation Details

### 1. Sending Locked Audio Messages

To send a locked audio message, use the `send_locked_audio_message` method:

```python
message_id = telegram_bot.send_locked_audio_message(chat_id, "🔒 Аудио откроется после оплаты")
```

This sends a message with inline buttons for 1⭐, 10⭐, and 100⭐ payments.

### 2. Creating Payment Records

After sending the locked message, create a payment record in the database:

```python
db.create_payment_record(
    chat_id=chat_id,
    message_id=message_id,
    invoice_payload="unique_payload_string",
    amount_stars=10,  # or 1 or 100
    audio_path="/path/to/audio.mp3",  # or audio_file_id="telegram_file_id"
    user_id="user-uuid",  # UUID from users table
    payer_user_id=telegram_user_id  # Telegram user ID from tg_users table
)
```

### 3. Handling Payment Callbacks

The system automatically handles three types of payment events:

- **Callback Queries**: When users click payment buttons
- **Pre-checkout Queries**: Payment confirmation requests (must be answered within 10 seconds)
- **Successful Payments**: Notifications when payments are completed

### 4. Unlocking Content

After a successful payment, the system will:
1. Update the payment status in the database
2. Edit the original locked message to reveal the audio content
3. If editing fails, send the audio as a new message

## Key Methods

### TelegramBot Methods

- `send_invoice(chat_id, title, description, payload, currency="XTR", prices)`: Send a payment invoice
- `answer_pre_checkout_query(pre_checkout_query_id, ok, error_message)`: Respond to pre-checkout queries
- `edit_message_media(chat_id, message_id, media_type, media_source, caption)`: Edit message media content
- `send_locked_audio_message(chat_id, text)`: Send a locked audio message with payment buttons
- `create_payment_keyboard(message_id)`: Create payment buttons
- `send_audio_file(chat_id, audio_path, caption)`: Send an audio file

### DatabaseManager Methods

- `create_payment_record(chat_id, message_id, invoice_payload, amount_stars, audio_path, audio_file_id, user_id, payer_user_id)`: Create payment record
- `get_payment_by_payload(invoice_payload)`: Get payment by payload
- `update_payment_status(invoice_payload, status, telegram_payment_charge_id, telegram_provider_payment_charge_id)`: Update payment status
- `mark_payment_revealed(invoice_payload)`: Mark payment as revealed
- `get_payment_by_message_id(chat_id, message_id)`: Get payment by message ID

## Example Usage

```python
# Send locked audio message
message_id = telegram_bot.send_locked_audio_message(chat_id)

# Create payment record
if message_id:
    db.create_payment_record(
        chat_id=chat_id,
        message_id=message_id,
        invoice_payload=f"unlock_{message_id}",
        amount_stars=10,
        audio_path="/path/to/audio.mp3",
        user_id=user_uuid,
        payer_user_id=tg_user_id
    )
```

## Error Handling

The system includes fallback mechanisms:
- If editing the original message fails, the audio is sent as a new message
- All operations are logged for debugging purposes
- Database operations include error handling

## Security Considerations

- Payloads are unique per payment to prevent replay attacks
- Payment status is tracked to prevent duplicate unlocks
- All financial operations are logged for audit purposes

## Testing

To test the payment functionality:
1. Create a test message with payment buttons
2. Simulate callback queries with different star amounts
3. Verify database records are created correctly
4. Test pre-checkout query handling
5. Simulate successful payments and verify content unlocking

## Database Setup

For information on setting up the foreign key constraints when database access is available, see `docs/DATABASE_FOREIGN_KEY_SETUP.md`.
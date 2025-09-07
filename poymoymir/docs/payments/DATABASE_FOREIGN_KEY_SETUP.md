# Database Foreign Key Setup for Payment Table

This document explains how to properly set up foreign key references for the `tg_locked_audio_payments` table once database access is available.

## Current Table Structure

The `tg_locked_audio_payments` table has been created with the following structure:

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

## Required Foreign Key Constraints

The following foreign key constraints should be added to maintain referential integrity:

1. **Reference to Telegram Users Table**:
   ```sql
   ALTER TABLE tg_locked_audio_payments 
     ADD CONSTRAINT fk_tg_payments_payer_user 
     FOREIGN KEY (payer_user_id) 
     REFERENCES tg_users(id) 
     ON DELETE SET NULL;
   ```

2. **Reference to Main Users Table**:
   ```sql
   ALTER TABLE tg_locked_audio_payments 
     ADD CONSTRAINT fk_tg_payments_user 
     FOREIGN KEY (user_id) 
     REFERENCES users(id) 
     ON DELETE SET NULL;
   ```

## Prerequisites for Adding Foreign Keys

Before adding the foreign key constraints, ensure that:

1. The referenced tables (`tg_users` and `users`) exist in the database
2. The referenced columns (`id` in both tables) exist and have the correct data types
3. Any existing data in the `tg_locked_audio_payments` table complies with the foreign key constraints

## Handling Existing Data Issues

If there are existing records with NULL values that conflict with the foreign key constraints:

1. Update NULL values in `payer_user_id` to valid `tg_users.id` values or leave as NULL if the constraint allows it
2. Update NULL values in `user_id` to valid `users.id` values or leave as NULL if the constraint allows it

Example update statements:
```sql
-- If you need to set default values for NULL entries
UPDATE tg_locked_audio_payments 
SET payer_user_id = 0 
WHERE payer_user_id IS NULL;

UPDATE tg_locked_audio_payments 
SET user_id = '00000000-0000-0000-0000-000000000000' 
WHERE user_id IS NULL;
```

## Applying the Changes

Once the database is accessible and the prerequisites are met, run the following commands:

```sql
-- Add foreign key constraint for Telegram users
ALTER TABLE tg_locked_audio_payments 
  ADD CONSTRAINT fk_tg_payments_payer_user 
  FOREIGN KEY (payer_user_id) 
  REFERENCES tg_users(id) 
  ON DELETE SET NULL;

-- Add foreign key constraint for main users
ALTER TABLE tg_locked_audio_payments 
  ADD CONSTRAINT fk_tg_payments_user 
  FOREIGN KEY (user_id) 
  REFERENCES users(id) 
  ON DELETE SET NULL;
```

## Verification

After applying the constraints, verify that they were created successfully:

```sql
SELECT 
    tc.table_name, 
    tc.constraint_name, 
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE 
    tc.table_name = 'tg_locked_audio_payments' 
    AND tc.constraint_type = 'FOREIGN KEY';
```

This will show all foreign key constraints on the `tg_locked_audio_payments` table.
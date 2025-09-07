# Migration Application Guide

This guide explains how to apply the database migrations when database access is available.

## Prerequisites

1. Ensure you have `dbmate` installed
2. Ensure you have access to the PostgreSQL database
3. Ensure you have the proper database credentials

## Setting Up Database Connection

Set the `DATABASE_URL` environment variable with your database connection string:

```bash
export DATABASE_URL="postgresql://username:password@host:port/database_name"
```

For example:
```bash
export DATABASE_URL="postgresql://postgres:password@localhost:5432/poymoymir"
```

## Applying Migrations

### 1. Check Current Migration Status

First, check which migrations have been applied:

```bash
cd /Users/nlebedev@tempo.io/pers/poymoymir/db-schema/nelyskazka
dbmate status
```

### 2. Apply Pending Migrations

Apply all pending migrations:

```bash
cd /Users/nlebedev@tempo.io/pers/poymoymir/db-schema/nelyskazka
dbmate up
```

This will apply the `20250907000001_add_telegram_payments_table.sql` migration.

### 3. Handling Migration Issues

If you encounter issues with the migration, particularly with the `20250907000000_allow_null_user_id_telegraph_pages.sql` migration:

1. Check if there are existing records with NULL values in the `telegraph_pages` table
2. Update those records to have valid values before applying the migration:

```sql
-- Update NULL user_id values
UPDATE telegraph_pages 
SET user_id = '00000000-0000-0000-0000-000000000000' 
WHERE user_id IS NULL;

-- Update NULL chat_id values
UPDATE telegraph_pages 
SET chat_id = 0 
WHERE chat_id IS NULL;
```

### 4. Verifying Migration Success

After applying migrations, verify that the `tg_locked_audio_payments` table was created:

```bash
cd /Users/nlebedev@tempo.io/pers/poymoymir/db-schema/nelyskazka
dbmate status
```

You should see that all migrations are marked as applied.

### 5. Adding Foreign Key Constraints

Once the migration is successfully applied, you can add the foreign key constraints as documented in `docs/DATABASE_FOREIGN_KEY_SETUP.md`.

Connect to your database and run:

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

## Rolling Back Migrations

If you need to roll back the payment table migration:

```bash
cd /Users/nlebedev@tempo.io/pers/poymoymir/db-schema/nelyskazka
dbmate down
```

This will roll back the last applied migration.

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure the database server is running and accessible
2. **Permission Denied**: Ensure you have the proper database credentials
3. **Foreign Key Constraint Violations**: Update existing data to comply with constraints before applying them
4. **NULL Value Conflicts**: Handle existing NULL values in tables before applying constraints

### Checking Table Structure

To verify the table structure after migration:

```sql
\d tg_locked_audio_payments
```

This will show the structure of the payment table.

### Checking Constraints

To verify foreign key constraints:

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

This query will show all foreign key constraints on the payment table.
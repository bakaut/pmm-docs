-- SQL script to create the statuses table
-- This can be used to manually create the table in a database

CREATE TABLE IF NOT EXISTS public.statuses (
    id uuid,
    session_id uuid references public.conversation_sessions(id) on delete cascade,
    user_id uuid references public.users(id) on delete cascade,
    message_id uuid references public.messages(id) on delete cascade,
    state TEXT,
    state_reason TEXT,
    intent TEXT,
    intent_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
-- CREATE INDEX IF NOT EXISTS idx_statuses_session_id ON statuses(session_id);
-- CREATE INDEX IF NOT EXISTS idx_statuses_user_id ON statuses(user_id);
-- CREATE INDEX IF NOT EXISTS idx_statuses_message_id ON statuses(message_id);
-- CREATE INDEX IF NOT EXISTS idx_statuses_created_at ON statuses(created_at);

-- Example query to retrieve statuses for a session
-- SELECT * FROM public.statuses WHERE session_id = 'session-uuid' ORDER BY created_at DESC;

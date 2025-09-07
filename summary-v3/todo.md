def save_memory(self, session_id: str, msg_id: str, type: str,
                summary_text: str, trigger_reason: str) -> str:
    """Save a conversation summary and return summary ID."""
    summary_id = str(uuid.uuid4())
    self.execute(
        "INSERT INTO memory("
        "id, session_id, msg_id, "
        "type, text, trigger, status, "
        "created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, "complited", NOW())",
        (summary_id, session_id, msg_id, type, summary_text, trigger_reason)
    )
    self.logger.debug("Saved summary %s for session %s", summary_id, session_id)
    return summary_id

    #last_2500_token_messages = ctx["last_2500_token_messages"]
    # Может по тупому каждые 2500 символов то есть делится без остатка на 2500 ближайшее overlap на 300 500 символов погрешность?
    # ( 2500 - len / 2500 целочивленно ) - 500 (погрешость) < 500 по модулю
    if 
    

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    msg_id UUID NOT NULL,
    m_type TEXT NOT NULL;
    text TEXT NOT NULL,
    trigger TEXT NOT NULL,    -- tokens|turns|time|topic_shift|manual
    status TEXT NOT NULL DEFAULT 'completed', -- completed|superseded|dirty
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB,
);

150 среднее число символов сообщении
обязательно болше одного
2500


def send_telegram_callback(callback_id, text):
    r = session.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": False
    })
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendMessage failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram markup sent OK %s", r.status_code)

def send_telegram_markup(chat_id: int, text: str, markup: dict) -> None:
    """
    Отправляет пользователю Telegram с кнопками для оплаты, поделиться и обнять автора.
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": json.dumps(markup),
        "parse_mode": "MarkdownV2"
    }
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = session.post(url, json=payload, timeout=timeout)
    try:
        r.raise_for_status()
    except HTTPError as e:
        logger.error("Telegram sendMessage failed: %s | response=%s", e, r.text)
        raise
    logger.debug("Telegram markup sent OK %s", r.status_code)
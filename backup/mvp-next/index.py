# Вспомогательные LLM
# Суммаризация смыслов раз в день или раз в n сообщений
# Категоризация по эмоциональному состоянию ответов пользователя
# Категоризация смыслов по пирамиде Маслоу
# Категорицация по колесу баланса
# Напоминания тоже здесь, день назад мы говорили про _эмоция_ _тема_ _категория_ _смысл_
# Хранить развернуто песни пользователя по шагам эмоция куплет припев вся песня
# Промты, шаблоны промтов как файлы

# def detect_user_state_via_llm(messages: List[str]) -> str:
#     """Определяет эмоциональное состояние пользователя через LLM."""
#     if not messages:
#         return "WAITING"
    
#     prompt = """Ты — эмпатичный помощник, который умеет чутко определять эмоциональное состояние пользователя на основе последних его сообщений.

# Задача:
# - Верни один из следующих TAG-ов:
#   "ACTIVE_TRUST"       — пользователь активно участвует, развивает идею, делится откликом
#   "LIGHT_DOUBT"        — осторожные, неуверенные, односложные ответы, мягкое замедление
#   "CONFUSION_OR_STUCK" — пользователь запутался, не понимает, как продолжить, просит помощи
#   "CONTEMPLATIVE_PAUSE"— человек в созерцании, молчит или пишет с редкими откликами
#   "FRUSTRATION"        — раздражение, обесценивание, недовольство
#   "DISENGAGED"         — отключение, пауза, исчезновение после эмоц. фразы

# Вход:
# - Список сообщений, где каждое сообщение — это текст пользователя в хронологическом порядке.

# Примеры:

# 1. ["Да", "Не знаю", "Ладно"] → "LIGHT_DOUBT"
# 2. ["Мне ничего не откликается", "что-то не то", "можно по-другому?"] → "CONFUSION_OR_STUCK"
# 3. ["Это тронуло", "Спасибо", "Можно сохранить?"] → "ACTIVE_TRUST"
# 4. ["не знаю что писать", "ладно", "что ты хочешь от меня"] → "CONFUSION_OR_STUCK"
# 5. ["всё", "я ухожу", "нет смысла"] → "DISENGAGED"
# 6. ["что за ерунда", "ты не понимаешь", "это плохо"] → "FRUSTRATION"

# Если данных недостаточно — верни "UNKNOWN".

# Отвечай только TAG-ом, без пояснений.

# """

#     messages_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(messages[-10:]))
#     full_prompt = f"{prompt}\nСообщения:\n{messages_text}\n\nОтвет:"

#     # Вызов LLM
#     try:
#         response = session.post(
#             ai_endpoint,
#             json={
#                 "model": ai_model,
#                 "messages": [
#                     {"role": "system", "content": full_prompt}
#                 ]
#             },
#             headers={"Authorization": f"Bearer {operouter_key}"},
#             timeout=timeout,
#         )
#         data = response.json()
#         result = data["choices"][0]["message"]["content"].strip().upper()
#         if result not in {"WAITING", "CONFUSED", "DOUBT", "TIRED", "LOOPING", "OK"}:
#             return "OK"
#         return result
#     except Exception as e:
#         logger.error(f"State detection failed: {e}")
#         return "OK"
# https://chatgpt.com/g/g-6804bfa1ecc08191b6562faa6de441d5-lifesong-telegramm-bot/c/68056dd3-4a78-8007-aab0-359c7cff4d7d
    # MVP_2_2 final можно назвать по semever 0.6.1
    # Сделать пересохранение песня на yandex s3 и редактирование id3 тегов Done + тест suno-generating регресс
    # Сделать прежний формат песню последоватьено пишет строка строка + куплет  куплет + куплет чтобы пользовател видел процесс а не только текущий куплет
    # сохранить intent emotion в базу jsonb messages - done
    # Сделать регресс? проверить что все предыдущие функции работают как ожидалось
    # Не переносить сделай сначала
    # Тесты сделать, все с начала 2 песни flow
    # Написать задачи в трекер задач
    ######################
    # Next steps
    # Добавить очистку истории пользователя
    # Добавить суммаризацию и вектор для суппаризации каждый 10 сообщение но чтобы не перекрывались
    # Подумать где хранить intent emotion в базе и как jsonb done
    # здесь json формируем большой который всю суммарную инфо собдержит и его сохраняем только или отдельно?
    # здесь же определить дополнительную информацию
    # сохранить имя пользователя
    # Созранить статус на котором находиимся и краткий самери что сделали и что осталось
    # Определить состочние пользователя замещательства и так далее и помочь ему -  done
    # Векторный поиск по сессии если пользователь похожее спрашивал и подгружать самери ответа что он уже давал
    # Отдельная таблица session/user short memory контекст пользователя имя самери и так далее
    # добавить проверку что предыдущая песня > 20 минут false positive два раза если благодарить после песни done 20 сообщений
    # Векторный поиск похожую песню уже делали не делать
    # Пока через - "feedback": Пользователь уже получил финальную версию песни и аудио песню считает песню готовой. решил
    # Микро промт или regexp [Verse 1] Белый змей в небе парит, и добавляем перепиши как будто ты песенник всего мира и сохраняем как
    # сообщение ассистента которыи не видт пользователь говорим используй этот текст
    # Развернутый промт про ии композитора и модель gpt turbo или o3 попробовать она дешевле стала 2е 8е
    # Или меняем место, ставим после ответа основной ИИ доработка перед отправкой текста

    # Проверить что финальная версия песни отправлена/получена пользователю
    # Сделать два условия отдельных
    # add default value none for is_final_song_received and is_final_song_sent

# with open("knowledge_bases/detect_userflow_state.txt", "r", encoding="utf-8") as system_prompt_userflow_state:
#     system_prompt_detect_emotion = system_prompt_userflow_state.read()

# def tg_escape(text: str) -> str:
#     return "".join("\\" + ch if ch in SPECIAL else ch for ch in text)

# def tg_escape(text: str) -> str:
#     """Экранируем только нужные символы."""
#     return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)


    # detect_userflow_state = llm_conversation(last_8_messages, system_prompt_userflow_state)
    # if detect_userflow_state == "assembly":
    #     adopt system promt, add ai-song-song_v3.md


I'll scan key files to understand architecture and define a practical testing strategy. Now I'll open the main orchestrator, DB layer, bot entry, and config/utilities.
Read file: /Users/nlebedev@tempo.io/pers/poymoymir/flow/index.py
Read file: /Users/nlebedev@tempo.io/pers/poymoymir/flow/database.py
Read file: /Users/nlebedev@tempo.io/pers/poymoymir/flow/telegram_bot.py
Read file: /Users/nlebedev@tempo.io/pers/poymoymir/flow/config.py
Read file: /Users/nlebedev@tempo.io/pers/poymoymir/flow/utils.py

### Стратегия тестирования (приоритет и порядок)

- **Unit (высокий, сначала)**
  - `flow/utils.py`
    - `parse_body`: JSON, base64(JSON), base64(binary), plain text.
    - `get_last_messages`: фильтры role, force_last_user, extra_message, границы.
  - `flow/config.py`
    - `from_env` валидация обязательных полей, Enum, значения по умолчанию.
  - `flow/telegram_bot.py`
    - `_clean_think_tags`, `_convert_basic_styles`, `_escape_specials`, shielding/unshielding.
    - `send_audio`, `send_callback_query_answer`: мокаем HTTP `requests.Session.post`.
  - `flow/database.py`
    - Локальная логика (hash/md5 токена), выбор `cutoff` в `get_active_session`.
    - Мокаем `psycopg2.connect`/курсор.

- **Интеграционные (средний, затем)**
  - БД: поднять тестовый Postgres, применить миграции; тесты `get_or_create_*`, `fetch_history`/`save_user_message`, транзакции и откаты.
  - S3: мокаем `boto3.client('s3').generate_presigned_url` и проверяем параметры.
  - HTTP: контракт с Telegram API — проверка формируемых payload’ов и таймаутов.

- **E2E (селективно, после интеграции)**
  - Сквозной сценарий: имитация апдейта Telegram → обработка → запись в БД → ответ бота.
  - Генерация песни: заглушка Suno/AI, загрузка в S3 (мок), отправка аудио.
  - Негатив: бан/варн через `moderate_user`, падение внешних сервисов → fallback.

- **Инфраструктура**
  - Pytest + fixtures: тестовая БД, временные директории для mp3, патчинг env.
  - Моки: `requests`, `psycopg2`, `boto3`, время (`freezegun`) для `cutoff`.

- **Приоритет баг-рисков**
  - Высокий: парсинг входа, экранирование Markdown, таймауты/ретраи, сессии/история.
  - Средний: модерация/правила, S3-ссылки, метаданные mp3.
  - Низкий: тексты/markup, случайные ответы.

- **Порядок запуска CI**
  1) Unit быстрые, 2) интеграция БД/HTTP-mock, 3) E2E ночные/по метке.

- **Метрики покрытия**
  - Цели: unit ≥80% в `utils`, `telegram_bot` форматирование ≥90%, критич. ветки БД ≥70%.

- **Артефакты**
  - Снимки payload’ов Telegram, фикстуры истории чата, дампы миграций.

- **Рекомендуемые инструменты**
  - pytest, pytest-async (если появится async), responses/requests-mock, moto (или прямой мок boto3), testcontainers-postgres/pytest-postgresql, freezegun.

- **Минимальные e2e без внешних зависимостей**
  - Локально: мок Telegram webhook, мок Suno/AI, in-memory/временная БД, проверка финального сообщения.

- Сделал обзор ключевых модулей и наметил приоритеты: сначала unit по чистым функциям и форматированию, затем интеграция с тестовым Postgres и моки внешних сервисов, после — узкие e2e сценарии со стабами сервисов.
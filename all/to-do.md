- [x] все переменные и секреты проверить 
- [x] забывает о чем говорили после того как сообщение об ошибке fixed
- [x] Формат телеграмм как сделать правильно


# MVP-2
- [ ] Сжатие смыслов как в prometeus на 30 лет
- [ ] Периодический сброс в s3 для холоднго хранения и не перегрузки базы данных podtgress



Дело не в фильтре в контексте system promt
Дело в конкретной модели  openai/gpt-4o работает openai/gpt-4o-2024-05-13 (RLHF обученая модель)


# После mvp-1 запуска 10 пользователей
- [ ] Сбор и обработка обратной связи!!!
- [ ] Улучшить стабильность  (Подобрвть и добавить fallback модели)
- [ ] Сбор и обработка обратной связи




Подобрвть и добавить fallback модели
https://openrouter.ai/docs/api-reference/chat-completion
models: [openai/gpt-4o, openai/gpt-3.5-turbo-16k, openai/gpt-4, openai/gpt-4-0613, openai/gpt-4-32k, openai/gpt-4-32k-0613, openai/gpt-4-turbo]



ЯГений
@MentorGeniyBot

МоиЭмоции
@IFeeMelBot

Интуиция
@GutFeelBot


МАК
@IntuitMapsBot

НоваяПолезнаяПривычка
@TrekerRostaBot



# MVP-2
Сделать настройки логики в зависимости от контекутного окна или выбирать можели только > 128к контектсное окно
Добавить в класс провайдера динамическое определение


# Заменить openrouter на DO агента подумать

# Все таки прокси, сделать и забыть не принимать решения, пока нужно и попробовать потом gpt-4-turbo для текстовов песен
В том числе и по стиль плач


system promt загружается из файла
используй opeai бибилиотеку вместо requests
для прокстирования инициализируй opeai с катомным httpx клиентом с proxy параметром
хранение в базе постгре сделай  чере langchain долговременная память
user flow из system promt сделай как lang graph конечный автомат
хранение в YDB сделай  чере langchain memory ram (если есть готовый плагин или адаптируй под redis)
Используй официальный telegram bot api, не requests
Соблюдай принцимы модульности взаимозаменяемости и чистого кода
Для реализации ИИ логики используй преимущественно langchain
Перед отправкой сделай double-check всего кода сам согласно описанным выше правилам


# Этика и безопасность
🔍 Ставь регулярную самопроверку: «Этот шаг усиливает человека? Или делает ИИ главным?»



Написать завтра
Определить что песня сгенерирована
- Попросить пользователя поставить лайк стайлик на песню
  - Переделать вебхук телеграм чтобы он принимал обновления  эмоджи
  - Запретить обрабобтку этоджи кроме одной
  - Добавить в базу хранение телеграмм message id


# Взять тект песни или переформатировать под формат suno +
- сделать opaai client  на requests
Из текста песни сделать аранжировку


## Передавть в suno +
Получить номер задачи в ответе +
Сохранить номер задачи в базе данных и связать с телеграмм chat_id через user_id ...+
Настроить парсинг callback сообщений и отправка аудио в телеграмм по chat_id и отдельый gateway+
Парсить ответ webhook и искать матч по task-id chat_id или session_id куда отправлять нужно+
База данных придется обновитьдобавить новые поля таблицы для песен +

Ретраи сообщений фигня ретрияи suno деньги (( телеграм логику

Suno request OK: {"code":429,"msg":"The current credits are insufficient. Please top up.","data":null}

LLM response: {'error': {'message': 'This endpoint\'s maximum context length is 128000 tokens. However, you requested about 132888 tokens (132733 of text input, 155 of tool input). Please reduce the length of either one, or use the "middle-out" transform to compress your prompt automatically.', 'code': 400, 'metadata': {'provider_name': None}}}


Отправлять последнюю сгенерированную по времени и равно пользователю


# анализ последних сообщений +
Мелодия звучит перелом, я молодец



Без эмоций люди могут


    - Скажи: «Я помогу тебе создать текст песни — живой, чувствующий, как дыхание.»


Почти дешево но не очень кчество
amazon/nova-micro-v1


Если хочу все забыть в сообщении пользователя  то на 30 сообщений начинаем все с нуля
Переопределяем history

    # Получаем все пользовательские сообщения (можно увеличить count, если истории много)
    user_msgs = get_last_user_messages(session_uuid, count=30)  # или напрямую _fetch_history + фильтр

    # Ищем последнее вхождение фразы
    start_idx = None
    for i in range(len(user_msgs)-1, -1, -1):
        if "Давай начнём всё с начала" in user_msgs[i]["content"]:
            start_idx = i
            break

    # Если нашли — берём сообщения начиная с этой фразы (или после неё)
    if start_idx is not None:
        msgs_from_phrase = user_msgs[start_idx:]
    else:
        msgs_from_phrase = user_msgs  # если не нашли — вся история

    # Теперь msgs_from_phrase — это список сообщений пользователя начиная с нужной фразы

Попробуем? Работа с возражениями
https://storage.yandexcloud.net/pmm-static/audio/pmm-bot/%D0%9F%D0%BE%D0%BF%D1%80%D0%BE%D0%B1%D1%83%D0%B5%D0%BC%3F.mp3

Давай пока без напоминаний
Протестируем что вс еработает
обновить таблицу в базе данных. messages добавить intent + emotion

Сохранять смысл сжимать смысл может в intent
(когда вызывается intent_detection)

я в тренде 2025
))
ИИ агент
безопасность
ИИ агент в повсденевности СИРИ посмотри билеты мне

# next steps
## Добавить суммаризацию и вектор для суппаризации каждый 10 сообщение но чтобы не перекрывались
определить где intent emotion summary хранить и использоваь ли сразу вектор  для summary
mailstones

archival_policy jsonb,

execute("UPDATE songs SET file_path = %s WHERE ...", (db_path, ...))  # допишите условия


execute("UPDATE songs SET warnings = %s WHERE id = %s", (new_warnings, tg_user_id))


| Где                     | Было                                        | Станет                                                                                                                                                                                                                                                       |
| ----------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Шаг 5. Сборка песни** | «Обязательно оформи согласно примеру…»      | **Сначала добавь короткое напоминание-чек-лист:**<br>«Перед отправкой финала проверь, что:<br>  • есть строка `Название:`<br>  • (опц.) строка `Стиль:`<br>  • блок `Текст песни:` в тройных \`\`\`<br>  • внутри все структурные теги, последний — `[End]`» |
|                         | «Собери песню в красивый блок кода \`\`\`…» | «*Всегда* начинай блок кода с `Текст песни:` на новой строке, а сам блок — **сразу** после этой метки без пустых строк.»                                                                                                                                     |
| **Стиль оформления**    | «Песни — всегда в блоке кода\`\`\`.»        | «Если забыта хоть одна из обязательных строк или тегов — *не отправляй ответ*, а пересобери сообщение до идеального вида (самопроверка).»                                                                                                                    |
| **Финал**               | «Поблагодари за доверие…»                   | + «Если всё правильно — в конце допиши: `_Формат совершен ✓_` (это скрытый маркер, по нему легче увидеть, что чек-лист пройден).»                                                                                                                            |

user flow потюнить
https://chatgpt.com/c/68718d4b-e810-8007-b457-4149ad865094

Почистил код, эксперименты отдельно сохранил
Самую важную фичу для АГА-эффекта добавил, генерация песни
Автоматически сохраняется intent, emotions
Сделал бота с семантическим поиском (RAG)


git tag -a v0.6.0-alpha -m "Добавлено аудио генерация, сохранение intent и эмоций, сделан RAG для семантического поиска, почистил код убрал эксперименты"
git push origin v0.6.0-alpha

Что дальше? 20-07-2025

50 человек пройти
49 человек пройти
20-07-2025 ключевая фишка генерация песни Никита Ярослав друг нужно понять почему а нет логов для прод не включал

- sqlduet для аналитики базы данных с авторизацией внутри (PostgreSQL)
00 формат вопроса Найди <начало вопроса который может интерпретироваться как SQL select> все сообщения пользователя Lebedev Nikolay имя < конец вопроса который может интерпретироваться как SQL select  и ответь <начало запроса по результату sql вывода select> на вопрос какие основные чувства <конец запроса по результату sql вывода select>
0 авторизация json файл с разрешенными telegramm id (auth/teleramm-id.json {"access": "granted"}) читается файл, если файла нет или access not granted запрещено выход
1 Превратить запрос пользователя в SQL запрос исходя из схемы БД если возможно
1,1 Схему базы postgresql получить самому и сохранить в файл и обновлять постоянно при каждом запросе database/schema.sql
1,2 Проверить что sql запрос валидный сделать explain перед фактическим execute
1.2.1 Разрешить только select делать
2 Получить ответ от SQL
3 Используя полученные данные ответить на первоначальный запрос тепмература 0 не фантазировать
4 langgraph использовать (state хранить в json state/teleramm-id.json {"state": "sql_explain_success"}) пишется файл при изменении стэйт, читается при запуске скрипта yandex function
 - статус проверки пользователь авторизован успешно нет (-- сброс в начало auth state unautorized))
 - Запрос SQL сформулирован (нельзя сформулировать -- сброс в начало)
 - Запрос SQL проверен explain (неверный -- сброс в начало)
 - Запрос SQL выполнен и получен результат не пустой (пустой ошибка -- сброс в начало)
 - Изначальный вопрос задан опираясь на данные SQL ответа
 - Результат отправлен пользователю -- сброс в начало

  - Сделать обработку результатов sql запроса
    - Вернуть ответ на запрос
    - Сохранить результат в переменной
    - Обратить к результату с изначальным вопросом

    Проанализируй основный эмоцию первой песни
    - Сформулировать запрос SQL
    - Выполнить запрос SQL
    - Получить результат success if not failed
    - Проанализировать результат LLM
- подумать может часть логов включить для прод например intent finalize song
- переделать формат логов чтобы фильтровать можно было

python async, aiogramm, sqlalhemy, openai, pydantic, proxy + openai
yandex serverless

Функционал обработка на натуральном языке запросов
На выходе код yandex serveless python



Как динамически делать system promt?
Берем большой ДБ
Ищем (может иерархия БД оглавение абзац самери абзац?) по RAG релевантное и из этих чанков сделать system promt релеватный

V4_5PLUS модель обновить
postgresql+asyncpg://admin:admin@orchestra.ru:6432/poymoymir


Давай добавим локальное тесирование для определенной сессии и создадим virtualenv для тестирования


python test_local.py --session-id "c22f8021-fc7c-4341-b1f5-287c36335743" --show-summaries-only


{"session_id": "f80b25ad-1962-4727-96ae-563dee04acc8", "summary_type": "L1", "role": "user", "structured": "True"}

python index.py --mode process --session-id session123 # обработка сессии
--user-id --role --summary-type --structured


Отпределиться с архитектуров
- Что такое короткая память 
- Что такое длинная память
- Как мы собираем короткую и длинную память
R - Retrive !!! цеаочка
 1 Сгенерируй запрос на основе схемы поумнее модель
 2 С помоцью regexp удаляем комментарии есть есть и ```sql(any owher markdown) ```
A
G - Generate

Для sql вход и выход json

Делать то что
- Не меняет текущую архитектуру
- Может использоваться


Подумать когда можно
_send_audio(chat_id, audio_url=FEEDBACK_INTENT_ANSWER_MP3, title="Береги своё вдохновение...")

{"tg_id_md5": "7cd97e451774b0472c3774a1c88ff3c5" "queue", "Найди последние 10 сообщений"}



curl  -X POST \
  https://d5dotua5sk9tflh18q38.svoluuab.apigw.yandexcloud.net/retrive \
  -d '{"tg_id_md5": "7cd97e451774b0472c3774a1c88ff3c5", "queue": "Найди последние 10 сообщений"}'

curl  -X POST \
  https://functions.yandexcloud.net/d4ecdert1hbac2iggs6d/retrive \
  -d '{"tg_id_md5": "7cd97e451774b0472c3774a1c88ff3c5", "queue": "Найди последние 10 сообщений"}'

curl  -X GET \
    https://d5dotua5sk9tflh18q38.svoluuab.apigw.yandexcloud.net/healthz


# Парсинг переделать +
# Proxy переделать +
# Добавиь header авторизацию

обновлять серт за 10 дней до expire brige orcestra
openssl s_client -connect orchestra.poymoymir.ru:6432 -servername orchestra.poymoymir.ru</dev/null | openssl x509 -text -noout

openssl s_client -connect orchestra.poymoymir.ru:5432 -servername orchestra.poymoymir.ru</dev/null | openssl x509 -text -noout

openssl s_client -connect <hostname>:<port>

# pgbouncer
openssl s_client -starttls postgres \
  -connect orchestra.poymoymir.ru:6432 \
  -servername orchestra.poymoymir.ru \
  -showcerts \
  -verify 5 -verify_return_error </dev/null

openssl s_client -starttls postgres \
  -connect orchestra.poymoymir.ru:5432 \
  -servername orchestra.poymoymir.ru \
  -showcerts \
  -verify 5 -verify_return_error </dev/null

openssl x509 -in server.crt -text -noout

openssl x509 -in /opt/projects/orchestra/certs/fullchain.pem -text -noout

Занятся рефакторингом (( сейчас не поддерживаемый код
Возможно свою pip бибилиотеку сделать
рефакторинг != новый стек только классы обертки над текущим разложить по полочкам
Если кого приглашать не помймут
Мне самому будет проще делать тогда

Плюсы
- мне проще писать
- команде проще поддерживать

После разделение рефакторинга
Убрать динамическую типизацию
Расширить логрировние чтобы в yandex можно было фильтровать


terraform apply -target=yandex_function.function_flow -auto-approve

хук

Подумать архитектуру какой контекст держать
короткий -- кеш ( redis оперативка)
- последние 10 сообщений
- факты которые удалось найти о пользователе
  - Имя - sql + rag | sql + regepx
  - Какой последнее intent на чем остановились - sql
  - Сколько песен написал - sql
  - Название песен которые написал - sql
  - Основные темы песен каждой которые написал sql + rag 
  - Основные эмоции песен каждой которые написал sql + rag
  - Дата последнего контакта sql
  - Дата каждой песни sql
  - Суммари по 30 сообщений всего диалога >  темы факты эмоции sql + rag + cache
  - Векторный поиск по элементам кеша sql? emd + save + retrive + find
  

длинный -- база (postgress)

1 Проверяем кеш по userid есть ли в redis uuid?
2 Если есть то добавляем в самое начало system promt 0 Факты о пользователе
3 Если кеша нет то создаем кеш и добавляем в самое начало system promt 0 Факты о пользователе | fallback работаем без кеша?


Добавь rest интерфейс на path /retrive
{"body": {"find" : sql_part, "analyze": rag_part, "database": "poymoymir", "message": {"from": {"id": "111"}}}}
Найди все сообщения пользователя Николай и ответь какая эмоция основная
{"body": {"find": "Найди все сообщения пользователя Николай" , "analyze": ответь какая эмоция основная, "database": "poymoymir", "message": {"from": {"id": "111"}}}}

ответ
{{"result": "Основная эмоция радость", "session_id": "sessionid"} 


analyze optional
session_id ключ
result человекочитаемый, то есть очистить от тегов и прочего


pip install mindset установит папку

семантический поиск long storage postgres
семантический поиск кеш redis

Начианем для каждого сообщения хранить embdeding и телеграм message id

Типы кеша
Просто текст (key - value)
key = tenat (почти)уникальный с сочетнии с user_id тэг подумать над типами
value = any text

Какие tenat могут быть


# testing
ctx = utils.compute_message_context(history, text)
last_8_messages = ctx["last_8_messages"]
user_history_flat = utils.flatten_messages(history, 8)['user']

cache_manager.put_cache("history", tg_user_id_str, f"session|{session_uuid}", user_history_flat, 36)
cached_history = cache_manager.get_cache_by_signature("history", f"session|{session_uuid}")
if cached_history:
    logger.debug("Retrieved cached history: %s", cached_history)
# testing end

~6-10 раз redis быстрее без embdeding
0.3 медленнее если embdeding есть?

# Cache manager with LLM dependency for embeddings
cache_manager = CacheManager(config, llm, logger)
# SQLite-Vec cache manager for testing
sqlvec_cache_manager = CacheSQLVecManager(config, llm, logger)


# default embdeding(not changed) 16 messages
SQLite-Vec: Write=7.0342s, Read=0.0012s, Total=7.0354s, Found=16
Redis: Write=7.6242s, Read=0.2344s, Total=7.8586s, Found=16
PostgreSQL: Write=2.6134s, Read=0.2603s, Total=2.8736s, Found=16

Найти что нужно в базе сделать materialized view make и добавлять эу инфо


Пример ответа:

current state 
previous state -- from db or cache
compleated states -- from db or cache
confidence
reason

Алгоритм для каждого сообщения прочитать стеэс current перенести в previous записать в current
Анализируй следующий диалог и определи текущий state user flow 

https://www.mermaidchart.com/play?utm_source=mermaid_live_editor&utm_medium=toggle#pako:eNqNVttqG1cU_ZWDTcAGCT-YPFitE0xcQ6CkEJe-uKbImiNpyGhGzIxSghVQ7LpOsRtTmr6lF5fSPvShshzVinUJ-AvO-YV8Sdfe54ykmchuXnSZc_baa9_Wnt25UuDIucJc2Qu-LlWLYSw-X__SF-LWLbG6uirUL_qZGqqR6vDnG6HeqpHew89LOqebUQyrha1N-tpepCeuH4eB0yjJLbFWgIVuqa56rZ_Brg2gnurj98nHO-HSnau_1T_iXeulUL8a-FfJV0-33rX-vOqLbYIsRo8eFGsGEIwIcoRvQAl8DPQJEwPwsbpgtm046-L_ibGXtSB2A3_dfQwM9nWuW3pf_YtLQyB0heoI_b0aAPZb-H4xdrshpef6FfYMtn9R8ELv6SOhDwHQ4bA6xiexGVKsHCcSdjfh78iSBdrllDDXfX1IEaie4Jx2VFfv3X3KOW1UKjKK79eK-EplEddHYM2Bj9QZHrbVhT7KcTYRexvYbX2gejlBrChXuDeAwRBnCDXJiHVxr-p6TjUInGu9dMYYZL2njwXOwTQJPAX3WVyV4fVQIHhORVFDBM9QQM6jN6gW5-RE7xMeIwZ-ZdP0lvoZMR1SfuEOJl1uyp7pNut5ww2j-FPX5_pmXVOKyayFaPZRXOJOLaQujT8u0IPgoax7T3bVT3x8bKpySdbqMlWXNT-gOG_yZkOa6S2Jbl0-TgL8jcpIswGP3I2ZIIuO84UMI3L3kuqeDBK5Aiqu96kmtmsdxzK81qarv9M_zDa9Vw3CRjTLiCraI2aYlYyjTzxZk358g6sRMoQmpCGDP3QTBg9eJ4GOJ-6hjOqBz7xP2WdbP4cpz3SmKrZ2gS93MdQMRFJwwf5RbhjSfLepegY9krUdT24i-1uMfwa4FuDaU0wKPEwsIOfgdZ_kbIlTuWSSA2Ey8zbS37D9IJmMDnJKoeYBTP1wiVpuM8laI3JLa2FIbl8h7RhacsuSRdLaFVNo_USWLJUpxWM_PHuko8c5wTwH6m2OlHBoeg34NsHQKeO_7PpFT5L3P6wY9A04DzexbfMEQruozOQm994QJ-M_IgC9t8S2r0lozRnpem6CmiadLpypdjmW4Ybru1F1y-gybvcpF9kSQrfGuRjpA9a94YTmDBrkj1dO8sT6jOqy5BY9TF4MbYVXmr0zJtdGYtmMpfWIyirYH-GMSLaIBz-2WHFQp9UX1GlMp_fmj5yys6TAAOvOgBrv0MZOJSzWq6LiBTtF76vIkPtAFKYCENeTfkkuLKjf8fS5qfLiojl0gsZOjKNTq-Q2p-ZY-k6a_Sl08gQ16KWWvMjn70yWO_-ze5l_T-3YzMpNrtoVyH8nGzG9H-mwiUU7NF1Affbiqt9Mr0RGGC-IGwDs4kpBjFfe_6JMLaZu8-abQ36ZGCb7iaaG-migj7ijuS2bqS2ZSUpm6RlumdWWJM5uqvTesjxIy5szFtU42GTrzLLG8Dczl7LLytC26yiJIZFsQxBynJHyFLfMepp5lYkkQPSdRTBCnPV_3e30lrrZil1PLwq-nsg3_zFaamAmCmYyPK0u5gnUYTxd6tQIN78i8OspvRClZ1wfvDfj6g3ZlzzQWpdlqxKg4XmF-XK5nIswk49kYX5lZcX-zjvFCK_zYfFJ4ba4nSsFXhAW5peXlz8aIyWCkWNtsKA4nnv6HyT2ShM


def render_detect_state_document(self, config_path: str = "knowledge_bases/templates/detect_state.txt.yaml", template_path: str = "knowledge_bases/templates/detect_state.txt.j2", extra_args: Optional[Dict[str, Any]] = None) -> str:

Начало еще раз
https://chatgpt.com/c/68b18df1-d0b4-8328-8c12-5a9712704268

За несколько шагов мы: вспомним чувство → накинем первую строку песни → соберём структуру → допишем текст → красиво оформим → подберём музыкальный стиль.
Если захочешь — сделаем аудио. Как к тебе обращаться?

"response_format": { "type": "json_object" },

LLM-SUMMARY
https://www.mermaidchart.com/play?utm_source=mermaid_live_editor&utm_medium=toggle#pako:eNp1Vltz4jYU_iuazGwnmdwM4Yks2UkCbdJisoNJ2amXYRRLGA2y5EoyhDL733t0MZhu8xLF5-jcv--I3UkmCT3pniy43GRLrAya9L8LhD59Qr1eDz2xfHnJ6ZpyNBzGSFdFgRX7BxsmBSpZSTkTFG2YWaKnaWxNvotg_ixyqu09-30fnaaJAfezM_fZSsc0o2xNUUG1xjmdOXE7Pe0_dBETmkImQaXPvPImPR1TwnQXlZVeIgUOhIHYgshNuNJJX0uCDUWZrIShSiPNREZtbl1E5oXOL-AwcuUOVoSwEbq8vIOk_NH2x40_OvuCJorlOVUohwBWpKu3XOFyiSZpraJrzCvXHOcYIcIgTdesyYOXTAr8vovxOzLe5gv6_Kau71xyd734_ts8Tn5L0MvYJ-pFk5c_BqNaCGmHi88jKzKyZNmcKLYwd73J0_hHHYiJXczEB4GeRz8FAtH_BLIXn0d7pxicYlFhjqRCOltSUnFK9kHcPSqIH4droa04_APZBInwbQ06JKRTPEZpsmLlHmf0FjSqgGCKlnw7c5f-AiwNBPFIsq6OHDS9bql20ocofZRFWVlgVEYuFnNGZk3rw8X9tKcOV0hT7gd4NPFpmjg5koJvIba43GdMAiI_BMC0lVqqdHsAUrEGjDq86CvvYTtfbgo7ojpFMGinIRmwqTnhOccIunPEw4LYj8-9_xQI1jfpr4wDFyBNpum13mpDi1sIzl0FdM0ItRxhRNcmnX27mIBjvsTANwm52kvo3CZugHtOPmsM_METaeqJNPVEmnoiTQ9EepQiq5SCqFv0C7ikRSmN_bL6YbS7z_6uoG2Iy2yFksFk9O0AiG7GiMPY1INrGHmjBgaGrfReSLOEdDdSreBQlRBM5AiU9J2ZGkYHy3r-_WjXr0rOMrtD_Bxda22hFtrWon9sAcG4ophsUQMCoFAAEKx9Ec2A_WaqSZQ-VIwTt1xdr7v1XgMI2FaHJM4Rx9rUIajVGCm5n8S7me17mzQ39BFmk_SnDf4hRpNW-oi53_m1R6rC9aS9-xNzQNvvycsIldSvgQJ_CTsiuYHlbtTWQ1TDZsgs_EoFmDJuawChuZ1OkyhJJ31ewG0GYZlYuwDQIS5zRJWS6uKooxd-kA3sJR57icde0naydrPXNx9qOo35eE093q_R0YvEhJGNISygpB7Q77x1deV5d1EvwosGdc4O4xlKkV9CNwogciGVQ3wc7QbvRmEg4wL-eLchytY39asvLo78_WaGcctnWJXhzbRu59myEquwJGjxRgkB_GuHZYPz8KLGTSi-RrWf8IA2dhNsQWPXTK8uUlErqR_Z4K0V_Bx4DvMSVWm_xlEKoDjM7xZ5B5IDAsQtgKOC3xHuea9h4Zy--sLH0X5CwfeAMHMNwDVbIKcg8DMkt5pBtIv9hkTgywAVAW8EAtt_YYiwbOrOIoXhF4rvb3jzB5H30ezvAPobY7VCeLEAloCb2h5r5BLw5Q98-YM21LnfBIG1NC-A0triWdBN7eAWQfXwAQzSlFC_sAftfRdPfvwLCrMZ7Q



Не работает классификация
1 Нужно динимически делать схемы json из базовой передавать labels или переделать на статические шаблоны

ВАЖНО критически определять состоняие стейта intrnt точно на это будет лгика завязаны уменьшения запросов
https://chatgpt.com/c/68ad7673-3210-8328-b69e-0c2354d743e3
1 Структура базы данных, структура данных
2 User flow поиска
3 yaml таблица с intents желательо на опыте пользователей!!!


После
Song request detected
Почему то нет lyrics
{"errorMessage": "'lyrics'", "errorType": "KeyError", "stackTrace": ["  File \"/function/runtime/runtime.py\", line 231, in handle_event\n    result = h(r.event, r.context)\n", "  File \"/function/code/index.py\", line 213, in handler\n    lyrics = get_song[\"lyrics\"]\n"]}
Проверить порядок генерации

Сохранили суммаризацию сообщений пользователя-Сохранили суммаризацию сообщений пользователя-Сохранили суммаризацию сообщений
отправляется пользователю а не сохраняется только в базу ассистент


    pinned_msg_id = db.get_session_pinned_message_id(session_uuid)
    if pinned_msg_id:
        if pinned_msg_id:
            # Update the existing pinned message
            update_text = "ПойМойМир"
            # create a telegram makup variable that contains inline keyboard with 1 button that pin to message
            markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "Навигация",
                            "url": f"https://t.me/c/{str(chat_id)}/{pinned_msg_id}" # to dynamic telegraph
                        }
                    ]
                ]
            }
            telegram_bot.edit_message_text(chat_id, pinned_msg_id, update_text, markup=markup)
        else:
            # Send and pin a new message
            pin_text = f"🎵 Мы написали первую песню!\n\nПоздравляю!\n\nЯ сохраню её песню в навигации"
            pinned_msg_id = telegram_bot.send_and_pin_message(chat_id, pin_text)
            if pinned_msg_id:
                # Save the pinned message ID to the session
                db.update_session_pinned_message_id(session_uuid, pinned_msg_id)


telegraph

https://api.telegra.ph/createAccount?short_name=poymoymir&author_name=PoyMoyMir

1 Создать run ones? ссылку
2 Обновлять
 - Новая песня завершена
 - Summary user style
 - Изменение правил


"ok":true,"result":{"short_name":"test","author_name":"sandbox","author_url":"","access_token":"3e52657449f1054c210291c7a2e5712eff217c8b129d27996a92c6603ad3","auth_url":"https:\/\/edit.telegra.ph\/auth\/QxMJBwHPkM5uWsaw9KutKcyK3zukuZEluo23SKRcuW"}}



System Telegraph pages initialized: {'privacy_policy': 'https://telegra.ph/Politika-obrabotki-personalnyh-dannyh-09-06-3', 'discussion_restrictions': 'https://telegra.ph/Zaprety-obsuzhdeniya-09-06-2', 'song_creation_journey': 'https://telegra.ph/Put-sozdaniya-pesni-v-PojMojMir-09-06-2', 'menu': 'https://telegra.ph/Menyu-dokumentov-09-06-2'}
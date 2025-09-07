# MindScribe Local Testing Guide

Этот документ описывает как настроить и использовать локальное тестирование для MindScribe.

## Настройка окружения

### 1. Создание виртуального окружения

```bash
cd mindscribe
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Скопируйте `env.example` в `.env` и заполните необходимые значения:

```bash
cp env.example .env
# Отредактируйте .env файл с вашими настройками
```

Минимально необходимые переменные:
- `operouter_key` - API ключ для OpenRouter
- `database_url_dev` - строка подключения к PostgreSQL

## Использование тестового скрипта

### Базовое тестирование

Тестирование существующей сессии:
```bash
python tests/test_local.py --session-id "your-session-id"
```

Тестирование с созданием mock данных:
```bash
python tests/test_local.py --session-id "test-session-123" --create-mock
```

### Расширенные опции

Тестирование с указанием пользователя:
```bash
python tests/test_local.py --session-id "test-session-123" --user-id "test-user-456" --create-mock
```

Показать только существующие саммари без обработки:
```bash
python tests/test_local.py --session-id "test-session-123" --show-summaries-only
```

Показать детали конкретного типа саммари:
```bash
python tests/test_local.py --session-id "test-session-123" --summary-type "L1"
```

Тестирование handler функции:
```bash
python tests/test_local.py --session-id "test-session-123" --test-handler
```

### Все опции

```bash
python tests/test_local.py --help
```

## Запуск pytest тестов

Запуск всех тестов:
```bash
pytest tests/ -v
```

Запуск конкретного класса тестов:
```bash
pytest tests/test_mindscribe.py::TestProcessingState -v
```

Запуск с покрытием кода:
```bash
pip install pytest-cov
pytest tests/ --cov=index --cov-report=html
```

## Структура тестирования

### Mock данные
Тестовый скрипт может создать mock сессию с 20 сообщениями (10 от пользователя, 10 от ассистента) для тестирования всех уровней саммари.

### Тестируемые компоненты

1. **Состояние обработки** (`TestProcessingState`)
   - Проверка существования состояния
   - Логика определения необходимости обработки

2. **Функции саммари** (`TestSummaryFunctions`)
   - Создание базовых и расширенных саммари
   - Получение саммари по ролям

3. **LLM интеграция** (`TestLLMIntegration`)
   - Запросы к AI API
   - Обработка ошибок

4. **Логика обработки** (`TestProcessingLogic`)
   - Обработка разных уровней (L1-L4)
   - Иерархическая логика

5. **Handler функция** (`TestHandler`)
   - Cron триггеры
   - Прямые запросы
   - Обработка ошибок

### Примеры вывода

При успешном тестировании вы увидите:

```
2024-01-20 10:30:15 - MindScribeTest - INFO - Testing session processing for session: test-session-123
2024-01-20 10:30:15 - MindScribeTest - INFO - Found 40 messages in session
2024-01-20 10:30:15 - MindScribeTest - INFO - User messages: 20
2024-01-20 10:30:15 - MindScribeTest - INFO - Assistant messages: 20
2024-01-20 10:30:15 - MindScribeTest - INFO - Starting summary processing...
2024-01-20 10:30:18 - MindScribeTest - INFO - Summary processing completed!

=== SUMMARY RESULTS ===

--- L1 Summaries ---
User L1 summaries: 2
Assistant L1 summaries: 2

--- L2 Summaries ---
User L2 summaries: 1
Assistant L2 summaries: 1

--- LALL Summaries ---
User LALL summaries: 1
Assistant LALL summaries: 1
```

## Отладка

### Включение debug логов

Установите `DEBUG=1` в .env файле или:
```bash
DEBUG=1 python tests/test_local.py --session-id "test-session-123"
```

### Проверка подключения к базе

```python
from index import get_conn, query_one

# Тест подключения
try:
    conn = get_conn()
    result = query_one("SELECT 1 as test")
    print("Database connection OK:", result)
except Exception as e:
    print("Database connection failed:", e)
```

### Проверка API ключа

```python
from index import llm_conversation

# Тест API
try:
    result = llm_conversation([{"role": "user", "content": "test"}], "Test prompt")
    print("API connection OK:", result)
except Exception as e:
    print("API connection failed:", e)
```

## Troubleshooting

### Частые проблемы

1. **База данных недоступна**
   - Проверьте `database_url_dev` в .env
   - Убедитесь что PostgreSQL запущен
   - Проверьте права доступа

2. **API ключ недействителен**
   - Проверьте `operouter_key` в .env
   - Убедитесь что у вас есть кредиты на OpenRouter

3. **Сессия не найдена**
   - Используйте `--create-mock` для создания тестовых данных
   - Проверьте что session_id существует в базе

4. **Недостаточно сообщений**
   - Минимум 15 сообщений нужно для обработки L1 саммари
   - Используйте mock данные для тестирования

### Логи

Все логи сохраняются в консоль с метками времени. Для сохранения в файл:

```bash
python tests/test_local.py --session-id "test-session-123" 2>&1 | tee test.log
```

## Производственное тестирование

Для тестирования на продакшн данных:

1. Установите `env=prod` в .env
2. Укажите `database_url_prod`
3. Используйте реальные session_id без `--create-mock`

**Внимание:** Будьте осторожны с продакшн данными!

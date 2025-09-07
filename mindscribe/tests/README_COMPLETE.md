# MindScribe - Intelligent Summary Processing System

MindScribe - это интеллектуальная система для создания иерархических саммари сообщений в чат-сессиях с использованием ИИ.

## 🎯 Основные возможности

- **Иерархическое саммаризация**: L1 → L2 → L3 → L4 → LALL
- **Разделение по ролям**: Отдельная обработка для пользователей и ассистентов
- **Интеллектуальное состояние**: Отслеживание обработанного контента
- **Батчевая обработка**: До 3 сессий одновременно
- **Cron поддержка**: Автоматическая обработка по расписанию
- **Прокси поддержка**: Работа через HTTP/HTTPS прокси

## 📋 Структура проекта

```
mindscribe/
├── index.py                # Основной код Lambda функции
├── system_prompt.txt       # Системный промпт для ИИ
├── requirements.txt        # Python зависимости
├── env.example            # Пример конфигурации
├── test.env               # Тестовая конфигурация
├── init.sql               # Первичная схема БД
├── migrate-1.sql          # Базовая миграция
├── migrate-2.sql          # Расширенная схема с состоянием
├── test_local.py          # Локальное тестирование
├── test_mindscribe.py     # Pytest тесты
├── run_tests.sh           # Тестовый runner
├── venv/                  # Виртуальное окружение
├── README_testing.md      # Подробное руководство по тестированию
└── README_COMPLETE.md     # Этот файл
```

## 🚀 Быстрый старт

### 1. Настройка окружения

```bash
# Клонирование и переход в директорию
cd mindscribe

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Создание конфигурации
cp env.example .env

# Редактирование конфигурации
nano .env  # Укажите реальные API ключи и БД
```

### 3. Тестирование

```bash
# Запуск всех тестов
./run_tests.sh

# Только юнит-тесты
./run_tests.sh --unit-only

# Тестирование конкретной сессии
python test_local.py --session-id "your-session-id" --create-mock
```

## 🏗️ Архитектура системы

### Иерархия саммари

```
Сообщения (Messages)
         ↓
    L1 (15 сообщений)
         ↓
    L2 (4 L1 саммари)
         ↓
    L3 (4 L2 саммари)
         ↓
    L4 (4 L3 саммари)
         ↓
    LALL (общий саммари)
```

### Разделение по ролям

Каждая роль (`user`, `assistant`) обрабатывается независимо:
- Отдельные саммари для пользователей и ассистентов
- Независимое отслеживание состояния
- Параллельная обработка

### Состояние обработки

Система отслеживает:
- Последнее количество обработанных сообщений
- Статус обработки (pending/processing/completed/error)
- Временные метки последней обработки

## 🔧 API использование

### Handler функция

```python
# Cron триггер (автоматическая обработка)
event = {}  # или {"trigger_type": "timer"}
result = handler(event, context)

# Прямая обработка сессии
event = {
    "body": {
        "session_id": "session-123",
        "user_id": "user-456"  # опционально
    }
}
result = handler(event, context)

# Получение конкретного типа саммари
event = {
    "body": {
        "session_id": "session-123",
        "summary_type": "L1"
    }
}
result = handler(event, context)
```

### Основные функции

```python
# Обработка саммари для сессии
process_session_summary(session_id, user_id)

# Получение саммари по ролям
summaries = get_summaries_by_role(session_id, "L1", "user")

# Проверка необходимости обработки
needs = needs_processing(session_id, "L1", "user", 30)

# Обновление состояния
update_processing_state(session_id, "L1", "user", 30, "completed")
```

## 🧪 Тестирование

### Автоматические тесты

```bash
# Полный набор тестов
./run_tests.sh

# Конкретные компоненты
pytest test_mindscribe.py::TestProcessingState -v
pytest test_mindscribe.py::TestLLMIntegration -v
```

### Ручное тестирование

```bash
# С mock данными
python test_local.py --session-id "test-123" --create-mock

# Реальная сессия
python test_local.py --session-id "real-session-id"

# Только просмотр саммари
python test_local.py --session-id "session-id" --show-summaries-only

# Детали конкретного типа
python test_local.py --session-id "session-id" --summary-type "L1"
```

## 🗄️ База данных

### Основные таблицы

**summary** - хранение саммари:
```sql
- id (UUID) - уникальный идентификатор
- session_id (TEXT) - идентификатор сессии  
- user_id (TEXT) - идентификатор пользователя
- role (TEXT) - роль (user/assistant/system)
- content (TEXT) - содержимое саммари (JSON)
- type (TEXT) - тип саммари (LALL/L1/L2/L3/L4)
- group_id (TEXT) - идентификатор группы
- source_range (TEXT) - диапазон исходных данных
- message_count (INTEGER) - количество сообщений
- created_at (TIMESTAMPTZ) - время создания
- processed_at (TIMESTAMPTZ) - время обработки
```

**summary_processing_state** - состояние обработки:
```sql
- id (UUID) - уникальный идентификатор
- session_id (TEXT) - идентификатор сессии
- summary_type (TEXT) - тип саммари
- role (TEXT) - роль
- last_processed_at (TIMESTAMPTZ) - время последней обработки
- last_message_count (INTEGER) - последнее количество сообщений
- processing_status (TEXT) - статус обработки
```

### Миграции

```bash
# Применение миграций
psql -d your_database -f init.sql
psql -d your_database -f migrate-1.sql  
psql -d your_database -f migrate-2.sql
```

## 🌐 Развертывание

### Yandex Cloud Function

1. **Подготовка архива**:
```bash
zip -r mindscribe.zip index.py system_prompt.txt requirements.txt
```

2. **Создание функции**:
```bash
yc serverless function create --name mindscribe
yc serverless function version create \
  --function-name mindscribe \
  --runtime python313 \
  --entrypoint index.handler \
  --memory 256m \
  --execution-timeout 300s \
  --source-path mindscribe.zip
```

3. **Настройка переменных окружения**:
```bash
yc serverless function version create \
  --function-name mindscribe \
  --environment operouter_key=your_key \
  --environment database_url_prod=your_db_url \
  --environment env=prod
```

### Cron триггер

```bash
yc serverless trigger create timer \
  --name mindscribe-timer \
  --cron-expression "0 */6 * * *" \
  --invoke-function-name mindscribe
```

## 📊 Мониторинг

### Логи

```bash
# Просмотр логов функции
yc serverless function logs mindscribe

# Фильтрация по уровню
yc serverless function logs mindscribe --filter 'level=ERROR'
```

### Метрики

Отслеживаемые метрики:
- Количество обработанных сессий
- Время выполнения обработки
- Ошибки API вызовов
- Состояния обработки

## 🔐 Безопасность

### Переменные окружения

```bash
# Критичные переменные
operouter_key=*********    # API ключ OpenRouter
database_url_prod=******   # Продакшн БД (зашифровано)

# Опциональные
proxy_url=http://proxy:8080  # Прокси (если нужен)
```

### Права доступа

- Минимальные права для Lambda функции
- Сетевая изоляция через VPC
- Шифрование переменных окружения

## 🤝 Разработка

### Workflow

1. Локальная разработка с тестами
2. Проверка через `run_tests.sh`
3. Коммит и push в репозиторий
4. Автоматическое развертывание (CI/CD)
5. Мониторинг продакшн логов

### Добавление новых функций

1. Обновите `index.py`
2. Добавьте тесты в `test_mindscribe.py`
3. Обновите миграции БД если нужно
4. Протестируйте локально
5. Обновите документацию

## 📈 Производительность

### Оптимизации

- Батчевая обработка до 3 сессий
- Кэширование состояния обработки  
- Эффективные SQL запросы с индексами
- Retry логика для API вызовов

### Масштабирование

- Горизонтальное: увеличение количества Lambda функций
- Вертикальное: увеличение памяти/CPU функции
- Базы данных: read replicas для чтения саммари

## 🐛 Troubleshooting

### Частые проблемы

1. **Ошибки подключения к БД**
   - Проверьте `database_url`
   - Убедитесь в доступности БД
   - Проверьте сетевые права

2. **API ошибки**
   - Проверьте `operouter_key`
   - Убедитесь в наличии кредитов
   - Проверьте прокси настройки

3. **Ошибки обработки**
   - Проверьте логи функции
   - Убедитесь в корректности данных
   - Проверьте состояние обработки

### Логирование

Все ошибки логируются с контекстом:
```json
{
  "message": "Error processing session session-123: API timeout",
  "level": "ERROR", 
  "logger": "MindScribeLogger",
  "session_id": "session-123",
  "error_type": "APITimeout"
}
```

## 📞 Поддержка

Для вопросов и проблем:
1. Проверьте логи и документацию
2. Запустите локальные тесты
3. Создайте issue с подробным описанием

---

**MindScribe** - Делаем саммаризацию интеллектуальной! 🧠✨

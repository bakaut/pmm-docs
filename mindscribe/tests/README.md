# MindScribe Testing

Структура тестирования для проекта MindScribe.

## Структура папки tests/

```
tests/
├── __init__.py              # Инициализация пакета
├── conftest.py              # Общие pytest фикстуры
├── test_mindscribe.py       # Unit тесты основной функциональности
├── test_local.py            # Скрипт локального тестирования
├── README.md                # Данный файл
└── README_testing.md        # Детальное руководство по тестированию
```

## Быстрый старт

### Запуск всех тестов через скрипт
```bash
./run_tests.sh
```

### Запуск только unit тестов
```bash
./run_tests.sh --unit-only
```

### Запуск только интеграционного теста
```bash
./run_tests.sh --integration-only
```

### Локальное тестирование конкретной сессии
```bash
python tests/test_local.py --session-id "your-session-id" --create-mock
```

### Запуск pytest напрямую
```bash
# Все тесты
pytest tests/ -v

# Конкретный класс тестов
pytest tests/test_mindscribe.py::TestProcessingState -v
```

## Типы тестов

### Unit тесты (test_mindscribe.py)
- **TestProcessingState** - состояние обработки сообщений
- **TestSummaryFunctions** - функции создания саммари
- **TestLLMIntegration** - интеграция с AI API
- **TestProcessingLogic** - логика обработки разных уровней
- **TestHandler** - главная handler функция
- **TestIntegration** - интеграционные тесты

### Локальное тестирование (test_local.py)
Интерактивный скрипт для тестирования с реальными данными:
- Создание mock данных для тестирования
- Тестирование с существующими сессиями
- Детальный вывод результатов обработки
- Проверка всех уровней саммари (L1-L4, LALL)

## Фикстуры (conftest.py)

Общие фикстуры доступные во всех тестах:
- `mock_env` - моковые переменные окружения
- `mock_db_functions` - моковые функции базы данных
- `mock_llm_response` - структура ответа от LLM
- `sample_messages` - примеры сообщений для тестов
- `sample_session_data` - данные тестовой сессии
- `sample_summary_data` - структура саммари

## Настройка окружения

1. Создайте виртуальное окружение:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Скопируйте конфигурацию:
```bash
cp env.example .env
# Заполните необходимые переменные в .env
```

## Переменные окружения для тестирования

Минимально необходимые:
- `operouter_key` - API ключ для OpenRouter
- `database_url_dev` - строка подключения к PostgreSQL

Опциональные:
- `DEBUG=1` - включить debug логирование
- `TEST_USER_ID` - ID пользователя для тестовых данных

## Детальная документация

Смотрите [README_testing.md](README_testing.md) для подробного руководства по:
- Настройке окружения
- Всем доступным опциям тестирования
- Отладке и troubleshooting
- Структуре mock данных
- Примерам использования

## Continuous Integration

Для CI/CD используйте:
```bash
# В Docker или CI окружении
./run_tests.sh --unit-only
```

Unit тесты не требуют внешних зависимостей (базы данных, API) и работают с моками.

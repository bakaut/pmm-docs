# PoyMoyMir Telegram Bot Testing Framework

## Overview
This testing framework provides comprehensive automated tests for the PoyMoyMir Telegram bot, simulating real user interactions to ensure all functionality works correctly.

## Test Structure
```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # pytest configuration and fixtures
├── requirements.txt            # Test-specific dependencies
├── README.md                   # Test documentation
├── TEST_PLAN.md                # Detailed test plan
├── run_tests.py                # Test runner script
├── test_config.py              # Test configuration and helpers
├── test_basic.py               # Basic setup verification tests
├── test_imports.py             # Module import tests
├── test_telegram_bot_unit.py   # Unit tests for Telegram bot functionality
├── test_telegram_e2e.py        # End-to-end tests for bot interactions
└── test_user_journey.py        # Complete user journey simulations
```

## Key Features

### 1. Comprehensive Test Coverage
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Simulate complete user workflows
- **User Journey Tests**: Test complete interaction scenarios

### 2. Realistic Test Data
- Authentic Telegram message structures
- Realistic user messages and interactions
- Proper callback query formats
- Suno API callback simulations

### 3. Robust Mocking Strategy
- All external dependencies are mocked
- Database operations are simulated
- LLM responses are controlled
- External API calls are intercepted

### 4. Flexible Test Execution
- Run individual tests or test suites
- Verbose output for debugging
- Coverage reporting
- Easy dependency management

## Test Categories

### Unit Tests (`test_telegram_bot_unit.py`)
Tests individual functions and methods of the TelegramBot class:
- Initialization
- Markdown escaping
- Text processing
- Message chunking

### End-to-End Tests (`test_telegram_e2e.py`)
Tests complete bot functionality with mocked dependencies:
- General conversation flow
- Song generation workflow
- Confusion detection and handling
- Feedback collection
- Callback query processing
- Suno API callback handling

### User Journey Tests (`test_user_journey.py`)
Tests complete user interactions from start to finish:
- Initial contact through conversation
- Song request and generation
- Feedback collection
- Confusion intervention scenarios

## Running Tests

### Prerequisites
```bash
# Install test dependencies
pip install -r tests/requirements.txt
```

### Basic Test Execution
```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_telegram_bot_unit.py

# Run specific test class
python -m pytest tests/test_telegram_e2e.py::TestTelegramE2E

# Run specific test method
python -m pytest tests/test_telegram_e2e.py::TestTelegramE2E::test_general_conversation
```

### Using the Test Runner Script
```bash
# Install dependencies and run all tests
python tests/run_tests.py --install-deps

# Run with coverage report
python tests/run_tests.py --coverage

# Run specific test
python tests/run_tests.py --test "test_general_conversation"

# Run with verbose output
python tests/run_tests.py --verbose
```

## Test Configuration

### Environment Variables
Tests use mock environment variables to avoid external dependencies:
- `bot_token`: Test bot token
- `database_url`: Test database connection
- `operouter_key`: Test LLM API key

### Test Data
Defined in `test_config.py`:
- User and chat IDs
- Sample messages for different scenarios
- Callback query data
- Expected responses
- Test song data

## Continuous Integration
The test framework is designed to integrate with CI/CD pipelines:
- Fast execution times
- No external dependencies
- Clear pass/fail indicators
- Detailed error reporting

## Maintenance
To maintain the test suite:
1. Update mocks when core logic changes
2. Add new test cases for new features
3. Review and update test data regularly
4. Monitor test coverage metrics
5. Refactor tests as the codebase evolves

## Benefits
- **Reliability**: Tests catch regressions before deployment
- **Speed**: Fast feedback on code changes
- **Coverage**: Comprehensive testing of all bot functionality
- **Maintainability**: Clear structure and documentation
- **Scalability**: Easy to add new tests as features are added
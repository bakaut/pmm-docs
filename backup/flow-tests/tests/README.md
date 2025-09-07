# PoyMoyMir Telegram Bot Tests

This directory contains automated end-to-end tests for the PoyMoyMir Telegram bot that simulate real user interactions.

## Test Structure

- `test_basic.py` - Basic tests to verify the test setup
- `test_telegram_e2e.py` - End-to-end tests for individual bot functionalities
- `test_user_journey.py` - Tests that simulate complete user journeys
- `test_config.py` - Test configuration and helper functions
- `conftest.py` - pytest configuration and fixtures
- `TEST_PLAN.md` - Detailed test plan and scenarios
- `run_tests.py` - Script to run tests with various options
- `requirements.txt` - Test-specific dependencies

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=flow --cov-report=html
```

### Using the Test Runner Script

```bash
# Install dependencies and run all tests
python tests/run_tests.py --install-deps

# Run with coverage
python tests/run_tests.py --coverage

# Run specific test
python tests/run_tests.py --test "test_general_conversation"

# Run with verbose output
python tests/run_tests.py --verbose
```

## Test Scenarios

The tests cover the following scenarios:

1. **General Conversation Flow** - Normal chat interactions
2. **Song Generation Flow** - Complete song creation process
3. **Confusion Handling** - Detection and response to user confusion
4. **Feedback Collection** - Gathering user feedback on generated songs
5. **Callback Query Handling** - Processing inline button interactions
6. **Suno API Callbacks** - Handling song generation completion notifications

## Writing New Tests

1. Use the existing test fixtures in `conftest.py` for common mock objects
2. Follow the pattern in `test_telegram_e2e.py` for individual functionality tests
3. Use `test_user_journey.py` as a template for complete user journey tests
4. Add new test data to `test_config.py` as needed
5. Document new test scenarios in `TEST_PLAN.md`

## Mocking Strategy

Tests use mocking to simulate external dependencies:

- **Telegram API** - Mocked using `unittest.mock.MagicMock`
- **LLM APIs** - Mocked to return predictable responses
- **Suno API** - Mocked to simulate song generation
- **Database** - Mocked to avoid external database dependencies
- **External Services** - All external HTTP calls are mocked

## Continuous Integration

Tests should be integrated into the CI pipeline to run automatically on:
- Pull requests
- Main branch commits
- Scheduled runs (daily)

## Test Data

The tests use realistic but synthetic data:
- User IDs and chat IDs are test values
- Message content covers typical user interactions
- Callback data matches real Telegram/Suno API responses
- All URLs are example URLs

## Troubleshooting

If tests fail:

1. Check that all dependencies are installed: `pip install -r tests/requirements.txt`
2. Verify the test environment matches the development environment
3. Check that mock responses match expected data structures
4. Ensure all required environment variables are set or mocked
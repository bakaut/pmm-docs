#!/bin/bash

# Demo test runner for PoyMoyMir Telegram bot tests
# This script demonstrates different ways to run the tests

echo "========================================="
echo "PoyMoyMir Telegram Bot Test Runner Demo"
echo "========================================="

echo
echo "1. Running basic setup tests..."
python -m pytest tests/test_basic.py -v

echo
echo "2. Running unit tests..."
python -m pytest tests/test_telegram_bot_unit.py -v

echo
echo "3. Running all tests..."
python -m pytest tests/ -v

echo
echo "4. Running tests with coverage..."
python -m pytest tests/ --cov=flow --cov-report=term-missing

echo
echo "5. Running specific test..."
python -m pytest tests/test_telegram_bot_unit.py::TestTelegramBotUnit::test_init -v

echo
echo "========================================="
echo "Test run completed!"
echo "========================================="
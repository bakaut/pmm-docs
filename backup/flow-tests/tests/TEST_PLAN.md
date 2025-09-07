# Telegram Bot End-to-End Test Plan

## Overview
This document outlines the end-to-end testing strategy for the PoyMoyMir Telegram bot. The tests simulate real user interactions with the bot to ensure all functionality works as expected.

## Test Scenarios

### 1. General Conversation Flow
- **Description**: Test normal conversation between user and bot
- **Steps**:
  1. User sends a general message ("Hello")
  2. Bot processes the message through intent detection
  3. Bot responds with a conversational reply
- **Expected Result**: Bot sends a response without triggering special flows

### 2. Song Generation Flow
- **Description**: Test the complete song generation workflow
- **Steps**:
  1. User requests a song ("Please create a song for me")
  2. Bot detects "finalize_song" intent
  3. Bot extracts song parameters using Suno preparation prompt
  4. Bot calls Suno API to generate song
  5. Bot sends confirmation message to user
- **Expected Result**: Song generation is initiated and user receives confirmation

### 3. Confusion Handling Flow
- **Description**: Test the confusion detection and response mechanism
- **Steps**:
  1. User sends a confused message ("I don't understand what's happening")
  2. Bot detects high "Растерянность" emotion (intensity > 90)
  3. Bot sends either text response or audio message
- **Expected Result**: User receives supportive response when confused

### 4. Feedback Flow
- **Description**: Test the feedback collection after song delivery
- **Steps**:
  1. User sends feedback after receiving a song ("I loved that song!")
  2. Bot detects "feedback" intent
  3. Bot sends feedback collection message
- **Expected Result**: Feedback prompt is sent to user

### 5. Callback Query Handling
- **Description**: Test inline button interactions
- **Steps**:
  1. User clicks on inline button (e.g., "silence_room")
  2. Bot receives callback query
  3. Bot processes callback and sends appropriate response
- **Expected Result**: Callback is handled and user receives appropriate response

### 6. Suno API Callback Handling
- **Description**: Test handling of completed song generation from Suno
- **Steps**:
  1. Suno API sends completion callback
  2. Bot processes callback data
  3. Bot updates user with song completion
- **Expected Result**: Song completion is processed correctly

## Test Data

### User Messages for Testing
- General conversation: "Hello", "How are you?", "What can you do?"
- Song requests: "Create a song", "Generate music", "Sing me something"
- Confusion indicators: "I'm confused", "Don't understand", "Help me"
- Feedback: "I love it", "That was amazing", "Not my favorite"

### Callback Queries for Testing
- `hug_author`: Simulate user appreciation
- `silence_room`: Simulate user wanting quiet space

## Test Execution

### Running Tests
```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=flow --cov-report=html
```

### Test Environment
- Tests use mocking to avoid external dependencies
- All external services (Telegram API, Suno API, LLMs) are mocked
- Database operations are mocked but maintain realistic interfaces

## Continuous Integration
Tests should be integrated into the CI pipeline to run automatically on:
- Pull requests
- Main branch commits
- Scheduled runs (daily)

## Test Maintenance
- Update mocks when core logic changes
- Add new test cases for new features
- Review and update test data regularly
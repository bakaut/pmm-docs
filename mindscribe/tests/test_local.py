#!/usr/bin/env python3
"""
MindScribe Local Testing Script

This script allows local testing of the MindScribe summary functionality
for specific sessions without deploying to the cloud.

Usage:
    python test_local.py --session-id SESSION_ID [--user-id USER_ID] [--summary-type TYPE]
    python test_local.py --help
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add parent directory to path so we can import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file if it exists
load_dotenv()

# Import our MindScribe functions
from index import (
    process_session_summary,
    get_session_messages,
    get_summaries,
    get_summaries_by_role,
    process_messages_for_summary,
    handler
)

# Configure logging for testing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MindScribeTest')

def validate_environment():
    """Validate that required environment variables are set"""
    required_vars = [
        'operouter_key',
        'database_url_dev'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file based on env.example and fill in the required values")
        return False
    
    return True

def create_mock_session_data(session_id: str, user_id: str, message_count: int = 20):
    """
    Create mock session data for testing if session doesn't exist
    
    Args:
        session_id: Session identifier
        user_id: User identifier  
        message_count: Number of mock messages to create
    """
    from index import execute, query_one
    
    # Check if session already exists
    existing_session = query_one("SELECT id FROM conversation_sessions WHERE id = %s", (session_id,))
    
    if existing_session:
        logger.info(f"Session {session_id} already exists, using existing data")
        return
    
    logger.info(f"Creating mock session data for {session_id} with {message_count} messages")
    
    try:
        # Create session
        execute("""
            INSERT INTO conversation_sessions (id, user_id, bot_id, started_at, model)
            VALUES (%s, %s, %s, %s, %s)
        """, (session_id, user_id, "test-bot-id", datetime.now(timezone.utc), "openai/gpt-4o-mini"))
        
        # Create mock messages
        mock_messages = [
            "Привет, как дела?",
            "Расскажи мне о своём дне",
            "Что ты думаешь о погоде?",
            "Мне грустно сегодня",
            "Хочется поговорить с кем-то",
            "Помоги мне разобраться в ситуации",
            "Я переживаю из-за работы",
            "Не знаю что делать дальше",
            "Чувствую себя одиноко",
            "Нужен совет по отношениям",
            "Хочется написать песню",
            "Помоги создать что-то творческое",
            "Расскажи о смысле жизни",
            "Что такое счастье?",
            "Как найти свой путь?",
            "Мне нужна поддержка",
            "Спасибо за разговор",
            "Ты помог мне понять себя",
            "Чувствую себя лучше",
            "До свидания!"
        ]
        
        assistant_responses = [
            "Привет! У меня всё хорошо, спасибо что спрашиваешь. А как у тебя дела?",
            "Конечно, расскажи! Я внимательно слушаю.",
            "Погода может влиять на настроение. Какие у тебя мысли об этом?",
            "Понимаю, что тебе грустно. Хочешь поговорить о том, что тебя беспокоит?",
            "Я здесь и готов выслушать. Что у тебя на душе?",
            "Давай разберём ситуацию вместе. Расскажи подробнее.",
            "Работа может быть источником стресса. Что именно тебя беспокоит?",
            "Иногда неопределённость пугает. Давай подумаем о возможных шагах.",
            "Одиночество - сложное чувство. Ты не одинок в этом разговоре.",
            "Отношения - важная часть жизни. Какой именно совет тебе нужен?",
            "Творчество - прекрасный способ выражения. Что тебя вдохновляет?",
            "Давай создадим что-то вместе! Какие у тебя идеи?",
            "Смысл жизни каждый находит свой. Что для тебя важно?",
            "Счастье - это моменты радости и удовлетворения. Что делает тебя счастливым?",
            "Путь у каждого свой. Что тебя интересует и вдохновляет?",
            "Я здесь, чтобы поддержать тебя. Ты справишься!",
            "Пожалуйста! Рад был помочь.",
            "Это замечательно! Самопонимание - важный шаг.",
            "Я рад, что наш разговор помог тебе почувствовать себя лучше.",
            "До свидания! Заходи ещё, когда захочется поговорить."
        ]
        
        # Insert alternating user and assistant messages
        for i in range(min(message_count, len(mock_messages))):
            # User message
            execute("""
                INSERT INTO messages (id, session_id, user_id, role, content, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (f"msg-user-{i}", session_id, user_id, "user", mock_messages[i], 
                  datetime.now(timezone.utc)))
            
            # Assistant response (if available)
            if i < len(assistant_responses):
                execute("""
                    INSERT INTO messages (id, session_id, user_id, role, content, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (f"msg-assistant-{i}", session_id, user_id, "assistant", assistant_responses[i], 
                      datetime.now(timezone.utc)))
        
        logger.info(f"Created mock session with {message_count * 2} messages")
        
    except Exception as e:
        logger.error(f"Error creating mock session data: {e}")
        raise

def test_session_processing(session_id: str, user_id: str = None, create_mock: bool = False):
    """
    Test summary processing for a specific session
    
    Args:
        session_id: Session identifier
        user_id: User identifier (optional)
        create_mock: Whether to create mock data if session doesn't exist
    """
    logger.info(f"Testing session processing for session: {session_id}")
    
    try:
        # Get or create session data
        messages = get_session_messages(session_id)
        
        if not messages and create_mock:
            if not user_id:
                user_id = os.getenv('TEST_USER_ID', 'test-user-123')
            create_mock_session_data(session_id, user_id)
            messages = get_session_messages(session_id)
        
        if not messages:
            logger.error(f"No messages found for session {session_id}")
            return False
        
        logger.info(f"Found {len(messages)} messages in session")
        
        # Show message breakdown by role
        user_messages = [m for m in messages if m['role'] == 'user']
        assistant_messages = [m for m in messages if m['role'] == 'assistant']
        
        logger.info(f"User messages: {len(user_messages)}")
        logger.info(f"Assistant messages: {len(assistant_messages)}")
        
        # Process summaries
        logger.info("Starting summary processing...")
        
        if not user_id:
            # Try to get user_id from database
            from index import query_one
            session_info = query_one("SELECT user_id FROM conversation_sessions WHERE id = %s", (session_id,))
            if session_info:
                user_id = session_info["user_id"]
            else:
                user_id = os.getenv('TEST_USER_ID', 'test-user-123')
        
        process_messages_for_summary(session_id, user_id, messages)
        
        logger.info("Summary processing completed!")
        
        # Display results
        display_summary_results(session_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing session processing: {e}")
        return False

def display_summary_results(session_id: str):
    """Display summary results for a session"""
    logger.info("=== SUMMARY RESULTS ===")
    
    summary_types = ['L1', 'L2', 'L3', 'L4', 'LALL']
    roles = ['user', 'assistant']
    
    for summary_type in summary_types:
        logger.info(f"\n--- {summary_type} Summaries ---")
        
        for role in roles:
            summaries = get_summaries_by_role(session_id, summary_type, role)
            logger.info(f"{role.capitalize()} {summary_type} summaries: {len(summaries)}")
            
            for i, summary in enumerate(summaries[:2]):  # Show first 2 summaries
                try:
                    logger.info(f"  [{i+1}] Group: {summary.get('group_id', 'N/A')}")
                    logger.info(f"      Summary: {summary.get('summary_text', 'N/A')[:100]}...")
                    logger.info(f"      Messages: {summary.get('message_count', 'N/A')}")
                    if 'content' in summary:
                        # For backward compatibility, if content is available
                        content = json.loads(summary['content'])
                        logger.info(f"      JSON Summary: {content.get('summary', 'N/A')[:100]}...")
                except:
                    logger.info(f"  [{i+1}] Summary text: {summary.get('summary_text', 'N/A')[:100]}...")

def test_handler_function(session_id: str, user_id: str = None):
    """Test the main handler function"""
    logger.info("Testing handler function...")
    
    # Test direct session processing
    event = {
        "body": {
            "session_id": session_id,
            "user_id": user_id
        }
    }
    
    try:
        result = handler(event, None)
        logger.info(f"Handler result: {result}")
        return result
    except Exception as e:
        logger.error(f"Handler test failed: {e}")
        return None

def main():
    """Main testing function"""
    parser = argparse.ArgumentParser(description='MindScribe Local Testing Tool')
    parser.add_argument('--session-id', required=True, help='Session ID to test')
    parser.add_argument('--user-id', help='User ID (optional)')
    parser.add_argument('--summary-type', help='Specific summary type to show (L1, L2, L3, L4, LALL)')
    parser.add_argument('--create-mock', action='store_true', help='Create mock data if session not found')
    parser.add_argument('--test-handler', action='store_true', help='Test the handler function')
    parser.add_argument('--show-summaries-only', action='store_true', help='Only show existing summaries without processing')
    
    args = parser.parse_args()
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    logger.info("Starting MindScribe local testing...")
    logger.info(f"Session ID: {args.session_id}")
    logger.info(f"User ID: {args.user_id or 'auto-detect'}")
    logger.info(f"Note: Using structured summary fields (content column removed)")
    
    try:
        if args.show_summaries_only:
            # Just show existing summaries
            logger.info("Showing existing summaries only...")
            display_summary_results(args.session_id)
        else:
            # Process session summaries
            success = test_session_processing(
                session_id=args.session_id,
                user_id=args.user_id,
                create_mock=args.create_mock
            )
            
            if not success:
                logger.error("Session processing failed")
                sys.exit(1)
        
        # Test handler if requested
        if args.test_handler:
            test_handler_function(args.session_id, args.user_id)
        
        # Show specific summary type if requested
        if args.summary_type:
            logger.info(f"\n=== {args.summary_type} SUMMARIES DETAIL ===")
            for role in ['user', 'assistant']:
                summaries = get_summaries_by_role(args.session_id, args.summary_type, role)
                logger.info(f"\n{role.capitalize()} {args.summary_type} summaries ({len(summaries)}):")
                
                for i, summary in enumerate(summaries):
                    logger.info(f"\n[{i+1}] ID: {summary['id']}")
                    logger.info(f"    Created: {summary['created_at']}")
                    logger.info(f"    Group ID: {summary.get('group_id', 'N/A')}")
                    logger.info(f"    Source Range: {summary.get('source_range', 'N/A')}")
                    try:
                        if 'content' in summary:
                            # For backward compatibility, if content is available
                            content = json.loads(summary['content'])
                            logger.info(f"    Summary: {content.get('summary', 'N/A')}")
                            logger.info(f"    Key Points: {content.get('key_points', [])}")
                        else:
                            # Use structured fields
                            logger.info(f"    Summary: {summary.get('summary_text', 'N/A')}")
                            key_points = summary.get('key_points', '[]')
                            if isinstance(key_points, str):
                                key_points = json.loads(key_points)
                            logger.info(f"    Key Points: {key_points}")
                            main_themes = summary.get('main_themes', '[]')
                            if isinstance(main_themes, str):
                                main_themes = json.loads(main_themes)
                            logger.info(f"    Main Themes: {main_themes}")
                            insights = summary.get('insights', '[]')
                            if isinstance(insights, str):
                                insights = json.loads(insights)
                            logger.info(f"    Insights: {insights}")
                    except Exception as e:
                        logger.info(f"    Error parsing summary: {e}")
                        logger.info(f"    Raw Summary Text: {summary.get('summary_text', 'N/A')}")
        
        logger.info("\nTesting completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\nTesting interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Testing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

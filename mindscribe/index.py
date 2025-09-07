import os
import re
import json
import hashlib
import uuid
import logging
from pythonjsonlogger import jsonlogger
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
import requests
from requests import HTTPError
from psycopg2 import connect, Error as PgError
from psycopg2.extras import RealDictCursor
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import tiktoken
import random
from pydantic import TypeAdapter, Base64Bytes, ValidationError

# ──────────────────────────
#  LOGGING
# ──────────────────────────

class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = record.levelname.replace("WARNING", "WARN").replace("CRITICAL", "FATAL")

logger = logging.getLogger('MindScribeLogger')
logger.setLevel(logging.DEBUG)
logger.propagate = False

console_handler = logging.StreamHandler()
console_formatter = YcLoggingFormatter('%(message)s %(level)s %(logger)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# ──────────────────────────
#  ENVIRONMENT VARIABLES
# ──────────────────────────

operouter_key    = os.getenv("operouter_key")
ai_model         = os.getenv("ai_model", "openai/gpt-5-nano")
ai_models_fallback  = os.getenv("ai_models_fallback", ["openai/gpt-4.1-nano","openai/gpt-4o-mini", "openai/gpt-4.1-mini"])
ai_endpoint      = os.getenv("ai_endpoint", "https://openrouter.ai/api/v1/chat/completions")
database_url_dev = os.getenv("database_url_dev")
database_url_prod = os.getenv("database_url_prod")
env = os.getenv("env", "dev")
database_url = database_url_dev if env == "dev" else database_url_prod

connect_timeout  = int(os.getenv('connect_timeout', 1))
read_timeout     = int(os.getenv('read_timeout', 5))
retry_total      = int(os.getenv('retry_total', 3))
retry_backoff_factor = int(os.getenv('retry_backoff_factor', 2))
timeout = (connect_timeout, read_timeout)
proxy_url = os.getenv("proxy_url")

# Proxy configuration
PROXY = {"http": proxy_url, "https": proxy_url} if proxy_url else None
test_url = "https://pmm-http-bin.website.yandexcloud.net"

# Загружаем system prompt
with open("system_prompt.txt", "r", encoding="utf-8") as file:
    system_prompt = file.read()

# Database connection params
DATABASE_URL = database_url
if DATABASE_URL:
    conn_params = {"dsn": DATABASE_URL}
else:
    conn_params = {
        "host":     os.getenv("DB_HOST"),
        "port":     os.getenv("DB_PORT", 5432),
        "dbname":   os.getenv("DB_NAME"),
        "user":     os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }

# Validate critical env vars
# for var in ("operouter_key",):
#     if not globals()[var]:
#         raise RuntimeError(f"ENV variable {var} is not set")

logger.info("Environment variables loaded")

def check_proxy(proxy_url, timeout=read_timeout, test_url=test_url):
    """
    Проверяет работоспособность HTTP/HTTPS прокси, отправляя запрос на test_url.
    Возвращает True, если прокси работает, иначе False.
    """
    if not proxy_url:
        return False
    
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.debug(f"Proxy check failed: {e}")
        return False

# ──────────────────────────
#  HTTP SESSION (reused from flow)
# ──────────────────────────

session = requests.Session()
retries = Retry(total=retry_total, backoff_factor=retry_backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)
logger.info("HTTP session initialised")

# ──────────────────────────
#  DATABASE HELPERS (reused from flow)
# ──────────────────────────

def get_conn():
    """Return a new psycopg2 connection."""
    try:
        conn = connect(**conn_params)
        conn.set_client_encoding('UTF8')
        return conn
    except PgError as e:
        logger.exception("Failed to connect to Postgres: %s", e)
        raise

def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """Execute SELECT returning a single row as dict, or None."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        conn.close()

def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """Execute SELECT returning all rows as list of dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

def execute(sql: str, params: tuple = ()):
    """Execute INSERT/UPDATE/DELETE and commit."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    finally:
        conn.close()

# ──────────────────────────
#  AI INTEGRATION (reused from flow)
# ──────────────────────────

def clean_ai_response_content(content: str) -> str:
    """
    Clean AI response content by removing markdown code blocks and extra whitespace
    
    Args:
        content: Raw content from AI response
        
    Returns:
        Cleaned content ready for JSON parsing
    """
    if not content:
        return content
    
    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    content = content.strip()
    
    # Check for markdown code blocks and extract content
    if content.startswith('```'):
        lines = content.split('\n')
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        content = '\n'.join(lines)
    
    # Remove any remaining leading/trailing whitespace
    content = content.strip()
    
    return content

def llm_conversation(messages: list[dict], system_message: str) -> dict:
    """
    Get AI response using conversation format (reused from flow)
    
    Args:
        messages: List of messages for the conversation
        system_message: System prompt
        
    Returns:
        Parsed JSON response or error dict
    """
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})
    try:
        resp = session.post(
            ai_endpoint,
            json={"model": ai_model, "messages": messages, "models": ai_models_fallback},
            headers={"Authorization": f"Bearer {operouter_key}", "Content-Type": "application/json"},
            proxies=(None if not check_proxy(proxy_url, read_timeout) else PROXY),
            timeout=timeout
        )
        
        # Check if response is successful
        resp.raise_for_status()
        
        # Parse the response JSON
        try:
            data = resp.json()
        except json.JSONDecodeError as json_err:
            logger.error("Failed to parse response as JSON: %s. Response content: %s", json_err, resp.text[:500])
            return {"error": f"Invalid JSON response from AI service: {json_err}"}
        
        logger.debug("LLM conversation response: %s", data)
        
        # Validate response structure
        if "choices" not in data or not data["choices"]:
            logger.error("Invalid response structure: missing 'choices'. Response: %s", data)
            return {"error": "Invalid response structure from AI service"}
        
        if "message" not in data["choices"][0] or "content" not in data["choices"][0]["message"]:
            logger.error("Invalid response structure: missing message content. Response: %s", data)
            return {"error": "Invalid response structure from AI service"}
        
        content = data["choices"][0]["message"]["content"]
        
        # Validate that content is not empty
        if not content or not content.strip():
            logger.error("Empty content received from AI service")
            return {"error": "Empty response content from AI service"}
        
        # Clean and parse content as JSON
        try:
            cleaned_content = clean_ai_response_content(content)
            return json.loads(cleaned_content)
        except json.JSONDecodeError as content_json_err:
            logger.error("Failed to parse AI response content as JSON: %s. Original content: %s", content_json_err, content[:500])
            return {"error": f"AI response content is not valid JSON: {content_json_err}"}
            
    except requests.exceptions.RequestException as req_err:
        logger.error("HTTP request failed: %s", req_err)
        return {"error": f"HTTP request failed: {req_err}"}
    except Exception as e:
        logger.error("LLM conversation call failed: %s", e)
        return {"error": str(e)}

def llm_summarize(messages: List[Dict[str, str]]) -> dict:
    """
    Generate summary using AI model
    
    Args:
        messages: List of messages to summarize
        
    Returns:
        Dictionary with summary data
    """
    try:
        # Prepare content for summarization
        content = "\n".join([f"{msg.get('role', '')}: {msg.get('content', '')}" for msg in messages])
        
        user_message = f"Создайте саммари для следующих сообщений:\n\n{content}"
        ai_messages = [{"role": "user", "content": user_message}]
        
        result = llm_conversation(ai_messages, system_prompt)
        
        if "error" in result:
            return {
                "summary": "Ошибка при создании саммари",
                "key_points": [],
                "main_themes": [],
                "insights": [],
                "language": "ru"
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return {
            "summary": "Ошибка при создании саммари",
            "key_points": [],
            "main_themes": [],
            "insights": [],
            "language": "ru"
        }

# ──────────────────────────
#  PROCESSING STATE MANAGEMENT
# ──────────────────────────

def get_processing_state(session_id: str, summary_type: str, role: str) -> dict:
    """
    Get processing state for session, type and role
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role (user/assistant)
        
    Returns:
        Processing state dict or None
    """
    try:
        return query_one("""
            SELECT * FROM summary_processing_state 
            WHERE session_id = %s AND summary_type = %s AND role = %s
        """, (session_id, summary_type, role))
    except PgError as e:
        logger.error(f"Error getting processing state: {e}")
        return None

def update_processing_state(session_id: str, summary_type: str, role: str, 
                          message_count: int, status: str = 'completed') -> None:
    """
    Update or create processing state
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role
        message_count: Number of messages processed
        status: Processing status
    """
    try:
        execute("""
            INSERT INTO summary_processing_state 
            (session_id, summary_type, role, last_message_count, processing_status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (session_id, summary_type, role)
            DO UPDATE SET 
                last_processed_at = NOW(),
                last_message_count = EXCLUDED.last_message_count,
                processing_status = EXCLUDED.processing_status
        """, (session_id, summary_type, role, message_count, status))
        
        logger.debug(f"Updated processing state: {session_id}, {summary_type}, {role}, {status}")
        
    except PgError as e:
        logger.error(f"Error updating processing state: {e}")
        raise

def is_group_already_processed(session_id: str, summary_type: str, role: str, group_id: str) -> bool:
    """
    Check if a specific group has already been processed
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role
        group_id: Group identifier to check
        
    Returns:
        True if group is already processed
    """
    try:
        result = query_one("""
            SELECT id FROM summary 
            WHERE session_id = %s AND type = %s AND role = %s AND group_id = %s
        """, (session_id, summary_type, role, group_id))
        
        return result is not None
    except PgError as e:
        logger.error(f"Error checking if group is processed: {e}")
        return False

def needs_processing(session_id: str, summary_type: str, role: str, current_count: int) -> bool:
    """
    Check if processing is needed based on current state
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role
        current_count: Current message count
        
    Returns:
        True if processing is needed
    """
    state = get_processing_state(session_id, summary_type, role)
    
    if not state:
        return True  # No state - needs processing
    
    # If processing status is error or pending, allow reprocessing
    if state.get('processing_status') in ['error', 'pending']:
        logger.debug(f"Reprocessing needed due to status: {state.get('processing_status')}")
        return True
    
    # Check if enough new content accumulated based on type
    last_count = state.get('last_message_count', 0)
    
    if summary_type == 'L1':
        # L1 processes groups of 15 messages, check if we have enough new messages for a new group
        return current_count >= last_count + 15
    elif summary_type in ['L2', 'L3', 'L4']:
        # L2-L4 process groups of 4 summaries from previous level
        return current_count >= last_count + 4
    elif summary_type == 'LALL':
        # LALL summary updates when significant new content is available
        return current_count >= last_count + 10
    
    return False

# ──────────────────────────
#  SUMMARY FUNCTIONS
# ──────────────────────────

def create_summary(session_id: str, user_id: str, role: str, content: str, summary_type: str) -> None:
    """
    Create a basic summary record in the database (legacy function)
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        role: Message role (user/assistant/system)
        content: Summary content (text or JSON)
        summary_type: Type of summary (LALL, L1, L2, L3, L4)
    """
    try:
        # Try to parse content as JSON, fallback to plain text
        try:
            content_data = json.loads(content)
            summary_text = content_data.get("summary", content)
            key_points = json.dumps(content_data.get("key_points", []), ensure_ascii=False)
            main_themes = json.dumps(content_data.get("main_themes", []), ensure_ascii=False)
            insights = json.dumps(content_data.get("insights", []), ensure_ascii=False)
            language = content_data.get("language", "ru")
        except (json.JSONDecodeError, TypeError):
            # If content is not JSON, treat as plain text summary
            summary_text = content
            key_points = "[]"
            main_themes = "[]"
            insights = "[]"
            language = "ru"
        
        execute("""
                    INSERT INTO summary (id, session_id, user_id, role, created_at, type,
                                       summary_text, key_points, main_themes, insights, language)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (str(uuid.uuid4()), session_id, user_id, role, datetime.now(timezone.utc), summary_type,
                      summary_text, key_points, main_themes, insights, language))
                
        logger.info(f"Summary created for session {session_id}, type {summary_type}")
        
    except PgError as e:
        logger.error(f"Error creating summary: {e}")
        raise

def create_enhanced_summary(session_id: str, user_id: str, role: str, content: str, 
                          summary_type: str, group_id: str, source_range: str, message_count: int) -> None:
    """
    Create an enhanced summary record with additional metadata
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        role: Message role
        content: Summary content (text or JSON)
        summary_type: Type of summary
        group_id: Group identifier
        source_range: Source data range
        message_count: Number of messages
    """
    try:
        # Try to parse content as JSON, fallback to plain text
        try:
            content_data = json.loads(content)
            summary_text = content_data.get("summary", content)
            key_points = json.dumps(content_data.get("key_points", []), ensure_ascii=False)
            main_themes = json.dumps(content_data.get("main_themes", []), ensure_ascii=False)
            insights = json.dumps(content_data.get("insights", []), ensure_ascii=False)
            language = content_data.get("language", "ru")
        except (json.JSONDecodeError, TypeError):
            # If content is not JSON, treat as plain text summary
            summary_text = content
            key_points = "[]"
            main_themes = "[]"
            insights = "[]"
            language = "ru"
        
        execute("""
            INSERT INTO summary (id, session_id, user_id, role, created_at, type, 
                               group_id, source_range, message_count, processed_at,
                               summary_text, key_points, main_themes, insights, language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(uuid.uuid4()), session_id, user_id, role, 
            datetime.now(timezone.utc), summary_type, group_id, source_range, 
            message_count, datetime.now(timezone.utc),
            summary_text, key_points, main_themes, insights, language
        ))
        
        logger.info(f"Enhanced summary created for session {session_id}, type {summary_type}, role {role}")
        
    except PgError as e:
        logger.error(f"Error creating enhanced summary: {e}")
        raise

def get_summaries(session_id: str, summary_type: str = None) -> list:
    """
    Get summaries for a session
    
    Args:
        session_id: Session identifier
        summary_type: Optional filter by summary type
        
    Returns:
        List of summary records
    """
    try:
        if summary_type:
            return query_all("""
                SELECT * FROM summary 
                WHERE session_id = %s AND type = %s 
                ORDER BY created_at DESC
            """, (session_id, summary_type))
        else:
            return query_all("""
                SELECT * FROM summary 
                WHERE session_id = %s 
                ORDER BY created_at DESC
            """, (session_id,))
                
    except PgError as e:
        logger.error(f"Error getting summaries: {e}")
        return []

def get_summaries_by_role(session_id: str, summary_type: str, role: str) -> list:
    """
    Get summaries for a session, type and role
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role (user/assistant)
        
    Returns:
        List of summary records
    """
    try:
        return query_all("""
            SELECT * FROM summary 
            WHERE session_id = %s AND type = %s AND role = %s
            ORDER BY created_at ASC
        """, (session_id, summary_type, role))
    except PgError as e:
        logger.error(f"Error getting summaries by role: {e}")
        return []

def get_structured_summaries_by_role(session_id: str, summary_type: str, role: str) -> list:
    """
    Get structured summaries for a session, type and role with separate fields
    
    Args:
        session_id: Session identifier
        summary_type: Type of summary
        role: Message role (user/assistant)
        
    Returns:
        List of summary records with structured data
    """
    try:
        results = query_all("""
            SELECT id, session_id, user_id, role, created_at, type, group_id, source_range, 
                   message_count, processed_at, summary_text, key_points, main_themes, 
                   insights, language
            FROM summary 
            WHERE session_id = %s AND type = %s AND role = %s
            ORDER BY created_at ASC
        """, (session_id, summary_type, role))
        
        # Convert JSONB fields to Python objects and add backward compatibility
        for record in results:
            if record.get('key_points'):
                try:
                    record['key_points'] = json.loads(record['key_points']) if isinstance(record['key_points'], str) else record['key_points']
                except:
                    record['key_points'] = []
            else:
                record['key_points'] = []
                
            if record.get('main_themes'):
                try:
                    record['main_themes'] = json.loads(record['main_themes']) if isinstance(record['main_themes'], str) else record['main_themes']
                except:
                    record['main_themes'] = []
            else:
                record['main_themes'] = []
                
            if record.get('insights'):
                try:
                    record['insights'] = json.loads(record['insights']) if isinstance(record['insights'], str) else record['insights']
                except:
                    record['insights'] = []
            else:
                record['insights'] = []
            
            # For backward compatibility, add content field constructed from structured data
            record['content'] = json.dumps({
                "summary": record.get('summary_text', ''),
                "key_points": record['key_points'],
                "main_themes": record['main_themes'],
                "insights": record['insights'],
                "language": record.get('language', 'ru')
            }, ensure_ascii=False)
        
        return results
    except PgError as e:
        logger.error(f"Error getting structured summaries by role: {e}")
        return []

def get_session_messages(session_id: str) -> List[Dict[str, str]]:
    """
    Get all messages for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        List of message records
    """
    try:
        return query_all("""
            SELECT role, content, created_at FROM messages 
            WHERE session_id = %s 
            ORDER BY created_at ASC
        """, (session_id,))
    except PgError as e:
        logger.error(f"Error getting session messages: {e}")
        return []

# ──────────────────────────
#  UNIVERSAL PROCESSING FUNCTION
# ──────────────────────────

def process_level_summaries(session_id: str, user_id: str, messages: List[Dict[str, str]], 
                            role: str, level: str, group_size: int, source_level: str = None) -> None:
    """
    Universal function to process summaries at any level (L1, L2, L3, L4)
    
    Args:
        session_id: Session identifier
        user_id: User identifier  
        messages: Messages to process (for L1) or None (for L2-L4)
        role: Message role (user/assistant)
        level: Summary level (L1, L2, L3, L4)
        group_size: Size of groups to process
        source_level: Source level for hierarchical processing (L1 for L2, etc.)
    """
    try:
        if level == 'L1':
            # Process raw messages
            if not messages:
                return
                
            total_processed = 0
            for i in range(0, len(messages), group_size):
                group = messages[i:i+group_size]
                if len(group) >= 5:  # Only process if we have at least 5 messages
                    group_id = f"{level}_{role}_{i//group_size}"
                    source_range = f"message_{i+1}_{i+len(group)}"
                    
                    # Check if this specific group is already processed
                    if is_group_already_processed(session_id, level, role, group_id):
                        logger.debug(f"Group {group_id} already processed, skipping")
                        continue
                    
                    # Check if general processing is needed
                    if not needs_processing(session_id, level, role, len(messages)):
                        continue
                    
                    summary_data = llm_summarize(group)
                    summary_data["group_id"] = group_id
                    summary_data["message_count"] = len(group)
                    summary_data["source_range"] = source_range
                    
                    create_enhanced_summary(
                        session_id=session_id,
                        user_id=user_id,
                        role=role,
                        content=json.dumps(summary_data, ensure_ascii=False),
                        summary_type=level,
                        group_id=group_id,
                        source_range=source_range,
                        message_count=len(group)
                    )
                    total_processed += len(group)
                    logger.debug(f"Created {level} summary for group {group_id}")
            
            # Update processing state
            if total_processed > 0:
                update_processing_state(session_id, level, role, len(messages))
                
        else:
            # Process summaries from previous level
            source_summaries = get_summaries_by_role(session_id, source_level, role)
            
            if not source_summaries:
                return
                
            total_processed = 0
            for i in range(0, len(source_summaries), group_size):
                group = source_summaries[i:i+group_size]
                if len(group) >= 2:  # Only process if we have at least 2 summaries
                    group_id = f"{level}_{role}_{i//group_size}"
                    source_range = f"{source_level}_{i}_{i+len(group)-1}"
                    
                    # Check if this specific group is already processed
                    if is_group_already_processed(session_id, level, role, group_id):
                        logger.debug(f"Group {group_id} already processed, skipping")
                        continue
                    
                    # Check if general processing is needed
                    if not needs_processing(session_id, level, role, len(source_summaries)):
                        continue
                    
                    # Prepare content from source summaries
                    source_content = []
                    total_messages = 0
                    for summary in group:
                        # Reconstruct content from structured fields for processing
                        content_dict = {
                            "summary": summary.get("summary_text", ""),
                            "key_points": json.loads(summary.get("key_points", "[]")) if isinstance(summary.get("key_points"), str) else summary.get("key_points", []),
                            "main_themes": json.loads(summary.get("main_themes", "[]")) if isinstance(summary.get("main_themes"), str) else summary.get("main_themes", []),
                            "insights": json.loads(summary.get("insights", "[]")) if isinstance(summary.get("insights"), str) else summary.get("insights", []),
                            "language": summary.get("language", "ru")
                        }
                        content_str = json.dumps(content_dict, ensure_ascii=False)
                        source_content.append({"role": "system", "content": content_str})
                        # Extract message count if available
                        total_messages += summary.get("message_count", 0)
                    
                    summary_data = llm_summarize(source_content)
                    summary_data["group_id"] = group_id
                    summary_data["source_summaries_count"] = len(group)
                    summary_data["total_message_count"] = total_messages
                    summary_data["source_range"] = source_range
                    
                    create_enhanced_summary(
                        session_id=session_id,
                        user_id=user_id,
                        role=role,
                        content=json.dumps(summary_data, ensure_ascii=False),
                        summary_type=level,
                        group_id=group_id,
                        source_range=source_range,
                        message_count=total_messages
                    )
                    total_processed += len(group)
                    logger.debug(f"Created {level} summary for group {group_id}")
            
            # Update processing state
            if total_processed > 0:
                update_processing_state(session_id, level, role, len(source_summaries))
        
    except Exception as e:
        logger.error(f"Error processing {level} summaries for {role}: {e}")

def process_lall_summary(session_id: str, user_id: str, messages: List[Dict[str, str]], role: str) -> None:
    """
    Process LALL summary (overall summary of all messages for specific role)
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        messages: Messages to summarize
        role: Message role (user/assistant)
    """
    try:
        # Check if LALL summary needs processing
        if not needs_processing(session_id, "LALL", role, len(messages)):
            logger.debug(f"LALL summary for {role} doesn't need processing for session {session_id}")
            return
        
        # Use highest level summaries available, fallback to messages
        l4_summaries = get_summaries_by_role(session_id, "L4", role)
        l3_summaries = get_summaries_by_role(session_id, "L3", role)
        l2_summaries = get_summaries_by_role(session_id, "L2", role)
        
        content_for_summary = []
        total_messages = len(messages)
        
        if l4_summaries:
            for l4 in l4_summaries[:5]:  # Take max 5 L4 summaries
                # Reconstruct content from structured fields
                content_dict = {
                    "summary": l4.get("summary_text", ""),
                    "key_points": json.loads(l4.get("key_points", "[]")) if isinstance(l4.get("key_points"), str) else l4.get("key_points", []),
                    "main_themes": json.loads(l4.get("main_themes", "[]")) if isinstance(l4.get("main_themes"), str) else l4.get("main_themes", []),
                    "insights": json.loads(l4.get("insights", "[]")) if isinstance(l4.get("insights"), str) else l4.get("insights", []),
                    "language": l4.get("language", "ru")
                }
                content_str = json.dumps(content_dict, ensure_ascii=False)
                content_for_summary.append({"role": "system", "content": content_str})
        elif l3_summaries:
            for l3 in l3_summaries[:10]:  # Take max 10 L3 summaries
                content_dict = {
                    "summary": l3.get("summary_text", ""),
                    "key_points": json.loads(l3.get("key_points", "[]")) if isinstance(l3.get("key_points"), str) else l3.get("key_points", []),
                    "main_themes": json.loads(l3.get("main_themes", "[]")) if isinstance(l3.get("main_themes"), str) else l3.get("main_themes", []),
                    "insights": json.loads(l3.get("insights", "[]")) if isinstance(l3.get("insights"), str) else l3.get("insights", []),
                    "language": l3.get("language", "ru")
                }
                content_str = json.dumps(content_dict, ensure_ascii=False)
                content_for_summary.append({"role": "system", "content": content_str})
        elif l2_summaries:
            for l2 in l2_summaries[:20]:  # Take max 20 L2 summaries
                content_dict = {
                    "summary": l2.get("summary_text", ""),
                    "key_points": json.loads(l2.get("key_points", "[]")) if isinstance(l2.get("key_points"), str) else l2.get("key_points", []),
                    "main_themes": json.loads(l2.get("main_themes", "[]")) if isinstance(l2.get("main_themes"), str) else l2.get("main_themes", []),
                    "insights": json.loads(l2.get("insights", "[]")) if isinstance(l2.get("insights"), str) else l2.get("insights", []),
                    "language": l2.get("language", "ru")
                }
                content_str = json.dumps(content_dict, ensure_ascii=False)
                content_for_summary.append({"role": "system", "content": content_str})
        else:
            # Fallback to raw messages, take representative sample
            step = max(1, len(messages) // 50)  # Take up to 50 messages
            content_for_summary = messages[::step]
        
        if content_for_summary:
            summary_data = llm_summarize(content_for_summary)
            summary_data["total_messages"] = total_messages
            summary_data["summary_type"] = "LALL"
            summary_data["role"] = role
            
            create_enhanced_summary(
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=json.dumps(summary_data, ensure_ascii=False),
                summary_type="LALL",
                group_id=f"LALL_{role}",
                source_range=f"all_{role}_messages",
                message_count=total_messages
            )
            
            # Update processing state
            update_processing_state(session_id, "LALL", role, total_messages)
            
            logger.debug(f"Created LALL summary for {role} in session {session_id}")
    
    except Exception as e:
        logger.error(f"Error processing LALL summary for {role}: {e}")

# ──────────────────────────
#  MAIN PROCESSING LOGIC
# ──────────────────────────

def process_messages_for_summary(session_id: str, user_id: str, messages: List[Dict[str, str]] = None) -> None:
    """
    Process messages and create appropriate hierarchical summaries
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        messages: Optional list of messages (if not provided, fetched from DB)
    """
    try:
        if messages is None:
            messages = get_session_messages(session_id)
        
        if not messages:
            logger.warning(f"No messages found for session {session_id}")
            return
        
        logger.info(f"Processing {len(messages)} messages for session {session_id}")
        
        # Separate messages by role
        user_messages = [msg for msg in messages if msg['role'] == 'user']
        assistant_messages = [msg for msg in messages if msg['role'] == 'assistant']
        
        # Process each role separately
        for role, role_messages in [('user', user_messages), ('assistant', assistant_messages)]:
            if not role_messages:
                continue
                
            logger.info(f"Processing {len(role_messages)} {role} messages for session {session_id}")
            
            # L1: Process groups of 15 messages
            process_level_summaries(session_id, user_id, role_messages, role, 'L1', 15)
            
            # L2: Process groups of 4 L1 summaries
            process_level_summaries(session_id, user_id, None, role, 'L2', 4, 'L1')
            
            # L3: Process groups of 4 L2 summaries
            process_level_summaries(session_id, user_id, None, role, 'L3', 4, 'L2')
            
            # L4: Process groups of 4 L3 summaries
            process_level_summaries(session_id, user_id, None, role, 'L4', 4, 'L3')
            
            # LALL: Create overall summary if we have enough content
            if len(role_messages) >= 15:
                process_lall_summary(session_id, user_id, role_messages, role)
        
        logger.info(f"Completed summary processing for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error processing messages for summary: {e}")

# ──────────────────────────
#  SESSION PROCESSING
# ──────────────────────────

def get_sessions_to_process(limit: int = 3) -> List[Dict[str, str]]:
    """
    Get sessions that need summary processing
    
    Args:
        limit: Maximum number of sessions to process
        
    Returns:
        List of session records
    """
    try:
        # Get sessions with messages but without recent summaries
        sessions = query_all("""
            SELECT DISTINCT 
                cs.id as session_id,
                cs.user_id,
                COUNT(m.id) as message_count,
                MAX(m.created_at) as last_message_at,
                MAX(s.created_at) as last_summary_at
            FROM conversation_sessions cs
            LEFT JOIN messages m ON cs.id = m.session_id
            LEFT JOIN summary s ON cs.id = s.session_id::uuid
            WHERE m.id IS NOT NULL
            GROUP BY cs.id, cs.user_id
            HAVING COUNT(m.id) >= 15
                AND (MAX(s.created_at) IS NULL 
                     OR MAX(s.created_at) < MAX(m.created_at) - INTERVAL '1 hour')
            ORDER BY MAX(m.created_at) DESC
            LIMIT %s
        """, (limit,))
        
        return sessions
        
    except PgError as e:
        logger.error(f"Error getting sessions to process: {e}")
        return []

def process_session_summary(session_id: str, user_id: str = None) -> None:
    """
    Process summary for a specific session
    
    Args:
        session_id: Session identifier
        user_id: Optional user identifier (fetched from DB if not provided)
    """
    try:
        logger.info(f"Processing summary for session {session_id}")
        
        # Get user_id if not provided
        if not user_id:
            session_info = query_one("SELECT user_id FROM conversation_sessions WHERE id = %s", (session_id,))
            if not session_info:
                logger.error(f"Session {session_id} not found")
                return
            user_id = session_info["user_id"]
        
        # Get messages for the session
        messages = get_session_messages(session_id)
        
        if not messages:
            logger.warning(f"No messages found for session {session_id}")
            return
        
        # Process hierarchical summaries
        process_messages_for_summary(session_id, user_id, messages)
        
        logger.info(f"Completed processing summary for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error processing session {session_id}: {e}")

# ──────────────────────────
#  UTILS (reused from flow)
# ──────────────────────────

def parse_body(event: Dict[str, Any]) -> Any:
    """
    Универсально разбирает event['body'] из Yandex Cloud (или AWS / GCP):
      • JSON  → dict / list
      • Base-64(JSON) → dict / list
      • Base-64(binary) → bytes
      • голый текст → str
    """
    raw: str | bytes = event.get("body", "")
    b64 = TypeAdapter(Base64Bytes)

    # 1. Пытаемся сразу прочитать JSON
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        pass          # не JSON — едем дальше

    # 2. Пытаемся декодировать Base-64
    #    (неважно, что говорит isBase64Encoded)
    try:
        decoded: bytes = b64.validate_python(raw)
    except ValidationError:
        return raw    # совсем не Base-64 → отдаём как есть (str)

    # 3. Декодировали Base-64 → возможно, внутри JSON?
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return decoded  # бинарные данные

# ──────────────────────────
#  MAIN HANDLER
# ──────────────────────────

def handler(event, context):
    """
    Main Lambda handler for MindScribe function
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        Response dict
    """
    try:
        logger.info(f"Received event: {json.dumps(event, ensure_ascii=False)}")
        
        # Parse the request body
        body = None
        if 'body' in event and event['body']:
            if isinstance(event['body'], str) and event['body'].strip():
                try:
                    body = json.loads(event['body'])
                except json.JSONDecodeError:
                    # Try using the universal parse_body function
                    body = parse_body(event)
            elif not isinstance(event['body'], str):
                body = event['body']
        
        # If no valid body, treat as empty dict (for GET requests, cron, etc.)
        if body is None:
            body = {}
        
        # Check HTTP method
        http_method = event.get("httpMethod", "").upper()
        request_context = event.get("requestContext", {})
        
        # Handle GET requests - return simple status
        if http_method == "GET":
            logger.info("Received GET request - returning service status")
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "service": "MindScribe",
                    "status": "running",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "MindScribe summary processing service is operational"
                }, ensure_ascii=False)
            }
        
        # Handle cron events (empty body or trigger-specific events)
        if not body or body.get("trigger_type") == "timer":
            logger.info("Processing cron trigger - batch summary processing")
            
            # Get sessions to process (max 3 at a time)
            sessions_to_process = get_sessions_to_process(limit=3)
            
            logger.info(f"Found {len(sessions_to_process)} sessions to process")
            
            for session in sessions_to_process:
                try:
                    process_session_summary(
                        session_id=session["session_id"],
                        user_id=session["user_id"]
                    )
                except Exception as e:
                    logger.error(f"Error processing session {session['session_id']}: {e}")
                    continue
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "message": f"Processed {len(sessions_to_process)} sessions",
                    "sessions_processed": [s["session_id"] for s in sessions_to_process]
                }, ensure_ascii=False)
            }
        
        # Handle direct processing requests
        session_id = body.get("session_id")
        summary_type = body.get("summary_type")
        user_id = body.get("user_id")
        role = body.get("role")
        structured = body.get("structured", False)  # New parameter for structured output
        
        if session_id:
            # Handle read-only requests (no processing)
            if body.get("action") == "get":
                logger.info(f"Getting summaries for session: {session_id}")
                
                response_data = {
                    "session_id": session_id
                }
                
                if summary_type and role:
                    if structured:
                        summaries = get_structured_summaries_by_role(session_id, summary_type, role)
                        response_data["summaries"] = summaries
                        response_data["format"] = "structured"
                    else:
                        summaries = get_summaries_by_role(session_id, summary_type, role)
                        response_data["summaries"] = summaries
                        response_data["format"] = "legacy"
                elif summary_type:
                    summaries = get_summaries(session_id, summary_type)
                    response_data["summaries"] = summaries
                    response_data["format"] = "legacy"
                else:
                    summaries = get_summaries(session_id)
                    response_data["summaries"] = summaries
                    response_data["format"] = "legacy"
                
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps(response_data, ensure_ascii=False)
                }
            
            # Process specific session
            logger.info(f"Processing specific session: {session_id}")
            process_session_summary(session_id, user_id)
            
            response_data = {
                "message": f"Processed session {session_id}",
                "session_id": session_id
            }
            
            if summary_type:
                if role and structured:
                    summaries = get_structured_summaries_by_role(session_id, summary_type, role)
                    response_data["format"] = "structured"
                else:
                    summaries = get_summaries(session_id, summary_type)
                    response_data["format"] = "legacy"
                response_data["summaries"] = summaries
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps(response_data, ensure_ascii=False)
            }
        
        # If we reach here, the request is malformed
        logger.warning(f"Invalid request received. HTTP method: {http_method}, Body: {body}")
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Invalid request",
                "message": "For POST requests, provide session_id in request body. For GET requests, the service returns status information.",
                "received_method": http_method,
                "valid_methods": ["GET", "POST"]
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"Handler error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }, ensure_ascii=False)
        }

# ──────────────────────────
#  LOCAL EXECUTION
# ──────────────────────────

def load_env_from_file(filepath: str = ".env") -> None:
    """
    Load environment variables from a .env file for local development
    
    Args:
        filepath: Path to the .env file
    """
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"').strip("'")
                        os.environ[key] = value
            logger.info(f"Loaded environment variables from {filepath}")
        else:
            logger.warning(f"Environment file {filepath} not found")
    except Exception as e:
        logger.error(f"Error loading environment file: {e}")

def local_test_session(session_id: str, user_id: str = None):
    """
    Test function for local development - process a specific session
    
    Args:
        session_id: Session ID to process
        user_id: Optional user ID
    """
    try:
        logger.info(f"Local test: Processing session {session_id}")
        
        if not user_id:
            user_id = "test-user-" + session_id[:8]
        
        # Mock event for testing
        test_event = {
            "body": json.dumps({
                "session_id": session_id,
                "user_id": user_id
            })
        }
        
        # Mock context
        class MockContext:
            def __init__(self):
                self.request_id = "local-test-" + str(uuid.uuid4())[:8]
                self.function_name = "mindscribe-local"
                self.memory_limit_in_mb = 512
        
        result = handler(test_event, MockContext())
        logger.info(f"Local test result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Local test error: {e}")
        return {"error": str(e)}

def local_get_summaries(session_id: str, summary_type: str = None, role: str = None, structured: bool = True):
    """
    Test function for local development - get summaries for a session
    
    Args:
        session_id: Session ID
        summary_type: Optional summary type filter
        role: Optional role filter
        structured: Whether to return structured format
    """
    try:
        logger.info(f"Local get summaries: {session_id}, type={summary_type}, role={role}")
        
        # Mock event for getting summaries
        body = {
            "session_id": session_id,
            "action": "get",
            "structured": structured
        }
        
        if summary_type:
            body["summary_type"] = summary_type
        if role:
            body["role"] = role
        
        test_event = {
            "body": json.dumps(body)
        }
        
        # Mock context
        class MockContext:
            def __init__(self):
                self.request_id = "local-get-" + str(uuid.uuid4())[:8]
                self.function_name = "mindscribe-local"
        
        result = handler(test_event, MockContext())
        logger.info(f"Local get result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Local get error: {e}")
        return {"error": str(e)}

def local_batch_process(limit: int = 3):
    """
    Test function for local development - batch process sessions like cron
    
    Args:
        limit: Maximum number of sessions to process
    """
    try:
        logger.info(f"Local batch processing up to {limit} sessions")
        
        # Mock cron event
        test_event = {
            "body": json.dumps({
                "trigger_type": "timer"
            })
        }
        
        # Mock context
        class MockContext:
            def __init__(self):
                self.request_id = "local-batch-" + str(uuid.uuid4())[:8]
                self.function_name = "mindscribe-local"
        
        result = handler(test_event, MockContext())
        logger.info(f"Local batch result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Local batch error: {e}")
        return {"error": str(e)}

def main():
    """
    Main function for local development and testing
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="MindScribe Local Development Tool")
    parser.add_argument("--env-file", default=".env", help="Environment file path")
    parser.add_argument("--mode", choices=["process", "get", "batch"], default="batch", help="Operation mode")
    parser.add_argument("--session-id", help="Session ID (required for process/get modes)")
    parser.add_argument("--user-id", help="User ID (optional for process mode)")
    parser.add_argument("--summary-type", choices=["LALL", "L1", "L2", "L3", "L4"], help="Summary type filter (for get mode)")
    parser.add_argument("--role", choices=["user", "assistant"], help="Role filter (for get mode)")
    parser.add_argument("--limit", type=int, default=3, help="Limit for batch processing")
    parser.add_argument("--structured", action="store_true", default=True, help="Use structured format")
    
    args = parser.parse_args()
    
    # Load environment variables
    load_env_from_file(args.env_file)
    
    logger.info("Starting MindScribe local development session")
    logger.info(f"Mode: {args.mode}")
    
    try:
        if args.mode == "process":
            if not args.session_id:
                logger.error("Session ID is required for process mode")
                return
            result = local_test_session(args.session_id, args.user_id)
            
        elif args.mode == "get":
            if not args.session_id:
                logger.error("Session ID is required for get mode")
                return
            result = local_get_summaries(args.session_id, args.summary_type, args.role, args.structured)
            
        elif args.mode == "batch":
            result = local_batch_process(args.limit)
        
        print("\n" + "="*50)
        print("RESULT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*50)
        
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

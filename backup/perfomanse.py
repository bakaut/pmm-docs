def performance_test():
    """
    Performance comparison test between Redis (CacheManager) and PostgreSQL (DatabaseManager)
    for session & history operations.
    """
    logger.info("Starting performance test: Redis vs PostgreSQL")
    
    # Test parameters
    message_counts = [10, 20, 50, 100]
    test_results = {
        "postgresql": {},
        "redis": {},
        "summary": {}
    }
    
    # Setup test data
    test_user_uuid = "d9928cfe-3b37-4b26-9ddb-89c0275413ba"
    test_session_uuid = "9e4f8054-5e1b-4dd9-98b3-70df40a85f32"
    test_tenant = "perftest"  # Use simple name without special characters
    
    # Test messages template
    test_messages = [
        f"Тестовое сообщение номер {i} для проверки производительности системы кэширования" 
        for i in range(max(message_counts))
    ]
    
    for count in message_counts:
        logger.info(f"Testing with {count} messages")
        
        # PostgreSQL Performance Test
        pg_start = time.time()
        
        # Simulate saving messages to PostgreSQL
        for i in range(count):
            try:
                db.save_message(
                    test_session_uuid, 
                    test_user_uuid, 
                    "user" if i % 2 == 0 else "assistant",
                    test_messages[i],
                    None,  # No embedding for performance test
                    i + 1000
                )
            except Exception as e:
                logger.error(f"PostgreSQL save error: {e}")
        
        pg_write_time = time.time() - pg_start
        
        # Read from PostgreSQL
        pg_read_start = time.time()
        try:
            pg_history = db.fetch_history(test_session_uuid, limit_count=count)
        except Exception as e:
            logger.error(f"PostgreSQL read error: {e}")
            pg_history = []
        pg_read_time = time.time() - pg_read_start
        
        pg_total_time = pg_write_time + pg_read_time
        
        # Redis Performance Test  
        redis_start = time.time()
        
        # Save to Redis cache
        for i in range(count):
            try:
                cache_key = f"msg_{test_tenant}_{i}"
                cache_data = {
                    "text": test_messages[i],
                    "role": "user" if i % 2 == 0 else "assistant",
                    "session_id": test_session_uuid,
                    "user_id": test_user_uuid,
                    "timestamp": int(time.time())
                }
                cache_manager.put_cache(
                    tenant=test_tenant,
                    user=test_user_uuid,
                    key_signature=cache_key,
                    text=json.dumps(cache_data),
                    ttl_seconds=3600
                )
            except Exception as e:
                logger.error(f"Redis save error: {e}")
        
        redis_write_time = time.time() - redis_start
        
        # Read from Redis
        redis_read_start = time.time()
        try:
            # Search for cached messages
            logger.info(f"Attempting Redis text_search with tenant={test_tenant}, user={test_user_uuid}")
            redis_results = cache_manager.text_search(
                tenant=test_tenant,
                query="session",
                user=test_user_uuid,
                limit=count
            )
            logger.info(f"Redis text_search completed successfully, found {len(redis_results.get('hits', []))} results")
        except Exception as e:
            logger.error(f"Redis read error: {e}")
            # Try a fallback approach without user filter
            try:
                logger.info(f"Trying fallback search without user filter")
                redis_results = cache_manager.text_search(
                    tenant=test_tenant,
                    query="session",
                    limit=count
                )
                logger.info(f"Fallback search completed, found {len(redis_results.get('hits', []))} results")
            except Exception as e2:
                logger.error(f"Fallback Redis search also failed: {e2}")
                redis_results = {"hits": []}
        redis_read_time = time.time() - redis_read_start
        
        redis_total_time = redis_write_time + redis_read_time
        
        # Store results
        test_results["postgresql"][count] = {
            "write_time": pg_write_time,
            "read_time": pg_read_time,
            "total_time": pg_total_time,
            "records_found": len(pg_history),
            "throughput_writes": count / pg_write_time if pg_write_time > 0 else 0,
            "throughput_reads": len(pg_history) / pg_read_time if pg_read_time > 0 else 0
        }
        
        test_results["redis"][count] = {
            "write_time": redis_write_time,
            "read_time": redis_read_time,
            "total_time": redis_total_time,
            "records_found": len(redis_results.get("hits", [])),
            "throughput_writes": count / redis_write_time if redis_write_time > 0 else 0,
            "throughput_reads": len(redis_results.get("hits", [])) / redis_read_time if redis_read_time > 0 else 0
        }
        
        # Performance comparison for this count
        speed_improvement = (pg_total_time / redis_total_time) if redis_total_time > 0 else 0
        test_results["summary"][count] = {
            "redis_faster_by": speed_improvement,
            "pg_vs_redis_ratio": pg_total_time / redis_total_time if redis_total_time > 0 else float('inf')
        }
        
        logger.info(f"Results for {count} messages:")
        logger.info(f"  PostgreSQL: Write={pg_write_time:.4f}s, Read={pg_read_time:.4f}s, Total={pg_total_time:.4f}s")
        logger.info(f"  Redis: Write={redis_write_time:.4f}s, Read={redis_read_time:.4f}s, Total={redis_total_time:.4f}s")
        logger.info(f"  Speed improvement: {speed_improvement:.2f}x")
        
        # Cleanup test data
        try:
            db.execute("DELETE FROM messages WHERE session_id = %s", (test_session_uuid,))
            cache_manager.clear_tenant_cache(test_tenant)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    # Overall summary
    avg_improvement = sum(test_results["summary"][count]["redis_faster_by"] 
                         for count in message_counts) / len(message_counts)
    
    logger.info("=== PERFORMANCE TEST SUMMARY ===")
    logger.info(f"Average Redis speed improvement: {avg_improvement:.2f}x")
    logger.info(f"Test completed for message counts: {message_counts}")
    
    return {
        "status": "completed",
        "results": test_results,
        "average_improvement": avg_improvement,
        "test_timestamp": time.time()
    }


def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = utils.parse_body(event)
    logger.debug("Incoming body: %s", body)

    results = performance_test()
    logger.error("Performance test results:", extra=results)
    return

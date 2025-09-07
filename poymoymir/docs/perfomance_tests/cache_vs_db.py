def performance_test():
    """
    Performance comparison test between Redis (CacheManager), SQLite-Vec (CacheSQLVecManager),
    and PostgreSQL (DatabaseManager) for session & history operations.
    """

    import numpy as np
    import time
    import json

    logger.info("Starting performance test: Redis vs SQLite-Vec vs PostgreSQL")

    vec = np.random.rand(1536).astype(np.float32)     # ваш эмбеддинг
    # Convert numpy array to Python list for database compatibility
    vec_list = vec.tolist()

    # Test parameters
    message_counts = [4, 8, 16]
    test_results = {
        "postgresql": {},
        "redis": {},
        "sqlitevec": {},
        "summary": {}
    }

    # Setup test data
    test_user_uuid = "d9928cfe-3b37-4b26-9ddb-89c0275413ba"
    test_session_uuid = "9e4f8054-5e1b-4dd9-98b3-70df40a85f32"
    test_tenant = "perftesta"  # Use simple name without special characters
    test_tenant_sqlvec = "perftest_sqlvec"  # Separate tenant for SQLite-Vec

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
                    vec_list,  # Use Python list instead of numpy array
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

        # Redis Cache Performance Test
        redis_start = time.time()
        cache_keys = []

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
                # Use correct cache API without blob parameter
                cache_manager.put_cache(
                    tenant=test_tenant,
                    user=test_user_uuid,
                    key_signature=cache_key,
                    text=json.dumps(cache_data),
                    ttl_seconds=3600
                )
                cache_keys.append(cache_key)
            except Exception as e:
                logger.error(f"Redis save error: {e}")

        redis_write_time = time.time() - redis_start

        # Read from Redis cache - test both get and search operations
        redis_read_start = time.time()
        redis_results = {"hits": []}

        try:
            # Test individual cache retrievals (similar to PostgreSQL fetch)
            retrieved_count = 0
            for cache_key in cache_keys:
                cached_entry = cache_manager.get_cache_by_signature(test_tenant, cache_key)
                if cached_entry:
                    retrieved_count += 1

            # Also test text search functionality
            search_results = cache_manager.text_search(
                tenant=test_tenant,
                query="сообщение",  # Search for actual content instead of "session"
                user=test_user_uuid,
                limit=count
            )

            redis_results = {
                "hits": search_results.get("hits", []),
                "retrieved_individually": retrieved_count
            }

            logger.info(f"Redis operations: {retrieved_count} individual retrievals, {len(search_results.get('hits', []))} search results")

        except Exception as e:
            logger.error(f"Redis read error: {e}")
            # Try fallback search without user filter
            try:
                logger.info(f"Trying fallback search without user filter")
                search_results = cache_manager.text_search(
                    tenant=test_tenant,
                    query="сообщение",
                    limit=count
                )
                redis_results = {
                    "hits": search_results.get("hits", []),
                    "retrieved_individually": 0
                }
                logger.info(f"Fallback search completed, found {len(search_results.get('hits', []))} results")
            except Exception as e2:
                logger.error(f"Fallback Redis search also failed: {e2}")
                redis_results = {"hits": [], "retrieved_individually": 0}

        redis_read_time = time.time() - redis_read_start
        redis_total_time = redis_write_time + redis_read_time

        # SQLite-Vec Cache Performance Test
        sqlvec_start = time.time()
        sqlvec_cache_keys = []

        # Save to SQLite-Vec cache
        for i in range(count):
            try:
                cache_key = f"msg_{test_tenant_sqlvec}_{i}"
                cache_data = {
                    "text": test_messages[i],
                    "role": "user" if i % 2 == 0 else "assistant",
                    "session_id": test_session_uuid,
                    "user_id": test_user_uuid,
                    "timestamp": int(time.time())
                }
                # Use SQLite-Vec cache API
                sqlvec_cache_manager.put_cache(
                    tenant=test_tenant_sqlvec,
                    user=test_user_uuid,
                    key_signature=cache_key,
                    text=json.dumps(cache_data),
                    ttl_seconds=3600
                )
                sqlvec_cache_keys.append(cache_key)
            except Exception as e:
                logger.error(f"SQLite-Vec save error: {e}")

        sqlvec_write_time = time.time() - sqlvec_start

        # Read from SQLite-Vec cache - test both get and search operations
        sqlvec_read_start = time.time()
        sqlvec_results = {"hits": []}

        try:
            # Test individual cache retrievals
            retrieved_count = 0
            for cache_key in sqlvec_cache_keys:
                cached_entry = sqlvec_cache_manager.get_cache_by_signature(test_tenant_sqlvec, cache_key)
                if cached_entry:
                    retrieved_count += 1

            # Also test text search functionality
            search_results = sqlvec_cache_manager.text_search(
                tenant=test_tenant_sqlvec,
                query="сообщение",  # Search for actual content
                user=test_user_uuid,
                limit=count
            )

            sqlvec_results = {
                "hits": search_results.get("hits", []),
                "retrieved_individually": retrieved_count
            }

            logger.info(f"SQLite-Vec operations: {retrieved_count} individual retrievals, {len(search_results.get('hits', []))} search results")

        except Exception as e:
            logger.error(f"SQLite-Vec read error: {e}")
            # Try fallback search without user filter
            try:
                logger.info(f"Trying SQLite-Vec fallback search without user filter")
                search_results = sqlvec_cache_manager.text_search(
                    tenant=test_tenant_sqlvec,
                    query="сообщение",
                    limit=count
                )
                sqlvec_results = {
                    "hits": search_results.get("hits", []),
                    "retrieved_individually": 0
                }
                logger.info(f"SQLite-Vec fallback search completed, found {len(search_results.get('hits', []))} results")
            except Exception as e2:
                logger.error(f"SQLite-Vec fallback search also failed: {e2}")
                sqlvec_results = {"hits": [], "retrieved_individually": 0}

        sqlvec_read_time = time.time() - sqlvec_read_start
        sqlvec_total_time = sqlvec_write_time + sqlvec_read_time

        # Store results
        total_redis_found = redis_results.get("retrieved_individually", 0) + len(redis_results.get("hits", []))
        total_sqlvec_found = sqlvec_results.get("retrieved_individually", 0) + len(sqlvec_results.get("hits", []))

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
            "records_found": total_redis_found,
            "individual_retrievals": redis_results.get("retrieved_individually", 0),
            "search_results": len(redis_results.get("hits", [])),
            "throughput_writes": count / redis_write_time if redis_write_time > 0 else 0,
            "throughput_reads": total_redis_found / redis_read_time if redis_read_time > 0 else 0
        }

        test_results["sqlitevec"][count] = {
            "write_time": sqlvec_write_time,
            "read_time": sqlvec_read_time,
            "total_time": sqlvec_total_time,
            "records_found": total_sqlvec_found,
            "individual_retrievals": sqlvec_results.get("retrieved_individually", 0),
            "search_results": len(sqlvec_results.get("hits", [])),
            "throughput_writes": count / sqlvec_write_time if sqlvec_write_time > 0 else 0,
            "throughput_reads": total_sqlvec_found / sqlvec_read_time if sqlvec_read_time > 0 else 0
        }

        # Performance comparison for this count
        redis_speed_improvement = (pg_total_time / redis_total_time) if redis_total_time > 0 else 0
        sqlvec_speed_improvement = (pg_total_time / sqlvec_total_time) if sqlvec_total_time > 0 else 0
        redis_vs_sqlvec = (sqlvec_total_time / redis_total_time) if redis_total_time > 0 else 0

        test_results["summary"][count] = {
            "redis_faster_than_pg": redis_speed_improvement,
            "sqlvec_faster_than_pg": sqlvec_speed_improvement,
            "redis_vs_sqlvec_ratio": redis_vs_sqlvec,
            "pg_vs_redis_ratio": pg_total_time / redis_total_time if redis_total_time > 0 else float('inf'),
            "pg_vs_sqlvec_ratio": pg_total_time / sqlvec_total_time if sqlvec_total_time > 0 else float('inf')
        }

        logger.info(f"Results for {count} messages:")
        logger.info(f"  PostgreSQL: Write={pg_write_time:.4f}s, Read={pg_read_time:.4f}s, Total={pg_total_time:.4f}s, Found={len(pg_history)}")
        logger.info(f"  Redis: Write={redis_write_time:.4f}s, Read={redis_read_time:.4f}s, Total={redis_total_time:.4f}s, Found={total_redis_found}")
        logger.info(f"  SQLite-Vec: Write={sqlvec_write_time:.4f}s, Read={sqlvec_read_time:.4f}s, Total={sqlvec_total_time:.4f}s, Found={total_sqlvec_found}")
        logger.info(f"  Redis vs PostgreSQL: {redis_speed_improvement:.2f}x")
        logger.info(f"  SQLite-Vec vs PostgreSQL: {sqlvec_speed_improvement:.2f}x")
        logger.info(f"  Redis vs SQLite-Vec: {redis_vs_sqlvec:.2f}x")

        # Cleanup test data
        try:
            db.execute("DELETE FROM messages WHERE session_id = %s", (test_session_uuid,))
            cache_manager.clear_tenant_cache(test_tenant)
            sqlvec_cache_manager.clear_tenant_cache(test_tenant_sqlvec)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    # Overall summary
    avg_redis_improvement = sum(test_results["summary"][count]["redis_faster_than_pg"]
                         for count in message_counts) / len(message_counts)
    avg_sqlvec_improvement = sum(test_results["summary"][count]["sqlvec_faster_than_pg"]
                         for count in message_counts) / len(message_counts)
    avg_redis_vs_sqlvec = sum(test_results["summary"][count]["redis_vs_sqlvec_ratio"]
                         for count in message_counts) / len(message_counts)

    logger.info("=== PERFORMANCE TEST SUMMARY ===")
    logger.info(f"Average Redis vs PostgreSQL improvement: {avg_redis_improvement:.2f}x")
    logger.info(f"Average SQLite-Vec vs PostgreSQL improvement: {avg_sqlvec_improvement:.2f}x")
    logger.info(f"Average Redis vs SQLite-Vec ratio: {avg_redis_vs_sqlvec:.2f}x")
    logger.info(f"Test completed for message counts: {message_counts}")

    return {
        "status": "completed",
        "results": test_results,
        "average_redis_improvement": avg_redis_improvement,
        "average_sqlvec_improvement": avg_sqlvec_improvement,
        "average_redis_vs_sqlvec": avg_redis_vs_sqlvec,
        "test_timestamp": time.time()
    }


def handler(event: Dict[str, Any], context):
    logger.debug("Incoming event: %s", event)
    body = utils.parse_body(event)
    logger.debug("Incoming body: %s", body)

    results = performance_test()
    logger.info("Performance test results:", extra=results)
    return

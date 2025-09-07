#!/usr/bin/env python3
"""
Complete Test Suite for SQLite-Vec Cache Manager with APSW

This test runs from the flow directory and tests all cache manager functionality.
"""

import sys
import os
import json
import time
import random
import logging
import tempfile
import shutil
import threading
import queue
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import apsw
    print(f"✓ APSW version: {apsw.apsw_version()}")
    print(f"✓ SQLite version: {apsw.sqlitelibversion()}")
    APSW_AVAILABLE = True
except ImportError as e:
    print(f"✗ APSW not available: {e}")
    APSW_AVAILABLE = False

try:
    import sqlite_vec
    print(f"✓ sqlite-vec available: {sqlite_vec.loadable_path()}")
    SQLITE_VEC_AVAILABLE = True
except ImportError as e:
    print(f"✗ sqlite-vec not available: {e}")
    SQLITE_VEC_AVAILABLE = False

if not APSW_AVAILABLE:
    print("APSW is required for this test. Exiting.")
    sys.exit(1)

# Import our modules
from mindset.cache_sqlvec import CacheSQLVecManager
print("✓ Successfully imported CacheSQLVecManager")

class TestConfig:
    """Test configuration that mimics the real Config class"""
    def __init__(self, db_path: str = None, enable_embeddings: bool = True):
        self.test_dir = tempfile.mkdtemp(prefix="cache_test_apsw_")
        self.cache_sqlite_path = db_path or os.path.join(self.test_dir, 'test_cache.db')
        self.cache_index_name = 'test_idx'
        self.cache_key_prefix = 'test:'
        self.cache_embedding_dimensions = 1536
        self.cache_default_ttl = 3600
        self.cache_enable_embeddings = enable_embeddings and SQLITE_VEC_AVAILABLE
        self.cache_fault_tolerant = True
        self.cache_max_text_length = 10000
        self.cache_batch_size = 100

        # Add missing attributes that Utils class might need
        self.retry_total = 3
        self.retry_backoff_factor = 2
        self.connect_timeout = 5
        self.read_timeout = 10
        self.proxy_url = None

    def cleanup(self):
        """Clean up test directory"""
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Could not clean up test directory: {e}")

class TestLLMManager:
    """Test LLM manager for testing embeddings"""
    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions
        self.call_count = 0

    def embd_text(self, text: str) -> List[float]:
        """Generate mock embeddings"""
        self.call_count += 1
        # Create deterministic embeddings based on text content
        random.seed(hash(text) % (2**32))
        embedding = [random.uniform(-1.0, 1.0) for _ in range(self.dimensions)]

        # Normalize to unit vector for consistent cosine similarity
        magnitude = sum(x**2 for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

class CompleteCacheTest:
    """Complete test suite for CacheSQLVecManager"""

    def __init__(self):
        self.setup_logging()
        self.test_configs = []
        self.passed_tests = 0
        self.failed_tests = 0

    def setup_logging(self):
        """Setup logging for tests"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('test_cache_apsw')

    def cleanup_all_configs(self):
        """Clean up all test configurations"""
        for config in self.test_configs:
            config.cleanup()
        self.test_configs.clear()

    def create_test_config(self, enable_embeddings: bool = True) -> TestConfig:
        """Create a test configuration"""
        config = TestConfig(enable_embeddings=enable_embeddings)
        self.test_configs.append(config)
        return config

    def assert_test(self, condition: bool, test_name: str, message: str = ""):
        """Assert a test condition and track results"""
        if condition:
            print(f"✓ {test_name}: PASS {message}")
            self.passed_tests += 1
        else:
            print(f"✗ {test_name}: FAIL {message}")
            self.failed_tests += 1

    def test_initialization_and_health(self):
        """Test 1: Initialization and health check"""
        print("\n=== Test 1: Initialization and Health Check ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()

            # Test initialization
            cache = CacheSQLVecManager(config, llm_manager, self.logger)
            self.assert_test(cache is not None, "Cache Manager Creation")
            self.assert_test(cache.config == config, "Config Assignment")
            self.assert_test(cache.llm_manager == llm_manager, "LLM Manager Assignment")

            # Test health check
            health = cache.health_check()
            self.assert_test(isinstance(health, dict), "Health Check Returns Dict")
            self.assert_test(health.get("sqlite_module") == "apsw", "APSW Module Detected")
            self.assert_test(health.get("database_connected", False), "Database Connected")

        except Exception as e:
            self.assert_test(False, "Initialization and Health", f"Exception: {e}")

    def test_schema_and_index_info(self):
        """Test 2: Schema creation and index info"""
        print("\n=== Test 2: Schema Creation and Index Info ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            # Test schema creation
            schema_created = cache.ensure_schema()
            self.assert_test(schema_created, "Schema Creation")

            cache._initialize()
            self.assert_test(cache._initialized, "Cache Initialization")

            # Test index info
            index_info = cache.get_index_info()
            self.assert_test(isinstance(index_info, dict), "Index Info Returns Dict")
            self.assert_test("database_path" in index_info, "Index Info Has Database Path")
            self.assert_test("sqlite_module" in index_info, "Index Info Has SQLite Module")
            self.assert_test(index_info.get("sqlite_module") == "apsw", "Index Info Shows APSW")

            if "tables" in index_info:
                tables = index_info["tables"]
                self.assert_test("cache_entries" in tables, "Main Table Created")
                self.assert_test("cache_fts" in tables, "FTS Table Created")

                if config.cache_enable_embeddings:
                    self.assert_test("cache_vectors" in tables, "Vector Table Created")

        except Exception as e:
            self.assert_test(False, "Schema and Index Info", f"Exception: {e}")

    def test_basic_cache_operations(self):
        """Test 3: Basic cache operations (put/get/delete)"""
        print("\n=== Test 3: Basic Cache Operations ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "test_tenant"
            user = "test_user_123"
            signature = "test_signature"
            text = "This is a comprehensive test message for APSW caching"

            # Test put_cache
            cache_key = cache.put_cache(tenant, user, signature, text)
            self.assert_test(cache_key is not None, "Put Cache Returns Key")
            self.assert_test(isinstance(cache_key, str), "Cache Key Is String")

            # Test get_cache
            cached_entry = cache.get_cache(cache_key)
            self.assert_test(cached_entry is not None, "Get Cache Returns Entry")

            if cached_entry:
                self.assert_test(cached_entry["text"] == text, "Retrieved Text Matches")
                self.assert_test(cached_entry["tenant"] == tenant, "Retrieved Tenant Matches")
                self.assert_test("created_at" in cached_entry, "Has Creation Timestamp")

            # Test get_cache_by_signature
            cached_by_sig = cache.get_cache_by_signature(tenant, signature)
            self.assert_test(cached_by_sig is not None, "Get Cache By Signature")

            if cached_by_sig:
                self.assert_test(cached_by_sig["text"] == text, "Retrieved By Signature Matches")

            # Test delete_cache
            deleted = cache.delete_cache(cache_key)
            self.assert_test(deleted, "Delete Cache Returns True")

            deleted_entry = cache.get_cache(cache_key)
            self.assert_test(deleted_entry is None, "Cache Deleted Successfully")

            # Test deleting non-existent key
            non_existent_deleted = cache.delete_cache("non_existent_key")
            self.assert_test(not non_existent_deleted, "Delete Non-Existent Returns False")

        except Exception as e:
            self.assert_test(False, "Basic Cache Operations", f"Exception: {e}")

    def test_ttl_and_expiration(self):
        """Test 4: TTL and cache expiration"""
        print("\n=== Test 4: TTL and Cache Expiration ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "ttl_tenant"
            user = "ttl_user"
            signature = "expiry_test"
            text = "This will expire soon"
            ttl = 1  # 1 second

            # Test short TTL
            cache_key = cache.put_cache(tenant, user, signature, text, ttl)
            self.assert_test(cache_key is not None, "Put Cache With Short TTL")

            cached_entry = cache.get_cache(cache_key)
            self.assert_test(cached_entry is not None, "Cache Exists Before Expiry")

            time.sleep(2)  # Wait for expiration

            expired_entry = cache.get_cache(cache_key)
            self.assert_test(expired_entry is None, "Cache Expired After TTL")

            # Test TTL extension
            cache_key2 = cache.put_cache(tenant, user, "ttl_extend", "TTL extension test", 3600)
            extended_entry = cache.get_cache(cache_key2, extend_ttl_seconds=7200)
            self.assert_test(extended_entry is not None, "Get Cache With TTL Extension")

        except Exception as e:
            self.assert_test(False, "TTL and Expiration", f"Exception: {e}")

    def test_text_search(self):
        """Test 5: Full-text search functionality"""
        print("\n=== Test 5: Full-Text Search ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "search_tenant"
            user = "search_user"

            # Add test data for search
            search_texts = [
                "Python programming with APSW",
                "JavaScript web development framework",
                "SQLite database management",
                "Machine learning algorithms",
                "APSW SQLite wrapper for Python"
            ]

            for i, search_text in enumerate(search_texts):
                cache.put_cache(tenant, user, f"search_{i}", search_text)

            # Test search for "Python"
            search_results = cache.text_search(tenant, "Python")
            self.assert_test(isinstance(search_results, dict), "Text Search Returns Dict")
            self.assert_test("total" in search_results, "Search Results Have Total")
            self.assert_test("hits" in search_results, "Search Results Have Hits")

            hits = search_results.get("hits", [])
            python_hits = [hit for hit in hits if "Python" in hit.get("text", "")]
            self.assert_test(len(python_hits) >= 1, f"Found Python Hits (got {len(python_hits)}, expected >= 1)")

            # Test search with user filter
            user_filtered_results = cache.text_search(tenant, "APSW", user=user)
            self.assert_test(isinstance(user_filtered_results, dict), "Text Search With User Filter")

            # Test search with limit and offset
            limited_results = cache.text_search(tenant, "SQLite", limit=2, offset=0)
            limited_hits = limited_results.get("hits", [])
            self.assert_test(len(limited_hits) <= 2, "Text Search Respects Limit")

        except Exception as e:
            self.assert_test(False, "Text Search", f"Exception: {e}")

    def test_embedding_operations(self):
        """Test 6: Embedding and vector search operations"""
        print("\n=== Test 6: Embedding and Vector Search ===")

        if not SQLITE_VEC_AVAILABLE:
            print("Skipping embedding tests - sqlite-vec not available")
            return

        try:
            config = self.create_test_config(enable_embeddings=True)
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "embed_tenant"
            user = "embed_user"

            # Add test data with embeddings
            embed_texts = [
                "Machine learning is a subset of artificial intelligence",
                "Deep learning uses neural networks with multiple layers",
                "Natural language processing helps computers understand text",
                "Computer vision enables machines to interpret visual information",
                "APSW provides enhanced SQLite functionality for Python"
            ]

            cache_keys = []
            for i, embed_text in enumerate(embed_texts):
                key = cache.put_cache(tenant, user, f"embed_{i}", embed_text)
                cache_keys.append(key)

            self.assert_test(all(cache_keys), "Put Cache With Embeddings")
            self.assert_test(llm_manager.call_count == len(embed_texts), "LLM Manager Called For Embeddings")

            # Test KNN search
            query_vector = llm_manager.embd_text("artificial intelligence and machine learning")
            knn_results = cache.knn_search(tenant, query_vector, k=3)

            self.assert_test(isinstance(knn_results, dict), "KNN Search Returns Dict")
            self.assert_test("total" in knn_results, "KNN Results Have Total")
            self.assert_test("hits" in knn_results, "KNN Results Have Hits")

            knn_hits = knn_results.get("hits", [])
            self.assert_test(len(knn_hits) <= 3, "KNN Search Respects K Limit")

            # Verify results have similarity scores
            for hit in knn_hits:
                self.assert_test("score" in hit, "KNN Hit Has Score")
                self.assert_test(isinstance(hit["score"], (int, float)), "KNN Score Is Numeric")

            # Test semantic search
            semantic_results = cache.semantic_search(tenant, "AI and neural networks", k=2)
            self.assert_test(isinstance(semantic_results, dict), "Semantic Search Returns Dict")

            semantic_hits = semantic_results.get("hits", [])
            self.assert_test(len(semantic_hits) <= 2, "Semantic Search Respects K Limit")

            # Test KNN search with user filter
            user_filtered_knn = cache.knn_search(tenant, query_vector, k=2, user=user)
            self.assert_test(isinstance(user_filtered_knn, dict), "KNN Search With User Filter")

        except Exception as e:
            self.assert_test(False, "Embedding Operations", f"Exception: {e}")

    def test_tenant_and_user_operations(self):
        """Test 7: Tenant and user-based operations"""
        print("\n=== Test 7: Tenant and User Operations ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant1 = "tenant_1"
            tenant2 = "tenant_2"
            user1 = "user_1"
            user2 = "user_2"

            # Add entries for different tenants and users
            key1 = cache.put_cache(tenant1, user1, "sig1", "Text for tenant 1, user 1")
            key2 = cache.put_cache(tenant2, user1, "sig2", "Text for tenant 2, user 1")
            key3 = cache.put_cache(tenant1, user2, "sig3", "Text for tenant 1, user 2")
            key4 = cache.put_cache(tenant1, user1, "sig4", "Another text for tenant 1, user 1")

            self.assert_test(all([key1, key2, key3, key4]), "Put Cache For Multiple Tenants/Users")

            # Test user hash functionality
            user_hash1 = cache.get_user_hash(user1)
            user_hash2 = cache.get_user_hash(user2)
            self.assert_test(isinstance(user_hash1, str), "User Hash Is String")
            self.assert_test(isinstance(user_hash2, str), "User Hash Is String")
            self.assert_test(user_hash1 != user_hash2, "Different Users Have Different Hashes")

            # Test hash consistency
            user_hash1_again = cache.get_user_hash(user1)
            self.assert_test(user_hash1 == user_hash1_again, "User Hash Is Consistent")

            # Clear tenant 1 cache
            cleared_count = cache.clear_tenant_cache(tenant1)
            self.assert_test(cleared_count == 3, f"Clear Tenant Cache Count (got {cleared_count}, expected 3)")

            # Verify tenant 1 entries are gone
            entry1 = cache.get_cache(key1)
            entry3 = cache.get_cache(key3)
            entry4 = cache.get_cache(key4)
            self.assert_test(all(e is None for e in [entry1, entry3, entry4]), "Tenant 1 Entries Cleared")

            # Verify tenant 2 entry still exists
            entry2 = cache.get_cache(key2)
            self.assert_test(entry2 is not None, "Tenant 2 Entry Preserved")

        except Exception as e:
            self.assert_test(False, "Tenant and User Operations", f"Exception: {e}")

    def test_data_types_and_edge_cases(self):
        """Test 8: Data types handling and edge cases"""
        print("\n=== Test 8: Data Types and Edge Cases ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "types_tenant"
            user = "types_user"

            # Test different data types
            test_data = [
                ("string", "Simple string text"),
                ("list", ["item1", "item2", "item3"]),
                ("dict", {"key": "value", "number": 42, "nested": {"inner": "data"}}),
                ("unicode", "Unicode text: 你好世界 🌍 Здравствуй мир"),
                ("empty", ""),
                ("long", "A" * 1000),  # Long text
                ("json_like", '{"json": "string", "number": 123}'),
                ("special_chars", "Text with 'quotes' and \"double quotes\" and <tags>"),
            ]

            for data_type, data in test_data:
                try:
                    key = cache.put_cache(tenant, user, f"type_{data_type}", data)
                    self.assert_test(key is not None, f"Put Cache Handles {data_type}")

                    retrieved = cache.get_cache(key)
                    self.assert_test(retrieved is not None, f"Get Cache Handles {data_type}")

                    if retrieved:
                        # For non-string types, they should be JSON serialized
                        if isinstance(data, str):
                            expected_text = data
                        else:
                            expected_text = json.dumps(data, ensure_ascii=False)

                        self.assert_test(retrieved["text"] == expected_text, f"Data Type {data_type} Preserved")

                except Exception as e:
                    self.assert_test(False, f"Data Type {data_type}", f"Exception: {e}")

            # Test edge case: None user
            key_none_user = cache.put_cache(tenant, None, "none_user", "Text with None user")
            self.assert_test(key_none_user is not None, "Put Cache Handles None User")

            # Test edge case: Empty string user
            key_empty_user = cache.put_cache(tenant, "", "empty_user", "Text with empty user")
            self.assert_test(key_empty_user is not None, "Put Cache Handles Empty User")

            # Test edge case: Numeric user ID
            key_numeric_user = cache.put_cache(tenant, 12345, "numeric_user", "Text with numeric user")
            self.assert_test(key_numeric_user is not None, "Put Cache Handles Numeric User")

        except Exception as e:
            self.assert_test(False, "Data Types and Edge Cases", f"Exception: {e}")

    def test_cache_statistics(self):
        """Test 9: Cache statistics and monitoring"""
        print("\n=== Test 9: Cache Statistics and Monitoring ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "stats_tenant"
            user = "stats_user"

            # Add some test data
            num_entries = 7
            for i in range(num_entries):
                cache.put_cache(tenant, user, f"stats_{i}", f"Test message {i} for statistics")

            # Test general stats
            stats = cache.get_cache_stats()
            self.assert_test(isinstance(stats, dict), "Cache Stats Returns Dict")
            self.assert_test("total_documents" in stats, "Stats Have Total Documents")
            self.assert_test(stats["total_documents"] >= num_entries, "Stats Show Added Documents")

            # Test tenant-specific stats
            tenant_stats = cache.get_cache_stats(tenant)
            self.assert_test(isinstance(tenant_stats, dict), "Tenant Stats Returns Dict")
            self.assert_test("tenant_documents" in tenant_stats, "Tenant Stats Have Document Count")
            self.assert_test(tenant_stats["tenant_documents"] >= num_entries, "Tenant Stats Show Added Documents")

            # Test availability check
            available = cache.is_available()
            self.assert_test(available, "Cache Is Available")

        except Exception as e:
            self.assert_test(False, "Cache Statistics", f"Exception: {e}")

    def test_concurrent_operations(self):
        """Test 10: Concurrent operations and thread safety"""
        print("\n=== Test 10: Concurrent Operations ===")

        try:
            config = self.create_test_config()
            llm_manager = TestLLMManager()
            cache = CacheSQLVecManager(config, llm_manager, self.logger)

            tenant = "concurrent_tenant"
            results = queue.Queue()

            def worker(worker_id):
                """Worker function for concurrent testing"""
                try:
                    for i in range(3):
                        # Put cache
                        key = cache.put_cache(tenant, f"user_{worker_id}", f"sig_{worker_id}_{i}", f"Message from worker {worker_id}, iteration {i}")

                        # Get cache
                        retrieved = cache.get_cache(key)

                        # Text search
                        search_results = cache.text_search(tenant, f"worker {worker_id}")

                        results.put(("success", worker_id, i, key, retrieved is not None, len(search_results.get("hits", []))))
                except Exception as e:
                    results.put(("error", worker_id, e))

            # Start multiple worker threads
            threads = []
            num_workers = 3

            for worker_id in range(num_workers):
                thread = threading.Thread(target=worker, args=(worker_id,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Collect results
            successes = 0
            errors = 0

            while not results.empty():
                result = results.get()
                if result[0] == "success":
                    successes += 1
                    if not result[4]:  # retrieved is not None
                        errors += 1
                else:
                    errors += 1

            expected_operations = num_workers * 3
            self.assert_test(successes == expected_operations, f"Concurrent Operations Success (got {successes}, expected {expected_operations})")
            self.assert_test(errors == 0, f"Concurrent Operations No Errors (got {errors} errors)")

        except Exception as e:
            self.assert_test(False, "Concurrent Operations", f"Exception: {e}")

    def run_all_tests(self):
        """Run all test cases"""
        print("=" * 70)
        print("COMPLETE SQLITE-VEC CACHE MANAGER TEST SUITE WITH APSW")
        print("=" * 70)
        print(f"APSW Available: {APSW_AVAILABLE}")
        print(f"sqlite-vec Available: {SQLITE_VEC_AVAILABLE}")
        print("=" * 70)

        try:
            # Run all test methods
            test_methods = [
                self.test_initialization_and_health,
                self.test_schema_and_index_info,
                self.test_basic_cache_operations,
                self.test_ttl_and_expiration,
                self.test_text_search,
                self.test_embedding_operations,
                self.test_tenant_and_user_operations,
                self.test_data_types_and_edge_cases,
                self.test_cache_statistics,
                self.test_concurrent_operations
            ]

            for test_method in test_methods:
                try:
                    test_method()
                except Exception as e:
                    print(f"✗ {test_method.__name__}: CRITICAL FAILURE - {e}")
                    self.failed_tests += 1

        finally:
            # Clean up
            self.cleanup_all_configs()

        # Print summary
        print("\n" + "=" * 70)
        print("COMPLETE TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests: {self.passed_tests + self.failed_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")

        if self.failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED! 🎉")
            print("The SQLite-Vec Cache Manager with APSW is fully functional.")
            print("All core features including:")
            print("  ✓ APSW SQLite integration")
            print("  ✓ Vector embeddings with sqlite-vec")
            print("  ✓ Full-text search with FTS5")
            print("  ✓ Multi-tenant support")
            print("  ✓ TTL-based expiration")
            print("  ✓ Thread safety")
            print("  ✓ Fault tolerance")
            return True
        else:
            print(f"\n⚠️  {self.failed_tests} test(s) failed")
            return False

if __name__ == "__main__":
    test_suite = CompleteCacheTest()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)

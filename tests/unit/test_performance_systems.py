#!/usr/bin/env python3
"""Tests for performance engineering systems"""
import unittest
import asyncio
import tempfile
import json
import time
import sys
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.distributed.query_service import (
    LoadBalancer, WorkerNode, QueryRequest, QueryResponse, 
    WorkerType, ServiceStatus, DistributedQueryService
)
from src.performance.caching import (
    MemoryCache, DiskCache, MultiLevelCache, CacheLevel, CacheEntry
)
from src.performance.benchmarking import (
    PerformanceBenchmark, PerformanceMetrics, BenchmarkResult, SystemMonitor
)

class TestDistributedQueryService(unittest.TestCase):
    """Test distributed query service components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.load_balancer = LoadBalancer()
        
        # Create test workers
        self.worker1 = WorkerNode(
            node_id="test-worker-1",
            worker_type=WorkerType.OLLAMA,
            endpoint="http://localhost:11434",
            status=ServiceStatus.HEALTHY,
            current_load=0,
            max_capacity=4,
            avg_response_time=1000.0,
            total_requests=100,
            successful_requests=95,
            last_heartbeat=time.time(),
            models=["llama3.1:latest", "deepseek-r1:14b"]
        )
        
        self.worker2 = WorkerNode(
            node_id="test-worker-2",
            worker_type=WorkerType.OLLAMA,
            endpoint="http://localhost:11435",
            status=ServiceStatus.DEGRADED,
            current_load=3,
            max_capacity=4,
            avg_response_time=2000.0,
            total_requests=200,
            successful_requests=180,
            last_heartbeat=time.time(),
            models=["llama3.1:latest"]
        )
    
    def test_worker_node_properties(self):
        """Test WorkerNode calculated properties"""
        self.assertEqual(self.worker1.load_percentage, 0.0)
        self.assertEqual(self.worker1.success_rate, 95.0)
        
        self.assertEqual(self.worker2.load_percentage, 75.0)
        self.assertEqual(self.worker2.success_rate, 90.0)
    
    def test_load_balancer_worker_registration(self):
        """Test worker registration and management"""
        # Register workers
        self.assertTrue(self.load_balancer.register_worker(self.worker1))
        self.assertTrue(self.load_balancer.register_worker(self.worker2))
        
        self.assertEqual(len(self.load_balancer.workers), 2)
        self.assertIn("test-worker-1", self.load_balancer.workers)
        self.assertIn("test-worker-2", self.load_balancer.workers)
        
        # Unregister worker
        self.assertTrue(self.load_balancer.unregister_worker("test-worker-1"))
        self.assertEqual(len(self.load_balancer.workers), 1)
        
        # Try to unregister non-existent worker
        self.assertFalse(self.load_balancer.unregister_worker("non-existent"))
    
    def test_optimal_worker_selection(self):
        """Test optimal worker selection algorithm"""
        # Register workers
        self.load_balancer.register_worker(self.worker1)
        self.load_balancer.register_worker(self.worker2)
        
        # Create test request
        request = QueryRequest(
            request_id="test-123",
            prompt="Test prompt",
            task_id="test-task",
            model="llama3.1:latest",
            method="constrained",
            timeout=60,
            priority=1,
            timestamp=time.time()
        )
        
        # Get optimal worker (should prefer worker1 due to better performance)
        optimal_worker = self.load_balancer.get_optimal_worker(request)
        self.assertIsNotNone(optimal_worker)
        self.assertEqual(optimal_worker.node_id, "test-worker-1")
        
        # Test with model not available on worker1
        request.model = "gpt-4"
        optimal_worker = self.load_balancer.get_optimal_worker(request)
        self.assertIsNone(optimal_worker)  # No worker supports gpt-4
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        request1 = QueryRequest(
            request_id="test1", prompt="test prompt", task_id="task1",
            model="llama3.1", method="constrained", timeout=60, priority=1, timestamp=time.time()
        )
        request2 = QueryRequest(
            request_id="test2", prompt="test prompt", task_id="task2",
            model="llama3.1", method="constrained", timeout=60, priority=1, timestamp=time.time()
        )
        request3 = QueryRequest(
            request_id="test3", prompt="different prompt", task_id="task3",
            model="llama3.1", method="constrained", timeout=60, priority=1, timestamp=time.time()
        )
        
        key1 = self.load_balancer.generate_cache_key(request1)
        key2 = self.load_balancer.generate_cache_key(request2)
        key3 = self.load_balancer.generate_cache_key(request3)
        
        # Same inputs should generate same key
        self.assertEqual(key1, key2)
        # Different inputs should generate different keys
        self.assertNotEqual(key1, key3)
    
    def test_performance_metrics(self):
        """Test performance metrics collection"""
        self.load_balancer.register_worker(self.worker1)
        self.load_balancer.register_worker(self.worker2)
        
        # Simulate some requests
        self.load_balancer.request_history = [
            {"timestamp": time.time(), "execution_time": 1000, "success": True, "cached": False},
            {"timestamp": time.time(), "execution_time": 1500, "success": True, "cached": True},
            {"timestamp": time.time(), "execution_time": 2000, "success": False, "cached": False}
        ]
        
        metrics = self.load_balancer.get_performance_metrics()
        
        self.assertIn("workers", metrics)
        self.assertIn("requests", metrics)
        self.assertIn("cache", metrics)
        self.assertIn("load_distribution", metrics)
        
        self.assertEqual(metrics["workers"]["total"], 2)
        self.assertEqual(metrics["workers"]["healthy"], 1)
        self.assertEqual(metrics["workers"]["degraded"], 1)
        self.assertEqual(metrics["requests"]["total"], 3)
    
    def test_distributed_service_initialization(self):
        """Test distributed service initialization"""
        config = {
            "workers": [
                {
                    "node_id": "test-ollama-1",
                    "worker_type": "ollama",
                    "endpoint": "http://localhost:11434",
                    "max_capacity": 2,
                    "models": ["llama3.1:latest"]
                }
            ]
        }
        
        service = DistributedQueryService(config)
        
        self.assertEqual(len(service.load_balancer.workers), 1)
        self.assertIn("test-ollama-1", service.load_balancer.workers)
        
        status = service.get_status()
        self.assertIn("service", status)
        self.assertIn("performance", status)

class TestCachingSystems(unittest.TestCase):
    """Test caching system components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.memory_cache = MemoryCache(max_size_mb=1, default_ttl=60)
        
        # Use temporary file for disk cache
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.disk_cache = DiskCache(db_path=self.temp_db.name, max_size_mb=1, default_ttl=60)
    
    def tearDown(self):
        """Clean up test fixtures"""
        Path(self.temp_db.name).unlink(missing_ok=True)
    
    def test_memory_cache_basic_operations(self):
        """Test basic memory cache operations"""
        # Test put and get
        test_value = {"query": {"term": {"label": "test"}}}
        
        success = self.memory_cache.put("test prompt", "test-model", "constrained", test_value)
        self.assertTrue(success)
        
        retrieved = self.memory_cache.get("test prompt", "test-model", "constrained")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["query"]["term"]["label"], "test")
        
        # Test cache miss
        not_found = self.memory_cache.get("different prompt", "test-model", "constrained")
        self.assertIsNone(not_found)
    
    def test_memory_cache_ttl_expiration(self):
        """Test TTL expiration in memory cache"""
        test_value = {"query": {"term": {"label": "test"}}}
        
        # Put with very short TTL
        self.memory_cache.put("test prompt", "test-model", "constrained", test_value, ttl=1)
        
        # Should be available immediately
        retrieved = self.memory_cache.get("test prompt", "test-model", "constrained")
        self.assertIsNotNone(retrieved)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        expired = self.memory_cache.get("test prompt", "test-model", "constrained")
        self.assertIsNone(expired)
    
    def test_memory_cache_lru_eviction(self):
        """Test LRU eviction in memory cache"""
        # Fill cache beyond capacity with small cache
        small_cache = MemoryCache(max_size_mb=0.001, default_ttl=60)  # Very small cache
        
        # Add entries until eviction occurs
        for i in range(10):
            small_cache.put(f"prompt_{i}", "test-model", "constrained", 
                          {"data": "x" * 1000})  # Large-ish data
        
        # First entries should be evicted
        first_entry = small_cache.get("prompt_0", "test-model", "constrained")
        self.assertIsNone(first_entry)
        
        # More recent entries should still be available
        recent_entry = small_cache.get("prompt_9", "test-model", "constrained")
        self.assertIsNotNone(recent_entry)
    
    def test_disk_cache_basic_operations(self):
        """Test basic disk cache operations"""
        test_value = {"query": {"term": {"label": "test"}}}
        
        # Test put and get
        success = self.disk_cache.put("test prompt", "test-model", "constrained", test_value)
        self.assertTrue(success)
        
        retrieved = self.disk_cache.get("test prompt", "test-model", "constrained")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["query"]["term"]["label"], "test")
    
    def test_disk_cache_persistence(self):
        """Test disk cache persistence across instances"""
        test_value = {"query": {"term": {"label": "persistent"}}}
        
        # Store in first cache instance
        self.disk_cache.put("persistent prompt", "test-model", "constrained", test_value)
        
        # Create new cache instance with same DB
        new_cache = DiskCache(db_path=self.temp_db.name, max_size_mb=1, default_ttl=60)
        
        # Should retrieve from persistent storage
        retrieved = new_cache.get("persistent prompt", "test-model", "constrained")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["query"]["term"]["label"], "persistent")
    
    def test_multi_level_cache(self):
        """Test multi-level cache operations"""
        # Use temporary DB for multi-level cache
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        try:
            # Create multi-level cache with small memory cache
            cache = MultiLevelCache(memory_size_mb=0.1, disk_size_mb=1)
            
            test_value = {"query": {"term": {"label": "multilevel"}}}
            
            # Put should go to both levels
            cache.put("test prompt", "test-model", "constrained", test_value)
            
            # Get should retrieve from memory (L1)
            retrieved = cache.get("test prompt", "test-model", "constrained")
            self.assertIsNotNone(retrieved)
            
            # Clear memory cache
            cache.memory_cache.clear()
            
            # Should still retrieve from disk (L2)
            retrieved = cache.get("test prompt", "test-model", "constrained")
            self.assertIsNotNone(retrieved)
            
        finally:
            Path(temp_db.name).unlink(missing_ok=True)
    
    def test_cache_statistics(self):
        """Test cache statistics collection"""
        test_value = {"query": {"term": {"label": "stats"}}}
        
        # Generate some cache activity
        self.memory_cache.put("prompt1", "model1", "constrained", test_value)
        self.memory_cache.put("prompt2", "model1", "constrained", test_value)
        
        self.memory_cache.get("prompt1", "model1", "constrained")  # Hit
        self.memory_cache.get("prompt2", "model1", "constrained")  # Hit
        self.memory_cache.get("prompt3", "model1", "constrained")  # Miss
        
        stats = self.memory_cache.get_stats()
        
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 66.67, places=1)
        self.assertGreater(stats["entry_count"], 0)
        self.assertGreater(stats["size_bytes"], 0)

class TestPerformanceBenchmarking(unittest.TestCase):
    """Test performance benchmarking system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.benchmark = PerformanceBenchmark()
        self.monitor = SystemMonitor()
    
    def test_performance_metrics_creation(self):
        """Test PerformanceMetrics data structure"""
        metrics = PerformanceMetrics(
            execution_time_ms=1000.0,
            memory_usage_mb=50.0,
            cpu_usage_percent=25.0,
            success=True,
            error=None,
            worker_id="test-worker",
            timestamp=time.time()
        )
        
        metrics_dict = metrics.to_dict()
        
        self.assertIn("execution_time_ms", metrics_dict)
        self.assertIn("success", metrics_dict)
        self.assertIn("worker_id", metrics_dict)
        self.assertEqual(metrics_dict["execution_time_ms"], 1000.0)
        self.assertTrue(metrics_dict["success"])
    
    def test_system_monitor(self):
        """Test system resource monitoring"""
        # Start monitoring briefly
        self.monitor.start_monitoring(interval=0.1)
        time.sleep(0.3)  # Let it collect a few samples
        self.monitor.stop_monitoring()
        
        # Should have collected some metrics
        self.assertGreater(len(self.monitor.metrics), 0)
        
        # Get peak metrics
        peak_metrics = self.monitor.get_peak_metrics()
        
        self.assertIn("peak_memory_mb", peak_metrics)
        self.assertIn("peak_cpu_percent", peak_metrics)
        self.assertIn("avg_memory_mb", peak_metrics)
        self.assertIn("total_samples", peak_metrics)
        
        self.assertGreater(peak_metrics["total_samples"], 0)
    
    def test_benchmark_result_creation(self):
        """Test BenchmarkResult data structure"""
        # Create mock individual metrics
        individual_metrics = [
            PerformanceMetrics(1000.0, 50.0, 25.0, True, None, "worker-1", time.time()),
            PerformanceMetrics(1200.0, 55.0, 30.0, True, None, "worker-1", time.time()),
            PerformanceMetrics(800.0, 45.0, 20.0, False, "Error", "worker-1", time.time())
        ]
        
        result = BenchmarkResult(
            test_name="test_benchmark",
            total_operations=3,
            successful_operations=2,
            failed_operations=1,
            total_time_seconds=5.0,
            avg_execution_time_ms=1000.0,
            median_execution_time_ms=1100.0,
            p95_execution_time_ms=1200.0,
            p99_execution_time_ms=1200.0,
            min_execution_time_ms=800.0,
            max_execution_time_ms=1200.0,
            operations_per_second=0.4,
            queries_per_minute=24.0,
            avg_memory_usage_mb=50.0,
            peak_memory_usage_mb=55.0,
            avg_cpu_usage_percent=25.0,
            peak_cpu_usage_percent=30.0,
            success_rate_percent=66.67,
            error_rate_percent=33.33,
            avg_concurrent_operations=1.0,
            max_concurrent_operations=1,
            individual_metrics=individual_metrics
        )
        
        result_dict = result.to_dict()
        
        self.assertIn("test_name", result_dict)
        self.assertIn("operations_per_second", result_dict)
        self.assertIn("individual_metrics", result_dict)
        self.assertEqual(result_dict["test_name"], "test_benchmark")
        self.assertEqual(len(result_dict["individual_metrics"]), 3)
    
    @patch('subprocess.run')
    def test_load_test_simulation(self, mock_subprocess):
        """Test load testing simulation logic"""
        # Mock successful subprocess calls
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        # Run a very short load test
        result = self.benchmark._run_load_test(
            test_name="test_load",
            prompt="test prompt", 
            concurrent_users=2,
            duration_seconds=1
        )
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.test_name, "test_load")
        self.assertGreaterEqual(result.total_operations, 0)
    
    def test_benchmark_report_generation(self):
        """Test benchmark report generation"""
        # Create mock results
        mock_metrics = [
            PerformanceMetrics(1000.0, 50.0, 25.0, True, None, "worker-1", time.time())
        ]
        
        mock_result = BenchmarkResult(
            test_name="mock_test",
            total_operations=1,
            successful_operations=1,
            failed_operations=0,
            total_time_seconds=1.0,
            avg_execution_time_ms=1000.0,
            median_execution_time_ms=1000.0,
            p95_execution_time_ms=1000.0,
            p99_execution_time_ms=1000.0,
            min_execution_time_ms=1000.0,
            max_execution_time_ms=1000.0,
            operations_per_second=1.0,
            queries_per_minute=60.0,
            avg_memory_usage_mb=50.0,
            peak_memory_usage_mb=50.0,
            avg_cpu_usage_percent=25.0,
            peak_cpu_usage_percent=25.0,
            success_rate_percent=100.0,
            error_rate_percent=0.0,
            avg_concurrent_operations=1.0,
            max_concurrent_operations=1,
            individual_metrics=mock_metrics
        )
        
        self.benchmark.results = [mock_result]
        
        # Test report generation (use temporary directory)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.benchmark.generate_performance_report(temp_dir)
            
            # Check that files were created
            report_files = list(Path(temp_dir).glob("*"))
            self.assertGreater(len(report_files), 0)
            
            # Check for expected files
            expected_files = ["benchmark_results.json", "performance_summary.md"]
            for expected_file in expected_files:
                self.assertTrue(any(f.name == expected_file for f in report_files))

class TestPerformanceIntegration(unittest.TestCase):
    """Integration tests for performance systems"""
    
    def test_cache_integration_with_generation(self):
        """Test cache integration with query generation"""
        from src.performance.caching import get_global_cache, cached_query_generation, cache_query_result
        
        # Test caching a query result
        test_result = {"query": {"term": {"label": "cached"}}}
        cache_query_result("test prompt", "test-model", test_result)
        
        # Test retrieving cached result
        cached_result = cached_query_generation("test prompt", "test-model")
        self.assertIsNotNone(cached_result)
        self.assertEqual(cached_result["query"]["term"]["label"], "cached")
        
        # Test cache miss
        miss_result = cached_query_generation("different prompt", "test-model")
        self.assertIsNone(miss_result)
    
    def test_performance_monitoring_integration(self):
        """Test integration between different performance components"""
        from src.performance.caching import get_cache_stats
        
        # Generate some cache activity
        from src.performance.caching import cache_query_result
        test_result = {"query": {"term": {"label": "integration"}}}
        
        for i in range(5):
            cache_query_result(f"prompt_{i}", "model", test_result)
        
        # Get cache statistics
        stats = get_cache_stats()
        
        self.assertIn("memory_cache", stats)
        self.assertIn("disk_cache", stats)
        self.assertGreater(stats.get("total_hits", 0) + stats.get("total_misses", 0), 0)
    
    def test_distributed_service_integration(self):
        """Test distributed service integration (sync version)"""
        # Create distributed service
        service = DistributedQueryService()
        
        # Test status retrieval
        status = service.get_status()
        
        self.assertIn("service", status)
        self.assertIn("performance", status)
        self.assertIsInstance(status["service"]["running"], bool)
        
        # Test that service has workers configured
        self.assertGreaterEqual(len(service.load_balancer.workers), 0)

if __name__ == "__main__":
    unittest.main()

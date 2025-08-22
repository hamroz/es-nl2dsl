import time
import threading
import concurrent.futures
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from authentication.rate_limiting import (
    TokenBucketStrategy, SlidingWindowStrategy, AdaptiveStrategy, HierarchicalRateLimiter
)
from authentication.security_middleware import ThreatDetectionMiddleware
from authentication.utils import log_audit_event

User = get_user_model()


class RateLimitPerformanceTestCase(TestCase):
    """Performance tests for rate limiting algorithms."""
    
    def setUp(self):
        """Set up test data."""
        cache.clear()
    
    def test_token_bucket_performance(self):
        """Test token bucket algorithm performance."""
        strategy = TokenBucketStrategy(limit=1000, window=3600, name='perf_test')
        
        start_time = time.time()
        
        # Perform 10,000 rate limit checks
        for i in range(10000):
            strategy.is_allowed(f'user_{i % 100}')  # 100 different users
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete in reasonable time (< 5 seconds for 10k checks)
        self.assertLess(execution_time, 5.0, 
                       f"Token bucket took {execution_time:.2f}s for 10k checks")
        
        print(f"Token bucket: 10k checks in {execution_time:.2f}s "
              f"({10000/execution_time:.0f} checks/sec)")
    
    def test_sliding_window_performance(self):
        """Test sliding window algorithm performance."""
        strategy = SlidingWindowStrategy(limit=100, window=60, name='perf_test')
        
        start_time = time.time()
        
        # Perform 5,000 rate limit checks (fewer due to higher complexity)
        for i in range(5000):
            strategy.is_allowed(f'user_{i % 50}')  # 50 different users
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete in reasonable time (< 10 seconds for 5k checks)
        self.assertLess(execution_time, 10.0,
                       f"Sliding window took {execution_time:.2f}s for 5k checks")
        
        print(f"Sliding window: 5k checks in {execution_time:.2f}s "
              f"({5000/execution_time:.0f} checks/sec)")
    
    def test_concurrent_rate_limiting(self):
        """Test rate limiting under concurrent load."""
        strategy = TokenBucketStrategy(limit=1000, window=3600, name='concurrent_test')
        results = []
        errors = []
        
        def rate_limit_worker(worker_id):
            """Worker function for concurrent testing."""
            try:
                local_results = []
                for i in range(100):
                    allowed, info = strategy.is_allowed(f'worker_{worker_id}_req_{i}')
                    local_results.append((allowed, info))
                return local_results
            except Exception as e:
                errors.append(e)
                return []
        
        start_time = time.time()
        
        # Run 50 concurrent workers, each making 100 requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(rate_limit_worker, i) for i in range(50)]
            
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle concurrent load without errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5000)  # 50 workers × 100 requests
        
        print(f"Concurrent rate limiting: 5k requests from 50 threads in {execution_time:.2f}s")
    
    def test_hierarchical_limiter_performance(self):
        """Test performance of hierarchical rate limiter."""
        limiter = HierarchicalRateLimiter()
        
        # Mock request object
        class MockRequest:
            def __init__(self, path, method='GET'):
                self.path = path
                self.method = method
                self.META = {'REMOTE_ADDR': '192.168.1.1', 'HTTP_USER_AGENT': 'Test'}
                self.user = None
        
        requests_data = [
            MockRequest('/api/v1/auth/login/', 'POST'),
            MockRequest('/api/v1/queries/', 'POST'),
            MockRequest('/api/v1/data/export/', 'GET'),
            MockRequest('/api/v1/system/health/', 'GET'),
        ]
        
        start_time = time.time()
        
        # Test 1000 requests across different endpoints
        for i in range(1000):
            request = requests_data[i % len(requests_data)]
            endpoint_type = limiter._get_endpoint_type(request.path, request.method)
            limiter.check_rate_limit(request, endpoint_type)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete in reasonable time
        self.assertLess(execution_time, 3.0,
                       f"Hierarchical limiter took {execution_time:.2f}s for 1k checks")
        
        print(f"Hierarchical limiter: 1k checks in {execution_time:.2f}s")


class SecurityMiddlewarePerformanceTestCase(TestCase):
    """Performance tests for security middleware."""
    
    def setUp(self):
        """Set up test data."""
        from django.http import HttpRequest, HttpResponse
        
        def mock_get_response(request):
            return HttpResponse('OK')
        
        self.middleware = ThreatDetectionMiddleware(mock_get_response)
        
        # Create test requests
        self.normal_request = HttpRequest()
        self.normal_request.path = '/api/v1/queries/'
        self.normal_request.method = 'POST'
        self.normal_request.META = {
            'HTTP_USER_AGENT': 'Mozilla/5.0 (normal browser)',
            'REMOTE_ADDR': '192.168.1.100'
        }
        self.normal_request.body = b'{"query": "normal query"}'
        
        self.suspicious_request = HttpRequest()
        self.suspicious_request.path = "/api/v1/queries/?id=1' OR '1'='1"
        self.suspicious_request.method = 'POST'
        self.suspicious_request.META = {
            'HTTP_USER_AGENT': 'sqlmap/1.0',
            'REMOTE_ADDR': '192.168.1.1'
        }
        self.suspicious_request.body = b'{"query": "SELECT * FROM users WHERE id=1 OR 1=1"}'
    
    def test_threat_analysis_performance(self):
        """Test threat analysis performance."""
        start_time = time.time()
        
        # Analyze 1000 normal requests
        for _ in range(1000):
            self.middleware._analyze_request_threats(self.normal_request)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should analyze requests quickly
        self.assertLess(execution_time, 2.0,
                       f"Threat analysis took {execution_time:.2f}s for 1k normal requests")
        
        print(f"Threat analysis (normal): 1k requests in {execution_time:.2f}s")
    
    def test_suspicious_request_analysis_performance(self):
        """Test performance with suspicious requests."""
        start_time = time.time()
        
        # Analyze 500 suspicious requests (typically slower due to pattern matching)
        for _ in range(500):
            self.middleware._analyze_request_threats(self.suspicious_request)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should still complete in reasonable time
        self.assertLess(execution_time, 3.0,
                       f"Suspicious request analysis took {execution_time:.2f}s for 500 requests")
        
        print(f"Threat analysis (suspicious): 500 requests in {execution_time:.2f}s")
    
    def test_concurrent_threat_analysis(self):
        """Test concurrent threat analysis performance."""
        results = []
        errors = []
        
        def analysis_worker(worker_id):
            """Worker function for concurrent threat analysis."""
            try:
                local_results = []
                for i in range(50):
                    if i % 2 == 0:
                        score, threats = self.middleware._analyze_request_threats(self.normal_request)
                    else:
                        score, threats = self.middleware._analyze_request_threats(self.suspicious_request)
                    local_results.append((score, threats))
                return local_results
            except Exception as e:
                errors.append(e)
                return []
        
        start_time = time.time()
        
        # Run 20 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(analysis_worker, i) for i in range(20)]
            
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle concurrent load
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 1000)  # 20 workers × 50 requests
        
        print(f"Concurrent threat analysis: 1k requests from 20 threads in {execution_time:.2f}s")


class AuditLoggingPerformanceTestCase(TestCase):
    """Performance tests for audit logging."""
    
    def setUp(self):
        """Set up test data."""
        self.test_user = User.objects.create_user(
            username='perftest',
            email='perf@example.com',
            password='TestPassword123!',
            role='analyst'
        )
    
    def test_audit_log_creation_performance(self):
        """Test audit log creation performance."""
        start_time = time.time()
        
        # Create 1000 audit log entries
        for i in range(1000):
            log_audit_event(
                user=self.test_user,
                action='performance_test',
                severity='info',
                description=f'Performance test log entry {i}',
                ip_address='192.168.1.1',
                metadata={'request_id': i, 'test_data': 'performance'}
            )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should create logs quickly
        self.assertLess(execution_time, 5.0,
                       f"Audit log creation took {execution_time:.2f}s for 1k entries")
        
        print(f"Audit logging: 1k entries in {execution_time:.2f}s")
    
    def test_concurrent_audit_logging(self):
        """Test concurrent audit logging performance."""
        errors = []
        
        def logging_worker(worker_id):
            """Worker function for concurrent logging."""
            try:
                for i in range(50):
                    log_audit_event(
                        user=self.test_user,
                        action='concurrent_test',
                        severity='info',
                        description=f'Concurrent test log from worker {worker_id}, entry {i}',
                        ip_address=f'192.168.1.{worker_id}',
                        metadata={'worker_id': worker_id, 'entry': i}
                    )
            except Exception as e:
                errors.append(e)
        
        start_time = time.time()
        
        # Run 20 concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(logging_worker, i) for i in range(20)]
            
            for future in concurrent.futures.as_completed(futures):
                future.result()  # Wait for completion
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle concurrent logging without errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        print(f"Concurrent audit logging: 1k entries from 20 threads in {execution_time:.2f}s")
    
    def tearDown(self):
        """Clean up audit logs."""
        from authentication.models import AuditLog
        AuditLog.objects.filter(action__in=['performance_test', 'concurrent_test']).delete()


class AuthenticationAPIPerformanceTestCase(APITestCase):
    """Performance tests for authentication API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test users
        self.test_users = []
        for i in range(100):
            user = User.objects.create_user(
                username=f'perfuser{i}',
                email=f'perf{i}@example.com',
                password='TestPassword123!',
                role='analyst'
            )
            self.test_users.append(user)
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPassword123!',
            role='admin'
        )
    
    def test_login_performance(self):
        """Test login endpoint performance."""
        start_time = time.time()
        
        # Perform 100 logins
        for i in range(100):
            login_data = {
                'email': f'perf{i}@example.com',
                'password': 'TestPassword123!'
            }
            
            response = self.client.post('/api/v1/auth/login/', login_data)
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete logins in reasonable time
        self.assertLess(execution_time, 10.0,
                       f"100 logins took {execution_time:.2f}s")
        
        print(f"Login performance: 100 logins in {execution_time:.2f}s "
              f"({100/execution_time:.1f} logins/sec)")
    
    def test_concurrent_logins(self):
        """Test concurrent login performance."""
        results = []
        errors = []
        
        def login_worker(worker_id):
            """Worker function for concurrent logins."""
            try:
                client = APIClient()
                local_results = []
                
                for i in range(10):
                    user_index = (worker_id * 10 + i) % 100
                    login_data = {
                        'email': f'perf{user_index}@example.com',
                        'password': 'TestPassword123!'
                    }
                    
                    response = client.post('/api/v1/auth/login/', login_data)
                    local_results.append(response.status_code)
                
                return local_results
            except Exception as e:
                errors.append(e)
                return []
        
        start_time = time.time()
        
        # Run 20 concurrent workers, each doing 10 logins
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(login_worker, i) for i in range(20)]
            
            for future in concurrent.futures.as_completed(futures):
                results.extend(future.result())
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should handle concurrent logins without errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        successful_logins = sum(1 for status_code in results if status_code == 200)
        self.assertEqual(successful_logins, 200)  # All should succeed
        
        print(f"Concurrent logins: 200 logins from 20 threads in {execution_time:.2f}s")
    
    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-performance',
        }
    })
    def test_user_list_performance(self):
        """Test user list endpoint performance."""
        self.client.force_authenticate(user=self.admin_user)
        
        start_time = time.time()
        
        # Fetch user list 50 times
        for _ in range(50):
            response = self.client.get('/api/v1/auth/users/')
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete quickly
        self.assertLess(execution_time, 5.0,
                       f"50 user list requests took {execution_time:.2f}s")
        
        print(f"User list performance: 50 requests in {execution_time:.2f}s")
    
    def tearDown(self):
        """Clean up test users."""
        User.objects.filter(username__startswith='perfuser').delete()


class MemoryUsageTestCase(TestCase):
    """Test memory usage patterns."""
    
    def setUp(self):
        """Set up test data."""
        import tracemalloc
        tracemalloc.start()
        self.initial_snapshot = tracemalloc.take_snapshot()
    
    def test_rate_limiter_memory_usage(self):
        """Test memory usage of rate limiter."""
        import tracemalloc
        
        strategy = TokenBucketStrategy(limit=1000, window=3600, name='memory_test')
        
        # Perform many operations to see memory growth
        for i in range(10000):
            strategy.is_allowed(f'user_{i % 1000}')  # 1000 different users
        
        current_snapshot = tracemalloc.take_snapshot()
        top_stats = current_snapshot.compare_to(self.initial_snapshot, 'lineno')
        
        # Check that memory usage is reasonable
        total_growth = sum(stat.size_diff for stat in top_stats[:10])
        
        # Should not use excessive memory (< 10MB for this test)
        self.assertLess(total_growth, 10 * 1024 * 1024,
                       f"Memory usage grew by {total_growth / 1024 / 1024:.2f}MB")
        
        print(f"Rate limiter memory growth: {total_growth / 1024 / 1024:.2f}MB for 10k operations")
    
    def test_audit_logging_memory_usage(self):
        """Test memory usage of audit logging."""
        import tracemalloc
        
        test_user = User.objects.create_user(
            username='memtest',
            email='mem@example.com',
            password='TestPassword123!',
            role='analyst'
        )
        
        baseline_snapshot = tracemalloc.take_snapshot()
        
        # Create many audit log entries
        for i in range(1000):
            log_audit_event(
                user=test_user,
                action='memory_test',
                severity='info',
                description=f'Memory test log entry {i}',
                ip_address='192.168.1.1',
                metadata={'iteration': i}
            )
        
        current_snapshot = tracemalloc.take_snapshot()
        top_stats = current_snapshot.compare_to(baseline_snapshot, 'lineno')
        
        total_growth = sum(stat.size_diff for stat in top_stats[:10])
        
        # Should not use excessive memory for logging
        self.assertLess(total_growth, 5 * 1024 * 1024,
                       f"Audit logging memory grew by {total_growth / 1024 / 1024:.2f}MB")
        
        print(f"Audit logging memory growth: {total_growth / 1024 / 1024:.2f}MB for 1k entries")
        
        # Clean up
        from authentication.models import AuditLog
        AuditLog.objects.filter(action='memory_test').delete()
    
    def tearDown(self):
        """Clean up memory tracing."""
        import tracemalloc
        tracemalloc.stop()


class StressTestCase(APITestCase):
    """Stress tests for the authentication system."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create a smaller set of users for stress testing
        self.stress_users = []
        for i in range(50):
            user = User.objects.create_user(
                username=f'stressuser{i}',
                email=f'stress{i}@example.com',
                password='StressPassword123!',
                role='analyst'
            )
            self.stress_users.append(user)
    
    @patch('authentication.middleware.time.sleep')  # Skip any sleep delays
    def test_rapid_fire_requests(self, mock_sleep):
        """Test system under rapid fire requests."""
        success_count = 0
        error_count = 0
        
        def rapid_request_worker():
            """Worker for rapid requests."""
            nonlocal success_count, error_count
            
            client = APIClient()
            
            for i in range(20):  # Each worker makes 20 requests
                try:
                    user_index = i % len(self.stress_users)
                    user = self.stress_users[user_index]
                    
                    login_data = {
                        'email': user.email,
                        'password': 'StressPassword123!'
                    }
                    
                    response = client.post('/api/v1/auth/login/', login_data)
                    
                    if response.status_code == 200:
                        success_count += 1
                        
                        # Try to access profile
                        token = response.data['access']
                        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                        
                        profile_response = client.get('/api/v1/auth/profile/')
                        if profile_response.status_code == 200:
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    print(f"Request error: {e}")
        
        start_time = time.time()
        
        # Launch many concurrent workers
        threads = []
        for _ in range(10):  # 10 workers
            thread = threading.Thread(target=rapid_request_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        total_requests = success_count + error_count
        
        print(f"Stress test: {total_requests} requests in {execution_time:.2f}s")
        print(f"Success rate: {success_count}/{total_requests} "
              f"({success_count/total_requests*100:.1f}%)")
        
        # Should handle stress reasonably well (at least 70% success rate)
        success_rate = success_count / total_requests if total_requests > 0 else 0
        self.assertGreater(success_rate, 0.7,
                          f"Success rate too low: {success_rate:.2f}")
    
    def tearDown(self):
        """Clean up stress test users."""
        User.objects.filter(username__startswith='stressuser').delete()
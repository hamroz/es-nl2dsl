"""
Tests for authentication services and utilities
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest
from freezegun import freeze_time

from authentication.utils import log_audit_event, get_client_ip, generate_session_token
from authentication.rate_limiting import HierarchicalRateLimiter, TokenBucketStrategy
from authentication.security_middleware import ThreatDetectionMiddleware
from authentication.session_manager import SessionManager
from authentication.models import AuditLog, UserSession
from tests.factories import UserFactory, AdminUserFactory

User = get_user_model()


@pytest.mark.django_db
class AuditUtilsTest(TestCase):
    """Test audit logging utilities"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
    
    def test_log_audit_event_with_user(self):
        """Test logging audit event with user"""
        log_audit_event(
            user=self.user,
            action='test_action',
            severity='info',
            description='Test audit event',
            ip_address='192.168.1.100',
            metadata={'test_key': 'test_value'}
        )
        
        log_entry = AuditLog.objects.filter(action='test_action').first()
        
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.action, 'test_action')
        self.assertEqual(log_entry.severity, 'info')
        self.assertEqual(log_entry.description, 'Test audit event')
        self.assertEqual(log_entry.ip_address, '192.168.1.100')
        self.assertEqual(log_entry.metadata['test_key'], 'test_value')
    
    def test_log_audit_event_without_user(self):
        """Test logging audit event without user (system event)"""
        log_audit_event(
            action='system_event',
            severity='warning',
            description='System maintenance event',
            metadata={'maintenance_type': 'database_cleanup'}
        )
        
        log_entry = AuditLog.objects.filter(action='system_event').first()
        
        self.assertIsNotNone(log_entry)
        self.assertIsNone(log_entry.user)
        self.assertEqual(log_entry.action, 'system_event')
        self.assertEqual(log_entry.severity, 'warning')
        self.assertEqual(log_entry.metadata['maintenance_type'], 'database_cleanup')
    
    def test_log_audit_event_with_all_parameters(self):
        """Test logging audit event with all parameters"""
        log_audit_event(
            user=self.user,
            action='comprehensive_event',
            severity='critical',
            description='Comprehensive test event',
            ip_address='10.0.0.1',
            user_agent='TestAgent/1.0',
            endpoint='/api/v1/test/',
            resource_type='test_resource',
            resource_id='test_id_123',
            tenant_id=self.user.tenant_id,
            metadata={
                'additional_info': 'test',
                'nested_data': {'key': 'value'}
            }
        )
        
        log_entry = AuditLog.objects.filter(action='comprehensive_event').first()
        
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.severity, 'critical')
        self.assertEqual(log_entry.ip_address, '10.0.0.1')
        self.assertEqual(log_entry.user_agent, 'TestAgent/1.0')
        self.assertEqual(log_entry.endpoint, '/api/v1/test/')
        self.assertEqual(log_entry.resource_type, 'test_resource')
        self.assertEqual(log_entry.resource_id, 'test_id_123')
        self.assertEqual(log_entry.tenant_id, self.user.tenant_id)
        self.assertEqual(log_entry.metadata['nested_data']['key'], 'value')


@pytest.mark.django_db
class NetworkUtilsTest(TestCase):
    """Test network-related utility functions"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
    
    def test_get_client_ip_from_x_forwarded_for(self):
        """Test getting client IP from X-Forwarded-For header"""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.100, 10.0.0.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.100')
    
    def test_get_client_ip_from_x_real_ip(self):
        """Test getting client IP from X-Real-IP header"""
        request = self.factory.get('/')
        request.META['HTTP_X_REAL_IP'] = '203.0.113.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.1')
    
    def test_get_client_ip_from_remote_addr(self):
        """Test getting client IP from REMOTE_ADDR"""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '198.51.100.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '198.51.100.1')
    
    def test_get_client_ip_fallback(self):
        """Test fallback when no IP is available"""
        request = self.factory.get('/')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, 'unknown')
    
    def test_get_client_ip_priority_order(self):
        """Test that X-Forwarded-For takes priority over other headers"""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '192.168.1.100'
        request.META['HTTP_X_REAL_IP'] = '203.0.113.1'
        request.META['REMOTE_ADDR'] = '198.51.100.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.100')


@pytest.mark.django_db
class SessionUtilsTest(TestCase):
    """Test session-related utility functions"""
    
    def test_generate_session_token(self):
        """Test session token generation"""
        token = generate_session_token()
        
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 64)  # 32 bytes hex encoded
        
        # Generate another token to ensure uniqueness
        token2 = generate_session_token()
        self.assertNotEqual(token, token2)


@pytest.mark.django_db
class RateLimitingTest(TestCase):
    """Test rate limiting functionality"""
    
    def setUp(self):
        """Set up test data"""
        cache.clear()
    
    def test_token_bucket_strategy_allows_requests_within_limit(self):
        """Test that token bucket allows requests within limit"""
        strategy = TokenBucketStrategy(limit=5, window=60, name='test')
        
        # First 5 requests should be allowed
        for i in range(5):
            allowed, info = strategy.is_allowed('test_user')
            self.assertTrue(allowed, f"Request {i+1} should be allowed")
            self.assertGreater(info['remaining'], -1)
    
    def test_token_bucket_strategy_denies_requests_over_limit(self):
        """Test that token bucket denies requests over limit"""
        strategy = TokenBucketStrategy(limit=3, window=60, name='test')
        
        # Use up the tokens
        for i in range(3):
            allowed, info = strategy.is_allowed('test_user')
            self.assertTrue(allowed)
        
        # Next request should be denied
        allowed, info = strategy.is_allowed('test_user')
        self.assertFalse(allowed)
        self.assertEqual(info['remaining'], 0)
    
    def test_token_bucket_strategy_different_users(self):
        """Test that different users have separate buckets"""
        strategy = TokenBucketStrategy(limit=2, window=60, name='test')
        
        # User 1 uses up their tokens
        for i in range(2):
            allowed, info = strategy.is_allowed('user1')
            self.assertTrue(allowed)
        
        # User 1's next request should be denied
        allowed, info = strategy.is_allowed('user1')
        self.assertFalse(allowed)
        
        # User 2 should still have tokens available
        allowed, info = strategy.is_allowed('user2')
        self.assertTrue(allowed)
    
    @freeze_time(\"2024-01-01 12:00:00\")
    def test_token_bucket_strategy_refill_over_time(self):
        \"\"\"Test that token bucket refills over time\"\"\"
        strategy = TokenBucketStrategy(limit=3, window=60, name='test')
        
        # Use up all tokens
        for i in range(3):
            allowed, info = strategy.is_allowed('test_user')
            self.assertTrue(allowed)
        
        # Next request should be denied
        allowed, info = strategy.is_allowed('test_user')
        self.assertFalse(allowed)
        
        # Move forward in time (past window)
        with freeze_time(\"2024-01-01 12:02:00\"):
            # Should have tokens available again
            allowed, info = strategy.is_allowed('test_user')
            self.assertTrue(allowed)
    
    def test_hierarchical_rate_limiter(self):
        \"\"\"Test hierarchical rate limiter\"\"\"
        limiter = HierarchicalRateLimiter()
        
        # Mock request
        request = HttpRequest()
        request.path = '/api/v1/auth/login/'
        request.method = 'POST'
        request.META = {
            'HTTP_USER_AGENT': 'Test Browser',
            'REMOTE_ADDR': '192.168.1.100'
        }
        
        # First few requests should be allowed
        for i in range(5):
            allowed, info = limiter.check_rate_limit(request, 'auth_login')
            self.assertTrue(allowed, f\"Request {i+1} should be allowed\")
        
        # Eventually should hit rate limit
        denied_count = 0
        for i in range(20):
            allowed, info = limiter.check_rate_limit(request, 'auth_login')
            if not allowed:
                denied_count += 1
        
        self.assertGreater(denied_count, 0, \"Should have some denied requests\")


@pytest.mark.django_db
class ThreatDetectionTest(TestCase):
    \"\"\"Test threat detection middleware\"\"\"
    
    def setUp(self):
        \"\"\"Set up test data\"\"\"
        def mock_get_response(request):
            from django.http import HttpResponse
            return HttpResponse('OK')
        
        self.middleware = ThreatDetectionMiddleware(mock_get_response)
        self.request = HttpRequest()
        self.request.META = {'HTTP_USER_AGENT': 'Mozilla/5.0'}
    
    def test_sql_injection_detection(self):
        \"\"\"Test SQL injection pattern detection\"\"\"
        self.request.path = \"/api/test?id=1' OR '1'='1\"
        self.request.GET = {'id': \"1' OR '1'='1\"}
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('url_sql_injection', threats)
    
    def test_xss_detection(self):
        \"\"\"Test XSS pattern detection\"\"\"
        self.request.path = \"/api/test?search=<script>alert('xss')</script>\"
        self.request.GET = {'search': \"<script>alert('xss')</script>\"}
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('url_xss', threats)
    
    def test_path_traversal_detection(self):
        \"\"\"Test path traversal detection\"\"\"
        self.request.path = \"/api/test?file=../../../etc/passwd\"
        self.request.GET = {'file': '../../../etc/passwd'}
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('path_traversal', threats)
    
    def test_honeypot_detection(self):
        \"\"\"Test honeypot endpoint detection\"\"\"
        honeypot_paths = [
            '/wp-admin/admin.php',
            '/phpmyadmin/',
            '/admin.php',
            '/.env',
            '/config.php'
        ]
        
        for path in honeypot_paths:
            self.request.path = path
            threat_score, threats = self.middleware._analyze_request_threats(self.request)
            
            self.assertEqual(threat_score, 100, f\"Honeypot path {path} should have max threat score\")
            self.assertIn('honeypot_access', threats)
    
    def test_scanner_user_agent_detection(self):
        \"\"\"Test detection of scanner user agents\"\"\"
        scanner_agents = [
            'sqlmap/1.0',
            'Nmap Scripting Engine',
            'w3af.org',
            'Nikto',
            'DirBuster'
        ]
        
        for agent in scanner_agents:
            self.request.META['HTTP_USER_AGENT'] = agent
            self.request.path = '/api/test'
            
            threat_score, threats = self.middleware._analyze_request_threats(self.request)
            
            self.assertGreater(threat_score, 0, f\"Scanner agent {agent} should be detected\")
            self.assertIn('scanner_user_agent', threats)
    
    def test_legitimate_request(self):
        \"\"\"Test that legitimate requests have low threat scores\"\"\"
        self.request.path = '/api/v1/queries/'
        self.request.GET = {'page': '1', 'size': '10'}
        self.request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertEqual(threat_score, 0)
        self.assertEqual(len(threats), 0)


@pytest.mark.django_db
class SessionManagerTest(TestCase):
    \"\"\"Test session manager functionality\"\"\"
    
    def setUp(self):
        \"\"\"Set up test data\"\"\"
        self.user = UserFactory()
        self.session_manager = SessionManager()
    
    def test_create_session(self):
        \"\"\"Test session creation\"\"\"
        session_data = {
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 Test Browser',
            'browser': 'Chrome',
            'os': 'Linux',
            'device': 'Desktop'
        }
        
        session = self.session_manager.create_session(self.user, **session_data)
        
        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.ip_address, '192.168.1.100')
        self.assertIsNotNone(session.session_token)
        self.assertTrue(session.is_active)
    
    def test_get_active_sessions(self):
        \"\"\"Test getting active sessions for user\"\"\"
        # Create multiple sessions
        session1 = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.100',
            user_agent='Browser 1',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        session2 = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.101',
            user_agent='Browser 2',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Create expired session
        expired_session = UserSession.objects.create(
            user=self.user,
            session_id=str(uuid.uuid4()),
            ip_address='192.168.1.102',
            user_agent='Browser 3',
            expires_at=timezone.now() - timedelta(hours=1)  # Expired
        )
        
        active_sessions = self.session_manager.get_active_sessions(self.user)
        
        self.assertEqual(len(active_sessions), 2)
        self.assertIn(session1, active_sessions)
        self.assertIn(session2, active_sessions)
        self.assertNotIn(expired_session, active_sessions)
    
    def test_terminate_session(self):
        \"\"\"Test session termination\"\"\"
        session = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.100',
            user_agent='Test Browser'
        )
        
        self.assertTrue(session.is_active)
        
        self.session_manager.terminate_session(session.id, 'manual_logout')
        
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertTrue(session.is_terminated)
        self.assertEqual(session.termination_reason, 'manual_logout')
        self.assertIsNotNone(session.terminated_at)
    
    def test_cleanup_expired_sessions(self):
        \"\"\"Test cleanup of expired sessions\"\"\"
        # Create active session
        active_session = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.100',
            user_agent='Active Browser',
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Create expired session
        expired_session = UserSession.objects.create(
            user=self.user,
            session_id=str(uuid.uuid4()),
            ip_address='192.168.1.101',
            user_agent='Expired Browser',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Run cleanup
        cleaned_count = self.session_manager.cleanup_expired_sessions()
        
        self.assertEqual(cleaned_count, 1)
        
        # Verify expired session was terminated
        expired_session.refresh_from_db()
        self.assertTrue(expired_session.is_terminated)
        self.assertEqual(expired_session.termination_reason, 'expired')
        
        # Verify active session was not affected
        active_session.refresh_from_db()
        self.assertFalse(active_session.is_terminated)
    
    def test_analyze_session_risk(self):
        \"\"\"Test session risk analysis\"\"\"
        # Low risk session (normal parameters)
        low_risk_session = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            location_country='US',
            location_city='New York'
        )
        
        risk_score = self.session_manager.analyze_session_risk(low_risk_session)
        self.assertLessEqual(risk_score, 0.5)  # Should be low risk
        
        # High risk session (suspicious parameters)
        high_risk_session = self.session_manager.create_session(
            self.user,
            ip_address='10.0.0.1',  # Different from usual
            user_agent='curl/7.68.0',  # Automated tool
            location_country='RU',  # Different country
            location_city='Moscow'
        )
        
        risk_score = self.session_manager.analyze_session_risk(high_risk_session)
        self.assertGreater(risk_score, 0.5)  # Should be higher risk
    
    def test_concurrent_session_limit(self):
        \"\"\"Test concurrent session limiting\"\"\"
        # Create maximum allowed concurrent sessions
        sessions = []
        max_concurrent = 3
        
        for i in range(max_concurrent):
            session = self.session_manager.create_session(
                self.user,
                ip_address=f'192.168.1.{100 + i}',
                user_agent=f'Browser {i + 1}',
                max_concurrent_sessions=max_concurrent
            )
            sessions.append(session)
        
        # All sessions should be active
        for session in sessions:
            session.refresh_from_db()
            self.assertTrue(session.is_active)
        
        # Create one more session (should terminate oldest)
        new_session = self.session_manager.create_session(
            self.user,
            ip_address='192.168.1.200',
            user_agent='New Browser',
            max_concurrent_sessions=max_concurrent
        )
        
        # Check that oldest session was terminated
        sessions[0].refresh_from_db()
        self.assertTrue(sessions[0].is_terminated)
        self.assertEqual(sessions[0].termination_reason, 'concurrent_limit_exceeded')
        
        # New session should be active
        self.assertTrue(new_session.is_active)
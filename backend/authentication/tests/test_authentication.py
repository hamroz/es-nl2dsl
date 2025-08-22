import json
import uuid
from datetime import datetime, timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
from authentication.models import UserSession, AuditLog
from authentication.rate_limiting import HierarchicalRateLimiter, TokenBucketStrategy
from authentication.security_middleware import ThreatDetectionMiddleware
from authentication.utils import log_audit_event

User = get_user_model()


class AuthenticationTestCase(APITestCase):
    """Test cases for JWT authentication system."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.test_user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'TestPassword123!',
            'role': 'analyst'
        }
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPassword123!',
            role='admin'
        )
        
        self.analyst_user = User.objects.create_user(
            username='analyst',
            email='analyst@example.com',
            password='AnalystPassword123!',
            role='analyst'
        )
        
        self.viewer_user = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='ViewerPassword123!',
            role='viewer'
        )
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
        User.objects.all().delete()
        AuditLog.objects.all().delete()
        UserSession.objects.all().delete()
    
    def test_user_registration_success(self):
        """Test successful user registration."""
        # Authenticate as admin (only admins can create users)
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.post('/api/v1/auth/register/', self.test_user_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=self.test_user_data['email']).exists())
        
        # Check audit log
        audit_log = AuditLog.objects.filter(action='user_create').first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.user, self.admin_user)
    
    def test_user_registration_permission_denied(self):
        """Test that non-admin users cannot register new users."""
        self.client.force_authenticate(user=self.analyst_user)
        
        response = self.client.post('/api/v1/auth/register/', self.test_user_data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email."""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create first user
        self.client.post('/api/v1/auth/register/', self.test_user_data)
        
        # Try to create user with same email
        duplicate_data = self.test_user_data.copy()
        duplicate_data['username'] = 'different_username'
        
        response = self.client.post('/api/v1/auth/register/', duplicate_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_success(self):
        """Test successful login."""
        login_data = {
            'email': self.analyst_user.email,
            'password': 'AnalystPassword123!'
        }
        
        response = self.client.post('/api/v1/auth/login/', login_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('session_token', response.data)
        
        # Check audit log
        audit_log = AuditLog.objects.filter(action='login', user=self.analyst_user).first()
        self.assertIsNotNone(audit_log)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        login_data = {
            'email': self.analyst_user.email,
            'password': 'WrongPassword'
        }
        
        response = self.client.post('/api/v1/auth/login/', login_data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Check failed login audit
        audit_log = AuditLog.objects.filter(
            action='login',
            severity='warning',
            description__icontains='failed'
        ).first()
        self.assertIsNotNone(audit_log)
    
    def test_login_account_lockout(self):
        """Test account lockout after failed attempts."""
        login_data = {
            'email': self.analyst_user.email,
            'password': 'WrongPassword'
        }
        
        # Make 5 failed login attempts
        for _ in range(5):
            self.client.post('/api/v1/auth/login/', login_data)
        
        # Refresh user from database
        self.analyst_user.refresh_from_db()
        
        # Check if account is locked
        self.assertTrue(self.analyst_user.is_locked_out)
        self.assertIsNotNone(self.analyst_user.lockout_until)
        
        # Try to login with correct password (should fail due to lockout)
        correct_login_data = {
            'email': self.analyst_user.email,
            'password': 'AnalystPassword123!'
        }
        
        response = self.client.post('/api/v1/auth/login/', correct_login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_token_refresh(self):
        """Test JWT token refresh."""
        # Get tokens
        login_data = {
            'email': self.analyst_user.email,
            'password': 'AnalystPassword123!'
        }
        
        login_response = self.client.post('/api/v1/auth/login/', login_data)
        refresh_token = login_response.data['refresh']
        
        # Use refresh token to get new access token
        refresh_data = {'refresh': refresh_token}
        response = self.client.post('/api/v1/auth/refresh/', refresh_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_logout(self):
        """Test user logout."""
        # Login first
        login_data = {
            'email': self.analyst_user.email,
            'password': 'AnalystPassword123!'
        }
        
        login_response = self.client.post('/api/v1/auth/login/', login_data)
        refresh_token = login_response.data['refresh']
        session_token = login_response.data['session_token']
        
        # Set authentication
        self.client.force_authenticate(user=self.analyst_user)
        
        # Logout
        logout_data = {
            'refresh_token': refresh_token,
            'session_token': session_token
        }
        
        response = self.client.post('/api/v1/auth/logout/', logout_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check audit log
        audit_log = AuditLog.objects.filter(action='logout', user=self.analyst_user).first()
        self.assertIsNotNone(audit_log)
    
    def test_profile_access(self):
        """Test accessing user profile."""
        self.client.force_authenticate(user=self.analyst_user)
        
        response = self.client.get('/api/v1/auth/profile/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.analyst_user.email)
        self.assertEqual(response.data['role'], self.analyst_user.role)
    
    def test_profile_update(self):
        """Test updating user profile."""
        self.client.force_authenticate(user=self.analyst_user)
        
        update_data = {
            'username': 'updated_analyst',
            'workspace': 'new_workspace'
        }
        
        response = self.client.patch('/api/v1/auth/profile/', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if user was updated
        self.analyst_user.refresh_from_db()
        self.assertEqual(self.analyst_user.username, 'updated_analyst')
        self.assertEqual(self.analyst_user.workspace, 'new_workspace')
    
    def test_password_change(self):
        """Test password change."""
        self.client.force_authenticate(user=self.analyst_user)
        
        password_data = {
            'current_password': 'AnalystPassword123!',
            'new_password': 'NewPassword123!',
            'new_password_confirm': 'NewPassword123!'
        }
        
        response = self.client.post('/api/v1/auth/change-password/', password_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test login with new password
        login_data = {
            'email': self.analyst_user.email,
            'password': 'NewPassword123!'
        }
        
        login_response = self.client.post('/api/v1/auth/login/', login_data)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
    
    def test_user_permissions(self):
        """Test user permissions endpoint."""
        self.client.force_authenticate(user=self.analyst_user)
        
        response = self.client.get('/api/v1/auth/permissions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('permissions', response.data)
        self.assertTrue(response.data['permissions']['can_modify_queries'])
        self.assertFalse(response.data['permissions']['can_admin_users'])


class RoleBasedAccessTestCase(APITestCase):
    """Test role-based access control."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPassword123!',
            role='admin'
        )
        
        self.analyst_user = User.objects.create_user(
            username='analyst',
            email='analyst@example.com',
            password='AnalystPassword123!',
            role='analyst'
        )
        
        self.viewer_user = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='ViewerPassword123!',
            role='viewer'
        )
    
    def test_admin_user_management_access(self):
        """Test that admins can access user management."""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.get('/api/v1/auth/users/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_analyst_user_management_denied(self):
        """Test that analysts cannot access user management."""
        self.client.force_authenticate(user=self.analyst_user)
        
        response = self.client.get('/api/v1/auth/users/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_viewer_user_management_denied(self):
        """Test that viewers cannot access user management."""
        self.client.force_authenticate(user=self.viewer_user)
        
        response = self.client.get('/api/v1/auth/users/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_admin_audit_log_access(self):
        """Test that admins can access audit logs."""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.get('/api/v1/auth/audit-logs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_analyst_audit_log_access(self):
        """Test that analysts can access audit logs."""
        self.client.force_authenticate(user=self.analyst_user)
        
        response = self.client.get('/api/v1/auth/audit-logs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_viewer_audit_log_denied(self):
        """Test that viewers cannot access audit logs."""
        self.client.force_authenticate(user=self.viewer_user)
        
        response = self.client.get('/api/v1/auth/audit-logs/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SessionManagementTestCase(APITestCase):
    """Test session management functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!',
            role='analyst'
        )
    
    def test_session_creation_on_login(self):
        """Test that session is created on login."""
        login_data = {
            'email': self.test_user.email,
            'password': 'TestPassword123!'
        }
        
        response = self.client.post('/api/v1/auth/login/', login_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_token', response.data)
        
        # Check if session was created in database
        session = UserSession.objects.filter(user=self.test_user, is_active=True).first()
        self.assertIsNotNone(session)
    
    def test_session_list(self):
        """Test listing user sessions."""
        # Create a session by logging in
        login_data = {
            'email': self.test_user.email,
            'password': 'TestPassword123!'
        }
        
        self.client.post('/api/v1/auth/login/', login_data)
        
        # Authenticate and get sessions
        self.client.force_authenticate(user=self.test_user)
        response = self.client.get('/api/v1/auth/sessions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['sessions']), 1)
    
    def test_session_termination(self):
        """Test terminating a session."""
        # Create a session
        session = UserSession.objects.create(
            user=self.test_user,
            session_token='test-session-token',
            ip_address='192.168.1.1',
            user_agent='Test Browser',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        self.client.force_authenticate(user=self.test_user)
        
        response = self.client.delete('/api/v1/auth/sessions/', {
            'session_id': str(session.id)
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if session was deactivated
        session.refresh_from_db()
        self.assertFalse(session.is_active)


class RateLimitingTestCase(APITestCase):
    """Test rate limiting functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.limiter = HierarchicalRateLimiter()
        cache.clear()
    
    def test_token_bucket_strategy(self):
        """Test token bucket rate limiting."""
        strategy = TokenBucketStrategy(limit=5, window=60, name='test')
        
        # Should allow first 5 requests
        for i in range(5):
            allowed, info = strategy.is_allowed('test_user')
            self.assertTrue(allowed, f"Request {i+1} should be allowed")
        
        # 6th request should be denied
        allowed, info = strategy.is_allowed('test_user')
        self.assertFalse(allowed, "6th request should be denied")
    
    @patch('authentication.rate_limiting.get_client_ip')
    def test_rate_limit_middleware(self, mock_get_ip):
        """Test rate limiting middleware."""
        mock_get_ip.return_value = '192.168.1.1'
        
        # Create a mock request
        from django.http import HttpRequest
        request = HttpRequest()
        request.path = '/api/v1/auth/login/'
        request.method = 'POST'
        request.META = {'HTTP_USER_AGENT': 'Test Browser'}
        
        # Test multiple requests
        allowed_count = 0
        for i in range(15):  # Try more than the limit
            allowed, info = self.limiter.check_rate_limit(request, 'auth_login')
            if allowed:
                allowed_count += 1
        
        # Should have allowed some but not all requests
        self.assertGreater(allowed_count, 0)
        self.assertLess(allowed_count, 15)


class SecurityMiddlewareTestCase(APITestCase):
    """Test security middleware functionality."""
    
    def setUp(self):
        """Set up test data."""
        from django.http import HttpRequest
        self.request = HttpRequest()
        self.request.META = {'HTTP_USER_AGENT': 'Test Browser'}
        
        # Mock get_response function
        def mock_get_response(request):
            from django.http import HttpResponse
            return HttpResponse('OK')
        
        self.middleware = ThreatDetectionMiddleware(mock_get_response)
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        self.request.path = "/api/test?id=1' OR '1'='1"
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('url_sql_injection', threats)
    
    def test_xss_detection(self):
        """Test XSS pattern detection."""
        self.request.path = "/api/test?search=<script>alert('xss')</script>"
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('url_xss', threats)
    
    def test_honeypot_detection(self):
        """Test honeypot endpoint detection."""
        self.request.path = "/wp-admin/admin.php"
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertEqual(threat_score, 100)
        self.assertIn('honeypot_access', threats)
    
    def test_suspicious_user_agent(self):
        """Test suspicious user agent detection."""
        self.request.META['HTTP_USER_AGENT'] = 'sqlmap/1.0'
        self.request.path = '/api/test'
        
        threat_score, threats = self.middleware._analyze_request_threats(self.request)
        
        self.assertGreater(threat_score, 0)
        self.assertIn('scanner_user_agent', threats)


class AuditLoggingTestCase(APITestCase):
    """Test audit logging functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!',
            role='analyst'
        )
    
    def test_audit_log_creation(self):
        """Test audit log creation."""
        log_audit_event(
            user=self.test_user,
            action='test_action',
            severity='info',
            description='Test audit log entry',
            ip_address='192.168.1.1',
            metadata={'test_key': 'test_value'}
        )
        
        log_entry = AuditLog.objects.filter(action='test_action').first()
        
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.test_user)
        self.assertEqual(log_entry.severity, 'info')
        self.assertEqual(log_entry.description, 'Test audit log entry')
        self.assertEqual(log_entry.metadata['test_key'], 'test_value')
    
    def test_audit_log_filtering(self):
        """Test audit log filtering."""
        # Create multiple log entries
        log_audit_event(
            user=self.test_user,
            action='login',
            severity='info',
            description='User login',
            ip_address='192.168.1.1'
        )
        
        log_audit_event(
            user=self.test_user,
            action='logout',
            severity='info',
            description='User logout',
            ip_address='192.168.1.1'
        )
        
        log_audit_event(
            user=self.test_user,
            action='security_event',
            severity='warning',
            description='Security warning',
            ip_address='192.168.1.1'
        )
        
        # Test filtering by action
        login_logs = AuditLog.objects.filter(action='login')
        self.assertEqual(login_logs.count(), 1)
        
        # Test filtering by severity
        warning_logs = AuditLog.objects.filter(severity='warning')
        self.assertEqual(warning_logs.count(), 1)
    
    def tearDown(self):
        """Clean up after tests."""
        AuditLog.objects.all().delete()


class TenantIsolationTestCase(APITestCase):
    """Test multi-tenant data isolation."""
    
    def setUp(self):
        """Set up test data."""
        self.tenant1_id = uuid.uuid4()
        self.tenant2_id = uuid.uuid4()
        
        self.tenant1_admin = User.objects.create_user(
            username='tenant1_admin',
            email='admin1@tenant1.com',
            password='AdminPassword123!',
            role='admin',
            tenant_id=self.tenant1_id
        )
        
        self.tenant2_admin = User.objects.create_user(
            username='tenant2_admin',
            email='admin2@tenant2.com',
            password='AdminPassword123!',
            role='admin',
            tenant_id=self.tenant2_id
        )
        
        self.tenant1_user = User.objects.create_user(
            username='tenant1_user',
            email='user1@tenant1.com',
            password='UserPassword123!',
            role='analyst',
            tenant_id=self.tenant1_id
        )
    
    def test_tenant_user_isolation(self):
        """Test that users can only see users from their tenant."""
        self.client.force_authenticate(user=self.tenant1_admin)
        
        response = self.client.get('/api/v1/auth/users/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only see users from tenant1
        user_emails = [user['email'] for user in response.data['results']]
        self.assertIn('admin1@tenant1.com', user_emails)
        self.assertIn('user1@tenant1.com', user_emails)
        self.assertNotIn('admin2@tenant2.com', user_emails)
    
    def test_cross_tenant_access_denied(self):
        """Test that users cannot access other tenant's data."""
        self.client.force_authenticate(user=self.tenant1_user)
        
        # Try to access tenant2 user data
        response = self.client.get(f'/api/v1/auth/users/{self.tenant2_admin.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class IntegrationTestCase(APITestCase):
    """Integration tests for complete authentication workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPassword123!',
            role='admin'
        )
    
    def test_complete_user_lifecycle(self):
        """Test complete user lifecycle: create, login, update, delete."""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        
        # 1. Create user
        user_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'NewUserPassword123!',
            'password_confirm': 'NewUserPassword123!',
            'role': 'analyst',
            'workspace': 'test_workspace'
        }
        
        create_response = self.client.post('/api/v1/auth/register/', user_data)
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        
        new_user = User.objects.get(email='newuser@example.com')
        
        # 2. Login as new user
        login_data = {
            'email': 'newuser@example.com',
            'password': 'NewUserPassword123!'
        }
        
        login_response = self.client.post('/api/v1/auth/login/', login_data)
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        
        access_token = login_response.data['access']
        
        # 3. Access profile with token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_response = self.client.get('/api/v1/auth/profile/')
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        
        # 4. Update profile
        update_data = {'workspace': 'updated_workspace'}
        update_response = self.client.patch('/api/v1/auth/profile/', update_data)
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # 5. Verify update
        new_user.refresh_from_db()
        self.assertEqual(new_user.workspace, 'updated_workspace')
        
        # 6. Check audit logs (authenticate as admin again)
        self.client.force_authenticate(user=self.admin_user)
        audit_response = self.client.get('/api/v1/auth/audit-logs/')
        self.assertEqual(audit_response.status_code, status.HTTP_200_OK)
        
        # Should have logs for user creation, login, and profile update
        audit_logs = audit_response.data['results']
        actions = [log['action'] for log in audit_logs]
        
        self.assertIn('user_create', actions)
        self.assertIn('login', actions)
        self.assertIn('user_modify', actions)
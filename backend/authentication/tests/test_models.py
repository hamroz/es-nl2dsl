"""
Comprehensive tests for authentication models
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from freezegun import freeze_time

from authentication.models import CustomUser, UserSession, AuditLog, SecurityPolicy
from tests.factories import UserFactory, AdminUserFactory, ViewerUserFactory

User = get_user_model()


@pytest.mark.django_db
class CustomUserModelTest(TestCase):
    """Test CustomUser model functionality"""
    
    def test_user_creation_with_defaults(self):
        """Test creating a user with default values"""
        user = UserFactory()
        
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, 'analyst')
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertFalse(user.is_locked_out)
        self.assertFalse(user.is_mfa_enabled)
        self.assertIsNotNone(user.tenant_id)
    
    def test_user_creation_with_custom_values(self):
        """Test creating a user with custom values"""
        tenant_id = uuid.uuid4()
        user = UserFactory(
            username='customuser',
            email='custom@example.com',
            role='admin',
            tenant_id=tenant_id,
            workspace='custom_workspace',
            is_mfa_enabled=True
        )
        
        self.assertEqual(user.username, 'customuser')
        self.assertEqual(user.email, 'custom@example.com')
        self.assertEqual(user.role, 'admin')
        self.assertEqual(user.tenant_id, tenant_id)
        self.assertEqual(user.workspace, 'custom_workspace')
        self.assertTrue(user.is_mfa_enabled)
    
    def test_user_string_representation(self):
        """Test user string representation"""
        user = UserFactory(username='testuser', email='test@example.com')
        expected_str = 'testuser (test@example.com)'
        self.assertEqual(str(user), expected_str)
    
    def test_email_unique_constraint(self):
        """Test that email must be unique"""
        UserFactory(email='duplicate@example.com')
        
        with self.assertRaises(IntegrityError):
            UserFactory(email='duplicate@example.com')
    
    def test_user_role_choices(self):
        """Test user role choices validation"""
        valid_roles = ['admin', 'analyst', 'viewer']
        
        for role in valid_roles:
            user = UserFactory(role=role)
            self.assertEqual(user.role, role)
    
    def test_can_admin_users_property(self):
        """Test can_admin_users property"""
        admin_user = AdminUserFactory()
        analyst_user = UserFactory(role='analyst')
        viewer_user = ViewerUserFactory()
        
        self.assertTrue(admin_user.can_admin_users)
        self.assertFalse(analyst_user.can_admin_users)
        self.assertFalse(viewer_user.can_admin_users)
    
    def test_can_modify_queries_property(self):
        """Test can_modify_queries property"""
        admin_user = AdminUserFactory()
        analyst_user = UserFactory(role='analyst')
        viewer_user = ViewerUserFactory()
        
        self.assertTrue(admin_user.can_modify_queries)
        self.assertTrue(analyst_user.can_modify_queries)
        self.assertFalse(viewer_user.can_modify_queries)
    
    def test_is_read_only_property(self):
        """Test is_read_only property"""
        admin_user = AdminUserFactory()
        analyst_user = UserFactory(role='analyst')
        viewer_user = ViewerUserFactory()
        
        self.assertFalse(admin_user.is_read_only)
        self.assertFalse(analyst_user.is_read_only)
        self.assertTrue(viewer_user.is_read_only)
    
    def test_username_field_configuration(self):
        """Test that email is used as username field"""
        self.assertEqual(User.USERNAME_FIELD, 'email')
        self.assertIn('username', User.REQUIRED_FIELDS)
    
    def test_user_indexing(self):
        """Test that proper indexes are created"""
        # This test ensures indexes are defined correctly
        # Django will create them during migration
        indexes = User._meta.indexes
        index_fields = [idx.fields for idx in indexes]
        
        self.assertIn(['tenant_id'], index_fields)
        self.assertIn(['role'], index_fields)
        self.assertIn(['is_active', 'is_locked_out'], index_fields)


@pytest.mark.django_db
class UserSessionModelTest(TestCase):
    """Test UserSession model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.session_data = {
            'user': self.user,
            'session_id': str(uuid.uuid4()),
            'session_token': str(uuid.uuid4()),
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 Test Browser',
            'browser': 'Chrome',
            'os': 'Linux',
            'device': 'Desktop',
            'location_country': 'US',
            'location_city': 'New York',
            'expires_at': timezone.now() + timedelta(hours=24)
        }
    
    def test_user_session_creation(self):
        """Test UserSession creation with default values"""
        session = UserSession.objects.create(**self.session_data)
        
        self.assertIsInstance(session.id, uuid.UUID)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.security_level, 'medium')
        self.assertEqual(session.risk_score, 0.5)
        self.assertFalse(session.is_suspicious)
        self.assertEqual(session.request_count, 0)
        self.assertFalse(session.is_terminated)
        self.assertIsNotNone(session.created_at)
    
    def test_user_session_string_representation(self):
        """Test UserSession string representation"""
        session = UserSession.objects.create(**self.session_data)
        expected_start = f"Session {session.session_id[:8]}... for {self.user.username}"
        self.assertEqual(str(session), expected_start)
    
    def test_user_session_security_levels(self):
        """Test security level choices"""
        valid_levels = ['low', 'medium', 'high', 'critical']
        
        for level in valid_levels:
            session_data = self.session_data.copy()
            session_data['security_level'] = level
            session = UserSession.objects.create(**session_data)
            self.assertEqual(session.security_level, level)
    
    def test_is_active_property_active_session(self):
        """Test is_active property for active session"""
        future_expiry = timezone.now() + timedelta(hours=1)
        session_data = self.session_data.copy()
        session_data['expires_at'] = future_expiry
        
        session = UserSession.objects.create(**session_data)
        self.assertTrue(session.is_active)
    
    def test_is_active_property_expired_session(self):
        """Test is_active property for expired session"""
        past_expiry = timezone.now() - timedelta(hours=1)
        session_data = self.session_data.copy()
        session_data['expires_at'] = past_expiry
        
        session = UserSession.objects.create(**session_data)
        self.assertFalse(session.is_active)
    
    def test_is_active_property_terminated_session(self):
        """Test is_active property for terminated session"""
        session_data = self.session_data.copy()
        session_data['is_terminated'] = True
        session_data['terminated_at'] = timezone.now()
        
        session = UserSession.objects.create(**session_data)
        self.assertFalse(session.is_active)
    
    @freeze_time(\"2024-01-01 12:00:00\")
    def test_session_duration_property(self):
        \"\"\"Test session_duration property\"\"\"
        created_time = timezone.now()\n        session_data = self.session_data.copy()
        session = UserSession.objects.create(**session_data)
        
        # Test with active session (no termination)
        with freeze_time(\"2024-01-01 14:00:00\"):
            duration = session.session_duration
            self.assertEqual(duration, timedelta(hours=2))
        
        # Test with terminated session
        termination_time = timezone.now() + timedelta(hours=1)
        session.terminated_at = termination_time
        session.save()
        
        duration = session.session_duration
        self.assertEqual(duration, timedelta(hours=1))
    
    def test_user_session_cascade_deletion(self):
        """Test that sessions are deleted when user is deleted"""
        session = UserSession.objects.create(**self.session_data)
        
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)
        
        self.user.delete()
        
        self.assertEqual(UserSession.objects.filter(id=session.id).count(), 0)
    
    def test_session_metadata_json_field(self):
        """Test session_data JSON field functionality"""
        metadata = {
            'login_method': 'password',
            'device_fingerprint': 'abc123',
            'geolocation': {'lat': 40.7128, 'lng': -74.0060}
        }
        
        session_data = self.session_data.copy()
        session_data['session_data'] = metadata
        
        session = UserSession.objects.create(**session_data)
        session.refresh_from_db()
        
        self.assertEqual(session.session_data['login_method'], 'password')
        self.assertEqual(session.session_data['geolocation']['lat'], 40.7128)


@pytest.mark.django_db
class AuditLogModelTest(TestCase):
    """Test AuditLog model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = UserFactory()
        self.audit_data = {
            'user': self.user,
            'event_type': 'login',
            'action': 'login',  # Backward compatibility
            'severity': 'info',
            'description': 'User logged in successfully',
            'ip_address': '192.168.1.100',
            'user_agent': 'Mozilla/5.0 Test Browser',
            'endpoint': '/api/v1/auth/login/',
            'resource_type': 'user',
            'resource_id': str(self.user.id),
            'tenant_id': self.user.tenant_id
        }
    
    def test_audit_log_creation(self):
        """Test AuditLog creation with all fields"""
        audit_log = AuditLog.objects.create(**self.audit_data)
        
        self.assertIsInstance(audit_log.id, uuid.UUID)
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.event_type, 'login')
        self.assertEqual(audit_log.severity, 'info')
        self.assertIsNotNone(audit_log.timestamp)
    
    def test_audit_log_string_representation(self):
        """Test AuditLog string representation"""
        audit_log = AuditLog.objects.create(**self.audit_data)
        expected_start = f\"{self.user.username} - login ({audit_log.timestamp})\"
        self.assertEqual(str(audit_log), expected_start)
    
    def test_audit_log_without_user(self):
        \"\"\"Test AuditLog creation without user (system events)\"\"\"
        audit_data = self.audit_data.copy()
        del audit_data['user']
        audit_data['description'] = 'System maintenance event'
        
        audit_log = AuditLog.objects.create(**audit_data)
        
        self.assertIsNone(audit_log.user)
        expected_str = f\"System - login ({audit_log.timestamp})\"
        self.assertEqual(str(audit_log), expected_str)
    
    def test_audit_log_event_types(self):
        \"\"\"Test various event types\"\"\"
        event_types = [
            'login', 'login_failed', 'logout', 'session_created',
            'query_generate', 'query_execute', 'data_export',
            'user_create', 'security_event', 'suspicious_activity'
        ]
        
        for event_type in event_types:
            audit_data = self.audit_data.copy()
            audit_data['event_type'] = event_type
            audit_data['action'] = event_type
            
            audit_log = AuditLog.objects.create(**audit_data)
            self.assertEqual(audit_log.event_type, event_type)
    
    def test_audit_log_severity_levels(self):
        \"\"\"Test severity level choices\"\"\"
        severity_levels = ['info', 'warning', 'error', 'critical']
        
        for severity in severity_levels:
            audit_data = self.audit_data.copy()
            audit_data['severity'] = severity
            
            audit_log = AuditLog.objects.create(**audit_data)
            self.assertEqual(audit_log.severity, severity)
    
    def test_audit_log_metadata_json_field(self):
        \"\"\"Test metadata JSON field functionality\"\"\"
        metadata = {
            'session_id': str(uuid.uuid4()),
            'query_method': 'constrained',
            'execution_time_ms': 1500,
            'additional_data': {
                'nested_field': 'value',
                'count': 42
            }
        }
        
        audit_data = self.audit_data.copy()
        audit_data['metadata'] = metadata
        
        audit_log = AuditLog.objects.create(**audit_data)
        audit_log.refresh_from_db()
        
        self.assertEqual(audit_log.metadata['query_method'], 'constrained')
        self.assertEqual(audit_log.metadata['additional_data']['count'], 42)
    
    def test_audit_log_ordering(self):
        \"\"\"Test AuditLog ordering by timestamp descending\"\"\"
        # Create logs with specific timestamps
        with freeze_time(\"2024-01-01 10:00:00\"):
            log1 = AuditLog.objects.create(**self.audit_data)
        
        with freeze_time(\"2024-01-01 11:00:00\"):
            audit_data2 = self.audit_data.copy()
            audit_data2['event_type'] = 'logout'
            log2 = AuditLog.objects.create(**audit_data2)
        
        with freeze_time(\"2024-01-01 12:00:00\"):
            audit_data3 = self.audit_data.copy()
            audit_data3['event_type'] = 'query_generate'
            log3 = AuditLog.objects.create(**audit_data3)
        
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs, [log3, log2, log1])  # Most recent first
    
    def test_audit_log_user_set_null_on_delete(self):
        \"\"\"Test that audit logs are preserved when user is deleted\"\"\"
        audit_log = AuditLog.objects.create(**self.audit_data)
        
        self.assertEqual(audit_log.user, self.user)
        
        self.user.delete()
        
        audit_log.refresh_from_db()
        self.assertIsNone(audit_log.user)


@pytest.mark.django_db
class SecurityPolicyModelTest(TestCase):
    \"\"\"Test SecurityPolicy model functionality\"\"\"
    
    def setUp(self):
        \"\"\"Set up test data\"\"\"
        self.admin_user = AdminUserFactory()
        self.policy_data = {
            'name': 'Test Login Policy',
            'description': 'Test policy for login restrictions',
            'policy_type': 'login',
            'user_role': 'all',
            'priority': 100,
            'policy_config': {
                'max_failed_attempts': 5,
                'lockout_duration_minutes': 30,
                'require_mfa': False
            },
            'created_by': self.admin_user
        }
    
    def test_security_policy_creation(self):
        \"\"\"Test SecurityPolicy creation with all fields\"\"\"
        policy = SecurityPolicy.objects.create(**self.policy_data)
        
        self.assertIsInstance(policy.id, uuid.UUID)
        self.assertEqual(policy.name, 'Test Login Policy')
        self.assertEqual(policy.policy_type, 'login')
        self.assertEqual(policy.user_role, 'all')
        self.assertTrue(policy.is_active)
        self.assertEqual(policy.created_by, self.admin_user)
        self.assertIsNotNone(policy.created_at)
        self.assertIsNotNone(policy.updated_at)
    
    def test_security_policy_string_representation(self):
        \"\"\"Test SecurityPolicy string representation\"\"\"
        policy = SecurityPolicy.objects.create(**self.policy_data)
        expected_str = 'Test Login Policy (login)'
        self.assertEqual(str(policy), expected_str)
    
    def test_security_policy_types(self):
        \"\"\"Test policy type choices\"\"\"
        policy_types = [
            'login', 'password', 'session', 'access',
            'rate_limit', 'mfa', 'ip_restriction', 'time_restriction'
        ]
        
        for policy_type in policy_types:
            policy_data = self.policy_data.copy()
            policy_data['policy_type'] = policy_type
            policy_data['name'] = f'Test {policy_type} Policy'
            
            policy = SecurityPolicy.objects.create(**policy_data)
            self.assertEqual(policy.policy_type, policy_type)
    
    def test_security_policy_user_roles(self):
        \"\"\"Test user role choices\"\"\"
        user_roles = ['all', 'admin', 'analyst', 'viewer']
        
        for user_role in user_roles:
            policy_data = self.policy_data.copy()
            policy_data['user_role'] = user_role
            policy_data['name'] = f'Test Policy for {user_role}'
            
            policy = SecurityPolicy.objects.create(**policy_data)
            self.assertEqual(policy.user_role, user_role)
    
    def test_security_policy_config_json_field(self):
        \"\"\"Test policy_config JSON field functionality\"\"\"
        complex_config = {
            'login': {
                'max_failed_attempts': 3,
                'lockout_duration_minutes': 15,
                'require_mfa': True,
                'allowed_ip_ranges': ['192.168.1.0/24', '10.0.0.0/16']
            },
            'session': {
                'max_duration_hours': 8,
                'idle_timeout_minutes': 30,
                'concurrent_sessions': 2
            },
            'access_control': {
                'allowed_endpoints': ['/api/v1/queries/', '/api/v1/auth/'],
                'rate_limits': {
                    'queries': '10/hour',
                    'auth': '30/hour'
                }
            }
        }
        
        policy_data = self.policy_data.copy()
        policy_data['policy_config'] = complex_config
        
        policy = SecurityPolicy.objects.create(**policy_data)
        policy.refresh_from_db()
        
        self.assertEqual(policy.policy_config['login']['max_failed_attempts'], 3)
        self.assertTrue(policy.policy_config['login']['require_mfa'])
        self.assertEqual(len(policy.policy_config['login']['allowed_ip_ranges']), 2)
        self.assertEqual(policy.policy_config['session']['max_duration_hours'], 8)
    
    def test_security_policy_unique_name(self):
        \"\"\"Test that policy names must be unique\"\"\"
        SecurityPolicy.objects.create(**self.policy_data)
        
        with self.assertRaises(IntegrityError):
            duplicate_policy_data = self.policy_data.copy()
            SecurityPolicy.objects.create(**duplicate_policy_data)
    
    def test_security_policy_ordering(self):
        \"\"\"Test SecurityPolicy ordering by priority then name\"\"\"
        policy1 = SecurityPolicy.objects.create(
            **{**self.policy_data, 'name': 'Policy A', 'priority': 200}
        )
        policy2 = SecurityPolicy.objects.create(
            **{**self.policy_data, 'name': 'Policy B', 'priority': 100}
        )
        policy3 = SecurityPolicy.objects.create(
            **{**self.policy_data, 'name': 'Policy C', 'priority': 100}
        )
        
        policies = list(SecurityPolicy.objects.all())
        # Should be ordered by priority (lower first), then by name
        self.assertEqual(policies, [policy2, policy3, policy1])
    
    def test_security_policy_created_by_set_null_on_delete(self):
        \"\"\"Test that policies are preserved when creator is deleted\"\"\"
        policy = SecurityPolicy.objects.create(**self.policy_data)
        
        self.assertEqual(policy.created_by, self.admin_user)
        
        self.admin_user.delete()
        
        policy.refresh_from_db()
        self.assertIsNone(policy.created_by)


@pytest.mark.django_db
class ModelRelationshipsTest(TestCase):
    \"\"\"Test relationships between authentication models\"\"\"
    
    def test_user_sessions_relationship(self):
        \"\"\"Test User to UserSession relationship\"\"\"
        user = UserFactory()
        
        # Create multiple sessions for user
        session1 = UserSession.objects.create(
            user=user,
            session_id=str(uuid.uuid4()),
            ip_address='192.168.1.100',
            user_agent='Browser 1',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        session2 = UserSession.objects.create(
            user=user,
            session_id=str(uuid.uuid4()),
            ip_address='192.168.1.101',
            user_agent='Browser 2',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Test forward relationship
        self.assertEqual(session1.user, user)
        self.assertEqual(session2.user, user)
        
        # Test reverse relationship
        self.assertEqual(user.sessions.count(), 2)
        self.assertIn(session1, user.sessions.all())
        self.assertIn(session2, user.sessions.all())
    
    def test_user_audit_logs_relationship(self):
        \"\"\"Test User to AuditLog relationship\"\"\"
        user = UserFactory()
        
        # Create audit logs for user
        log1 = AuditLog.objects.create(
            user=user,
            event_type='login',
            description='User login'
        )
        
        log2 = AuditLog.objects.create(
            user=user,
            event_type='logout',
            description='User logout'
        )
        
        # Test reverse relationship through default related name
        self.assertEqual(user.auditlog_set.count(), 2)
        self.assertIn(log1, user.auditlog_set.all())
        self.assertIn(log2, user.auditlog_set.all())
    
    def test_user_created_policies_relationship(self):
        \"\"\"Test User to SecurityPolicy relationship\"\"\"
        admin_user = AdminUserFactory()
        
        # Create policies created by user
        policy1 = SecurityPolicy.objects.create(
            name='Policy 1',
            policy_type='login',
            policy_config={'test': 'config'},
            created_by=admin_user
        )
        
        policy2 = SecurityPolicy.objects.create(
            name='Policy 2',
            policy_type='session',
            policy_config={'test': 'config'},
            created_by=admin_user
        )
        
        # Test reverse relationship
        self.assertEqual(admin_user.created_policies.count(), 2)
        self.assertIn(policy1, admin_user.created_policies.all())
        self.assertIn(policy2, admin_user.created_policies.all())
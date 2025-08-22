"""
Django management command to test security policy evaluation
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.utils import timezone
from datetime import timedelta

from authentication.models import SecurityPolicy, UserSession
from authentication.security_policies import SecurityPolicyEngine, PolicyAction
from authentication.session_manager import SessionManager

User = get_user_model()


class Command(BaseCommand):
    help = 'Test security policy evaluation and session management'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to test policies against',
        )
        parser.add_argument(
            '--test-type',
            type=str,
            choices=['all', 'login', 'session', 'password', 'mfa', 'rate-limit'],
            default='all',
            help='Type of policies to test',
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test user and session data',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Testing security policies...')
        )
        
        try:
            if options['create_test_data']:
                self._create_test_data()
            
            user = self._get_test_user(options.get('user'))
            test_type = options['test_type']
            
            if test_type in ['all', 'login']:
                self._test_login_policies(user)
            
            if test_type in ['all', 'session']:
                self._test_session_policies(user)
            
            if test_type in ['all', 'password']:
                self._test_password_policies()
            
            if test_type in ['all', 'mfa']:
                self._test_mfa_policies(user)
            
            if test_type in ['all', 'rate-limit']:
                self._test_rate_limit_policies(user)
            
            self.stdout.write(
                self.style.SUCCESS('\nAll security policy tests completed!')
            )
            
        except Exception as e:
            raise CommandError(f'Policy testing failed: {e}')
    
    def _get_test_user(self, username):
        """Get test user"""
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f'User {username} not found')
        
        # Get any non-admin user for testing
        user = User.objects.filter(role__in=['analyst', 'viewer']).first()
        if not user:
            raise CommandError('No test users found. Use --create-test-data or specify --user')
        
        return user
    
    def _create_test_data(self):
        """Create test users and data"""
        self.stdout.write('Creating test data...')
        
        # Create test users
        test_users = [
            {'username': 'test_analyst', 'email': 'analyst@test.com', 'role': 'analyst'},
            {'username': 'test_viewer', 'email': 'viewer@test.com', 'role': 'viewer'},
        ]
        
        for user_data in test_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'role': user_data['role'],
                    'is_active': True,
                }
            )
            if created:
                user.set_password('TestPassword123!')
                user.save()
                self.stdout.write(f'  Created user: {user.username}')
        
        self.stdout.write('Test data creation complete.')
    
    def _test_login_policies(self, user):
        """Test login policy evaluation"""
        self.stdout.write(f'\n--- Testing Login Policies for {user.username} ---')
        
        policy_engine = SecurityPolicyEngine()
        factory = RequestFactory()
        request = factory.post('/api/auth/login/', {'username': user.username})
        request.user = user
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        
        # Test normal login
        results = policy_engine.evaluate_login_policy(user, request)
        self._display_policy_results('Normal Login', results)
        
        # Test login with failed attempts
        user.failed_login_attempts = 3
        user.save()
        
        results = policy_engine.evaluate_login_policy(user, request)
        self._display_policy_results('Login with Failed Attempts', results)
        
        # Reset user state
        user.failed_login_attempts = 0
        user.is_locked_out = False
        user.save()
    
    def _test_session_policies(self, user):
        """Test session policy evaluation"""
        self.stdout.write(f'\n--- Testing Session Policies for {user.username} ---')
        
        session_manager = SessionManager()
        factory = RequestFactory()
        request = factory.get('/api/test/')
        request.user = user
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        
        # Create test session
        session = session_manager.create_session(user, request, {'jti': 'test-session-123'})
        
        # Test session validation
        validation = session_manager.validate_session(session, request)
        self.stdout.write('Session Validation Results:')
        self.stdout.write(f'  Valid: {validation["is_valid"]}')
        self.stdout.write(f'  Warnings: {validation["warnings"]}')
        self.stdout.write(f'  Actions Required: {validation["actions_required"]}')
        self.stdout.write(f'  Risk Factors: {validation["risk_factors"]}')
        
        # Test session analytics
        analytics = session_manager.get_session_analytics(user, days=7)
        self.stdout.write('\nSession Analytics:')
        self.stdout.write(f'  Total Sessions: {analytics["total_sessions"]}')
        self.stdout.write(f'  Active Sessions: {analytics["active_sessions"]}')
        self.stdout.write(f'  Suspicious Sessions: {analytics["suspicious_sessions"]}')
        
        # Cleanup
        session.delete()
    
    def _test_password_policies(self):
        """Test password policy validation"""
        self.stdout.write('\n--- Testing Password Policies ---')
        
        policy_engine = SecurityPolicyEngine()
        
        test_passwords = [
            ('weak', 'Test password with weak strength'),
            ('StrongP@ssw0rd123!', 'Test strong password'),
            ('password', 'Test common password'),
            ('short', 'Test short password'),
        ]
        
        for password, description in test_passwords:
            result = policy_engine.check_password_policy(password)
            self.stdout.write(f'\n{description}:')
            self.stdout.write(f'  Password: {"*" * len(password)}')
            self.stdout.write(f'  Valid: {result["is_valid"]}')
            self.stdout.write(f'  Strength Score: {result["strength_score"]:.2f}')
            if result["issues"]:
                self.stdout.write(f'  Issues: {", ".join(result["issues"])}')
    
    def _test_mfa_policies(self, user):
        """Test MFA policy enforcement"""
        self.stdout.write(f'\n--- Testing MFA Policies for {user.username} ---')
        
        policy_engine = SecurityPolicyEngine()
        
        # Test MFA requirement for different roles
        for role in ['viewer', 'analyst', 'admin']:
            user.role = role
            user.save()
            
            mfa_result = policy_engine.enforce_mfa_policy(user)
            self.stdout.write(f'\nRole {role}:')
            self.stdout.write(f'  MFA Required: {mfa_result["mfa_required"]}')
            if mfa_result["mfa_required"]:
                self.stdout.write(f'  Reason: {mfa_result["reason"]}')
    
    def _test_rate_limit_policies(self, user):
        """Test rate limiting policies"""
        self.stdout.write(f'\n--- Testing Rate Limit Policies for {user.username} ---')
        
        policy_engine = SecurityPolicyEngine()
        
        # Test rate limits for different roles
        for role in ['viewer', 'analyst', 'admin']:
            user.role = role
            user.save()
            
            rate_limits = policy_engine.get_rate_limit_policy(user)
            self.stdout.write(f'\nRole {role} Rate Limits:')
            self.stdout.write(f'  Per Minute: {rate_limits.get("requests_per_minute", "N/A")}')
            self.stdout.write(f'  Per Hour: {rate_limits.get("requests_per_hour", "N/A")}')
            self.stdout.write(f'  Per Day: {rate_limits.get("requests_per_day", "N/A")}')
        
        # Test endpoint-specific limits
        endpoint_rate_limits = policy_engine.get_rate_limit_policy(user, '/api/queries/execute')
        self.stdout.write(f'\nEndpoint-specific limits for /api/queries/execute:')
        self.stdout.write(f'  Per Minute: {endpoint_rate_limits.get("requests_per_minute", "N/A")}')
    
    def _display_policy_results(self, test_name, results):
        """Display policy evaluation results"""
        self.stdout.write(f'\n{test_name}:')
        
        if not results:
            self.stdout.write('  No policy violations detected')
            return
        
        for i, result in enumerate(results, 1):
            self.stdout.write(f'  Result {i}:')
            self.stdout.write(f'    Action: {result.action}')
            self.stdout.write(f'    Reason: {result.reason}')
            if result.metadata:
                self.stdout.write(f'    Metadata: {result.metadata}')
    
    def _display_policy_summary(self):
        """Display summary of all security policies"""
        self.stdout.write('\n--- Policy Summary ---')
        
        policies = SecurityPolicy.objects.all()
        policy_types = {}
        
        for policy in policies:
            policy_type = policy.policy_type
            if policy_type not in policy_types:
                policy_types[policy_type] = {'active': 0, 'inactive': 0}
            
            if policy.is_active:
                policy_types[policy_type]['active'] += 1
            else:
                policy_types[policy_type]['inactive'] += 1
        
        for policy_type, counts in policy_types.items():
            self.stdout.write(
                f'  {policy_type}: {counts["active"]} active, {counts["inactive"]} inactive'
            )
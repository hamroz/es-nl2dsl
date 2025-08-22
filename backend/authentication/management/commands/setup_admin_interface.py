"""
Django management command to set up the complete admin interface system
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from authentication.models import SecurityPolicy, AuditLog
from authentication.security_policies import SecurityPolicyEngine

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up the complete admin interface system with security policies and monitoring'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Create a default admin user if none exists',
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Username for admin user (default: admin)',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@es-nl2dsl.local',
            help='Email for admin user',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Password for admin user (will prompt if not provided)',
        )
        parser.add_argument(
            '--skip-policies',
            action='store_true',
            help='Skip security policy initialization',
        )
        parser.add_argument(
            '--create-demo-data',
            action='store_true',
            help='Create demonstration data for testing',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up ES-NL2DSL Admin Interface System...')
        )
        
        try:
            with transaction.atomic():
                # Step 1: Create admin user if needed
                admin_user = self._setup_admin_user(options)
                
                # Step 2: Initialize security policies
                if not options['skip_policies']:
                    self._setup_security_policies(admin_user)
                
                # Step 3: Create demo data if requested
                if options['create_demo_data']:
                    self._create_demo_data(admin_user)
                
                # Step 4: Verify system components
                self._verify_system_setup()
                
                # Step 5: Display final instructions
                self._display_setup_complete(admin_user)
                
        except Exception as e:
            raise CommandError(f'Admin interface setup failed: {e}')
    
    def _setup_admin_user(self, options) -> User:
        """Create or verify admin user"""
        
        username = options['admin_username']
        email = options['admin_email']
        
        try:
            admin_user = User.objects.get(username=username)
            
            if admin_user.role != 'admin':
                admin_user.role = 'admin'
                admin_user.save()
                self.stdout.write(f'  Updated user {username} role to admin')
            else:
                self.stdout.write(f'  Admin user {username} already exists')
            
        except User.DoesNotExist:
            if not options['create_admin']:
                raise CommandError(
                    f'Admin user {username} does not exist. Use --create-admin to create one.'
                )
            
            password = options['admin_password']
            if not password:
                password = input(f'Enter password for admin user {username}: ')
                if not password:
                    raise CommandError('Password is required')
            
            admin_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role='admin',
                is_active=True,
                is_staff=True,
                is_superuser=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'  Created admin user: {username}')
            )
        
        return admin_user
    
    def _setup_security_policies(self, admin_user: User):
        """Initialize security policies"""
        
        self.stdout.write('Setting up security policies...')
        
        policy_engine = SecurityPolicyEngine()
        created_policies = policy_engine.create_default_policies()
        
        # Update policy creators
        for policy in created_policies:
            policy.created_by = admin_user
            policy.save()
        
        if created_policies:
            self.stdout.write(
                self.style.SUCCESS(f'  Created {len(created_policies)} security policies')
            )
            
            for policy in created_policies:
                self.stdout.write(f'    - {policy.name} ({policy.policy_type})')
        else:
            self.stdout.write('  Security policies already exist')
        
        # Log policy setup
        AuditLog.objects.create(
            user=admin_user,
            event_type='system_config',
            severity='info',
            description='Admin interface security policies initialized',
            metadata={
                'policies_created': len(created_policies),
                'setup_method': 'management_command'
            }
        )
    
    def _create_demo_data(self, admin_user: User):
        """Create demonstration data for testing"""
        
        self.stdout.write('Creating demonstration data...')
        
        # Create demo users
        demo_users = [
            {
                'username': 'analyst_demo',
                'email': 'analyst@demo.local',
                'role': 'analyst',
                'password': 'DemoAnalyst123!'
            },
            {
                'username': 'viewer_demo',
                'email': 'viewer@demo.local',
                'role': 'viewer',
                'password': 'DemoViewer123!'
            }
        ]
        
        created_users = []
        for user_data in demo_users:
            try:
                user = User.objects.get(username=user_data['username'])
                self.stdout.write(f'  Demo user {user_data["username"]} already exists')
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    password=user_data['password'],
                    role=user_data['role'],
                    is_active=True
                )
                created_users.append(user)
                self.stdout.write(f'  Created demo user: {user_data["username"]}')
        
        # Create some demo audit logs
        demo_events = [
            {
                'event_type': 'login',
                'severity': 'info',
                'description': 'Demo user login',
                'user': created_users[0] if created_users else admin_user
            },
            {
                'event_type': 'query_generate',
                'severity': 'info',
                'description': 'Demo query generated',
                'user': created_users[0] if created_users else admin_user
            },
            {
                'event_type': 'login_failed',
                'severity': 'warning',
                'description': 'Demo failed login attempt',
                'user': None
            }
        ]
        
        for event in demo_events:
            AuditLog.objects.create(
                user=event['user'],
                event_type=event['event_type'],
                severity=event['severity'],
                description=event['description'],
                ip_address='127.0.0.1',
                user_agent='Demo User Agent',
                metadata={'demo': True}
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'  Created {len(created_users)} demo users and sample audit logs')
        )
    
    def _verify_system_setup(self):
        """Verify all system components are properly set up"""
        
        self.stdout.write('Verifying system setup...')
        
        # Check admin users
        admin_count = User.objects.filter(role='admin').count()
        self.stdout.write(f'  Admin users: {admin_count}')
        
        # Check security policies
        policy_count = SecurityPolicy.objects.filter(is_active=True).count()
        self.stdout.write(f'  Active security policies: {policy_count}')
        
        # Check audit log functionality
        recent_logs = AuditLog.objects.filter(
            timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
        ).count()
        self.stdout.write(f'  Recent audit logs: {recent_logs}')
        
        # Verify critical components
        checks = [
            (admin_count > 0, 'At least one admin user exists'),
            (policy_count > 0, 'Security policies are configured'),
        ]
        
        for check_result, description in checks:
            if check_result:
                self.stdout.write(f'  ✓ {description}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ {description}')
                )
        
        self.stdout.write('System verification complete')
    
    def _display_setup_complete(self, admin_user: User):
        """Display setup completion message with instructions"""
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('ES-NL2DSL Admin Interface Setup Complete!')
        )
        self.stdout.write('='*60)
        
        self.stdout.write('\nAdmin User Information:')
        self.stdout.write(f'  Username: {admin_user.username}')
        self.stdout.write(f'  Email: {admin_user.email}')
        self.stdout.write(f'  Role: {admin_user.role}')
        
        self.stdout.write('\nNext Steps:')
        self.stdout.write('1. Start the Django development server:')
        self.stdout.write('   python manage.py runserver')
        
        self.stdout.write('\n2. Start the React frontend:')
        self.stdout.write('   cd frontend && npm start')
        
        self.stdout.write('\n3. Access the admin interface:')
        self.stdout.write('   - Login at: http://localhost:3000/login')
        self.stdout.write(f'   - Use credentials: {admin_user.username} / [your password]')
        self.stdout.write('   - Navigate to Admin Dashboard after login')
        
        self.stdout.write('\n4. Available Admin Features:')
        self.stdout.write('   - System Health Monitoring')
        self.stdout.write('   - User Management & Session Control')
        self.stdout.write('   - Security Policy Management')
        self.stdout.write('   - Threat Analysis & Security Events')
        self.stdout.write('   - Performance Metrics & Analytics')
        self.stdout.write('   - Audit Log Management')
        self.stdout.write('   - System Maintenance Tools')
        
        self.stdout.write('\n5. API Endpoints Available:')
        self.stdout.write('   - /api/auth/admin/* - Admin dashboard APIs')
        self.stdout.write('   - /api/auth/sessions/* - Session management')
        self.stdout.write('   - /api/auth/security-policies/* - Policy management')
        self.stdout.write('   - /api/auth/audit-logs/* - Audit log access')
        
        self.stdout.write('\n6. Management Commands:')
        self.stdout.write('   - python manage.py setup_session_security')
        self.stdout.write('   - python manage.py test_security_policies')
        self.stdout.write('   - python manage.py setup_admin_interface --help')
        
        self.stdout.write('\n7. Security Considerations:')
        self.stdout.write('   - Change default admin password in production')
        self.stdout.write('   - Configure proper SSL/HTTPS')
        self.stdout.write('   - Set up proper firewall rules')
        self.stdout.write('   - Configure log rotation and backup')
        self.stdout.write('   - Review and customize security policies')
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS('Admin interface is ready for use!')
        )
        self.stdout.write('='*60 + '\n')
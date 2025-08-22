"""
Django management command to set up session management and security policies
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from authentication.models import SecurityPolicy, AuditLog
from authentication.security_policies import SecurityPolicyEngine

User = get_user_model()


class Command(BaseCommand):
    help = 'Set up session management and security policies'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all existing policies and recreate defaults',
        )
        parser.add_argument(
            '--admin-user',
            type=str,
            help='Username of admin user to assign as policy creator',
            default='admin'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up session management and security policies...')
        )
        
        try:
            with transaction.atomic():
                # Get or create admin user
                admin_user = self._get_admin_user(options['admin_user'])
                
                if options['reset']:
                    self._reset_policies()
                
                # Initialize security policies
                policy_engine = SecurityPolicyEngine()
                created_policies = policy_engine.create_default_policies()
                
                # Update policy creator
                for policy in created_policies:
                    policy.created_by = admin_user
                    policy.save()
                
                self._display_results(created_policies)
                
        except Exception as e:
            raise CommandError(f'Failed to set up session security: {e}')
    
    def _get_admin_user(self, username):
        """Get or create admin user"""
        try:
            admin_user = User.objects.get(username=username)
            if admin_user.role != 'admin':
                self.stdout.write(
                    self.style.WARNING(
                        f'User {username} exists but is not an admin. '
                        f'Current role: {admin_user.role}'
                    )
                )
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f'Admin user {username} not found. '
                    f'Please create an admin user first.'
                )
            )
            # Try to get any admin user
            admin_user = User.objects.filter(role='admin').first()
            if not admin_user:
                raise CommandError(
                    'No admin users found. Please create an admin user first.'
                )
        
        return admin_user
    
    def _reset_policies(self):
        """Reset all existing security policies"""
        policy_count = SecurityPolicy.objects.count()
        SecurityPolicy.objects.all().delete()
        
        self.stdout.write(
            self.style.WARNING(f'Deleted {policy_count} existing security policies')
        )
    
    def _display_results(self, created_policies):
        """Display setup results"""
        
        if not created_policies:
            self.stdout.write(
                self.style.WARNING('No new policies were created (they may already exist)')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {len(created_policies)} security policies:')
        )
        
        for policy in created_policies:
            self.stdout.write(f'  - {policy.name} ({policy.policy_type})')
        
        # Display policy summary by type
        policy_types = {}
        for policy in SecurityPolicy.objects.all():
            policy_types[policy.policy_type] = policy_types.get(policy.policy_type, 0) + 1
        
        self.stdout.write('\nCurrent policy summary:')
        for policy_type, count in sorted(policy_types.items()):
            self.stdout.write(f'  {policy_type}: {count} policies')
        
        # Display next steps
        self.stdout.write('\nNext steps:')
        self.stdout.write('1. Run migrations if needed: python manage.py migrate')
        self.stdout.write('2. Test policy evaluation: python manage.py test_security_policies')
        self.stdout.write('3. Review policies in admin interface or via API')
        self.stdout.write('4. Configure GeoIP2 database for location-based security (optional)')
        
        self.stdout.write(
            self.style.SUCCESS('\nSession management and security policies setup complete!')
        )
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import AuditLog
from .utils import log_audit_event, get_client_ip

User = get_user_model()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login via Django auth."""
    # Update last activity
    user.last_activity = timezone.now()
    user.save(update_fields=['last_activity'])


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout via Django auth."""
    if user and user.is_authenticated:
        log_audit_event(
            user=user,
            action='logout',
            severity='info',
            description='User logged out (Django auth)',
            ip_address=get_client_ip(request) if request else ''
        )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    username = credentials.get('username', 'Unknown')
    email = credentials.get('email', 'Unknown')
    
    log_audit_event(
        user=None,
        action='login',
        severity='warning',
        description=f'Failed login attempt - Username: {username}, Email: {email}',
        ip_address=get_client_ip(request) if request else '',
        metadata={'attempted_username': username, 'attempted_email': email}
    )


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user creation and modifications."""
    if created:
        log_audit_event(
            user=None,  # System event for new user creation
            action='user_create',
            severity='info',
            description=f'New user created: {instance.username}',
            resource_type='user',
            resource_id=str(instance.id),
            metadata={
                'username': instance.username,
                'email': instance.email,
                'role': instance.role
            }
        )
    else:
        # Log significant changes (role, active status)
        if hasattr(instance, '_original_role') and instance._original_role != instance.role:
            log_audit_event(
                user=None,  # System event
                action='role_change',
                severity='warning',
                description=f'User role changed: {instance.username}',
                resource_type='user',
                resource_id=str(instance.id),
                metadata={
                    'username': instance.username,
                    'old_role': instance._original_role,
                    'new_role': instance.role
                }
            )
        
        if hasattr(instance, '_original_is_active') and instance._original_is_active != instance.is_active:
            action = 'activated' if instance.is_active else 'deactivated'
            log_audit_event(
                user=None,  # System event
                action='user_modify',
                severity='warning',
                description=f'User {action}: {instance.username}',
                resource_type='user',
                resource_id=str(instance.id),
                metadata={'username': instance.username, 'action': action}
            )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion."""
    log_audit_event(
        user=None,  # System event
        action='user_delete',
        severity='critical',
        description=f'User deleted: {instance.username}',
        resource_type='user',
        resource_id=str(instance.id),
        metadata={
            'username': instance.username,
            'email': instance.email,
            'role': instance.role
        }
    )


# Store original values for comparison
@receiver(post_save, sender=User)
def store_original_values(sender, instance, **kwargs):
    """Store original values for change tracking."""
    instance._original_role = instance.role
    instance._original_is_active = instance.is_active
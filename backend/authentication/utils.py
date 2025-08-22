from django.utils import timezone
from django.conf import settings
from .models import AuditLog, UserSession
import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def log_audit_event(
    user=None,
    action: str = '',
    severity: str = 'info',
    description: str = '',
    ip_address: str = '',
    user_agent: str = '',
    endpoint: str = '',
    resource_type: str = '',
    resource_id: str = '',
    tenant_id: Optional[uuid.UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Centralized audit logging function.
    
    Args:
        user: User instance (can be None for system events)
        action: Type of action performed
        severity: Severity level ('info', 'warning', 'error', 'critical')
        description: Human-readable description
        ip_address: Client IP address
        user_agent: Client user agent
        endpoint: API endpoint accessed
        resource_type: Type of resource affected
        resource_id: ID of the resource affected
        tenant_id: Tenant ID for multi-tenant logging
        metadata: Additional metadata as dict
    """
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            severity=severity,
            description=description,
            ip_address=ip_address or '',
            user_agent=user_agent or '',
            endpoint=endpoint or '',
            resource_type=resource_type or '',
            resource_id=resource_id or '',
            tenant_id=tenant_id or (user.tenant_id if user else None),
            metadata=metadata or {}
        )
    except Exception as e:
        # Fail silently but log to console in development
        if settings.DEBUG:
            print(f"Audit logging failed: {e}")


def create_user_session(user, request, session_token: str, expires_at: datetime):
    """Create a new user session record."""
    try:
        UserSession.objects.create(
            user=user,
            session_token=session_token,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],  # Truncate long user agents
            expires_at=expires_at
        )
    except Exception as e:
        if settings.DEBUG:
            print(f"Session creation failed: {e}")


def invalidate_user_session(session_token: str):
    """Mark a session as inactive."""
    try:
        UserSession.objects.filter(
            session_token=session_token,
            is_active=True
        ).update(
            is_active=False
        )
    except Exception as e:
        if settings.DEBUG:
            print(f"Session invalidation failed: {e}")


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    try:
        expired_count = UserSession.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        ).update(is_active=False)
        
        if settings.DEBUG:
            print(f"Cleaned up {expired_count} expired sessions")
            
        return expired_count
    except Exception as e:
        if settings.DEBUG:
            print(f"Session cleanup failed: {e}")
        return 0


def get_client_ip(request) -> str:
    """Get the real client IP address from request."""
    # Check for forwarded IP first (load balancers, proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    # Check for real IP header
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    # Fallback to remote addr
    return request.META.get('REMOTE_ADDR', '')


def generate_session_token() -> str:
    """Generate a secure session token."""
    return str(uuid.uuid4())


def validate_tenant_access(user, tenant_id: Optional[str] = None) -> bool:
    """
    Validate if user has access to the specified tenant.
    
    Args:
        user: User instance
        tenant_id: Tenant ID to check access for
        
    Returns:
        bool: True if user has access, False otherwise
    """
    if not tenant_id:
        return True
    
    # Admins have access to all tenants
    if user.role == 'admin':
        return True
    
    # Regular users only have access to their own tenant
    return str(user.tenant_id) == tenant_id


def get_user_permissions(user) -> Dict[str, bool]:
    """
    Get user permissions based on role.
    
    Args:
        user: User instance
        
    Returns:
        Dict of permission flags
    """
    permissions = {
        'can_admin_users': False,
        'can_modify_queries': False,
        'can_execute_queries': False,
        'can_view_audit_logs': False,
        'can_manage_system': False,
        'can_export_data': False,
        'is_read_only': True,
    }
    
    if user.role == 'admin':
        permissions.update({
            'can_admin_users': True,
            'can_modify_queries': True,
            'can_execute_queries': True,
            'can_view_audit_logs': True,
            'can_manage_system': True,
            'can_export_data': True,
            'is_read_only': False,
        })
    elif user.role == 'analyst':
        permissions.update({
            'can_modify_queries': True,
            'can_execute_queries': True,
            'can_export_data': True,
            'is_read_only': False,
        })
    elif user.role == 'viewer':
        permissions.update({
            'can_execute_queries': True,  # Viewers can execute but not modify
        })
    
    return permissions


def check_rate_limit(user, action: str, limit: int = 60, window_minutes: int = 60) -> bool:
    """
    Check if user has exceeded rate limit for a specific action.
    
    Args:
        user: User instance
        action: Action type to check
        limit: Maximum number of actions allowed
        window_minutes: Time window in minutes
        
    Returns:
        bool: True if within rate limit, False if exceeded
    """
    if user.role == 'admin':
        return True  # Admins are not rate limited
    
    try:
        window_start = timezone.now() - timedelta(minutes=window_minutes)
        
        recent_actions = AuditLog.objects.filter(
            user=user,
            action=action,
            timestamp__gte=window_start
        ).count()
        
        return recent_actions < limit
    except Exception:
        # If rate limiting fails, allow the action
        return True


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data in metadata before logging.
    
    Args:
        data: Dictionary potentially containing sensitive data
        
    Returns:
        Dictionary with sensitive fields masked
    """
    sensitive_fields = {
        'password', 'token', 'secret', 'key', 'auth', 'credential',
        'ssn', 'social', 'cc', 'card', 'cvv', 'pin'
    }
    
    masked_data = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_fields):
            masked_data[key] = '***MASKED***'
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value)
        else:
            masked_data[key] = value
    
    return masked_data
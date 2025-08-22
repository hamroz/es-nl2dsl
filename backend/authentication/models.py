from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class CustomUser(AbstractUser):
    """Extended user model with additional security fields."""
    
    USER_ROLES = [
        ('admin', 'Administrator'),
        ('analyst', 'Security Analyst'),
        ('viewer', 'Read-Only Viewer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='viewer')
    
    # Multi-tenant support
    tenant_id = models.UUIDField(null=True, blank=True, help_text="Tenant for data isolation")
    workspace = models.CharField(max_length=100, blank=True, help_text="User workspace identifier")
    
    # Security fields
    is_mfa_enabled = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    is_locked_out = models.BooleanField(default=False)
    lockout_until = models.DateTimeField(null=True, blank=True)
    
    # Activity tracking
    last_activity = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'auth_users'
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['role']),
            models.Index(fields=['is_active', 'is_locked_out']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    @property
    def can_admin_users(self):
        """Check if user can manage other users."""
        return self.role == 'admin'
    
    @property
    def can_modify_queries(self):
        """Check if user can create/modify queries."""
        return self.role in ['admin', 'analyst']
    
    @property
    def is_read_only(self):
        """Check if user has read-only access."""
        return self.role == 'viewer'


class UserSession(models.Model):
    """Enhanced user session tracking with security analysis."""
    
    SECURITY_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sessions')
    
    # Session identification
    session_id = models.CharField(max_length=255, unique=True, help_text="JWT token ID")
    session_token = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Network and device information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    browser = models.CharField(max_length=100, blank=True)
    os = models.CharField(max_length=100, blank=True)
    device = models.CharField(max_length=100, blank=True)
    
    # Geographic information
    location_country = models.CharField(max_length=2, blank=True, help_text="ISO country code")
    location_city = models.CharField(max_length=100, blank=True)
    
    # Security analysis
    security_level = models.CharField(max_length=20, choices=SECURITY_LEVELS, default='medium')
    risk_score = models.FloatField(default=0.5, help_text="Risk score 0-1")
    is_suspicious = models.BooleanField(default=False)
    
    # Session activity
    request_count = models.PositiveIntegerField(default=0)
    session_data = models.JSONField(default=dict, blank=True, help_text="Additional session metadata")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Session state
    is_terminated = models.BooleanField(default=False)
    terminated_at = models.DateTimeField(null=True, blank=True)
    termination_reason = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'auth_user_sessions'
        indexes = [
            models.Index(fields=['user', 'is_terminated']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['is_suspicious']),
            models.Index(fields=['security_level']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id[:8]}... for {self.user.username}"
    
    @property
    def is_active(self):
        """Check if session is currently active."""
        from django.utils import timezone
        return not self.is_terminated and self.expires_at > timezone.now()
    
    @property
    def session_duration(self):
        """Get current session duration."""
        from django.utils import timezone
        end_time = self.terminated_at or self.last_activity or timezone.now()
        return end_time - self.created_at


class AuditLog(models.Model):
    """Comprehensive audit logging for security events."""
    
    ACTION_TYPES = [
        ('login', 'User Login'),
        ('login_failed', 'Failed Login'),
        ('logout', 'User Logout'),
        ('session_created', 'Session Created'),
        ('session_terminated', 'Session Terminated'),
        ('session_ip_changed', 'Session IP Changed'),
        ('query_generate', 'Query Generation'),
        ('query_execute', 'Query Execution'),
        ('data_export', 'Data Export'),
        ('user_create', 'User Creation'),
        ('user_modify', 'User Modification'),
        ('user_delete', 'User Deletion'),
        ('role_change', 'Role Change'),
        ('system_config', 'System Configuration'),
        ('security_event', 'Security Event'),
        ('policy_evaluated', 'Policy Evaluated'),
        ('rate_limit_exceeded', 'Rate Limit Exceeded'),
        ('suspicious_activity', 'Suspicious Activity'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Event details
    event_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    action = models.CharField(max_length=50, choices=ACTION_TYPES, null=True, blank=True)  # Backward compatibility
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='info')
    description = models.TextField(blank=True)
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    endpoint = models.CharField(max_length=255, blank=True)
    
    # Additional context
    resource_type = models.CharField(max_length=100, blank=True)
    resource_id = models.CharField(max_length=100, blank=True)
    tenant_id = models.UUIDField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),  # Backward compatibility
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['tenant_id', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        user_str = self.user.username if self.user else "System"
        event = self.event_type or self.action
        return f"{user_str} - {event} ({self.timestamp})"


class SecurityPolicy(models.Model):
    """Security policies for user access control and behavior enforcement."""
    
    POLICY_TYPES = [
        ('login', 'Login Policy'),
        ('password', 'Password Policy'),
        ('session', 'Session Policy'),
        ('access', 'Access Control Policy'),
        ('rate_limit', 'Rate Limiting Policy'),
        ('mfa', 'Multi-Factor Authentication Policy'),
        ('ip_restriction', 'IP Restriction Policy'),
        ('time_restriction', 'Time Restriction Policy'),
    ]
    
    USER_ROLES = [
        ('all', 'All Users'),
        ('admin', 'Administrator'),
        ('analyst', 'Security Analyst'),
        ('viewer', 'Read-Only Viewer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    
    # Policy classification
    policy_type = models.CharField(max_length=50, choices=POLICY_TYPES)
    user_role = models.CharField(max_length=50, choices=USER_ROLES, default='all')
    priority = models.PositiveIntegerField(default=100, help_text="Lower numbers = higher priority")
    
    # Policy configuration (JSON)
    policy_config = models.JSONField(help_text="Policy rules and parameters")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_policies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_policies'
        indexes = [
            models.Index(fields=['policy_type', 'is_active']),
            models.Index(fields=['user_role', 'is_active']),
            models.Index(fields=['priority']),
        ]
        ordering = ['priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.policy_type})"
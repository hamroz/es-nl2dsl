from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserSession, AuditLog


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Custom user admin with additional fields."""
    
    list_display = ['username', 'email', 'role', 'workspace', 'tenant_id', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'is_locked_out', 'created_at']
    search_fields = ['username', 'email', 'workspace']
    
    fieldsets = UserAdmin.fieldsets + (
        ('ES-NL2DSL Fields', {
            'fields': ('role', 'tenant_id', 'workspace')
        }),
        ('Security', {
            'fields': ('is_mfa_enabled', 'failed_login_attempts', 'is_locked_out', 'lockout_until')
        }),
        ('Activity', {
            'fields': ('last_activity',)
        }),
    )
    
    readonly_fields = ['created_at', 'last_activity', 'failed_login_attempts']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """User session admin."""
    
    list_display = ['user', 'ip_address', 'is_active', 'created_at', 'expires_at']
    list_filter = ['is_active', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'ip_address']
    readonly_fields = ['session_token', 'created_at', 'last_activity']
    
    def has_add_permission(self, request):
        return False  # Sessions are created programmatically


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit log admin with read-only access."""
    
    list_display = ['timestamp', 'user', 'action', 'severity', 'description', 'ip_address']
    list_filter = ['action', 'severity', 'timestamp']
    search_fields = ['user__username', 'user__email', 'description', 'ip_address']
    readonly_fields = '__all__'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete audit logs
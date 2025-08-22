from rest_framework import permissions
from rest_framework.permissions import BasePermission
from .utils import validate_tenant_access


class IsAdminUser(BasePermission):
    """Permission class for admin-only views."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsAnalystOrAdmin(BasePermission):
    """Permission class for analyst and admin users."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ['analyst', 'admin']
        )


class CanModifyQueries(BasePermission):
    """Permission class for users who can modify queries."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.can_modify_queries
        )


class CanExecuteQueries(BasePermission):
    """Permission class for users who can execute queries."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ['viewer', 'analyst', 'admin']
        )


class CanExportData(BasePermission):
    """Permission class for users who can export data."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ['analyst', 'admin']
        )


class TenantAccessPermission(BasePermission):
    """Permission class that validates tenant access."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Get tenant_id from request (query params, body, or headers)
        tenant_id = (
            request.query_params.get('tenant_id') or
            getattr(request.data, {}).get('tenant_id') or
            request.headers.get('X-Tenant-ID')
        )
        
        return validate_tenant_access(request.user, tenant_id)
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for tenant isolation."""
        if not request.user.is_authenticated:
            return False
        
        # Check if object has tenant_id attribute
        if hasattr(obj, 'tenant_id'):
            return validate_tenant_access(request.user, str(obj.tenant_id))
        
        # Check if object has user attribute (user-owned resources)
        if hasattr(obj, 'user'):
            # Admins can access any user's resources
            if request.user.role == 'admin':
                return True
            # Users can only access their own resources
            return obj.user == request.user
        
        return True


class ReadOnlyOrModify(BasePermission):
    """Permission that allows read-only users to GET, others to modify."""
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Allow GET requests for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Allow modifications only for non-read-only users
        return not request.user.is_read_only
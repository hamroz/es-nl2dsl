from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework import status
from .utils import log_audit_event, get_client_ip
import time
import re
from typing import Dict, Tuple

User = get_user_model()


class AuditLogMiddleware:
    """Middleware for comprehensive request/response auditing."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Compile patterns for performance
        self.sensitive_patterns = [
            re.compile(r'password', re.IGNORECASE),
            re.compile(r'token', re.IGNORECASE),
            re.compile(r'secret', re.IGNORECASE),
            re.compile(r'key', re.IGNORECASE),
        ]
    
    def __call__(self, request):
        # Skip audit logging for certain endpoints
        skip_paths = ['/health/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Record start time
        start_time = time.time()
        
        # Get request details
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:1000]
        endpoint = request.path
        method = request.method
        
        # Get user if authenticated
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        
        # Process request
        response = self.get_response(request)
        
        # Calculate response time
        response_time = round((time.time() - start_time) * 1000, 2)  # ms
        
        # Determine audit action based on endpoint and method
        action = self._determine_action(endpoint, method)
        
        # Determine severity based on response status
        severity = self._determine_severity(response.status_code, method)
        
        # Create audit log entry
        if action and getattr(settings, 'AUDIT_LOGGING', {}).get('ENABLED', True):
            description = f"{method} {endpoint} - {response.status_code}"
            
            metadata = {
                'method': method,
                'status_code': response.status_code,
                'response_time_ms': response_time,
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
            }
            
            # Skip request body logging to avoid conflicts with DRF
            # Request body logging will be handled at the view level if needed
            
            log_audit_event(
                user=user,
                action=action,
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                metadata=metadata
            )
        
        return response
    
    def _determine_action(self, endpoint: str, method: str) -> str:
        """Determine audit action based on endpoint and method."""
        endpoint_actions = {
            '/api/auth/login/': 'login',
            '/api/auth/logout/': 'logout',
            '/api/queries/': 'query_generate' if method in ['POST', 'PUT', 'PATCH'] else '',
            '/api/queries/execute/': 'query_execute',
            '/api/evaluation/': 'evaluation',
            '/api/security/': 'security_test',
            '/api/system-admin/': 'system_config',
            '/api/auth/users/': 'user_manage' if method in ['POST', 'PUT', 'PATCH', 'DELETE'] else '',
        }
        
        # Check for exact matches first
        if endpoint in endpoint_actions:
            return endpoint_actions[endpoint]
        
        # Check for pattern matches
        for pattern, action in endpoint_actions.items():
            if endpoint.startswith(pattern.rstrip('/')):
                return action
        
        # Default action for API endpoints
        if endpoint.startswith('/api/'):
            return 'api_access'
        
        return ''
    
    def _determine_severity(self, status_code: int, method: str) -> str:
        """Determine severity based on response status and method."""
        if status_code >= 500:
            return 'error'
        elif status_code >= 400:
            if status_code == 401 or status_code == 403:
                return 'warning'
            return 'warning'
        elif method in ['DELETE', 'PUT', 'PATCH']:
            return 'warning'  # Modification operations
        else:
            return 'info'
    
    def _filter_sensitive_data(self, data: Dict) -> Dict:
        """Filter sensitive data from request body."""
        if not isinstance(data, dict):
            return data
        
        filtered_data = {}
        for key, value in data.items():
            if any(pattern.search(key) for pattern in self.sensitive_patterns):
                filtered_data[key] = '***FILTERED***'
            elif isinstance(value, dict):
                filtered_data[key] = self._filter_sensitive_data(value)
            else:
                filtered_data[key] = value
        
        return filtered_data


class RateLimitMiddleware:
    """Rate limiting middleware with configurable limits per endpoint."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = getattr(settings, 'RATE_LIMITING', {})
    
    def __call__(self, request):
        # Skip rate limiting for admins and certain endpoints
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.role == 'admin':
                return self.get_response(request)
        
        # Skip for health checks and static files
        skip_paths = ['/health/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Determine rate limit for this endpoint
        rate_limit = self._get_rate_limit(request.path, request.method)
        if not rate_limit:
            return self.get_response(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if not self._check_rate_limit(client_id, request.path, rate_limit):
            # Log rate limit violation
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            log_audit_event(
                user=user,
                action='security_event',
                severity='warning',
                description=f'Rate limit exceeded for {request.path}',
                ip_address=get_client_ip(request),
                endpoint=request.path,
                metadata={
                    'rate_limit': rate_limit,
                    'client_id': client_id
                }
            )
            
            return JsonResponse(
                {
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Rate limit: {rate_limit}',
                    'retry_after': self._get_retry_after(rate_limit)
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        return self.get_response(request)
    
    def _get_rate_limit(self, path: str, method: str) -> str:
        """Get rate limit configuration for endpoint."""
        # Specific endpoint limits
        endpoint_limits = {
            '/api/auth/login/': self.rate_limits.get('LOGIN_RATE'),
            '/api/queries/generate/': self.rate_limits.get('QUERY_GENERATION_RATE'),
            '/api/queries/execute/': self.rate_limits.get('QUERY_EXECUTION_RATE'),
            '/api/data/export/': self.rate_limits.get('DATA_EXPORT_RATE'),
        }
        
        for endpoint, limit in endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        
        # Default rate limit
        return self.rate_limits.get('DEFAULT_RATE', '60/min')
    
    def _get_client_id(self, request) -> str:
        """Get client identifier for rate limiting."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        else:
            return f"ip:{get_client_ip(request)}"
    
    def _check_rate_limit(self, client_id: str, endpoint: str, rate_limit: str) -> bool:
        """Check if client has exceeded rate limit."""
        if not rate_limit:
            return True
        
        try:
            # Parse rate limit (e.g., "60/min", "100/hour")
            count, period = rate_limit.split('/')
            count = int(count)
            
            # Convert period to seconds
            period_seconds = {
                'sec': 1,
                'min': 60,
                'hour': 3600,
                'day': 86400
            }.get(period, 60)
            
            # Create cache key
            cache_key = f"rate_limit:{client_id}:{endpoint}"
            
            # Get current count
            current = cache.get(cache_key, 0)
            
            if current >= count:
                return False
            
            # Increment counter
            cache.set(cache_key, current + 1, period_seconds)
            return True
            
        except (ValueError, KeyError):
            # If rate limit parsing fails, allow request
            return True
    
    def _get_retry_after(self, rate_limit: str) -> int:
        """Get retry after seconds from rate limit."""
        try:
            _, period = rate_limit.split('/')
            return {'sec': 1, 'min': 60, 'hour': 3600, 'day': 86400}.get(period, 60)
        except:
            return 60


class SecurityHeadersMiddleware:
    """Add security headers to responses."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Add CSP header for API endpoints
        if request.path.startswith('/api/'):
            response['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        
        return response


class TenantIsolationMiddleware:
    """Middleware to enforce tenant isolation."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add tenant context to request if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.tenant_id = request.user.tenant_id
            
            # Validate tenant access for multi-tenant endpoints
            if request.path.startswith('/api/') and request.user.tenant_id:
                # Extract tenant_id from request if provided
                requested_tenant = (
                    request.GET.get('tenant_id') or
                    getattr(request.data, {}).get('tenant_id') if hasattr(request, 'data') else None or
                    request.META.get('HTTP_X_TENANT_ID')
                )
                
                if requested_tenant and str(request.user.tenant_id) != requested_tenant:
                    if request.user.role != 'admin':  # Admins can access all tenants
                        return JsonResponse(
                            {'error': 'Access denied to requested tenant'},
                            status=status.HTTP_403_FORBIDDEN
                        )
        
        return self.get_response(request)
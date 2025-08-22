from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.core.exceptions import PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from .utils import log_audit_event, get_client_ip
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that adds audit logging and standardized error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # Get request from context
    request = context.get('request')
    
    if response is not None:
        # Log security-related exceptions
        if response.status_code in [401, 403]:
            user = request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None
            
            log_audit_event(
                user=user,
                action='security_event',
                severity='warning',
                description=f'Access denied: {str(exc)}',
                ip_address=get_client_ip(request) if request else '',
                user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
                endpoint=request.path if request else '',
                metadata={
                    'exception_type': type(exc).__name__,
                    'status_code': response.status_code
                }
            )
        
        # Customize error response format
        custom_response_data = {
            'error': True,
            'message': _get_error_message(exc, response),
            'code': _get_error_code(exc, response.status_code),
            'status_code': response.status_code
        }
        
        # Add details for validation errors
        if hasattr(response, 'data') and isinstance(response.data, dict):
            if 'detail' in response.data:
                custom_response_data['details'] = response.data
            elif any(key in response.data for key in ['non_field_errors', 'field_errors']):
                custom_response_data['validation_errors'] = response.data
        
        response.data = custom_response_data
    
    else:
        # Handle uncaught exceptions
        if isinstance(exc, Http404):
            response = Response(
                {
                    'error': True,
                    'message': 'Resource not found',
                    'code': 'NOT_FOUND',
                    'status_code': 404
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        elif isinstance(exc, PermissionDenied):
            response = Response(
                {
                    'error': True,
                    'message': 'Permission denied',
                    'code': 'PERMISSION_DENIED',
                    'status_code': 403
                },
                status=status.HTTP_403_FORBIDDEN
            )
            
            # Log permission denied
            user = request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None
            log_audit_event(
                user=user,
                action='security_event',
                severity='warning',
                description=f'Permission denied: {str(exc)}',
                ip_address=get_client_ip(request) if request else '',
                endpoint=request.path if request else ''
            )
        
        elif isinstance(exc, (TokenError, InvalidToken)):
            response = Response(
                {
                    'error': True,
                    'message': 'Invalid or expired token',
                    'code': 'INVALID_TOKEN',
                    'status_code': 401
                },
                status=status.HTTP_401_UNAUTHORIZED
            )
            
            # Log token error
            log_audit_event(
                user=None,
                action='security_event',
                severity='warning',
                description=f'Token error: {str(exc)}',
                ip_address=get_client_ip(request) if request else '',
                endpoint=request.path if request else '',
                metadata={'exception_type': type(exc).__name__}
            )
        
        else:
            # Log unexpected errors
            logger.exception(f"Unhandled exception: {exc}")
            
            # Don't expose internal errors in production
            from django.conf import settings
            if settings.DEBUG:
                error_message = str(exc)
            else:
                error_message = 'An unexpected error occurred'
            
            response = Response(
                {
                    'error': True,
                    'message': error_message,
                    'code': 'INTERNAL_ERROR',
                    'status_code': 500
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return response


def _get_error_message(exc, response):
    """Get appropriate error message from exception."""
    if hasattr(response, 'data'):
        if isinstance(response.data, dict):
            # Try to get detail message
            if 'detail' in response.data:
                return response.data['detail']
            
            # For validation errors, create a summary
            errors = []
            for field, messages in response.data.items():
                if isinstance(messages, list):
                    errors.extend(messages)
                else:
                    errors.append(str(messages))
            
            if errors:
                return '; '.join(errors)
        
        elif isinstance(response.data, list):
            return '; '.join(response.data)
    
    return str(exc)


def _get_error_code(exc, status_code):
    """Get error code based on exception type and status code."""
    exception_codes = {
        'ValidationError': 'VALIDATION_ERROR',
        'AuthenticationFailed': 'AUTHENTICATION_FAILED',
        'NotAuthenticated': 'NOT_AUTHENTICATED',
        'PermissionDenied': 'PERMISSION_DENIED',
        'NotFound': 'NOT_FOUND',
        'MethodNotAllowed': 'METHOD_NOT_ALLOWED',
        'Throttled': 'RATE_LIMITED',
        'TokenError': 'INVALID_TOKEN',
        'InvalidToken': 'INVALID_TOKEN',
    }
    
    exc_name = type(exc).__name__
    if exc_name in exception_codes:
        return exception_codes[exc_name]
    
    # Fallback to status code-based codes
    status_codes = {
        400: 'BAD_REQUEST',
        401: 'UNAUTHORIZED',
        403: 'FORBIDDEN',
        404: 'NOT_FOUND',
        405: 'METHOD_NOT_ALLOWED',
        429: 'RATE_LIMITED',
        500: 'INTERNAL_ERROR',
    }
    
    return status_codes.get(status_code, 'UNKNOWN_ERROR')


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


class AuthorizationError(Exception):
    """Custom authorization error."""
    pass


class RateLimitError(Exception):
    """Custom rate limit error."""
    pass


class TenantAccessError(Exception):
    """Custom tenant access error."""
    pass
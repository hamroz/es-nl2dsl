"""
Session Security Middleware
Integrates session management and security policies into Django request processing
"""

import json
import logging
from datetime import datetime
from typing import Optional

from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache

from .models import UserSession, AuditLog
from .session_manager import SessionManager
from .security_policies import SecurityPolicyEngine, PolicyAction

User = get_user_model()
logger = logging.getLogger(__name__)


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to enforce session security policies and manage session lifecycle
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.session_manager = SessionManager()
        self.policy_engine = SecurityPolicyEngine()
        
        # Paths that don't require session validation
        self.exempt_paths = getattr(settings, 'SESSION_SECURITY_EXEMPT_PATHS', [
            '/api/auth/login/',
            '/api/auth/register/',
            '/api/auth/refresh/',
            '/api/health/',
            '/static/',
            '/media/',
        ])
        
        # Paths that require enhanced security
        self.high_security_paths = getattr(settings, 'HIGH_SECURITY_PATHS', [
            '/api/auth/users/',
            '/api/admin/',
            '/api/system/',
        ])
    
    def process_request(self, request):
        """Process incoming request for security validation"""
        
        # Skip processing for exempt paths
        if self._is_exempt_path(request.path):
            return None
        
        # Skip for unauthenticated requests
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        try:
            # Get current session
            session = self._get_current_session(request)
            if not session:
                return self._handle_no_session(request)
            
            # Validate session
            validation_result = self.session_manager.validate_session(session, request)
            if not validation_result['is_valid']:
                return self._handle_invalid_session(request, session, validation_result)
            
            # Update session activity
            self.session_manager.update_session_activity(session, request)
            
            # Evaluate security policies
            policy_violations = self._evaluate_security_policies(request, session)
            if policy_violations:
                return self._handle_policy_violations(request, session, policy_violations)
            
            # Add session info to request
            request.session_info = {
                'session': session,
                'validation': validation_result,
                'security_level': session.security_level,
                'risk_score': session.risk_score,
                'is_suspicious': session.is_suspicious,
            }
            
        except Exception as e:
            logger.error(f"Session security middleware error: {e}")
            # Continue processing on error to avoid breaking the application
            pass
        
        return None
    
    def process_response(self, request, response):
        """Process response for session security logging"""
        
        if hasattr(request, 'session_info') and hasattr(request, 'user'):
            try:
                self._log_request_activity(request, response)
            except Exception as e:
                logger.error(f"Session activity logging error: {e}")
        
        return response
    
    def _get_current_session(self, request) -> Optional[UserSession]:
        """Get current user session"""
        
        # Try to get session from JWT token
        if hasattr(request, 'auth') and request.auth:
            try:
                # Extract session ID from JWT token
                token_payload = request.auth.payload
                session_id = token_payload.get('jti')
                
                if session_id:
                    return UserSession.objects.get(
                        session_id=session_id,
                        user=request.user,
                        is_terminated=False
                    )
            except (AttributeError, UserSession.DoesNotExist):
                pass
        
        # Fallback: get most recent active session for user
        return UserSession.objects.filter(
            user=request.user,
            is_terminated=False,
            expires_at__gt=timezone.now()
        ).order_by('-last_activity').first()
    
    def _evaluate_security_policies(self, request, session: UserSession) -> list:
        """Evaluate security policies for current request"""
        
        violations = []
        
        try:
            # Check IP restrictions
            ip_result = self.policy_engine.check_ip_whitelist(request.user, request.META.get('REMOTE_ADDR', ''))
            if ip_result.action == PolicyAction.DENY:
                violations.append(ip_result)
            
            # Check time restrictions
            time_result = self.policy_engine.check_time_restriction(request.user)
            if time_result.action == PolicyAction.DENY:
                violations.append(time_result)
            
            # Evaluate access policies for high-security paths
            if self._is_high_security_path(request.path):
                access_results = self.policy_engine.evaluate_access_policy(
                    request.user, 
                    request.path, 
                    request.method,
                    request,
                    {'session_id': session.session_id}
                )
                violations.extend([r for r in access_results if r.action in [PolicyAction.DENY, PolicyAction.REQUIRE_MFA]])
            
            # Evaluate session policies
            session_results = self.policy_engine.evaluate_session_policy(
                request.user,
                {
                    'session_id': session.session_id,
                    'active_session_count': self._get_active_session_count(request.user),
                    'security_level': session.security_level,
                    'is_suspicious': session.is_suspicious,
                },
                request
            )
            violations.extend([r for r in session_results if r.action in [PolicyAction.DENY, PolicyAction.TERMINATE_SESSION]])
            
        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
        
        return violations
    
    def _handle_no_session(self, request):
        """Handle request with no valid session"""
        
        logger.warning(f"No valid session found for user {request.user.username}")
        
        # Log security event
        AuditLog.objects.create(
            user=request.user,
            event_type='session_not_found',
            severity='warning',
            description=f'No valid session found for authenticated user',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            endpoint=request.path,
        )
        
        return JsonResponse({
            'error': 'Invalid session',
            'code': 'SESSION_INVALID',
            'message': 'Please log in again'
        }, status=401)
    
    def _handle_invalid_session(self, request, session: UserSession, validation_result):
        """Handle invalid session"""
        
        logger.warning(f"Invalid session for user {request.user.username}: {validation_result}")
        
        # Determine action based on validation result
        if 'session_expired' in validation_result['actions_required']:
            message = 'Session expired'
        elif 'session_terminated' in validation_result['actions_required']:
            message = 'Session terminated'
        elif 'session_inactive' in validation_result['actions_required']:
            message = 'Session inactive too long'
        else:
            message = 'Session validation failed'
        
        # Log security event
        AuditLog.objects.create(
            user=request.user,
            event_type='session_validation_failed',
            severity='warning',
            description=f'Session validation failed: {message}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            endpoint=request.path,
            metadata={'validation_result': validation_result},
        )
        
        return JsonResponse({
            'error': 'Session invalid',
            'code': 'SESSION_VALIDATION_FAILED',
            'message': message,
            'details': validation_result
        }, status=401)
    
    def _handle_policy_violations(self, request, session: UserSession, violations: list):
        """Handle security policy violations"""
        
        logger.warning(f"Security policy violations for user {request.user.username}: {len(violations)} violations")
        
        # Process violations by severity
        critical_violations = [v for v in violations if v.action == PolicyAction.DENY]
        termination_violations = [v for v in violations if v.action == PolicyAction.TERMINATE_SESSION]
        mfa_violations = [v for v in violations if v.action == PolicyAction.REQUIRE_MFA]
        
        # Handle termination violations
        if termination_violations:
            violation = termination_violations[0]
            self.session_manager.terminate_session(session, f'policy_violation: {violation.reason}')
            
            AuditLog.objects.create(
                user=request.user,
                event_type='session_terminated_policy',
                severity='critical',
                description=f'Session terminated due to policy violation: {violation.reason}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                endpoint=request.path,
                metadata={'violation': violation.metadata},
            )
            
            return JsonResponse({
                'error': 'Session terminated',
                'code': 'POLICY_VIOLATION_TERMINATION',
                'message': violation.reason
            }, status=403)
        
        # Handle critical violations
        if critical_violations:
            violation = critical_violations[0]
            
            AuditLog.objects.create(
                user=request.user,
                event_type='policy_violation_deny',
                severity='critical',
                description=f'Access denied due to policy violation: {violation.reason}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                endpoint=request.path,
                metadata={'violation': violation.metadata},
            )
            
            return JsonResponse({
                'error': 'Access denied',
                'code': 'POLICY_VIOLATION_DENY',
                'message': violation.reason
            }, status=403)
        
        # Handle MFA violations
        if mfa_violations:
            violation = mfa_violations[0]
            
            return JsonResponse({
                'error': 'Multi-factor authentication required',
                'code': 'MFA_REQUIRED',
                'message': violation.reason,
                'next_step': 'complete_mfa'
            }, status=428)  # 428 Precondition Required
        
        return None
    
    def _log_request_activity(self, request, response):
        """Log request activity for security monitoring"""
        
        session_info = request.session_info
        session = session_info['session']
        
        # Only log certain types of activities to avoid spam
        should_log = (
            response.status_code >= 400 or  # Errors
            self._is_high_security_path(request.path) or  # High-security paths
            session_info['is_suspicious'] or  # Suspicious sessions
            request.method in ['POST', 'PUT', 'DELETE', 'PATCH']  # Modifying operations
        )
        
        if should_log:
            severity = 'error' if response.status_code >= 500 else 'warning' if response.status_code >= 400 else 'info'
            
            AuditLog.objects.create(
                user=request.user,
                event_type='request_activity',
                severity=severity,
                description=f'{request.method} {request.path} -> {response.status_code}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                endpoint=request.path,
                metadata={
                    'method': request.method,
                    'status_code': response.status_code,
                    'session_id': session.session_id,
                    'security_level': session.security_level,
                    'risk_score': session.risk_score,
                },
            )
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from session security"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
    
    def _is_high_security_path(self, path: str) -> bool:
        """Check if path requires enhanced security"""
        return any(path.startswith(secure) for secure in self.high_security_paths)
    
    def _get_active_session_count(self, user) -> int:
        """Get count of active sessions for user"""
        cache_key = f"active_sessions_{user.id}"
        count = cache.get(cache_key)
        
        if count is None:
            count = UserSession.objects.filter(
                user=user,
                is_terminated=False,
                expires_at__gt=timezone.now()
            ).count()
            cache.set(cache_key, count, 60)  # Cache for 1 minute
        
        return count
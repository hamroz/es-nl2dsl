"""
Security Policy Engine
Manages and enforces security policies across the application
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from .models import SecurityPolicy, AuditLog, CustomUser

logger = logging.getLogger(__name__)


class PolicyAction:
    """Policy action types"""
    ALLOW = 'allow'
    DENY = 'deny'
    WARN = 'warn'
    REQUIRE_MFA = 'require_mfa'
    LIMIT_ACCESS = 'limit_access'
    TERMINATE_SESSION = 'terminate_session'


class PolicyResult:
    """Policy evaluation result"""
    
    def __init__(self, action: str, reason: str = None, metadata: Dict = None):
        self.action = action
        self.reason = reason or ""
        self.metadata = metadata or {}
        self.timestamp = timezone.now()


class SecurityPolicyEngine:
    """Advanced security policy engine for enforcing business rules"""
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'POLICY_CACHE_TIMEOUT', 300)  # 5 minutes
        
    def evaluate_login_policy(self, user: CustomUser, request, context: Dict = None) -> List[PolicyResult]:
        """Evaluate login policies for a user"""
        
        context = context or {}
        results = []
        
        # Get applicable policies
        policies = self._get_applicable_policies(user, 'login')
        
        for policy in policies:
            result = self._evaluate_policy(policy, user, request, context)
            if result:
                results.append(result)
                
                # Log policy evaluation
                self._log_policy_evaluation(user, policy, result, request)
        
        return results
    
    def evaluate_access_policy(self, user: CustomUser, resource: str, action: str, 
                              request, context: Dict = None) -> List[PolicyResult]:
        """Evaluate access policies for a specific resource"""
        
        context = context or {'resource': resource, 'action': action}
        results = []
        
        policies = self._get_applicable_policies(user, 'access')
        
        for policy in policies:
            result = self._evaluate_policy(policy, user, request, context)
            if result:
                results.append(result)
                self._log_policy_evaluation(user, policy, result, request)
        
        return results
    
    def evaluate_session_policy(self, user: CustomUser, session_data: Dict, 
                               request) -> List[PolicyResult]:
        """Evaluate session-related policies"""
        
        context = {'session_data': session_data}
        results = []
        
        policies = self._get_applicable_policies(user, 'session')
        
        for policy in policies:
            result = self._evaluate_policy(policy, user, request, context)
            if result:
                results.append(result)
                self._log_policy_evaluation(user, policy, result, request)
        
        return results
    
    def check_password_policy(self, password: str, user: CustomUser = None) -> Dict[str, Any]:
        """Check password against security policies"""
        
        policies = SecurityPolicy.objects.filter(
            policy_type='password',
            is_active=True
        ).first()
        
        if not policies:
            return {'is_valid': True, 'issues': []}
        
        config = json.loads(policies.policy_config)
        issues = []
        
        # Check minimum length
        min_length = config.get('min_length', 8)
        if len(password) < min_length:
            issues.append(f'Password must be at least {min_length} characters long')
        
        # Check complexity requirements
        if config.get('require_uppercase', False):
            if not any(c.isupper() for c in password):
                issues.append('Password must contain at least one uppercase letter')
        
        if config.get('require_lowercase', False):
            if not any(c.islower() for c in password):
                issues.append('Password must contain at least one lowercase letter')
        
        if config.get('require_digits', False):
            if not any(c.isdigit() for c in password):
                issues.append('Password must contain at least one digit')
        
        if config.get('require_special', False):
            special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
            if not any(c in special_chars for c in password):
                issues.append('Password must contain at least one special character')
        
        # Check against common passwords
        if config.get('check_common_passwords', False):
            if self._is_common_password(password):
                issues.append('Password is too common, please choose a more secure password')
        
        # Check against user information
        if user and config.get('check_user_info', False):
            if self._password_contains_user_info(password, user):
                issues.append('Password cannot contain your personal information')
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'strength_score': self._calculate_password_strength(password)
        }
    
    def enforce_mfa_policy(self, user: CustomUser) -> Dict[str, Any]:
        """Check if MFA should be enforced for user"""
        
        policies = self._get_applicable_policies(user, 'mfa')
        
        for policy in policies:
            config = json.loads(policy.policy_config)
            
            # Check if MFA is required for this user role
            if config.get('required_for_roles', []):
                if user.role in config['required_for_roles']:
                    return {
                        'mfa_required': True,
                        'reason': f'MFA required for {user.role} role',
                        'policy_name': policy.name
                    }
            
            # Check if MFA is required for admin actions
            if config.get('required_for_admin', False) and user.role == 'admin':
                return {
                    'mfa_required': True,
                    'reason': 'MFA required for admin users',
                    'policy_name': policy.name
                }
            
            # Check based on recent failed login attempts
            if config.get('required_after_failed_attempts'):
                failed_attempts = self._get_recent_failed_attempts(user)
                threshold = config['required_after_failed_attempts']
                
                if failed_attempts >= threshold:
                    return {
                        'mfa_required': True,
                        'reason': f'MFA required after {failed_attempts} failed attempts',
                        'policy_name': policy.name
                    }
        
        return {'mfa_required': False}
    
    def get_rate_limit_policy(self, user: CustomUser, endpoint: str = None) -> Dict[str, int]:
        """Get rate limiting configuration for user"""
        
        cache_key = f"rate_limit_policy_{user.id}_{endpoint or 'default'}"
        cached_policy = cache.get(cache_key)
        
        if cached_policy:
            return cached_policy
        
        policies = self._get_applicable_policies(user, 'rate_limit')
        rate_limits = {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'requests_per_day': 10000
        }
        
        for policy in policies:
            config = json.loads(policy.policy_config)
            
            # Apply role-based limits
            role_limits = config.get('role_limits', {}).get(user.role, {})
            rate_limits.update(role_limits)
            
            # Apply endpoint-specific limits
            if endpoint and 'endpoint_limits' in config:
                endpoint_limits = config['endpoint_limits'].get(endpoint, {})
                rate_limits.update(endpoint_limits)
        
        cache.set(cache_key, rate_limits, self.cache_timeout)
        return rate_limits
    
    def check_ip_whitelist(self, user: CustomUser, ip_address: str) -> PolicyResult:
        """Check if IP address is allowed for user"""
        
        policies = self._get_applicable_policies(user, 'ip_restriction')
        
        for policy in policies:
            config = json.loads(policy.policy_config)
            
            # Check whitelist
            if 'allowed_ips' in config:
                allowed_ips = config['allowed_ips']
                if ip_address not in allowed_ips:
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'IP address {ip_address} not in whitelist',
                        {'policy': policy.name, 'ip': ip_address}
                    )
            
            # Check blacklist
            if 'blocked_ips' in config:
                blocked_ips = config['blocked_ips']
                if ip_address in blocked_ips:
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'IP address {ip_address} is blacklisted',
                        {'policy': policy.name, 'ip': ip_address}
                    )
        
        return PolicyResult(PolicyAction.ALLOW)
    
    def check_time_restriction(self, user: CustomUser, current_time: datetime = None) -> PolicyResult:
        """Check if current time is within allowed access hours"""
        
        current_time = current_time or timezone.now()
        policies = self._get_applicable_policies(user, 'time_restriction')
        
        for policy in policies:
            config = json.loads(policy.policy_config)
            
            # Check allowed hours
            if 'allowed_hours' in config:
                allowed_hours = config['allowed_hours']
                current_hour = current_time.hour
                
                if current_hour not in allowed_hours:
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'Access not allowed at {current_hour:02d}:00',
                        {'policy': policy.name, 'current_hour': current_hour}
                    )
            
            # Check allowed days
            if 'allowed_days' in config:
                allowed_days = config['allowed_days']  # 0=Monday, 6=Sunday
                current_day = current_time.weekday()
                
                if current_day not in allowed_days:
                    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                                'Friday', 'Saturday', 'Sunday']
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'Access not allowed on {day_names[current_day]}',
                        {'policy': policy.name, 'current_day': current_day}
                    )
        
        return PolicyResult(PolicyAction.ALLOW)
    
    def create_default_policies(self) -> List[SecurityPolicy]:
        """Create default security policies"""
        
        default_policies = [
            {
                'name': 'Default Password Policy',
                'policy_type': 'password',
                'user_role': 'all',
                'policy_config': {
                    'min_length': 12,
                    'require_uppercase': True,
                    'require_lowercase': True,
                    'require_digits': True,
                    'require_special': True,
                    'check_common_passwords': True,
                    'check_user_info': True,
                    'password_history': 5
                }
            },
            {
                'name': 'Admin MFA Policy',
                'policy_type': 'mfa',
                'user_role': 'admin',
                'policy_config': {
                    'required_for_roles': ['admin'],
                    'required_for_admin': True,
                    'required_after_failed_attempts': 3
                }
            },
            {
                'name': 'Rate Limiting Policy',
                'policy_type': 'rate_limit',
                'user_role': 'all',
                'policy_config': {
                    'role_limits': {
                        'viewer': {
                            'requests_per_minute': 30,
                            'requests_per_hour': 500,
                            'requests_per_day': 5000
                        },
                        'analyst': {
                            'requests_per_minute': 60,
                            'requests_per_hour': 1000,
                            'requests_per_day': 10000
                        },
                        'admin': {
                            'requests_per_minute': 120,
                            'requests_per_hour': 2000,
                            'requests_per_day': 20000
                        }
                    }
                }
            },
            {
                'name': 'Session Security Policy',
                'policy_type': 'session',
                'user_role': 'all',
                'policy_config': {
                    'max_concurrent_sessions': {
                        'viewer': 2,
                        'analyst': 3,
                        'admin': 5
                    },
                    'max_session_duration': 480,  # 8 hours
                    'max_idle_time': 60,  # 1 hour
                    'require_reauth_for_sensitive': True
                }
            }
        ]
        
        created_policies = []
        for policy_data in default_policies:
            policy, created = SecurityPolicy.objects.get_or_create(
                name=policy_data['name'],
                defaults={
                    'policy_type': policy_data['policy_type'],
                    'user_role': policy_data['user_role'],
                    'policy_config': json.dumps(policy_data['policy_config']),
                    'is_active': True,
                    'created_by_id': 1  # Assume admin user exists
                }
            )
            if created:
                created_policies.append(policy)
        
        return created_policies
    
    def _get_applicable_policies(self, user: CustomUser, policy_type: str) -> List[SecurityPolicy]:
        """Get policies applicable to a user"""
        
        cache_key = f"policies_{user.id}_{policy_type}"
        cached_policies = cache.get(cache_key)
        
        if cached_policies:
            return cached_policies
        
        policies = list(SecurityPolicy.objects.filter(
            policy_type=policy_type,
            is_active=True
        ).filter(
            user_role__in=[user.role, 'all']
        ).order_by('priority'))
        
        cache.set(cache_key, policies, self.cache_timeout)
        return policies
    
    def _evaluate_policy(self, policy: SecurityPolicy, user: CustomUser, 
                        request, context: Dict) -> Optional[PolicyResult]:
        """Evaluate a single policy"""
        
        try:
            config = json.loads(policy.policy_config)
            
            # Policy-specific evaluation logic
            if policy.policy_type == 'login':
                return self._evaluate_login_rules(config, user, request, context)
            elif policy.policy_type == 'access':
                return self._evaluate_access_rules(config, user, request, context)
            elif policy.policy_type == 'session':
                return self._evaluate_session_rules(config, user, request, context)
            
        except Exception as e:
            logger.error(f"Policy evaluation error for {policy.name}: {e}")
            
        return None
    
    def _evaluate_login_rules(self, config: Dict, user: CustomUser, 
                             request, context: Dict) -> Optional[PolicyResult]:
        """Evaluate login-specific rules"""
        
        # Check maximum failed attempts
        if 'max_failed_attempts' in config:
            failed_attempts = self._get_recent_failed_attempts(user)
            max_attempts = config['max_failed_attempts']
            
            if failed_attempts >= max_attempts:
                return PolicyResult(
                    PolicyAction.DENY,
                    f'Account locked due to {failed_attempts} failed attempts',
                    {'failed_attempts': failed_attempts}
                )
        
        # Check account lockout duration
        if user.is_locked_out:
            lockout_duration = config.get('lockout_duration_minutes', 30)
            last_failed = self._get_last_failed_attempt(user)
            
            if last_failed:
                unlock_time = last_failed + timedelta(minutes=lockout_duration)
                if timezone.now() < unlock_time:
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'Account locked until {unlock_time}',
                        {'unlock_time': unlock_time.isoformat()}
                    )
        
        return None
    
    def _evaluate_access_rules(self, config: Dict, user: CustomUser,
                              request, context: Dict) -> Optional[PolicyResult]:
        """Evaluate access control rules"""
        
        resource = context.get('resource')
        action = context.get('action')
        
        # Check resource permissions
        if 'resource_permissions' in config:
            permissions = config['resource_permissions']
            user_perms = permissions.get(user.role, {})
            
            if resource in user_perms:
                allowed_actions = user_perms[resource]
                if action not in allowed_actions:
                    return PolicyResult(
                        PolicyAction.DENY,
                        f'Action {action} not allowed on {resource}',
                        {'resource': resource, 'action': action}
                    )
        
        return None
    
    def _evaluate_session_rules(self, config: Dict, user: CustomUser,
                               request, context: Dict) -> Optional[PolicyResult]:
        """Evaluate session security rules"""
        
        session_data = context.get('session_data', {})
        
        # Check concurrent sessions
        if 'max_concurrent_sessions' in config:
            limits = config['max_concurrent_sessions']
            user_limit = limits.get(user.role, limits.get('default', 3))
            
            current_sessions = session_data.get('active_session_count', 0)
            if current_sessions >= user_limit:
                return PolicyResult(
                    PolicyAction.LIMIT_ACCESS,
                    f'Maximum concurrent sessions ({user_limit}) reached',
                    {'current_sessions': current_sessions, 'limit': user_limit}
                )
        
        return None
    
    def _get_recent_failed_attempts(self, user: CustomUser, hours: int = 1) -> int:
        """Get count of recent failed login attempts"""
        
        since = timezone.now() - timedelta(hours=hours)
        return AuditLog.objects.filter(
            user=user,
            event_type='login_failed',
            timestamp__gte=since
        ).count()
    
    def _get_last_failed_attempt(self, user: CustomUser) -> Optional[datetime]:
        """Get timestamp of last failed login attempt"""
        
        last_attempt = AuditLog.objects.filter(
            user=user,
            event_type='login_failed'
        ).order_by('-timestamp').first()
        
        return last_attempt.timestamp if last_attempt else None
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is in common password list"""
        
        # This would typically check against a database of common passwords
        # For demo purposes, using a simple list
        common_passwords = [
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', '1234567890'
        ]
        
        return password.lower() in common_passwords
    
    def _password_contains_user_info(self, password: str, user: CustomUser) -> bool:
        """Check if password contains user information"""
        
        password_lower = password.lower()
        
        # Check against username
        if user.username.lower() in password_lower:
            return True
        
        # Check against email parts
        if user.email:
            email_parts = user.email.lower().split('@')[0]
            if email_parts in password_lower:
                return True
        
        # Check against first/last name if available
        if hasattr(user, 'first_name') and user.first_name:
            if user.first_name.lower() in password_lower:
                return True
        
        if hasattr(user, 'last_name') and user.last_name:
            if user.last_name.lower() in password_lower:
                return True
        
        return False
    
    def _calculate_password_strength(self, password: str) -> float:
        """Calculate password strength score (0-1)"""
        
        score = 0.0
        
        # Length bonus
        score += min(len(password) / 20, 0.3)
        
        # Character variety bonus
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        variety_score = sum([has_lower, has_upper, has_digit, has_special]) / 4
        score += variety_score * 0.4
        
        # Uniqueness bonus (no repeated patterns)
        unique_chars = len(set(password))
        uniqueness = unique_chars / len(password) if password else 0
        score += uniqueness * 0.3
        
        return min(score, 1.0)
    
    def _log_policy_evaluation(self, user: CustomUser, policy: SecurityPolicy, 
                              result: PolicyResult, request):
        """Log policy evaluation for audit purposes"""
        
        AuditLog.objects.create(
            user=user,
            event_type='policy_evaluated',
            resource_type='security_policy',
            resource_id=str(policy.id),
            ip_address=self._get_client_ip(request),
            metadata=json.dumps({
                'policy_name': policy.name,
                'policy_type': policy.policy_type,
                'action': result.action,
                'reason': result.reason,
                'metadata': result.metadata
            }),
            timestamp=result.timestamp
        )
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
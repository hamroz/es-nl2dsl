from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from rest_framework import status
from typing import Dict, Tuple, Optional
import time
import hashlib
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from .utils import log_audit_event, get_client_ip

logger = logging.getLogger(__name__)


class RateLimitStrategy:
    """Base class for rate limiting strategies."""
    
    def __init__(self, limit: int, window: int, name: str = "default"):
        self.limit = limit
        self.window = window  # in seconds
        self.name = name
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict]:
        """Check if request is allowed. Returns (allowed, info)."""
        raise NotImplementedError
    
    def get_reset_time(self, identifier: str) -> Optional[datetime]:
        """Get when the rate limit resets."""
        raise NotImplementedError


class TokenBucketStrategy(RateLimitStrategy):
    """Token bucket rate limiting strategy."""
    
    def __init__(self, limit: int, window: int, refill_rate: float = None, name: str = "token_bucket"):
        super().__init__(limit, window, name)
        self.refill_rate = refill_rate or (limit / window)  # tokens per second
        self.bucket_size = limit
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict]:
        """Token bucket algorithm implementation."""
        cache_key = f"rate_limit:token_bucket:{identifier}"
        
        now = time.time()
        bucket_data = cache.get(cache_key, {
            'tokens': self.bucket_size,
            'last_refill': now
        })
        
        # Calculate tokens to add based on time elapsed
        time_elapsed = now - bucket_data['last_refill']
        tokens_to_add = time_elapsed * self.refill_rate
        
        # Update token count (capped at bucket size)
        bucket_data['tokens'] = min(
            self.bucket_size,
            bucket_data['tokens'] + tokens_to_add
        )
        bucket_data['last_refill'] = now
        
        # Check if request is allowed
        if bucket_data['tokens'] >= 1:
            bucket_data['tokens'] -= 1
            allowed = True
        else:
            allowed = False
        
        # Update cache
        cache.set(cache_key, bucket_data, self.window * 2)
        
        info = {
            'remaining': int(bucket_data['tokens']),
            'reset_time': now + (1 - bucket_data['tokens']) / self.refill_rate if not allowed else None,
            'strategy': self.name
        }
        
        return allowed, info


class SlidingWindowStrategy(RateLimitStrategy):
    """Sliding window rate limiting strategy."""
    
    def __init__(self, limit: int, window: int, name: str = "sliding_window"):
        super().__init__(limit, window, name)
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict]:
        """Sliding window algorithm implementation."""
        cache_key = f"rate_limit:sliding_window:{identifier}"
        
        now = time.time()
        window_start = now - self.window
        
        # Get existing requests
        requests = cache.get(cache_key, [])
        
        # Remove old requests outside the window
        requests = [req_time for req_time in requests if req_time > window_start]
        
        # Check if under limit
        if len(requests) < self.limit:
            requests.append(now)
            allowed = True
        else:
            allowed = False
        
        # Update cache
        cache.set(cache_key, requests, self.window + 60)
        
        # Calculate reset time (when oldest request expires)
        reset_time = None
        if requests and len(requests) >= self.limit:
            reset_time = requests[0] + self.window
        
        info = {
            'remaining': max(0, self.limit - len(requests)),
            'reset_time': reset_time,
            'strategy': self.name,
            'current_count': len(requests)
        }
        
        return allowed, info


class AdaptiveStrategy(RateLimitStrategy):
    """Adaptive rate limiting that adjusts based on system load."""
    
    def __init__(self, base_limit: int, window: int, name: str = "adaptive"):
        super().__init__(base_limit, window, name)
        self.base_limit = base_limit
    
    def is_allowed(self, identifier: str) -> Tuple[bool, Dict]:
        """Adaptive rate limiting with system load consideration."""
        # Get current system load factor
        load_factor = self._get_system_load_factor()
        
        # Adjust limit based on load (higher load = lower limits)
        adjusted_limit = max(1, int(self.base_limit * (2 - load_factor)))
        
        # Use sliding window with adjusted limit
        strategy = SlidingWindowStrategy(adjusted_limit, self.window, f"{self.name}_adjusted")
        allowed, info = strategy.is_allowed(identifier)
        
        info.update({
            'base_limit': self.base_limit,
            'adjusted_limit': adjusted_limit,
            'load_factor': load_factor,
            'strategy': self.name
        })
        
        return allowed, info
    
    def _get_system_load_factor(self) -> float:
        """Calculate system load factor (1.0 = normal, 2.0 = high load)."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_factor = min(2.0, cpu_percent / 50.0)  # 50% CPU = 1.0 factor
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_factor = min(2.0, memory.percent / 50.0)  # 50% memory = 1.0 factor
            
            # Active sessions (from cache/database)
            active_sessions = cache.get('system:active_sessions', 0)
            session_factor = min(2.0, active_sessions / 100.0)  # 100 sessions = 1.0 factor
            
            # Combined load factor (weighted average)
            load_factor = (cpu_factor * 0.4 + memory_factor * 0.4 + session_factor * 0.2)
            
            return max(0.1, min(2.0, load_factor))
            
        except Exception as e:
            logger.warning(f"Failed to calculate system load: {e}")
            return 1.0  # Default to normal load


class HierarchicalRateLimiter:
    """Multi-level rate limiter with different strategies per endpoint/user type."""
    
    def __init__(self):
        self.strategies = self._load_strategies()
        self.user_type_limits = {
            'admin': {'multiplier': 10.0, 'priority': 'high'},
            'analyst': {'multiplier': 3.0, 'priority': 'medium'},
            'viewer': {'multiplier': 1.0, 'priority': 'low'},
        }
    
    def _load_strategies(self) -> Dict[str, RateLimitStrategy]:
        """Load rate limiting strategies from configuration."""
        config = getattr(settings, 'RATE_LIMITING', {})
        
        strategies = {
            # Global limits
            'global': TokenBucketStrategy(
                limit=int(config.get('GLOBAL_RATE', '1000')),
                window=3600,  # 1 hour
                name='global'
            ),
            
            # Authentication endpoints
            'auth_login': SlidingWindowStrategy(
                limit=int(config.get('LOGIN_RATE', '10').split('/')[0]),
                window=self._parse_window(config.get('LOGIN_RATE', '10/min')),
                name='auth_login'
            ),
            
            'auth_register': SlidingWindowStrategy(
                limit=5,  # Strict limit for registration
                window=3600,  # 1 hour
                name='auth_register'
            ),
            
            # Query endpoints
            'query_generate': AdaptiveStrategy(
                base_limit=int(config.get('QUERY_GENERATION_RATE', '30').split('/')[0]),
                window=self._parse_window(config.get('QUERY_GENERATION_RATE', '30/min')),
                name='query_generate'
            ),
            
            'query_execute': TokenBucketStrategy(
                limit=int(config.get('QUERY_EXECUTION_RATE', '100').split('/')[0]),
                window=self._parse_window(config.get('QUERY_EXECUTION_RATE', '100/min')),
                name='query_execute'
            ),
            
            # Data export
            'data_export': SlidingWindowStrategy(
                limit=int(config.get('DATA_EXPORT_RATE', '20').split('/')[0]),
                window=self._parse_window(config.get('DATA_EXPORT_RATE', '20/min')),
                name='data_export'
            ),
            
            # Administrative actions
            'admin_actions': SlidingWindowStrategy(
                limit=50,
                window=3600,  # 1 hour
                name='admin_actions'
            ),
            
            # Default for other endpoints
            'default': SlidingWindowStrategy(
                limit=int(config.get('DEFAULT_RATE', '60').split('/')[0]),
                window=self._parse_window(config.get('DEFAULT_RATE', '60/min')),
                name='default'
            ),
        }
        
        return strategies
    
    def _parse_window(self, rate_string: str) -> int:
        """Parse rate string like '60/min' to window in seconds."""
        if '/' not in rate_string:
            return 60  # Default to 1 minute
        
        _, period = rate_string.split('/')
        periods = {
            'sec': 1,
            'min': 60,
            'hour': 3600,
            'day': 86400
        }
        
        return periods.get(period, 60)
    
    def check_rate_limit(self, request, endpoint_type: str = 'default') -> Tuple[bool, Dict]:
        """Check rate limits for a request."""
        try:
            # Get user identifier
            user_id = self._get_user_identifier(request)
            ip_address = get_client_ip(request)
            
            # Check multiple levels
            checks = []
            
            # 1. Global rate limit (by IP)
            global_allowed, global_info = self.strategies['global'].is_allowed(f"global:{ip_address}")
            checks.append(('global', global_allowed, global_info))
            
            # 2. User-specific rate limit
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_strategy = self._get_user_strategy(request.user, endpoint_type)
                user_allowed, user_info = user_strategy.is_allowed(f"user:{user_id}")
                checks.append(('user', user_allowed, user_info))
            
            # 3. Endpoint-specific rate limit
            endpoint_strategy = self.strategies.get(endpoint_type, self.strategies['default'])
            endpoint_allowed, endpoint_info = endpoint_strategy.is_allowed(f"endpoint:{endpoint_type}:{user_id}")
            checks.append(('endpoint', endpoint_allowed, endpoint_info))
            
            # 4. IP-based rate limit (for unauthenticated requests)
            if not (hasattr(request, 'user') and request.user.is_authenticated):
                ip_strategy = SlidingWindowStrategy(limit=20, window=300, name='ip_limit')  # 20 per 5 min
                ip_allowed, ip_info = ip_strategy.is_allowed(f"ip:{ip_address}")
                checks.append(('ip', ip_allowed, ip_info))
            
            # Determine overall result (all must pass)
            overall_allowed = all(allowed for _, allowed, _ in checks)
            
            # Find the most restrictive limit for response headers
            most_restrictive = min(checks, key=lambda x: x[2].get('remaining', float('inf')))
            
            result_info = {
                'allowed': overall_allowed,
                'checks': {name: {'allowed': allowed, **info} for name, allowed, info in checks},
                'most_restrictive': most_restrictive[0],
                'limit_info': most_restrictive[2],
                'user_id': user_id,
                'ip_address': ip_address,
                'endpoint_type': endpoint_type
            }
            
            return overall_allowed, result_info
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open for availability
            return True, {'error': str(e), 'allowed': True}
    
    def _get_user_identifier(self, request) -> str:
        """Get unique identifier for the user."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user_{request.user.id}"
        else:
            return f"anon_{get_client_ip(request)}"
    
    def _get_user_strategy(self, user, endpoint_type: str) -> RateLimitStrategy:
        """Get rate limiting strategy adjusted for user type."""
        base_strategy = self.strategies.get(endpoint_type, self.strategies['default'])
        user_config = self.user_type_limits.get(user.role, self.user_type_limits['viewer'])
        
        # Create adjusted strategy
        adjusted_limit = int(base_strategy.limit * user_config['multiplier'])
        
        if isinstance(base_strategy, TokenBucketStrategy):
            return TokenBucketStrategy(
                limit=adjusted_limit,
                window=base_strategy.window,
                name=f"{base_strategy.name}_user_{user.role}"
            )
        elif isinstance(base_strategy, AdaptiveStrategy):
            return AdaptiveStrategy(
                base_limit=adjusted_limit,
                window=base_strategy.window,
                name=f"{base_strategy.name}_user_{user.role}"
            )
        else:  # SlidingWindowStrategy
            return SlidingWindowStrategy(
                limit=adjusted_limit,
                window=base_strategy.window,
                name=f"{base_strategy.name}_user_{user.role}"
            )


class AdvancedRateLimitMiddleware:
    """Enhanced rate limiting middleware with multiple strategies and detailed logging."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.limiter = HierarchicalRateLimiter()
        self.endpoint_map = self._build_endpoint_map()
    
    def __call__(self, request):
        # Skip rate limiting for certain paths
        skip_paths = ['/health/', '/static/', '/media/', '/admin/']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Determine endpoint type
        endpoint_type = self._get_endpoint_type(request.path, request.method)
        
        # Check rate limits
        allowed, info = self.limiter.check_rate_limit(request, endpoint_type)
        
        if not allowed:
            # Log rate limit violation
            self._log_rate_limit_violation(request, info)
            
            # Create response with rate limit headers
            response = JsonResponse({
                'error': 'Rate limit exceeded',
                'message': f'Too many requests for {endpoint_type}',
                'retry_after': self._calculate_retry_after(info),
                'limit_info': {
                    'type': info.get('most_restrictive'),
                    'remaining': info['limit_info'].get('remaining', 0),
                    'reset_time': info['limit_info'].get('reset_time')
                }
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Add rate limit headers
            self._add_rate_limit_headers(response, info)
            return response
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers to successful responses
        self._add_rate_limit_headers(response, info)
        
        # Log successful rate-limited request (debug level)
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.debug(f"Rate limit check passed for user {request.user.username} on {endpoint_type}")
        
        return response
    
    def _build_endpoint_map(self) -> Dict[str, str]:
        """Build mapping from URL patterns to endpoint types."""
        return {
            '/api/v1/auth/login/': 'auth_login',
            '/api/v1/auth/register/': 'auth_register',
            '/api/v1/queries/': 'query_generate',
            '/api/v1/queries/execute/': 'query_execute',
            '/api/v1/data/export/': 'data_export',
            '/api/v1/auth/users/': 'admin_actions',
            '/api/v1/system/': 'admin_actions',
        }
    
    def _get_endpoint_type(self, path: str, method: str) -> str:
        """Determine the endpoint type for rate limiting."""
        # Check exact matches first
        for pattern, endpoint_type in self.endpoint_map.items():
            if path.startswith(pattern):
                return endpoint_type
        
        # Check by method for generic patterns
        if method == 'POST' and '/execute' in path:
            return 'query_execute'
        elif method == 'POST' and '/queries' in path:
            return 'query_generate'
        elif '/export' in path:
            return 'data_export'
        elif '/admin' in path or '/users' in path:
            return 'admin_actions'
        
        return 'default'
    
    def _log_rate_limit_violation(self, request, info: Dict):
        """Log rate limit violations for security monitoring."""
        user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
        
        log_audit_event(
            user=user,
            action='security_event',
            severity='warning',
            description='Rate limit exceeded',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            endpoint=request.path,
            metadata={
                'method': request.method,
                'endpoint_type': info.get('endpoint_type'),
                'most_restrictive': info.get('most_restrictive'),
                'limit_checks': info.get('checks', {}),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
    
    def _add_rate_limit_headers(self, response, info: Dict):
        """Add rate limit headers to response."""
        if 'limit_info' in info:
            limit_info = info['limit_info']
            
            response['X-RateLimit-Limit'] = str(limit_info.get('limit', 'unknown'))
            response['X-RateLimit-Remaining'] = str(limit_info.get('remaining', 0))
            
            if limit_info.get('reset_time'):
                if isinstance(limit_info['reset_time'], (int, float)):
                    response['X-RateLimit-Reset'] = str(int(limit_info['reset_time']))
                else:
                    response['X-RateLimit-Reset'] = str(int(limit_info['reset_time'].timestamp()))
            
            response['X-RateLimit-Strategy'] = limit_info.get('strategy', 'unknown')
    
    def _calculate_retry_after(self, info: Dict) -> int:
        """Calculate retry-after header value in seconds."""
        if 'limit_info' in info and 'reset_time' in info['limit_info']:
            reset_time = info['limit_info']['reset_time']
            if reset_time:
                if isinstance(reset_time, (int, float)):
                    return max(1, int(reset_time - time.time()))
                else:
                    return max(1, int((reset_time.timestamp() - time.time())))
        
        return 60  # Default to 1 minute


class DynamicRateLimitManager:
    """Manages dynamic rate limit adjustments based on system conditions."""
    
    def __init__(self):
        self.base_limits = self._load_base_limits()
        self.adjustment_factors = {}
    
    def adjust_limits_for_conditions(self, conditions: Dict[str, float]):
        """Adjust rate limits based on system conditions."""
        # Conditions might include: cpu_usage, memory_usage, error_rate, threat_level
        
        adjustment = 1.0
        
        # CPU-based adjustment
        cpu_usage = conditions.get('cpu_usage', 0)
        if cpu_usage > 80:
            adjustment *= 0.5  # Halve limits if CPU high
        elif cpu_usage > 60:
            adjustment *= 0.7
        
        # Memory-based adjustment
        memory_usage = conditions.get('memory_usage', 0)
        if memory_usage > 85:
            adjustment *= 0.6
        elif memory_usage > 70:
            adjustment *= 0.8
        
        # Threat-level adjustment
        threat_level = conditions.get('threat_level', 'low')
        if threat_level == 'high':
            adjustment *= 0.3  # Very restrictive
        elif threat_level == 'medium':
            adjustment *= 0.6
        
        # Error rate adjustment
        error_rate = conditions.get('error_rate', 0)
        if error_rate > 10:  # 10% error rate
            adjustment *= 0.4
        elif error_rate > 5:
            adjustment *= 0.7
        
        # Update adjustment factors
        self.adjustment_factors['system_load'] = adjustment
        
        # Apply adjustments to cache
        cache.set('rate_limit_adjustment_factor', adjustment, 300)  # 5 minutes
        
        logger.info(f"Dynamic rate limit adjustment: {adjustment:.2f} based on conditions: {conditions}")
    
    def _load_base_limits(self) -> Dict:
        """Load base rate limits from configuration."""
        return getattr(settings, 'RATE_LIMITING', {})
    
    def get_effective_limit(self, endpoint_type: str, base_limit: int) -> int:
        """Get effective limit after applying dynamic adjustments."""
        adjustment = cache.get('rate_limit_adjustment_factor', 1.0)
        return max(1, int(base_limit * adjustment))
"""
Advanced Session Management and Security Policies
Provides comprehensive session control, security enforcement, and monitoring
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.contrib.gis.geoip2 import GeoIP2
from user_agents import parse as parse_user_agent
import hashlib
import uuid

from .models import UserSession, AuditLog, SecurityPolicy

User = get_user_model()
logger = logging.getLogger(__name__)


class SessionSecurityLevel:
    """Session security level classifications"""
    LOW = 'low'
    MEDIUM = 'medium' 
    HIGH = 'high'
    CRITICAL = 'critical'


class SessionManager:
    """Advanced session management with security policies"""
    
    def __init__(self):
        self.geo = self._init_geoip()
        
    def _init_geoip(self):
        """Initialize GeoIP2 if configured"""
        try:
            return GeoIP2()
        except Exception as e:
            logger.warning(f"GeoIP2 not available: {e}")
            return None
    
    def create_session(self, user, request, token_data: Dict) -> UserSession:
        """Create new session with comprehensive security analysis"""
        
        # Extract session information
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        parsed_ua = parse_user_agent(user_agent)
        
        # Analyze session security
        security_analysis = self._analyze_session_security(
            user, ip_address, user_agent, parsed_ua
        )
        
        # Create session record
        session = UserSession.objects.create(
            user=user,
            session_id=token_data.get('jti', str(uuid.uuid4())),
            ip_address=ip_address,
            user_agent=user_agent,
            browser=parsed_ua.browser.family,
            os=parsed_ua.os.family,
            device=parsed_ua.device.family,
            location_country=security_analysis.get('country'),
            location_city=security_analysis.get('city'),
            security_level=security_analysis.get('security_level'),
            risk_score=security_analysis.get('risk_score', 0),
            is_suspicious=security_analysis.get('is_suspicious', False),
            session_data=json.dumps({
                'login_method': security_analysis.get('login_method', 'password'),
                'security_flags': security_analysis.get('security_flags', []),
                'browser_fingerprint': self._generate_fingerprint(request),
            }),
            expires_at=timezone.now() + timedelta(
                hours=getattr(settings, 'JWT_EXPIRATION_HOURS', 24)
            )
        )
        
        # Log session creation
        self._audit_session_event(
            user, 'session_created', session, 
            {'security_analysis': security_analysis}
        )
        
        # Apply security policies
        self._apply_session_policies(session, security_analysis)
        
        return session
    
    def update_session_activity(self, session: UserSession, request) -> None:
        """Update session with new activity"""
        
        current_ip = self._get_client_ip(request)
        
        # Check for IP changes
        if session.ip_address != current_ip:
            self._handle_ip_change(session, current_ip, request)
        
        # Update activity
        session.last_activity = timezone.now()
        session.request_count += 1
        
        # Update session data
        session_data = json.loads(session.session_data or '{}')
        session_data['last_endpoint'] = request.path
        session_data['last_activity_details'] = {
            'timestamp': timezone.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'ip': current_ip
        }
        session.session_data = json.dumps(session_data)
        
        session.save()
    
    def validate_session(self, session: UserSession, request) -> Dict[str, Any]:
        """Comprehensive session validation"""
        
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'actions_required': [],
            'risk_factors': []
        }
        
        # Check expiration
        if session.expires_at < timezone.now():
            validation_result['is_valid'] = False
            validation_result['actions_required'].append('session_expired')
        
        # Check if session is terminated
        if session.is_terminated:
            validation_result['is_valid'] = False
            validation_result['actions_required'].append('session_terminated')
        
        # Check concurrent session limits
        active_sessions = self.get_user_active_sessions(session.user)
        max_sessions = self._get_max_concurrent_sessions(session.user)
        
        if len(active_sessions) > max_sessions:
            validation_result['warnings'].append('max_concurrent_sessions_exceeded')
            validation_result['risk_factors'].append('multiple_active_sessions')
        
        # Check for suspicious activity
        if session.is_suspicious:
            validation_result['warnings'].append('suspicious_session')
            validation_result['risk_factors'].append('flagged_as_suspicious')
        
        # Check session age
        session_age = timezone.now() - session.created_at
        max_age = timedelta(hours=getattr(settings, 'MAX_SESSION_AGE_HOURS', 168))  # 1 week
        
        if session_age > max_age:
            validation_result['warnings'].append('session_too_old')
            validation_result['actions_required'].append('force_reauth')
        
        # Check inactivity
        if session.last_activity:
            inactive_time = timezone.now() - session.last_activity
            max_inactive = timedelta(hours=getattr(settings, 'MAX_INACTIVE_HOURS', 24))
            
            if inactive_time > max_inactive:
                validation_result['is_valid'] = False
                validation_result['actions_required'].append('session_inactive')
        
        # Location-based validation
        current_ip = self._get_client_ip(request)
        if current_ip != session.ip_address:
            location_risk = self._assess_location_risk(
                session.ip_address, current_ip, session.user
            )
            if location_risk > 0.7:
                validation_result['warnings'].append('high_location_risk')
                validation_result['risk_factors'].append('location_change')
        
        return validation_result
    
    def terminate_session(self, session: UserSession, reason: str, terminated_by=None) -> None:
        """Terminate session with audit trail"""
        
        session.is_terminated = True
        session.terminated_at = timezone.now()
        session.termination_reason = reason
        session.save()
        
        # Clear any cached session data
        cache.delete(f"session_{session.session_id}")
        
        # Log termination
        self._audit_session_event(
            session.user, 'session_terminated', session,
            {
                'reason': reason,
                'terminated_by': str(terminated_by) if terminated_by else 'system',
                'session_duration': str(timezone.now() - session.created_at)
            }
        )
    
    def get_user_active_sessions(self, user) -> List[UserSession]:
        """Get all active sessions for a user"""
        return UserSession.objects.filter(
            user=user,
            is_terminated=False,
            expires_at__gt=timezone.now()
        ).order_by('-last_activity')
    
    def terminate_all_user_sessions(self, user, except_session_id=None, reason="admin_action") -> int:
        """Terminate all user sessions except optionally one"""
        sessions = self.get_user_active_sessions(user)
        
        if except_session_id:
            sessions = sessions.exclude(session_id=except_session_id)
        
        terminated_count = 0
        for session in sessions:
            self.terminate_session(session, reason)
            terminated_count += 1
        
        return terminated_count
    
    def get_session_analytics(self, user=None, days=30) -> Dict[str, Any]:
        """Generate session analytics"""
        
        start_date = timezone.now() - timedelta(days=days)
        sessions_query = UserSession.objects.filter(created_at__gte=start_date)
        
        if user:
            sessions_query = sessions_query.filter(user=user)
        
        sessions = sessions_query.all()
        
        analytics = {
            'total_sessions': len(sessions),
            'active_sessions': len([s for s in sessions if not s.is_terminated]),
            'suspicious_sessions': len([s for s in sessions if s.is_suspicious]),
            'avg_session_duration': self._calculate_avg_session_duration(sessions),
            'top_locations': self._get_top_locations(sessions),
            'device_breakdown': self._get_device_breakdown(sessions),
            'security_level_distribution': self._get_security_level_distribution(sessions),
            'termination_reasons': self._get_termination_reasons(sessions),
        }
        
        return analytics
    
    def _analyze_session_security(self, user, ip_address: str, user_agent: str, parsed_ua) -> Dict[str, Any]:
        """Analyze session security and assign risk level"""
        
        analysis = {
            'security_level': SessionSecurityLevel.MEDIUM,
            'risk_score': 0.5,
            'is_suspicious': False,
            'security_flags': [],
            'country': None,
            'city': None,
            'login_method': 'password'
        }
        
        # Geographic analysis
        if self.geo and ip_address:
            try:
                location = self.geo.city(ip_address)
                analysis['country'] = location.country.iso_code
                analysis['city'] = location.city.name
                
                # Check if login from new country
                user_sessions = UserSession.objects.filter(user=user).order_by('-created_at')[:10]
                previous_countries = set(s.location_country for s in user_sessions if s.location_country)
                
                if analysis['country'] and analysis['country'] not in previous_countries:
                    analysis['security_flags'].append('new_country')
                    analysis['risk_score'] += 0.2
                    
            except Exception as e:
                logger.warning(f"GeoIP lookup failed: {e}")
        
        # User agent analysis
        if not user_agent or len(user_agent) < 10:
            analysis['security_flags'].append('suspicious_user_agent')
            analysis['risk_score'] += 0.3
        
        # Check for known bot patterns
        bot_patterns = ['bot', 'crawler', 'spider', 'scraper']
        if any(pattern in user_agent.lower() for pattern in bot_patterns):
            analysis['security_flags'].append('bot_user_agent')
            analysis['risk_score'] += 0.4
        
        # Time-based analysis
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:  # Outside normal hours
            analysis['security_flags'].append('unusual_time')
            analysis['risk_score'] += 0.1
        
        # Previous session analysis
        recent_failed_attempts = AuditLog.objects.filter(
            user=user,
            event_type='login_failed',
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_failed_attempts > 3:
            analysis['security_flags'].append('recent_failed_attempts')
            analysis['risk_score'] += 0.2
        
        # Determine security level based on risk score
        if analysis['risk_score'] >= 0.8:
            analysis['security_level'] = SessionSecurityLevel.CRITICAL
            analysis['is_suspicious'] = True
        elif analysis['risk_score'] >= 0.6:
            analysis['security_level'] = SessionSecurityLevel.HIGH
        elif analysis['risk_score'] >= 0.4:
            analysis['security_level'] = SessionSecurityLevel.MEDIUM
        else:
            analysis['security_level'] = SessionSecurityLevel.LOW
        
        return analysis
    
    def _apply_session_policies(self, session: UserSession, security_analysis: Dict) -> None:
        """Apply security policies based on session analysis"""
        
        # Get applicable policies
        policies = SecurityPolicy.objects.filter(
            is_active=True,
            user_role__in=[session.user.role, 'all']
        )
        
        for policy in policies:
            policy_config = json.loads(policy.policy_config)
            
            # Apply session duration limits
            if 'max_session_duration' in policy_config:
                max_duration = policy_config['max_session_duration']
                session.expires_at = min(
                    session.expires_at,
                    session.created_at + timedelta(minutes=max_duration)
                )
            
            # Apply IP restrictions
            if 'allowed_ips' in policy_config:
                allowed_ips = policy_config['allowed_ips']
                if session.ip_address not in allowed_ips:
                    session.is_suspicious = True
                    session.security_level = SessionSecurityLevel.HIGH
            
            # Apply time restrictions
            if 'allowed_hours' in policy_config:
                current_hour = timezone.now().hour
                allowed_hours = policy_config['allowed_hours']
                if current_hour not in allowed_hours:
                    session.is_suspicious = True
        
        session.save()
    
    def _handle_ip_change(self, session: UserSession, new_ip: str, request) -> None:
        """Handle IP address change during session"""
        
        # Log IP change
        self._audit_session_event(
            session.user, 'session_ip_changed', session,
            {
                'old_ip': session.ip_address,
                'new_ip': new_ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
        
        # Assess risk of IP change
        risk_level = self._assess_location_risk(session.ip_address, new_ip, session.user)
        
        if risk_level > 0.7:
            session.is_suspicious = True
            session.security_level = SessionSecurityLevel.HIGH
            
            # Optionally terminate session for high-risk IP changes
            if risk_level > 0.9:
                self.terminate_session(session, 'high_risk_ip_change')
                return
        
        # Update session with new IP
        session.ip_address = new_ip
        session.save()
    
    def _assess_location_risk(self, old_ip: str, new_ip: str, user) -> float:
        """Assess risk level of location change"""
        if not self.geo:
            return 0.5  # Default medium risk if no geo data
        
        try:
            old_location = self.geo.city(old_ip)
            new_location = self.geo.city(new_ip)
            
            # Same country = low risk
            if old_location.country.iso_code == new_location.country.iso_code:
                return 0.2
            
            # Different continent = high risk
            old_continent = old_location.continent.code
            new_continent = new_location.continent.code
            
            if old_continent != new_continent:
                return 0.9
            
            # Different country, same continent = medium risk
            return 0.6
            
        except Exception:
            return 0.5  # Default if geo lookup fails
    
    def _get_max_concurrent_sessions(self, user) -> int:
        """Get maximum concurrent sessions allowed for user"""
        
        # Check if user has specific limit
        policies = SecurityPolicy.objects.filter(
            is_active=True,
            user_role__in=[user.role, 'all']
        )
        
        for policy in policies:
            config = json.loads(policy.policy_config)
            if 'max_concurrent_sessions' in config:
                return config['max_concurrent_sessions']
        
        # Default limits based on role
        role_limits = {
            'admin': 5,
            'analyst': 3,
            'viewer': 2
        }
        
        return role_limits.get(user.role, 2)
    
    def _generate_fingerprint(self, request) -> str:
        """Generate browser fingerprint"""
        fingerprint_data = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
        }
        
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]
    
    def _audit_session_event(self, user, event_type: str, session: UserSession, metadata: Dict = None):
        """Log session-related audit event"""
        AuditLog.objects.create(
            user=user,
            event_type=event_type,
            resource_type='session',
            resource_id=session.session_id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            metadata=json.dumps(metadata or {}),
            timestamp=timezone.now()
        )
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
    
    def _calculate_avg_session_duration(self, sessions) -> str:
        """Calculate average session duration"""
        active_sessions = [s for s in sessions if s.last_activity]
        if not active_sessions:
            return "N/A"
        
        total_duration = sum(
            (s.last_activity - s.created_at).total_seconds() 
            for s in active_sessions
        )
        
        avg_seconds = total_duration / len(active_sessions)
        return str(timedelta(seconds=int(avg_seconds)))
    
    def _get_top_locations(self, sessions) -> List[Dict]:
        """Get top session locations"""
        location_counts = {}
        for session in sessions:
            if session.location_country:
                key = f"{session.location_city or 'Unknown'}, {session.location_country}"
                location_counts[key] = location_counts.get(key, 0) + 1
        
        return [
            {'location': location, 'count': count}
            for location, count in sorted(
                location_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
        ]
    
    def _get_device_breakdown(self, sessions) -> Dict[str, int]:
        """Get device type breakdown"""
        device_counts = {}
        for session in sessions:
            device = session.device or 'Unknown'
            device_counts[device] = device_counts.get(device, 0) + 1
        return device_counts
    
    def _get_security_level_distribution(self, sessions) -> Dict[str, int]:
        """Get security level distribution"""
        level_counts = {}
        for session in sessions:
            level = session.security_level or 'unknown'
            level_counts[level] = level_counts.get(level, 0) + 1
        return level_counts
    
    def _get_termination_reasons(self, sessions) -> Dict[str, int]:
        """Get session termination reasons"""
        reason_counts = {}
        terminated_sessions = [s for s in sessions if s.is_terminated and s.termination_reason]
        
        for session in terminated_sessions:
            reason = session.termination_reason
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return reason_counts
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from typing import Dict, List, Tuple, Optional
import re
import json
import hashlib
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from .utils import log_audit_event, get_client_ip
import ipaddress

logger = logging.getLogger(__name__)


class ThreatDetectionMiddleware:
    """Advanced threat detection and prevention middleware."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.blocked_ips = set()
        self.trusted_ips = self._load_trusted_ips()
        self.attack_signatures = self._load_attack_signatures()
        self.honeypot_endpoints = {'/wp-admin/', '/admin.php', '/.env', '/config.php'}
    
    def __call__(self, request):
        # Skip for trusted IPs
        client_ip = get_client_ip(request)
        if self._is_trusted_ip(client_ip):
            return self.get_response(request)
        
        # Check if IP is blocked
        if self._is_blocked_ip(client_ip):
            return self._create_blocked_response(client_ip)
        
        # Analyze request for threats
        threat_score, detected_threats = self._analyze_request_threats(request)
        
        # Handle high-threat requests
        if threat_score >= 80:
            return self._handle_high_threat_request(request, threat_score, detected_threats)
        elif threat_score >= 50:
            self._handle_medium_threat_request(request, threat_score, detected_threats)
        
        # Process request normally
        response = self.get_response(request)
        
        # Analyze response for information leakage
        self._analyze_response_security(request, response)
        
        return response
    
    def _load_suspicious_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load patterns for detecting suspicious requests."""
        return {
            'sql_injection': [
                re.compile(r"(\b(SELECT|UNION|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)", re.IGNORECASE),
                re.compile(r"(\b(OR|AND)\s+\d+\s*=\s*\d+)", re.IGNORECASE),
                re.compile(r"('|\")(\s*;|\s*--|\s*/\*)", re.IGNORECASE),
                re.compile(r"(\bhex\(|\bchar\(|\bascii\()", re.IGNORECASE),
            ],
            'xss': [
                re.compile(r"<script[^>]*>", re.IGNORECASE),
                re.compile(r"javascript:", re.IGNORECASE),
                re.compile(r"on\w+\s*=", re.IGNORECASE),
                re.compile(r"<iframe[^>]*>", re.IGNORECASE),
            ],
            'path_traversal': [
                re.compile(r"\.\.[\\/]", re.IGNORECASE),
                re.compile(r"[\\/]etc[\\/]passwd", re.IGNORECASE),
                re.compile(r"[\\/]proc[\\/]", re.IGNORECASE),
                re.compile(r"[\\/]var[\\/]log", re.IGNORECASE),
            ],
            'command_injection': [
                re.compile(r"[;&|`$]", re.IGNORECASE),
                re.compile(r"\b(cat|ls|pwd|whoami|id|uname)\b", re.IGNORECASE),
                re.compile(r"(\|\s*\w+)", re.IGNORECASE),
            ],
            'nosql_injection': [
                re.compile(r"\$where", re.IGNORECASE),
                re.compile(r"\$ne\s*:", re.IGNORECASE),
                re.compile(r"\$regex\s*:", re.IGNORECASE),
                re.compile(r"\$gt\s*:", re.IGNORECASE),
            ]
        }
    
    def _load_trusted_ips(self) -> List[ipaddress.IPv4Network]:
        """Load trusted IP ranges."""
        trusted_ranges = getattr(settings, 'TRUSTED_IP_RANGES', [
            '127.0.0.0/8',    # Localhost
            '10.0.0.0/8',     # Private class A
            '172.16.0.0/12',  # Private class B
            '192.168.0.0/16', # Private class C
        ])
        
        networks = []
        for range_str in trusted_ranges:
            try:
                networks.append(ipaddress.IPv4Network(range_str, strict=False))
            except ValueError as e:
                logger.warning(f"Invalid trusted IP range: {range_str}, error: {e}")
        
        return networks
    
    def _load_attack_signatures(self) -> Dict[str, Dict]:
        """Load attack signatures for pattern matching."""
        return {
            'brute_force': {
                'failed_attempts': 5,
                'time_window': 300,  # 5 minutes
                'block_duration': 3600,  # 1 hour
            },
            'credential_stuffing': {
                'unique_usernames': 10,
                'time_window': 600,  # 10 minutes
                'block_duration': 7200,  # 2 hours
            },
            'api_abuse': {
                'requests_per_minute': 200,
                'block_duration': 1800,  # 30 minutes
            },
            'scanner_activity': {
                'unique_endpoints': 20,
                'time_window': 300,  # 5 minutes
                'block_duration': 3600,  # 1 hour
            }
        }
    
    def _is_trusted_ip(self, ip_address: str) -> bool:
        """Check if IP is in trusted ranges."""
        try:
            ip = ipaddress.IPv4Address(ip_address)
            return any(ip in network for network in self.trusted_ips)
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    def _is_blocked_ip(self, ip_address: str) -> bool:
        """Check if IP is currently blocked."""
        blocked_until = cache.get(f"blocked_ip:{ip_address}")
        if blocked_until and timezone.now() < blocked_until:
            return True
        
        # Clean up expired blocks
        if blocked_until and timezone.now() >= blocked_until:
            cache.delete(f"blocked_ip:{ip_address}")
        
        return False
    
    def _analyze_request_threats(self, request) -> Tuple[int, List[str]]:
        """Analyze request for various threat indicators."""
        threat_score = 0
        detected_threats = []
        
        # Check honeypot endpoints
        if any(endpoint in request.path for endpoint in self.honeypot_endpoints):
            threat_score += 100
            detected_threats.append('honeypot_access')
            
            log_audit_event(
                user=None,
                action='security_event',
                severity='critical',
                description=f'Honeypot endpoint accessed: {request.path}',
                ip_address=get_client_ip(request),
                endpoint=request.path,
                metadata={
                    'threat_type': 'honeypot_access',
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')
                }
            )
        
        # Analyze URL for suspicious patterns
        url_score, url_threats = self._analyze_url_patterns(request.path)
        threat_score += url_score
        detected_threats.extend(url_threats)
        
        # Analyze request headers
        header_score, header_threats = self._analyze_request_headers(request)
        threat_score += header_score
        detected_threats.extend(header_threats)
        
        # Analyze request body
        if hasattr(request, 'body') and request.body:
            body_score, body_threats = self._analyze_request_body(request.body)
            threat_score += body_score
            detected_threats.extend(body_threats)
        
        # Check for attack patterns
        pattern_score, pattern_threats = self._check_attack_patterns(request)
        threat_score += pattern_score
        detected_threats.extend(pattern_threats)
        
        # Behavioral analysis
        behavior_score, behavior_threats = self._analyze_behavior_patterns(request)
        threat_score += behavior_score
        detected_threats.extend(behavior_threats)
        
        return min(threat_score, 100), detected_threats
    
    def _analyze_url_patterns(self, url: str) -> Tuple[int, List[str]]:
        """Analyze URL for suspicious patterns."""
        score = 0
        threats = []
        
        for threat_type, patterns in self.suspicious_patterns.items():
            for pattern in patterns:
                if pattern.search(url):
                    score += 20
                    threats.append(f'url_{threat_type}')
                    break  # Only count each threat type once per URL
        
        # Check for unusual URL characteristics
        if len(url) > 500:
            score += 10
            threats.append('url_length_suspicious')
        
        # Check for encoded characters that might be obfuscation
        if '%' in url and url.count('%') > 10:
            score += 15
            threats.append('url_excessive_encoding')
        
        return score, threats
    
    def _analyze_request_headers(self, request) -> Tuple[int, List[str]]:
        """Analyze request headers for suspicious indicators."""
        score = 0
        threats = []
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Missing or suspicious User-Agent
        if not user_agent:
            score += 15
            threats.append('missing_user_agent')
        elif len(user_agent) < 10:
            score += 10
            threats.append('suspicious_user_agent')
        elif any(scanner in user_agent.lower() for scanner in ['nmap', 'sqlmap', 'burp', 'nikto']):
            score += 50
            threats.append('scanner_user_agent')
        
        # Suspicious headers
        suspicious_headers = [
            'X-Forwarded-For',  # If not from trusted proxy
            'X-Real-IP',
            'X-Originating-IP',
        ]
        
        forwarded_ips = []
        for header in suspicious_headers:
            if header in request.META:
                forwarded_ips.extend(request.META[header].split(','))
        
        # Check for header injection attempts
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                for threat_type, patterns in self.suspicious_patterns.items():
                    for pattern in patterns:
                        if pattern.search(value):
                            score += 15
                            threats.append(f'header_{threat_type}')
                            break
        
        return score, threats
    
    def _analyze_request_body(self, body: bytes) -> Tuple[int, List[str]]:
        """Analyze request body for suspicious content."""
        score = 0
        threats = []
        
        try:
            # Convert to string for analysis
            if isinstance(body, bytes):
                body_str = body.decode('utf-8', errors='ignore')
            else:
                body_str = str(body)
            
            # Check for injection patterns
            for threat_type, patterns in self.suspicious_patterns.items():
                for pattern in patterns:
                    if pattern.search(body_str):
                        score += 25
                        threats.append(f'body_{threat_type}')
                        break
            
            # Check for large payloads (potential DoS)
            if len(body) > 10 * 1024 * 1024:  # 10MB
                score += 20
                threats.append('large_payload')
            
            # Check for JSON parsing attempts with malicious content
            if body_str.strip().startswith('{'):
                try:
                    data = json.loads(body_str)
                    if self._contains_suspicious_json(data):
                        score += 20
                        threats.append('suspicious_json_content')
                except json.JSONDecodeError:
                    pass
            
        except UnicodeDecodeError:
            score += 10
            threats.append('non_utf8_body')
        
        return score, threats
    
    def _contains_suspicious_json(self, data) -> bool:
        """Check JSON data for suspicious content."""
        if isinstance(data, dict):
            # Check for NoSQL injection patterns
            for key, value in data.items():
                if key.startswith('$') or (isinstance(value, str) and any(
                    pattern.search(value) for patterns in self.suspicious_patterns.values() 
                    for pattern in patterns
                )):
                    return True
                if isinstance(value, (dict, list)):
                    if self._contains_suspicious_json(value):
                        return True
        elif isinstance(data, list):
            for item in data:
                if self._contains_suspicious_json(item):
                    return True
        
        return False
    
    def _check_attack_patterns(self, request) -> Tuple[int, List[str]]:
        """Check for specific attack patterns."""
        score = 0
        threats = []
        client_ip = get_client_ip(request)
        
        # Check for brute force attempts
        if self._detect_brute_force(request, client_ip):
            score += 40
            threats.append('brute_force_detected')
        
        # Check for credential stuffing
        if self._detect_credential_stuffing(request, client_ip):
            score += 35
            threats.append('credential_stuffing')
        
        # Check for API abuse
        if self._detect_api_abuse(request, client_ip):
            score += 30
            threats.append('api_abuse')
        
        # Check for scanner activity
        if self._detect_scanner_activity(request, client_ip):
            score += 45
            threats.append('scanner_activity')
        
        return score, threats
    
    def _analyze_behavior_patterns(self, request) -> Tuple[int, List[str]]:
        """Analyze behavioral patterns for anomalies."""
        score = 0
        threats = []
        client_ip = get_client_ip(request)
        
        # Check request frequency
        request_count = self._get_recent_request_count(client_ip, 60)  # Last minute
        if request_count > 60:  # More than 1 request per second
            score += 20
            threats.append('high_frequency_requests')
        
        # Check for unusual access patterns
        if self._detect_unusual_access_pattern(request, client_ip):
            score += 25
            threats.append('unusual_access_pattern')
        
        # Check for time-based anomalies
        if self._detect_time_based_anomaly(request, client_ip):
            score += 15
            threats.append('time_based_anomaly')
        
        return score, threats
    
    def _detect_brute_force(self, request, client_ip: str) -> bool:
        """Detect brute force login attempts."""
        if 'login' not in request.path.lower():
            return False
        
        cache_key = f"failed_logins:{client_ip}"
        failed_attempts = cache.get(cache_key, 0)
        
        signature = self.attack_signatures['brute_force']
        return failed_attempts >= signature['failed_attempts']
    
    def _detect_credential_stuffing(self, request, client_ip: str) -> bool:
        """Detect credential stuffing attacks."""
        if 'login' not in request.path.lower():
            return False
        
        cache_key = f"login_usernames:{client_ip}"
        usernames = cache.get(cache_key, set())
        
        signature = self.attack_signatures['credential_stuffing']
        return len(usernames) >= signature['unique_usernames']
    
    def _detect_api_abuse(self, request, client_ip: str) -> bool:
        """Detect API abuse patterns."""
        cache_key = f"api_requests:{client_ip}"
        request_count = cache.get(cache_key, 0)
        
        signature = self.attack_signatures['api_abuse']
        return request_count >= signature['requests_per_minute']
    
    def _detect_scanner_activity(self, request, client_ip: str) -> bool:
        """Detect web scanner activity."""
        cache_key = f"scanned_endpoints:{client_ip}"
        endpoints = cache.get(cache_key, set())
        
        signature = self.attack_signatures['scanner_activity']
        return len(endpoints) >= signature['unique_endpoints']
    
    def _get_recent_request_count(self, client_ip: str, seconds: int) -> int:
        """Get count of recent requests from IP."""
        cache_key = f"request_count:{client_ip}:{seconds}"
        return cache.get(cache_key, 0)
    
    def _detect_unusual_access_pattern(self, request, client_ip: str) -> bool:
        """Detect unusual access patterns."""
        # Check for rapid endpoint changes
        cache_key = f"recent_endpoints:{client_ip}"
        recent_endpoints = cache.get(cache_key, [])
        
        # If accessing many different endpoints rapidly
        unique_endpoints = len(set(recent_endpoints[-20:]))  # Last 20 requests
        return unique_endpoints > 15
    
    def _detect_time_based_anomaly(self, request, client_ip: str) -> bool:
        """Detect time-based access anomalies."""
        current_hour = timezone.now().hour
        
        # Check if this is unusual time for this IP
        cache_key = f"access_hours:{client_ip}"
        access_hours = cache.get(cache_key, set())
        
        # If accessing at completely different hours than usual
        if len(access_hours) > 5 and current_hour not in access_hours:
            return True
        
        return False
    
    def _handle_high_threat_request(self, request, threat_score: int, threats: List[str]):
        """Handle high-threat requests."""
        client_ip = get_client_ip(request)
        
        # Block IP temporarily
        block_duration = self._calculate_block_duration(threat_score, threats)
        cache.set(f"blocked_ip:{client_ip}", timezone.now() + block_duration, block_duration.total_seconds())
        
        # Log critical security event
        log_audit_event(
            user=getattr(request, 'user', None),
            action='security_event',
            severity='critical',
            description=f'High threat request blocked (score: {threat_score})',
            ip_address=client_ip,
            endpoint=request.path,
            metadata={
                'threat_score': threat_score,
                'detected_threats': threats,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'block_duration_seconds': block_duration.total_seconds()
            }
        )
        
        return JsonResponse({
            'error': 'Request blocked due to security policy',
            'message': 'Your request has been identified as potentially malicious',
            'reference_id': hashlib.md5(f"{client_ip}{timezone.now()}".encode()).hexdigest()[:8]
        }, status=status.HTTP_403_FORBIDDEN)
    
    def _handle_medium_threat_request(self, request, threat_score: int, threats: List[str]):
        """Handle medium-threat requests."""
        client_ip = get_client_ip(request)
        
        # Log warning
        log_audit_event(
            user=getattr(request, 'user', None),
            action='security_event',
            severity='warning',
            description=f'Medium threat request detected (score: {threat_score})',
            ip_address=client_ip,
            endpoint=request.path,
            metadata={
                'threat_score': threat_score,
                'detected_threats': threats,
                'method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')
            }
        )
        
        # Increase monitoring for this IP
        cache.set(f"high_watch:{client_ip}", True, 3600)  # Watch for 1 hour
    
    def _calculate_block_duration(self, threat_score: int, threats: List[str]) -> timedelta:
        """Calculate block duration based on threat level."""
        base_duration = timedelta(minutes=30)
        
        if threat_score >= 90:
            multiplier = 4
        elif threat_score >= 80:
            multiplier = 2
        else:
            multiplier = 1
        
        # Increase duration for specific threat types
        if 'honeypot_access' in threats:
            multiplier *= 2
        if 'scanner_activity' in threats:
            multiplier *= 1.5
        
        return base_duration * multiplier
    
    def _create_blocked_response(self, client_ip: str):
        """Create response for blocked IPs."""
        return JsonResponse({
            'error': 'Access denied',
            'message': 'Your IP address has been temporarily blocked due to suspicious activity'
        }, status=status.HTTP_403_FORBIDDEN)
    
    def _analyze_response_security(self, request, response):
        """Analyze response for security issues."""
        # Check for information leakage in error responses
        if response.status_code >= 500:
            # Log internal errors for monitoring
            log_audit_event(
                user=getattr(request, 'user', None),
                action='security_event',
                severity='error',
                description='Internal server error occurred',
                ip_address=get_client_ip(request),
                endpoint=request.path,
                metadata={
                    'status_code': response.status_code,
                    'method': request.method
                }
            )
        
        # Add security headers if not present
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
        
        for header, value in security_headers.items():
            if header not in response:
                response[header] = value


class GeolocationSecurityMiddleware:
    """Security middleware with geolocation-based filtering."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.blocked_countries = getattr(settings, 'BLOCKED_COUNTRIES', [])
        self.high_risk_countries = getattr(settings, 'HIGH_RISK_COUNTRIES', [])
    
    def __call__(self, request):
        client_ip = get_client_ip(request)
        
        # Skip for trusted IPs
        if self._is_local_ip(client_ip):
            return self.get_response(request)
        
        # Get geolocation info
        country_code = self._get_country_code(client_ip)
        
        if country_code:
            # Block requests from blocked countries
            if country_code in self.blocked_countries:
                log_audit_event(
                    user=None,
                    action='security_event',
                    severity='warning',
                    description=f'Request blocked from country: {country_code}',
                    ip_address=client_ip,
                    endpoint=request.path,
                    metadata={'country_code': country_code, 'reason': 'blocked_country'}
                )
                
                return JsonResponse({
                    'error': 'Access denied',
                    'message': 'Requests from your location are not permitted'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Add extra monitoring for high-risk countries
            if country_code in self.high_risk_countries:
                cache.set(f"high_risk_country:{client_ip}", country_code, 3600)
                
                log_audit_event(
                    user=getattr(request, 'user', None),
                    action='security_event',
                    severity='info',
                    description=f'Request from high-risk country: {country_code}',
                    ip_address=client_ip,
                    endpoint=request.path,
                    metadata={'country_code': country_code, 'reason': 'high_risk_country'}
                )
        
        return self.get_response(request)
    
    def _is_local_ip(self, ip_address: str) -> bool:
        """Check if IP is local/private."""
        try:
            ip = ipaddress.IPv4Address(ip_address)
            return ip.is_private or ip.is_loopback
        except ipaddress.AddressValueError:
            return False
    
    def _get_country_code(self, ip_address: str) -> Optional[str]:
        """Get country code for IP address."""
        # This would typically use a geolocation service like MaxMind
        # For now, returning None (disabled)
        return None
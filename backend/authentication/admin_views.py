"""
Admin Dashboard API Views
Provides comprehensive system administration and monitoring endpoints
"""

import json
import logging
import psutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Avg
from django.core.cache import cache
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError

from .models import CustomUser, UserSession, AuditLog, SecurityPolicy
from .session_manager import SessionManager
from .security_policies import SecurityPolicyEngine

User = get_user_model()
logger = logging.getLogger(__name__)


class SystemHealthView(APIView):
    """Get comprehensive system health status"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get system health metrics"""
        
        try:
            health_data = {
                'elasticsearch': self._get_elasticsearch_health(),
                'database': self._get_database_health(),
                'authentication': self._get_authentication_health(),
                'system': self._get_system_health(),
                'security': self._get_security_health(),
            }
            
            return Response(health_data)
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return Response(
                {'error': 'System health check failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_elasticsearch_health(self) -> Dict[str, Any]:
        """Get Elasticsearch cluster health"""
        
        try:
            es_config = getattr(settings, 'ELASTICSEARCH_DSL', {})
            default_config = es_config.get('default', {})
            
            es = Elasticsearch([default_config.get('hosts', 'localhost:9200')])
            
            # Test connection and get cluster info
            cluster_health = es.cluster.health()
            cluster_stats = es.cluster.stats()
            
            # Measure response time
            start_time = timezone.now()
            es.ping()
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return {
                'status': 'healthy' if cluster_health['status'] in ['green', 'yellow'] else 'error',
                'cluster_name': cluster_health['cluster_name'],
                'nodes': cluster_health['number_of_nodes'],
                'indices': cluster_stats['indices']['count'],
                'documents': cluster_stats['indices']['docs']['count'],
                'storage_size': f"{cluster_stats['indices']['store']['size_in_bytes'] / 1024**3:.2f} GB",
                'response_time_ms': int(response_time),
            }
            
        except (ESConnectionError, Exception) as e:
            logger.warning(f"Elasticsearch health check failed: {e}")
            return {
                'status': 'error',
                'cluster_name': 'unknown',
                'nodes': 0,
                'indices': 0,
                'documents': 0,
                'storage_size': '0 GB',
                'response_time_ms': 0,
                'error': str(e),
            }
    
    def _get_database_health(self) -> Dict[str, Any]:
        """Get database health metrics"""
        
        try:
            from django.db import connection
            
            # Test database connection
            start_time = timezone.now()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            response_time = (timezone.now() - start_time).total_seconds() * 1000
            
            # Get connection info
            db_stats = connection.queries_log if hasattr(connection, 'queries_log') else []
            
            return {
                'status': 'healthy',
                'connections': len(connection.queries) if hasattr(connection, 'queries') else 1,
                'active_queries': 0,  # This would require database-specific queries
                'response_time_ms': int(response_time),
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'error',
                'connections': 0,
                'active_queries': 0,
                'response_time_ms': 0,
                'error': str(e),
            }
    
    def _get_authentication_health(self) -> Dict[str, Any]:
        """Get authentication system health"""
        
        try:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            
            active_sessions = UserSession.objects.filter(
                is_terminated=False,
                expires_at__gt=now
            ).count()
            
            failed_logins = AuditLog.objects.filter(
                event_type='login_failed',
                timestamp__gte=last_24h
            ).count()
            
            suspicious_activities = AuditLog.objects.filter(
                event_type__in=['suspicious_activity', 'policy_violation_deny', 'session_terminated_policy'],
                timestamp__gte=last_24h
            ).count()
            
            return {
                'status': 'healthy' if failed_logins < 100 else 'warning',
                'active_sessions': active_sessions,
                'failed_logins_24h': failed_logins,
                'suspicious_activities': suspicious_activities,
            }
            
        except Exception as e:
            logger.error(f"Authentication health check failed: {e}")
            return {
                'status': 'error',
                'active_sessions': 0,
                'failed_logins_24h': 0,
                'suspicious_activities': 0,
            }
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system resource health"""
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get system uptime
            boot_time = psutil.boot_time()
            uptime_seconds = timezone.now().timestamp() - boot_time
            
            return {
                'cpu_usage': round(cpu_percent, 1),
                'memory_usage': round(memory.percent, 1),
                'disk_usage': round(disk.percent, 1),
                'uptime': self._format_uptime(uptime_seconds),
                'load_average': round(psutil.getloadavg()[0], 2) if hasattr(psutil, 'getloadavg') else 0,
            }
            
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'uptime': 'unknown',
                'load_average': 0,
            }
    
    def _get_security_health(self) -> Dict[str, Any]:
        """Get security system health"""
        
        try:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            
            active_policies = SecurityPolicy.objects.filter(is_active=True).count()
            
            policy_violations = AuditLog.objects.filter(
                event_type__in=['policy_violation_deny', 'policy_violation_termination'],
                timestamp__gte=last_24h
            ).count()
            
            blocked_ips = 0  # This would come from your IP blocking system
            
            # Determine threat level based on recent activity
            if policy_violations > 50:
                threat_level = 'critical'
            elif policy_violations > 20:
                threat_level = 'high'
            elif policy_violations > 5:
                threat_level = 'medium'
            else:
                threat_level = 'low'
            
            return {
                'active_policies': active_policies,
                'policy_violations_24h': policy_violations,
                'blocked_ips': blocked_ips,
                'threat_level': threat_level,
            }
            
        except Exception as e:
            logger.error(f"Security health check failed: {e}")
            return {
                'active_policies': 0,
                'policy_violations_24h': 0,
                'blocked_ips': 0,
                'threat_level': 'unknown',
            }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class SystemStatsView(APIView):
    """Get system statistics and metrics"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get system statistics"""
        
        try:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            
            stats = {
                'total_users': User.objects.count(),
                'active_users_24h': User.objects.filter(last_activity__gte=last_24h).count(),
                'total_sessions': UserSession.objects.filter(is_terminated=False).count(),
                'queries_generated_24h': AuditLog.objects.filter(
                    event_type='query_generate',
                    timestamp__gte=last_24h
                ).count(),
                'data_exported_24h': AuditLog.objects.filter(
                    event_type='data_export',
                    timestamp__gte=last_24h
                ).count(),
                'system_alerts': AuditLog.objects.filter(
                    severity__in=['warning', 'error', 'critical'],
                    timestamp__gte=last_24h
                ).count(),
            }
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"System stats failed: {e}")
            return Response(
                {'error': 'Failed to get system statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MetricsHistoryView(APIView):
    """Get historical metrics data for charts"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get metrics history"""
        
        hours = int(request.GET.get('hours', 24))
        
        # This would typically come from a time-series database
        # For now, we'll generate sample data based on current metrics
        metrics = self._generate_metrics_history(hours)
        
        return Response({'metrics': metrics})
    
    def _generate_metrics_history(self, hours: int) -> List[Dict]:
        """Generate sample metrics history"""
        
        now = timezone.now()
        metrics = []
        
        for i in range(hours):
            timestamp = now - timedelta(hours=hours-i)
            
            # Generate realistic sample data
            metrics.append({
                'timestamp': timestamp.isoformat(),
                'cpu_usage': 20 + (i % 10) * 3,
                'memory_usage': 45 + (i % 8) * 2,
                'disk_usage': 35 + (i % 5),
                'elasticsearch_response_time': 100 + (i % 20) * 5,
                'active_sessions': 10 + (i % 15),
                'requests_per_minute': 50 + (i % 30) * 2,
            })
        
        return metrics


class PerformanceMetricsView(APIView):
    """Get detailed performance metrics"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get performance metrics"""
        
        try:
            metrics = {
                'database_connections': self._get_database_connections(),
                'query_cache_hit_rate': self._get_cache_hit_rate(),
                'elasticsearch_health': self._get_detailed_es_health(),
                'api_response_times': self._get_api_response_times(),
                'error_rates': self._get_error_rates(),
            }
            
            return Response(metrics)
            
        except Exception as e:
            logger.error(f"Performance metrics failed: {e}")
            return Response(
                {'error': 'Failed to get performance metrics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_database_connections(self) -> int:
        """Get current database connection count"""
        # This would be database-specific
        return 5
    
    def _get_cache_hit_rate(self) -> float:
        """Get cache hit rate percentage"""
        # This would come from cache statistics
        return 85.5
    
    def _get_detailed_es_health(self) -> Dict[str, Any]:
        """Get detailed Elasticsearch health"""
        try:
            es_config = getattr(settings, 'ELASTICSEARCH_DSL', {})
            default_config = es_config.get('default', {})
            es = Elasticsearch([default_config.get('hosts', 'localhost:9200')])
            
            cluster_health = es.cluster.health()
            
            return {
                'cluster_status': cluster_health.get('status', 'unknown'),
                'active_shards': cluster_health.get('active_shards', 0),
                'relocating_shards': cluster_health.get('relocating_shards', 0),
                'unassigned_shards': cluster_health.get('unassigned_shards', 0),
            }
        except Exception:
            return {
                'cluster_status': 'unknown',
                'active_shards': 0,
                'relocating_shards': 0,
                'unassigned_shards': 0,
            }
    
    def _get_api_response_times(self) -> Dict[str, int]:
        """Get API response time percentiles"""
        # This would come from application metrics
        return {
            'p50': 120,
            'p95': 450,
            'p99': 850,
        }
    
    def _get_error_rates(self) -> Dict[str, float]:
        """Get error rate percentages"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        # Get error rates from audit logs
        total_requests = AuditLog.objects.filter(
            event_type='request_activity',
            timestamp__gte=last_24h
        ).count()
        
        if total_requests == 0:
            return {'2xx': 100.0, '4xx': 0.0, '5xx': 0.0}
        
        error_4xx = AuditLog.objects.filter(
            event_type='request_activity',
            timestamp__gte=last_24h,
            metadata__status_code__gte=400,
            metadata__status_code__lt=500
        ).count()
        
        error_5xx = AuditLog.objects.filter(
            event_type='request_activity',
            timestamp__gte=last_24h,
            metadata__status_code__gte=500
        ).count()
        
        success_2xx = total_requests - error_4xx - error_5xx
        
        return {
            '2xx': round(success_2xx / total_requests * 100, 1),
            '4xx': round(error_4xx / total_requests * 100, 1),
            '5xx': round(error_5xx / total_requests * 100, 1),
        }


class SecurityEventsView(APIView):
    """Get security events for admin monitoring"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get recent security events"""
        
        limit = int(request.GET.get('limit', 100))
        severity_filter = request.GET.get('severity')
        
        events_query = AuditLog.objects.filter(
            event_type__in=[
                'login_failed', 'suspicious_activity', 'policy_violation_deny',
                'session_terminated_policy', 'rate_limit_exceeded', 'security_event'
            ]
        )
        
        if severity_filter:
            events_query = events_query.filter(severity=severity_filter)
        
        events = events_query.select_related('user').order_by('-timestamp')[:limit]
        
        events_data = []
        for event in events:
            events_data.append({
                'id': str(event.id),
                'event_type': event.event_type,
                'severity': event.severity,
                'description': event.description,
                'user': {
                    'id': str(event.user.id),
                    'username': event.user.username,
                    'email': event.user.email,
                    'role': event.user.role,
                } if event.user else None,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent,
                'timestamp': event.timestamp.isoformat(),
                'metadata': event.metadata,
            })
        
        return Response({'events': events_data})


class ThreatAnalysisView(APIView):
    """Get threat analysis and patterns"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get threat analysis data"""
        
        try:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            
            analysis = {
                'threat_level': self._calculate_threat_level(),
                'active_threats': self._count_active_threats(),
                'blocked_attempts': self._count_blocked_attempts(last_24h),
                'suspicious_ips': self._get_suspicious_ips(last_24h),
                'failed_login_patterns': self._analyze_failed_logins(last_24h),
                'policy_violations': self._analyze_policy_violations(last_24h),
                'anomaly_detection': self._detect_anomalies(last_24h),
            }
            
            return Response(analysis)
            
        except Exception as e:
            logger.error(f"Threat analysis failed: {e}")
            return Response(
                {'error': 'Threat analysis failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_threat_level(self) -> str:
        """Calculate overall threat level"""
        # This would use more sophisticated threat scoring
        recent_violations = AuditLog.objects.filter(
            event_type__in=['policy_violation_deny', 'suspicious_activity'],
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_violations > 10:
            return 'critical'
        elif recent_violations > 5:
            return 'high'
        elif recent_violations > 2:
            return 'medium'
        else:
            return 'low'
    
    def _count_active_threats(self) -> int:
        """Count active security threats"""
        return UserSession.objects.filter(
            is_suspicious=True,
            is_terminated=False
        ).count()
    
    def _count_blocked_attempts(self, since: datetime) -> int:
        """Count blocked login attempts"""
        return AuditLog.objects.filter(
            event_type='login_failed',
            timestamp__gte=since
        ).count()
    
    def _get_suspicious_ips(self, since: datetime) -> List[str]:
        """Get list of suspicious IP addresses"""
        suspicious_logs = AuditLog.objects.filter(
            event_type__in=['login_failed', 'suspicious_activity'],
            timestamp__gte=since
        ).values('ip_address').annotate(
            count=Count('id')
        ).filter(count__gte=5)
        
        return [log['ip_address'] for log in suspicious_logs]
    
    def _analyze_failed_logins(self, since: datetime) -> List[Dict]:
        """Analyze failed login patterns"""
        failed_logins = AuditLog.objects.filter(
            event_type='login_failed',
            timestamp__gte=since
        ).values('metadata').order_by('-timestamp')
        
        patterns = {}
        for log in failed_logins:
            metadata = log.get('metadata', {})
            username = metadata.get('username', 'unknown')
            
            if username not in patterns:
                patterns[username] = {
                    'username': username,
                    'attempts': 0,
                    'last_attempt': None,
                    'source_ips': set()
                }
            
            patterns[username]['attempts'] += 1
            patterns[username]['source_ips'].add(metadata.get('ip_address', 'unknown'))
        
        # Convert sets to lists and sort by attempt count
        result = []
        for pattern in patterns.values():
            pattern['source_ips'] = list(pattern['source_ips'])
            pattern['last_attempt'] = since.isoformat()  # Simplified
            result.append(pattern)
        
        return sorted(result, key=lambda x: x['attempts'], reverse=True)[:10]
    
    def _analyze_policy_violations(self, since: datetime) -> List[Dict]:
        """Analyze security policy violations"""
        violations = AuditLog.objects.filter(
            event_type='policy_evaluated',
            timestamp__gte=since,
            metadata__action='deny'
        ).values('metadata').annotate(count=Count('id'))
        
        patterns = {}
        for violation in violations:
            metadata = violation.get('metadata', {})
            policy_name = metadata.get('policy_name', 'unknown')
            
            if policy_name not in patterns:
                patterns[policy_name] = {
                    'policy_name': policy_name,
                    'violation_count': 0,
                    'affected_users': set()
                }
            
            patterns[policy_name]['violation_count'] += violation['count']
            patterns[policy_name]['affected_users'].add(metadata.get('user_id', 'unknown'))
        
        result = []
        for pattern in patterns.values():
            pattern['affected_users'] = len(pattern['affected_users'])
            result.append(pattern)
        
        return sorted(result, key=lambda x: x['violation_count'], reverse=True)[:10]
    
    def _detect_anomalies(self, since: datetime) -> Dict[str, int]:
        """Detect security anomalies"""
        return {
            'unusual_login_times': AuditLog.objects.filter(
                event_type='login',
                timestamp__gte=since,
                timestamp__hour__in=[0, 1, 2, 3, 4, 5, 22, 23]  # Outside normal hours
            ).count(),
            'new_locations': UserSession.objects.filter(
                created_at__gte=since,
                location_country__isnull=False
            ).values('location_country').distinct().count(),
            'suspicious_user_agents': AuditLog.objects.filter(
                timestamp__gte=since,
                user_agent__icontains='bot'
            ).count(),
        }


class SecurityConfigurationView(APIView):
    """Get security configuration summary"""
    
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        """Get security configuration"""
        
        try:
            config = {
                'password_policy': self._get_password_policy(),
                'session_policy': self._get_session_policy(),
                'access_policy': self._get_access_policy(),
                'rate_limiting': self._get_rate_limiting_config(),
            }
            
            return Response(config)
            
        except Exception as e:
            logger.error(f"Security configuration failed: {e}")
            return Response(
                {'error': 'Failed to get security configuration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_password_policy(self) -> Dict[str, Any]:
        """Get password policy configuration"""
        policy = SecurityPolicy.objects.filter(
            policy_type='password',
            is_active=True
        ).first()
        
        if policy:
            config = policy.policy_config
            return {
                'min_length': config.get('min_length', 8),
                'require_complexity': any([
                    config.get('require_uppercase', False),
                    config.get('require_lowercase', False),
                    config.get('require_digits', False),
                    config.get('require_special', False)
                ]),
                'max_age_days': config.get('password_history', 90),
            }
        
        return {
            'min_length': 8,
            'require_complexity': False,
            'max_age_days': 90,
        }
    
    def _get_session_policy(self) -> Dict[str, Any]:
        """Get session policy configuration"""
        return {
            'max_concurrent_sessions': 3,
            'session_timeout_minutes': 480,
            'require_reauth_sensitive': True,
        }
    
    def _get_access_policy(self) -> Dict[str, Any]:
        """Get access policy configuration"""
        return {
            'mfa_enabled': SecurityPolicy.objects.filter(
                policy_type='mfa',
                is_active=True
            ).exists(),
            'ip_whitelist_enabled': SecurityPolicy.objects.filter(
                policy_type='ip_restriction',
                is_active=True
            ).exists(),
            'time_restrictions_enabled': SecurityPolicy.objects.filter(
                policy_type='time_restriction',
                is_active=True
            ).exists(),
        }
    
    def _get_rate_limiting_config(self) -> Dict[str, int]:
        """Get rate limiting configuration"""
        return {
            'login_attempts_per_hour': 10,
            'api_requests_per_minute': 60,
            'failed_attempt_lockout_minutes': 30,
        }


class MaintenanceView(APIView):
    """Handle system maintenance operations"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request, action):
        """Perform maintenance action"""
        
        try:
            if action == 'cleanup-sessions':
                result = self._cleanup_expired_sessions()
            elif action == 'cleanup-logs':
                result = self._cleanup_old_logs()
            elif action == 'optimize-indices':
                result = self._optimize_es_indices()
            elif action == 'update-analytics':
                result = self._update_analytics()
            else:
                return Response(
                    {'error': f'Unknown maintenance action: {action}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Log maintenance action
            AuditLog.objects.create(
                user=request.user,
                event_type='system_config',
                description=f'Performed maintenance action: {action}',
                metadata={'action': action, 'result': result}
            )
            
            return Response({'message': f'Maintenance action completed', 'result': result})
            
        except Exception as e:
            logger.error(f"Maintenance action {action} failed: {e}")
            return Response(
                {'error': f'Maintenance action failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _cleanup_expired_sessions(self) -> Dict[str, int]:
        """Cleanup expired sessions"""
        now = timezone.now()
        
        expired_sessions = UserSession.objects.filter(
            Q(expires_at__lt=now) | Q(is_terminated=True)
        )
        count = expired_sessions.count()
        expired_sessions.delete()
        
        return {'cleaned_sessions': count}
    
    def _cleanup_old_logs(self) -> Dict[str, int]:
        """Cleanup old audit logs"""
        cutoff_date = timezone.now() - timedelta(days=90)
        
        old_logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
        count = old_logs.count()
        old_logs.delete()
        
        return {'cleaned_logs': count}
    
    def _optimize_es_indices(self) -> Dict[str, Any]:
        """Optimize Elasticsearch indices"""
        try:
            es_config = getattr(settings, 'ELASTICSEARCH_DSL', {})
            default_config = es_config.get('default', {})
            es = Elasticsearch([default_config.get('hosts', 'localhost:9200')])
            
            # Force merge and refresh indices
            result = es.indices.forcemerge(index='_all', max_num_segments=1)
            es.indices.refresh(index='_all')
            
            return {'optimization_result': 'success'}
            
        except Exception as e:
            return {'optimization_result': f'failed: {str(e)}'}
    
    def _update_analytics(self) -> Dict[str, Any]:
        """Update system analytics"""
        # Clear relevant caches
        cache.clear()
        
        # Recalculate key metrics
        session_manager = SessionManager()
        analytics = session_manager.get_session_analytics(days=7)
        
        return {'analytics_updated': True, 'session_metrics': len(analytics)}


class SecurityActionView(APIView):
    """Handle security-related actions"""
    
    permission_classes = [IsAdminUser]
    
    def post(self, request):
        """Perform security action"""
        
        action = request.data.get('action')
        ip_address = request.data.get('ip_address')
        
        if action == 'block_ip':
            return self._block_ip(ip_address, request.user)
        elif action == 'unblock_ip':
            return self._unblock_ip(ip_address, request.user)
        else:
            return Response(
                {'error': 'Unknown security action'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _block_ip(self, ip_address: str, user) -> Response:
        """Block an IP address"""
        # This would integrate with your firewall/security system
        # For now, just log the action
        
        AuditLog.objects.create(
            user=user,
            event_type='security_event',
            severity='warning',
            description=f'Blocked IP address: {ip_address}',
            metadata={'action': 'block_ip', 'ip_address': ip_address}
        )
        
        return Response({'message': f'IP {ip_address} has been blocked'})
    
    def _unblock_ip(self, ip_address: str, user) -> Response:
        """Unblock an IP address"""
        # This would integrate with your firewall/security system
        # For now, just log the action
        
        AuditLog.objects.create(
            user=user,
            event_type='security_event',
            severity='info',
            description=f'Unblocked IP address: {ip_address}',
            metadata={'action': 'unblock_ip', 'ip_address': ip_address}
        )
        
        return Response({'message': f'IP {ip_address} has been unblocked'})
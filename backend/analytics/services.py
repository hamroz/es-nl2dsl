from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from authentication.models import AuditLog, UserSession
from .models import AnalyticsSnapshot, CustomMetric, MetricData, Alert, AlertRule
import psutil
import logging
from django.db import connection
from django.core.cache import cache
import json

User = get_user_model()
logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for generating analytics data."""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes default cache
    
    def get_analytics_data(self, time_range: str = '7d', tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive analytics data for the specified time range.
        
        Args:
            time_range: Time range ('1h', '24h', '7d', '30d', '90d')
            tenant_id: Optional tenant ID for filtering
            
        Returns:
            Dictionary with all analytics metrics
        """
        try:
            # Calculate date range
            end_date = timezone.now()
            start_date = self._get_start_date(time_range, end_date)
            
            # Get all metrics
            return {
                'user_metrics': self._get_user_metrics(start_date, end_date, tenant_id),
                'query_metrics': self._get_query_metrics(start_date, end_date, tenant_id),
                'security_metrics': self._get_security_metrics(start_date, end_date, tenant_id),
                'system_metrics': self._get_system_metrics(start_date, end_date),
                'business_metrics': self._get_business_metrics(start_date, end_date, tenant_id),
                'time_range': time_range,
                'generated_at': end_date.isoformat(),
            }
        except Exception as e:
            logger.error(f"Analytics generation failed: {e}")
            raise
    
    def _get_start_date(self, time_range: str, end_date: datetime) -> datetime:
        """Calculate start date based on time range."""
        if time_range == '1h':
            return end_date - timedelta(hours=1)
        elif time_range == '24h':
            return end_date - timedelta(days=1)
        elif time_range == '7d':
            return end_date - timedelta(days=7)
        elif time_range == '30d':
            return end_date - timedelta(days=30)
        elif time_range == '90d':
            return end_date - timedelta(days=90)
        else:
            return end_date - timedelta(days=7)  # Default to 7 days
    
    def _get_user_metrics(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> Dict[str, Any]:
        """Get user-related metrics."""
        try:
            # Base queryset
            users_qs = User.objects.all()
            if tenant_id:
                users_qs = users_qs.filter(tenant_id=tenant_id)
            
            # Total users
            total_users = users_qs.count()
            
            # Active users in the last 24 hours
            active_24h_cutoff = timezone.now() - timedelta(hours=24)
            active_users_24h = users_qs.filter(
                last_activity__gte=active_24h_cutoff
            ).count()
            
            # New users in the last 7 days
            new_users_7d = users_qs.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # User growth rate (comparing last 7d with previous 7d)
            prev_period_start = start_date - (end_date - start_date)
            prev_new_users = users_qs.filter(
                created_at__gte=prev_period_start,
                created_at__lt=start_date
            ).count()
            
            growth_rate = 0.0
            if prev_new_users > 0:
                growth_rate = ((new_users_7d - prev_new_users) / prev_new_users) * 100
            
            # Users by role
            users_by_role = list(
                users_qs.values('role')
                .annotate(count=Count('id'))
                .order_by('role')
            )
            
            # Calculate percentages
            for role_data in users_by_role:
                role_data['percentage'] = round((role_data['count'] / total_users) * 100, 1) if total_users > 0 else 0
            
            # User activity trend
            activity_trend = self._get_user_activity_trend(start_date, end_date, tenant_id)
            
            return {
                'total_users': total_users,
                'active_users_24h': active_users_24h,
                'new_users_7d': new_users_7d,
                'user_growth_rate': round(growth_rate, 2),
                'users_by_role': users_by_role,
                'user_activity_trend': activity_trend,
            }
            
        except Exception as e:
            logger.error(f"User metrics calculation failed: {e}")
            return self._get_default_user_metrics()
    
    def _get_query_metrics(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> Dict[str, Any]:
        """Get query-related metrics."""
        try:
            # Query metrics from audit logs
            query_logs = AuditLog.objects.filter(
                action__in=['query_generate', 'query_execute'],
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if tenant_id:
                query_logs = query_logs.filter(tenant_id=tenant_id)
            
            total_queries = query_logs.count()
            
            # Queries in last 24h
            queries_24h = query_logs.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Average response time from metadata
            response_times = []
            success_count = 0
            
            for log in query_logs:
                if 'response_time_ms' in log.metadata:
                    response_times.append(log.metadata['response_time_ms'])
                
                if log.metadata.get('status_code', 500) < 400:
                    success_count += 1
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            success_rate = (success_count / total_queries) * 100 if total_queries > 0 else 100.0
            
            # Queries by method (from metadata)
            queries_by_method = []
            method_stats = {}
            
            for log in query_logs.filter(action='query_generate'):
                method = log.metadata.get('method', 'unknown')
                if method not in method_stats:
                    method_stats[method] = {'count': 0, 'total_time': 0, 'times': []}
                
                method_stats[method]['count'] += 1
                if 'response_time_ms' in log.metadata:
                    time_ms = log.metadata['response_time_ms']
                    method_stats[method]['total_time'] += time_ms
                    method_stats[method]['times'].append(time_ms)
            
            for method, stats in method_stats.items():
                avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
                queries_by_method.append({
                    'method': method,
                    'count': stats['count'],
                    'avg_time': round(avg_time, 2)
                })
            
            # Query volume trend
            volume_trend = self._get_query_volume_trend(start_date, end_date, tenant_id)
            
            return {
                'total_queries': total_queries,
                'queries_24h': queries_24h,
                'avg_response_time': round(avg_response_time, 2),
                'success_rate': round(success_rate, 2),
                'queries_by_method': queries_by_method,
                'query_volume_trend': volume_trend,
            }
            
        except Exception as e:
            logger.error(f"Query metrics calculation failed: {e}")
            return self._get_default_query_metrics()
    
    def _get_security_metrics(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> Dict[str, Any]:
        """Get security-related metrics."""
        try:
            security_logs = AuditLog.objects.filter(
                severity__in=['warning', 'error', 'critical'],
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if tenant_id:
                security_logs = security_logs.filter(tenant_id=tenant_id)
            
            # Failed logins in last 24h
            failed_logins_24h = security_logs.filter(
                action='login',
                description__icontains='failed',
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Locked accounts
            locked_accounts = User.objects.filter(is_locked_out=True).count()
            if tenant_id:
                locked_accounts = User.objects.filter(
                    is_locked_out=True,
                    tenant_id=tenant_id
                ).count()
            
            # Security events
            security_events = security_logs.filter(
                action='security_event'
            ).count()
            
            # Threat level calculation
            threat_level = self._calculate_threat_level(failed_logins_24h, locked_accounts, security_events)
            
            # Security events trend
            events_trend = self._get_security_events_trend(start_date, end_date, tenant_id)
            
            return {
                'failed_logins_24h': failed_logins_24h,
                'locked_accounts': locked_accounts,
                'security_events': security_events,
                'threat_level': threat_level,
                'security_events_trend': events_trend,
            }
            
        except Exception as e:
            logger.error(f"Security metrics calculation failed: {e}")
            return self._get_default_security_metrics()
    
    def _get_system_metrics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get system-related metrics."""
        try:
            # System uptime (simplified calculation)
            uptime_percentage = 99.9  # Would be calculated from monitoring data
            
            # CPU and memory usage
            avg_cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage_gb = memory.used / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percentage = (disk.used / disk.total) * 100
            
            # Active sessions
            active_sessions = UserSession.objects.filter(
                is_active=True,
                expires_at__gt=timezone.now()
            ).count()
            
            # Error rate from logs
            total_requests = AuditLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                action='api_access'
            ).count()
            
            error_requests = AuditLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                action='api_access',
                metadata__status_code__gte=400
            ).count()
            
            error_rate = (error_requests / total_requests) * 100 if total_requests > 0 else 0.0
            
            # Performance trend
            performance_trend = self._get_performance_trend(start_date, end_date)
            
            return {
                'uptime_percentage': uptime_percentage,
                'avg_cpu_usage': round(avg_cpu_usage, 2),
                'memory_usage_gb': round(memory_usage_gb, 2),
                'disk_usage_percentage': round(disk_usage_percentage, 2),
                'active_sessions': active_sessions,
                'error_rate': round(error_rate, 2),
                'performance_trend': performance_trend,
            }
            
        except Exception as e:
            logger.error(f"System metrics calculation failed: {e}")
            return self._get_default_system_metrics()
    
    def _get_business_metrics(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> Dict[str, Any]:
        """Get business-related metrics."""
        try:
            # This would typically query custom business tables
            # For now, providing mock data structure
            
            return {
                'tenant_count': 1,
                'workspace_count': 3,
                'data_processed_gb': 45.2,
                'export_count_24h': 12,
                'top_indices': [
                    {'index': 'logs_net', 'query_count': 150, 'data_size_gb': 12.5},
                    {'index': 'logs_cic_ids2017', 'query_count': 89, 'data_size_gb': 32.7},
                ]
            }
            
        except Exception as e:
            logger.error(f"Business metrics calculation failed: {e}")
            return self._get_default_business_metrics()
    
    def _get_user_activity_trend(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> List[Dict]:
        """Get user activity trend data."""
        try:
            # Group by day and count active users
            from django.db.models.functions import TruncDate
            
            activity_data = AuditLog.objects.filter(
                action='login',
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if tenant_id:
                activity_data = activity_data.filter(tenant_id=tenant_id)
            
            daily_activity = activity_data.annotate(
                date=TruncDate('timestamp')
            ).values('date').annotate(
                active_users=Count('user', distinct=True)
            ).order_by('date')
            
            return [
                {
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'active_users': item['active_users']
                }
                for item in daily_activity
            ]
        except Exception as e:
            logger.error(f"User activity trend calculation failed: {e}")
            return []
    
    def _get_query_volume_trend(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> List[Dict]:
        """Get query volume trend data."""
        try:
            from django.db.models.functions import TruncDate
            
            query_data = AuditLog.objects.filter(
                action__in=['query_generate', 'query_execute'],
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if tenant_id:
                query_data = query_data.filter(tenant_id=tenant_id)
            
            daily_queries = query_data.annotate(
                date=TruncDate('timestamp')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            # Calculate average response times by day
            result = []
            for item in daily_queries:
                day_queries = query_data.filter(
                    timestamp__date=item['date']
                )
                
                response_times = []
                for log in day_queries:
                    if 'response_time_ms' in log.metadata:
                        response_times.append(log.metadata['response_time_ms'])
                
                avg_time = sum(response_times) / len(response_times) if response_times else 0
                
                result.append({
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'count': item['count'],
                    'avg_time': round(avg_time, 2)
                })
            
            return result
        except Exception as e:
            logger.error(f"Query volume trend calculation failed: {e}")
            return []
    
    def _get_security_events_trend(self, start_date: datetime, end_date: datetime, tenant_id: Optional[str]) -> List[Dict]:
        """Get security events trend data."""
        try:
            from django.db.models.functions import TruncDate
            
            security_data = AuditLog.objects.filter(
                severity__in=['warning', 'error', 'critical'],
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            if tenant_id:
                security_data = security_data.filter(tenant_id=tenant_id)
            
            daily_events = security_data.annotate(
                date=TruncDate('timestamp')
            ).values('date').annotate(
                events=Count('id')
            ).order_by('date')
            
            return [
                {
                    'date': item['date'].strftime('%Y-%m-%d'),
                    'events': item['events'],
                    'severity': 'mixed'  # Could be enhanced to show severity distribution
                }
                for item in daily_events
            ]
        except Exception as e:
            logger.error(f"Security events trend calculation failed: {e}")
            return []
    
    def _get_performance_trend(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get system performance trend data."""
        try:
            from django.db.models.functions import TruncDate
            
            # Performance data from audit logs
            perf_data = AuditLog.objects.filter(
                action='api_access',
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).annotate(
                date=TruncDate('timestamp')
            ).values('date').order_by('date')
            
            result = []
            for date_group in perf_data.distinct():
                day_logs = AuditLog.objects.filter(
                    action='api_access',
                    timestamp__date=date_group['date']
                )
                
                response_times = []
                error_count = 0
                total_count = 0
                
                for log in day_logs:
                    total_count += 1
                    if 'response_time_ms' in log.metadata:
                        response_times.append(log.metadata['response_time_ms'])
                    
                    if log.metadata.get('status_code', 200) >= 400:
                        error_count += 1
                
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                error_rate = (error_count / total_count) * 100 if total_count > 0 else 0
                
                result.append({
                    'date': date_group['date'].strftime('%Y-%m-%d'),
                    'response_time': round(avg_response_time, 2),
                    'error_rate': round(error_rate, 2)
                })
            
            return result
        except Exception as e:
            logger.error(f"Performance trend calculation failed: {e}")
            return []
    
    def _calculate_threat_level(self, failed_logins: int, locked_accounts: int, security_events: int) -> str:
        """Calculate overall threat level based on security metrics."""
        score = 0
        
        if failed_logins > 50:
            score += 3
        elif failed_logins > 20:
            score += 2
        elif failed_logins > 5:
            score += 1
        
        if locked_accounts > 10:
            score += 3
        elif locked_accounts > 3:
            score += 2
        elif locked_accounts > 0:
            score += 1
        
        if security_events > 20:
            score += 3
        elif security_events > 10:
            score += 2
        elif security_events > 3:
            score += 1
        
        if score >= 6:
            return 'high'
        elif score >= 3:
            return 'medium'
        else:
            return 'low'
    
    # Default/fallback metrics
    def _get_default_user_metrics(self):
        return {
            'total_users': 0,
            'active_users_24h': 0,
            'new_users_7d': 0,
            'user_growth_rate': 0.0,
            'users_by_role': [],
            'user_activity_trend': [],
        }
    
    def _get_default_query_metrics(self):
        return {
            'total_queries': 0,
            'queries_24h': 0,
            'avg_response_time': 0.0,
            'success_rate': 100.0,
            'queries_by_method': [],
            'query_volume_trend': [],
        }
    
    def _get_default_security_metrics(self):
        return {
            'failed_logins_24h': 0,
            'locked_accounts': 0,
            'security_events': 0,
            'threat_level': 'low',
            'security_events_trend': [],
        }
    
    def _get_default_system_metrics(self):
        return {
            'uptime_percentage': 100.0,
            'avg_cpu_usage': 0.0,
            'memory_usage_gb': 0.0,
            'disk_usage_percentage': 0.0,
            'active_sessions': 0,
            'error_rate': 0.0,
            'performance_trend': [],
        }
    
    def _get_default_business_metrics(self):
        return {
            'tenant_count': 0,
            'workspace_count': 0,
            'data_processed_gb': 0.0,
            'export_count_24h': 0,
            'top_indices': [],
        }


class CustomMetricsService:
    """Service for managing custom metrics."""
    
    def __init__(self):
        self.cache_timeout = 300
    
    def execute_custom_metric(self, metric: CustomMetric) -> Dict[str, Any]:
        """Execute a custom metric and return results."""
        try:
            start_time = timezone.now()
            
            # Execute the metric query
            # This would depend on the query type (SQL, Elasticsearch, etc.)
            result_data, current_value = self._execute_query(metric.query)
            
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            # Store the result
            MetricData.objects.create(
                metric=metric,
                data=result_data,
                current_value=current_value,
                execution_time_ms=int(execution_time),
                record_count=len(result_data) if isinstance(result_data, list) else 1
            )
            
            # Update metric metadata
            metric.last_executed = timezone.now()
            metric.execution_count += 1
            metric.save()
            
            return {
                'data': result_data,
                'current_value': current_value,
                'execution_time_ms': int(execution_time),
                'timestamp': start_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Custom metric execution failed: {e}")
            raise
    
    def _execute_query(self, query: str) -> tuple:
        """Execute the metric query and return data and current value."""
        # This is a simplified implementation
        # In practice, would support different query types
        
        if query.startswith('SELECT'):
            # SQL query
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                
                result_data = [
                    dict(zip(columns, row))
                    for row in rows
                ]
                
                current_value = len(result_data)
                if result_data and 'value' in result_data[0]:
                    current_value = result_data[0]['value']
                
                return result_data, current_value
        
        else:
            # Default handling
            return [], 0


class AlertingService:
    """Service for managing alerts and notifications."""
    
    def check_alert_rules(self):
        """Check all active alert rules and trigger alerts if needed."""
        active_rules = AlertRule.objects.filter(is_active=True)
        
        for rule in active_rules:
            try:
                self._check_rule(rule)
            except Exception as e:
                logger.error(f"Alert rule check failed for {rule.name}: {e}")
    
    def _check_rule(self, rule: AlertRule):
        """Check a specific alert rule."""
        # Get current metric value
        current_value = self._get_metric_value(rule.metric_name)
        
        # Check if threshold is exceeded
        threshold_exceeded = self._evaluate_threshold(
            current_value, rule.operator, rule.threshold_value
        )
        
        if threshold_exceeded:
            # Check cooldown period
            if rule.last_triggered:
                cooldown_expires = rule.last_triggered + timedelta(minutes=rule.cooldown_minutes)
                if timezone.now() < cooldown_expires:
                    return  # Still in cooldown
            
            # Trigger alert
            alert = Alert.objects.create(
                rule=rule,
                current_value=current_value,
                message=f"{rule.metric_name} is {current_value} {rule.operator} {rule.threshold_value}",
                metadata={
                    'rule_name': rule.name,
                    'threshold': rule.threshold_value,
                    'operator': rule.operator
                }
            )
            
            # Update rule
            rule.last_triggered = timezone.now()
            rule.trigger_count += 1
            rule.save()
            
            # Send notifications (would integrate with notification services)
            self._send_alert_notifications(alert)
    
    def _get_metric_value(self, metric_name: str) -> float:
        """Get current value for a metric."""
        # This would map metric names to actual data sources
        metric_map = {
            'active_users': lambda: User.objects.filter(
                last_activity__gte=timezone.now() - timedelta(hours=24)
            ).count(),
            'error_rate': lambda: self._calculate_error_rate(),
            'response_time': lambda: self._calculate_avg_response_time(),
        }
        
        if metric_name in metric_map:
            return float(metric_map[metric_name]())
        
        return 0.0
    
    def _evaluate_threshold(self, current_value: float, operator: str, threshold: float) -> bool:
        """Evaluate if threshold condition is met."""
        operators = {
            'gt': lambda c, t: c > t,
            'lt': lambda c, t: c < t,
            'eq': lambda c, t: c == t,
            'gte': lambda c, t: c >= t,
            'lte': lambda c, t: c <= t,
        }
        
        return operators.get(operator, lambda c, t: False)(current_value, threshold)
    
    def _calculate_error_rate(self) -> float:
        """Calculate current error rate."""
        last_hour = timezone.now() - timedelta(hours=1)
        
        total_requests = AuditLog.objects.filter(
            action='api_access',
            timestamp__gte=last_hour
        ).count()
        
        error_requests = AuditLog.objects.filter(
            action='api_access',
            timestamp__gte=last_hour,
            metadata__status_code__gte=400
        ).count()
        
        return (error_requests / total_requests) * 100 if total_requests > 0 else 0.0
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        last_hour = timezone.now() - timedelta(hours=1)
        
        logs = AuditLog.objects.filter(
            action='api_access',
            timestamp__gte=last_hour
        )
        
        response_times = []
        for log in logs:
            if 'response_time_ms' in log.metadata:
                response_times.append(log.metadata['response_time_ms'])
        
        return sum(response_times) / len(response_times) if response_times else 0.0
    
    def _send_alert_notifications(self, alert: Alert):
        """Send alert notifications via configured channels."""
        # This would integrate with email, Slack, webhook services, etc.
        logger.info(f"Alert triggered: {alert.message}")
        # TODO: Implement actual notification sending
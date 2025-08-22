"""
System Health Checking Service
Performs automated health checks across all system components
"""

import requests
import subprocess
import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from django.utils import timezone
from django.db import connection
from django.conf import settings
from django.contrib.auth import get_user_model

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError

from .models import (
    SystemHealthCheck, HealthCheckResult, Alert, AlertRule, AlertSeverity
)
from .alert_manager import AlertManager

User = get_user_model()
logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive system health checking service"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
        self.es_client = self._init_elasticsearch()
        
    def _init_elasticsearch(self):
        """Initialize Elasticsearch client"""
        try:
            es_config = getattr(settings, 'ELASTICSEARCH_DSL', {})
            default_config = es_config.get('default', {})
            hosts = default_config.get('hosts', ['localhost:9200'])
            return Elasticsearch(hosts)
        except Exception as e:
            logger.warning(f"Failed to initialize Elasticsearch client: {e}")
            return None
    
    def run_all_health_checks(self) -> Dict[str, Any]:
        """Run all active health checks"""
        
        logger.info("Starting comprehensive health check cycle")
        results = {
            'timestamp': timezone.now().isoformat(),
            'checks_run': 0,
            'checks_passed': 0,
            'checks_failed': 0,
            'checks_warning': 0,
            'details': {}
        }
        
        # Get all active health checks
        health_checks = SystemHealthCheck.objects.filter(is_active=True)
        
        for check in health_checks:
            try:
                result = self._execute_health_check(check)
                results['details'][check.name] = {
                    'status': result.status,
                    'response_time': result.response_time,
                    'value': result.value,
                    'message': result.message
                }
                
                results['checks_run'] += 1
                
                if result.status == 'healthy':
                    results['checks_passed'] += 1
                elif result.status == 'warning':
                    results['checks_warning'] += 1
                else:
                    results['checks_failed'] += 1
                
                # Update check status
                check.current_status = result.status
                check.last_check_time = result.executed_at
                
                if result.status == 'healthy':
                    check.last_success_time = result.executed_at
                    check.consecutive_failures = 0
                else:
                    check.consecutive_failures += 1
                
                check.save()
                
                # Generate alerts if needed
                self._check_for_alerts(check, result)
                
            except Exception as e:
                logger.error(f"Error executing health check {check.name}: {e}")
                results['checks_run'] += 1
                results['checks_failed'] += 1
        
        logger.info(
            f"Health check cycle complete: {results['checks_run']} checks run, "
            f"{results['checks_passed']} passed, {results['checks_warning']} warnings, "
            f"{results['checks_failed']} failed"
        )
        
        return results
    
    def _execute_health_check(self, check: SystemHealthCheck) -> HealthCheckResult:
        """Execute a single health check"""
        
        start_time = time.time()
        
        try:
            if check.check_type == 'http':
                result = self._check_http_endpoint(check)
            elif check.check_type == 'database':
                result = self._check_database(check)
            elif check.check_type == 'elasticsearch':
                result = self._check_elasticsearch(check)
            elif check.check_type == 'disk_space':
                result = self._check_disk_space(check)
            elif check.check_type == 'memory':
                result = self._check_memory(check)
            elif check.check_type == 'process':
                result = self._check_process(check)
            elif check.check_type == 'custom':
                result = self._check_custom_script(check)
            else:
                raise ValueError(f"Unknown check type: {check.check_type}")
            
        except Exception as e:
            logger.error(f"Health check {check.name} failed: {e}")
            result = {
                'status': 'critical',
                'value': None,
                'message': f"Check execution failed: {str(e)}",
                'metadata': {'error': str(e)}
            }
        
        execution_duration = (time.time() - start_time) * 1000  # Convert to ms
        
        # Create result record
        health_result = HealthCheckResult.objects.create(
            health_check=check,
            status=result['status'],
            response_time=result.get('response_time', execution_duration),
            value=result.get('value'),
            message=result['message'],
            executed_at=timezone.now(),
            execution_duration=execution_duration,
            metadata=result.get('metadata', {})
        )
        
        return health_result
    
    def _check_http_endpoint(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check HTTP endpoint health"""
        
        config = check.configuration
        url = config.get('url')
        method = config.get('method', 'GET').upper()
        expected_status = config.get('expected_status', 200)
        expected_content = config.get('expected_content')
        headers = config.get('headers', {})
        
        if not url:
            raise ValueError("URL is required for HTTP health check")
        
        start_time = time.time()
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=check.timeout)
            elif method == 'POST':
                response = requests.post(url, headers=headers, timeout=check.timeout)
            else:
                response = requests.request(method, url, headers=headers, timeout=check.timeout)
            
            response_time = (time.time() - start_time) * 1000
            
            # Check status code
            if response.status_code != expected_status:
                return {
                    'status': 'critical',
                    'response_time': response_time,
                    'value': response.status_code,
                    'message': f"Unexpected status code: {response.status_code} (expected {expected_status})",
                    'metadata': {'status_code': response.status_code}
                }
            
            # Check content if specified
            if expected_content and expected_content not in response.text:
                return {
                    'status': 'warning',
                    'response_time': response_time,
                    'value': response.status_code,
                    'message': f"Expected content not found in response",
                    'metadata': {'status_code': response.status_code}
                }
            
            # Check response time thresholds
            status = 'healthy'
            message = f"HTTP {method} successful"
            
            if check.critical_threshold and response_time > check.critical_threshold:
                status = 'critical'
                message = f"Response time {response_time:.1f}ms exceeds critical threshold"
            elif check.warning_threshold and response_time > check.warning_threshold:
                status = 'warning'
                message = f"Response time {response_time:.1f}ms exceeds warning threshold"
            
            return {
                'status': status,
                'response_time': response_time,
                'value': response_time,
                'message': message,
                'metadata': {
                    'status_code': response.status_code,
                    'response_size': len(response.content)
                }
            }
            
        except requests.RequestException as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': response_time,
                'value': None,
                'message': f"HTTP request failed: {str(e)}",
                'metadata': {'error': str(e)}
            }
    
    def _check_database(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        
        config = check.configuration
        query = config.get('query', 'SELECT 1')
        
        start_time = time.time()
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            # Check response time thresholds
            status = 'healthy'
            message = "Database query successful"
            
            if check.critical_threshold and response_time > check.critical_threshold:
                status = 'critical'
                message = f"Database response time {response_time:.1f}ms exceeds critical threshold"
            elif check.warning_threshold and response_time > check.warning_threshold:
                status = 'warning'
                message = f"Database response time {response_time:.1f}ms exceeds warning threshold"
            
            return {
                'status': status,
                'response_time': response_time,
                'value': response_time,
                'message': message,
                'metadata': {'query': query}
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': response_time,
                'value': None,
                'message': f"Database check failed: {str(e)}",
                'metadata': {'error': str(e), 'query': query}
            }
    
    def _check_elasticsearch(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check Elasticsearch cluster health"""
        
        if not self.es_client:
            return {
                'status': 'critical',
                'response_time': 0,
                'value': None,
                'message': "Elasticsearch client not available",
                'metadata': {'error': 'client_not_initialized'}
            }
        
        start_time = time.time()
        
        try:
            # Check cluster health
            cluster_health = self.es_client.cluster.health()
            response_time = (time.time() - start_time) * 1000
            
            cluster_status = cluster_health.get('status', 'unknown')
            
            # Determine health status based on cluster status
            if cluster_status == 'green':
                status = 'healthy'
                message = "Elasticsearch cluster is healthy (green)"
            elif cluster_status == 'yellow':
                status = 'warning'
                message = "Elasticsearch cluster has warnings (yellow)"
            else:  # red or unknown
                status = 'critical'
                message = f"Elasticsearch cluster is unhealthy ({cluster_status})"
            
            # Check response time thresholds
            if check.critical_threshold and response_time > check.critical_threshold:
                status = 'critical'
                message = f"Elasticsearch response time {response_time:.1f}ms exceeds critical threshold"
            elif check.warning_threshold and response_time > check.warning_threshold and status == 'healthy':
                status = 'warning'
                message = f"Elasticsearch response time {response_time:.1f}ms exceeds warning threshold"
            
            return {
                'status': status,
                'response_time': response_time,
                'value': response_time,
                'message': message,
                'metadata': {
                    'cluster_status': cluster_status,
                    'number_of_nodes': cluster_health.get('number_of_nodes', 0),
                    'active_shards': cluster_health.get('active_shards', 0),
                    'unassigned_shards': cluster_health.get('unassigned_shards', 0)
                }
            }
            
        except ESConnectionError:
            response_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': response_time,
                'value': None,
                'message': "Cannot connect to Elasticsearch",
                'metadata': {'error': 'connection_failed'}
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': response_time,
                'value': None,
                'message': f"Elasticsearch check failed: {str(e)}",
                'metadata': {'error': str(e)}
            }
    
    def _check_disk_space(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check disk space usage"""
        
        config = check.configuration
        path = config.get('path', '/')
        
        try:
            disk_usage = psutil.disk_usage(path)
            used_percent = (disk_usage.used / disk_usage.total) * 100
            
            # Determine status based on thresholds
            status = 'healthy'
            message = f"Disk usage at {used_percent:.1f}%"
            
            if check.critical_threshold and used_percent > check.critical_threshold:
                status = 'critical'
                message = f"Disk usage {used_percent:.1f}% exceeds critical threshold {check.critical_threshold}%"
            elif check.warning_threshold and used_percent > check.warning_threshold:
                status = 'warning'
                message = f"Disk usage {used_percent:.1f}% exceeds warning threshold {check.warning_threshold}%"
            
            return {
                'status': status,
                'response_time': 0,
                'value': used_percent,
                'message': message,
                'metadata': {
                    'path': path,
                    'total_gb': disk_usage.total / 1024**3,
                    'used_gb': disk_usage.used / 1024**3,
                    'free_gb': disk_usage.free / 1024**3,
                    'used_percent': used_percent
                }
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': 0,
                'value': None,
                'message': f"Disk space check failed: {str(e)}",
                'metadata': {'error': str(e), 'path': path}
            }
    
    def _check_memory(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check memory usage"""
        
        try:
            memory = psutil.virtual_memory()
            used_percent = memory.percent
            
            # Determine status based on thresholds
            status = 'healthy'
            message = f"Memory usage at {used_percent:.1f}%"
            
            if check.critical_threshold and used_percent > check.critical_threshold:
                status = 'critical'
                message = f"Memory usage {used_percent:.1f}% exceeds critical threshold {check.critical_threshold}%"
            elif check.warning_threshold and used_percent > check.warning_threshold:
                status = 'warning'
                message = f"Memory usage {used_percent:.1f}% exceeds warning threshold {check.warning_threshold}%"
            
            return {
                'status': status,
                'response_time': 0,
                'value': used_percent,
                'message': message,
                'metadata': {
                    'total_gb': memory.total / 1024**3,
                    'available_gb': memory.available / 1024**3,
                    'used_percent': used_percent
                }
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': 0,
                'value': None,
                'message': f"Memory check failed: {str(e)}",
                'metadata': {'error': str(e)}
            }
    
    def _check_process(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Check if specific process is running"""
        
        config = check.configuration
        process_name = config.get('process_name')
        min_instances = config.get('min_instances', 1)
        max_instances = config.get('max_instances')
        
        if not process_name:
            raise ValueError("process_name is required for process health check")
        
        try:
            # Find processes by name
            matching_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if process_name in proc.info['name'] or any(process_name in arg for arg in proc.info['cmdline'] or []):
                        matching_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            process_count = len(matching_processes)
            
            # Determine status based on count
            status = 'healthy'
            message = f"Found {process_count} instances of {process_name}"
            
            if process_count < min_instances:
                status = 'critical'
                message = f"Only {process_count} instances of {process_name} running (minimum: {min_instances})"
            elif max_instances and process_count > max_instances:
                status = 'warning'
                message = f"Too many instances of {process_name}: {process_count} (maximum: {max_instances})"
            
            return {
                'status': status,
                'response_time': 0,
                'value': process_count,
                'message': message,
                'metadata': {
                    'process_name': process_name,
                    'process_count': process_count,
                    'min_instances': min_instances,
                    'max_instances': max_instances,
                    'processes': [{'pid': p.pid, 'cmdline': ' '.join(p.cmdline())} for p in matching_processes[:5]]
                }
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': 0,
                'value': None,
                'message': f"Process check failed: {str(e)}",
                'metadata': {'error': str(e), 'process_name': process_name}
            }
    
    def _check_custom_script(self, check: SystemHealthCheck) -> Dict[str, Any]:
        """Execute custom health check script"""
        
        config = check.configuration
        script_path = config.get('script_path')
        script_args = config.get('script_args', [])
        
        if not script_path:
            raise ValueError("script_path is required for custom health check")
        
        start_time = time.time()
        
        try:
            # Execute script
            result = subprocess.run(
                [script_path] + script_args,
                timeout=check.timeout,
                capture_output=True,
                text=True
            )
            
            execution_time = (time.time() - start_time) * 1000
            
            # Interpret exit code
            if result.returncode == 0:
                status = 'healthy'
                message = "Custom script executed successfully"
            elif result.returncode == 1:
                status = 'warning'
                message = "Custom script returned warning"
            else:
                status = 'critical'
                message = f"Custom script failed with exit code {result.returncode}"
            
            # Try to parse numeric output as value
            value = None
            try:
                output_lines = result.stdout.strip().split('\n')
                if output_lines:
                    value = float(output_lines[0])
            except (ValueError, IndexError):
                pass
            
            return {
                'status': status,
                'response_time': execution_time,
                'value': value,
                'message': message,
                'metadata': {
                    'exit_code': result.returncode,
                    'stdout': result.stdout[:500],  # Truncate long output
                    'stderr': result.stderr[:500],
                    'script_path': script_path
                }
            }
            
        except subprocess.TimeoutExpired:
            execution_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': execution_time,
                'value': None,
                'message': f"Custom script timed out after {check.timeout} seconds",
                'metadata': {'error': 'timeout', 'script_path': script_path}
            }
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return {
                'status': 'critical',
                'response_time': execution_time,
                'value': None,
                'message': f"Custom script execution failed: {str(e)}",
                'metadata': {'error': str(e), 'script_path': script_path}
            }
    
    def _check_for_alerts(self, check: SystemHealthCheck, result: HealthCheckResult) -> None:
        """Check if health check result should trigger alerts"""
        
        try:
            # Look for existing alert rules for this health check
            alert_rules = AlertRule.objects.filter(
                metric_name=f"health_check_{check.name}",
                is_active=True
            )
            
            if not alert_rules.exists() and result.status in ['warning', 'critical']:
                # Create automatic alert rule for failed health checks
                severity = AlertSeverity.CRITICAL if result.status == 'critical' else AlertSeverity.WARNING
                
                AlertRule.objects.create(
                    name=f"Health Check Alert: {check.name}",
                    description=f"Automatic alert for {check.name} health check failures",
                    metric_name=f"health_check_{check.name}",
                    metric_category='system',
                    component_filter=check.check_type,
                    threshold_operator='ne',  # not equal
                    threshold_value=0,  # 0 = healthy, anything else = problem
                    threshold_duration=60,  # 1 minute
                    severity=severity,
                    cooldown_period=1800,  # 30 minutes
                    notification_channels=['default']
                )
                
                logger.info(f"Created automatic alert rule for health check: {check.name}")
            
        except Exception as e:
            logger.error(f"Error checking alerts for health check {check.name}: {e}")
    
    def create_default_health_checks(self) -> List[SystemHealthCheck]:
        """Create default health checks for common system components"""
        
        logger.info("Creating default health checks")
        created_checks = []
        
        default_checks = [
            {
                'name': 'Database Connectivity',
                'description': 'Check database connection and response time',
                'check_type': 'database',
                'configuration': {'query': 'SELECT 1'},
                'warning_threshold': 500.0,  # 500ms
                'critical_threshold': 2000.0,  # 2 seconds
                'check_interval': 300,  # 5 minutes
            },
            {
                'name': 'Elasticsearch Health',
                'description': 'Check Elasticsearch cluster health',
                'check_type': 'elasticsearch',
                'configuration': {},
                'warning_threshold': 1000.0,  # 1 second
                'critical_threshold': 5000.0,  # 5 seconds
                'check_interval': 300,
            },
            {
                'name': 'Disk Space Usage',
                'description': 'Monitor disk space usage',
                'check_type': 'disk_space',
                'configuration': {'path': '/'},
                'warning_threshold': 80.0,  # 80%
                'critical_threshold': 90.0,  # 90%
                'check_interval': 600,  # 10 minutes
            },
            {
                'name': 'Memory Usage',
                'description': 'Monitor system memory usage',
                'check_type': 'memory',
                'configuration': {},
                'warning_threshold': 80.0,  # 80%
                'critical_threshold': 95.0,  # 95%
                'check_interval': 300,
            },
            {
                'name': 'Application HTTP Health',
                'description': 'Check application HTTP endpoint',
                'check_type': 'http',
                'configuration': {
                    'url': 'http://localhost:8000/api/auth/health/',
                    'method': 'GET',
                    'expected_status': 200
                },
                'warning_threshold': 2000.0,  # 2 seconds
                'critical_threshold': 5000.0,  # 5 seconds
                'check_interval': 300,
            }
        ]
        
        for check_config in default_checks:
            try:
                check, created = SystemHealthCheck.objects.get_or_create(
                    name=check_config['name'],
                    defaults=check_config
                )
                
                if created:
                    created_checks.append(check)
                    logger.info(f"Created health check: {check.name}")
                else:
                    logger.info(f"Health check already exists: {check.name}")
                    
            except Exception as e:
                logger.error(f"Error creating health check {check_config['name']}: {e}")
        
        logger.info(f"Created {len(created_checks)} default health checks")
        return created_checks
    
    def cleanup_old_results(self, days: int = 7) -> int:
        """Clean up old health check results"""
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        old_results = HealthCheckResult.objects.filter(executed_at__lt=cutoff_date)
        count = old_results.count()
        old_results.delete()
        
        logger.info(f"Cleaned up {count} old health check results (older than {days} days)")
        return count
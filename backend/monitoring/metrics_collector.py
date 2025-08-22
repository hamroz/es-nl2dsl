"""
Performance Metrics Collection System
Collects system, application, and infrastructure metrics
"""

import psutil
import time
import logging
import subprocess
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.db import connection
from django.conf import settings
from django.core.cache import cache

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError

from .models import (
    PerformanceMetric, MetricCategory, PerformanceBaseline,
    SystemHealthCheck, HealthCheckResult
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Comprehensive metrics collection system"""
    
    def __init__(self):
        self.collection_start_time = timezone.now()
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
    
    def collect_all_metrics(self) -> Dict[str, List[PerformanceMetric]]:
        """Collect all available metrics"""
        
        logger.info("Starting comprehensive metrics collection")
        collected_metrics = {}
        
        try:
            # System resource metrics
            collected_metrics['system'] = self.collect_system_metrics()
            
            # Database performance metrics
            collected_metrics['database'] = self.collect_database_metrics()
            
            # Elasticsearch metrics
            if self.es_client:
                collected_metrics['elasticsearch'] = self.collect_elasticsearch_metrics()
            
            # Application performance metrics
            collected_metrics['application'] = self.collect_application_metrics()
            
            # Security metrics
            collected_metrics['security'] = self.collect_security_metrics()
            
            # Network metrics
            collected_metrics['network'] = self.collect_network_metrics()
            
            # Store metrics in database
            total_stored = 0
            for category, metrics in collected_metrics.items():
                stored = self._store_metrics(metrics)
                total_stored += stored
                logger.info(f"Stored {stored} {category} metrics")
            
            logger.info(f"Metrics collection complete: {total_stored} metrics stored")
            
        except Exception as e:
            logger.error(f"Error during metrics collection: {e}")
        
        return collected_metrics
    
    def collect_system_metrics(self) -> List[PerformanceMetric]:
        """Collect system resource metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            metrics.extend([
                PerformanceMetric(
                    name='cpu_usage_percent',
                    category=MetricCategory.SYSTEM,
                    component='cpu',
                    value=cpu_percent,
                    unit='%',
                    timestamp=timestamp,
                    tags={'cores': cpu_count}
                ),
                PerformanceMetric(
                    name='cpu_frequency',
                    category=MetricCategory.SYSTEM,
                    component='cpu',
                    value=cpu_freq.current if cpu_freq else 0,
                    unit='MHz',
                    timestamp=timestamp
                )
            ])
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            metrics.extend([
                PerformanceMetric(
                    name='memory_usage_percent',
                    category=MetricCategory.SYSTEM,
                    component='memory',
                    value=memory.percent,
                    unit='%',
                    timestamp=timestamp,
                    tags={'total_gb': round(memory.total / 1024**3, 2)}
                ),
                PerformanceMetric(
                    name='memory_available',
                    category=MetricCategory.SYSTEM,
                    component='memory',
                    value=memory.available / 1024**3,
                    unit='GB',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='swap_usage_percent',
                    category=MetricCategory.SYSTEM,
                    component='memory',
                    value=swap.percent,
                    unit='%',
                    timestamp=timestamp
                )
            ])
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            metrics.extend([
                PerformanceMetric(
                    name='disk_usage_percent',
                    category=MetricCategory.SYSTEM,
                    component='disk',
                    value=(disk_usage.used / disk_usage.total) * 100,
                    unit='%',
                    timestamp=timestamp,
                    tags={'total_gb': round(disk_usage.total / 1024**3, 2)}
                ),
                PerformanceMetric(
                    name='disk_free_space',
                    category=MetricCategory.SYSTEM,
                    component='disk',
                    value=disk_usage.free / 1024**3,
                    unit='GB',
                    timestamp=timestamp
                )
            ])
            
            if disk_io:
                metrics.extend([
                    PerformanceMetric(
                        name='disk_read_bytes_per_sec',
                        category=MetricCategory.SYSTEM,
                        component='disk',
                        value=disk_io.read_bytes,
                        unit='bytes/sec',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='disk_write_bytes_per_sec',
                        category=MetricCategory.SYSTEM,
                        component='disk',
                        value=disk_io.write_bytes,
                        unit='bytes/sec',
                        timestamp=timestamp
                    )
                ])
            
            # Load average (Unix-like systems)
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
                metrics.append(
                    PerformanceMetric(
                        name='load_average_1min',
                        category=MetricCategory.SYSTEM,
                        component='cpu',
                        value=load_avg[0],
                        unit='load',
                        timestamp=timestamp
                    )
                )
            
            # Process count
            process_count = len(psutil.pids())
            metrics.append(
                PerformanceMetric(
                    name='process_count',
                    category=MetricCategory.SYSTEM,
                    component='processes',
                    value=process_count,
                    unit='count',
                    timestamp=timestamp
                )
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def collect_database_metrics(self) -> List[PerformanceMetric]:
        """Collect database performance metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        try:
            # Connection count
            with connection.cursor() as cursor:
                # Database-agnostic connection test
                start_time = time.time()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                db_response_time = (time.time() - start_time) * 1000
                
                metrics.append(
                    PerformanceMetric(
                        name='database_response_time',
                        category=MetricCategory.DATABASE,
                        component='database',
                        value=db_response_time,
                        unit='ms',
                        timestamp=timestamp
                    )
                )
            
            # Query performance from Django's query log (if debug is enabled)
            if hasattr(connection, 'queries'):
                recent_queries = connection.queries[-10:]  # Last 10 queries
                if recent_queries:
                    avg_query_time = sum(float(q['time']) for q in recent_queries) / len(recent_queries)
                    
                    metrics.append(
                        PerformanceMetric(
                            name='average_query_time',
                            category=MetricCategory.DATABASE,
                            component='database',
                            value=avg_query_time * 1000,  # Convert to ms
                            unit='ms',
                            timestamp=timestamp,
                            tags={'sample_size': len(recent_queries)}
                        )
                    )
            
            # Cache hit rate (if available)
            try:
                cache_stats = cache._cache.get_stats()
                if cache_stats and len(cache_stats) > 0:
                    stats = cache_stats[0][1]
                    hits = stats.get('get_hits', 0)
                    misses = stats.get('get_misses', 0)
                    total = hits + misses
                    
                    if total > 0:
                        hit_rate = (hits / total) * 100
                        metrics.append(
                            PerformanceMetric(
                                name='cache_hit_rate',
                                category=MetricCategory.DATABASE,
                                component='cache',
                                value=hit_rate,
                                unit='%',
                                timestamp=timestamp,
                                tags={'hits': hits, 'misses': misses}
                            )
                        )
            except Exception:
                pass  # Cache stats not available
            
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
        
        return metrics
    
    def collect_elasticsearch_metrics(self) -> List[PerformanceMetric]:
        """Collect Elasticsearch performance metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        if not self.es_client:
            return metrics
        
        try:
            # Cluster health
            start_time = time.time()
            cluster_health = self.es_client.cluster.health()
            es_response_time = (time.time() - start_time) * 1000
            
            metrics.extend([
                PerformanceMetric(
                    name='elasticsearch_response_time',
                    category=MetricCategory.ELASTICSEARCH,
                    component='cluster',
                    value=es_response_time,
                    unit='ms',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='elasticsearch_nodes',
                    category=MetricCategory.ELASTICSEARCH,
                    component='cluster',
                    value=cluster_health.get('number_of_nodes', 0),
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='elasticsearch_active_shards',
                    category=MetricCategory.ELASTICSEARCH,
                    component='cluster',
                    value=cluster_health.get('active_shards', 0),
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='elasticsearch_relocating_shards',
                    category=MetricCategory.ELASTICSEARCH,
                    component='cluster',
                    value=cluster_health.get('relocating_shards', 0),
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='elasticsearch_unassigned_shards',
                    category=MetricCategory.ELASTICSEARCH,
                    component='cluster',
                    value=cluster_health.get('unassigned_shards', 0),
                    unit='count',
                    timestamp=timestamp
                )
            ])
            
            # Cluster stats
            cluster_stats = self.es_client.cluster.stats()
            indices_stats = cluster_stats.get('indices', {})
            
            if indices_stats:
                metrics.extend([
                    PerformanceMetric(
                        name='elasticsearch_indices_count',
                        category=MetricCategory.ELASTICSEARCH,
                        component='indices',
                        value=indices_stats.get('count', 0),
                        unit='count',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='elasticsearch_documents_count',
                        category=MetricCategory.ELASTICSEARCH,
                        component='indices',
                        value=indices_stats.get('docs', {}).get('count', 0),
                        unit='count',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='elasticsearch_storage_size',
                        category=MetricCategory.ELASTICSEARCH,
                        component='indices',
                        value=indices_stats.get('store', {}).get('size_in_bytes', 0) / 1024**3,
                        unit='GB',
                        timestamp=timestamp
                    )
                ])
            
            # Node stats
            nodes_stats = self.es_client.nodes.stats()
            if 'nodes' in nodes_stats:
                node_count = len(nodes_stats['nodes'])
                total_heap_used = 0
                total_heap_max = 0
                
                for node_id, node_stats in nodes_stats['nodes'].items():
                    jvm_stats = node_stats.get('jvm', {}).get('mem', {})
                    heap_used = jvm_stats.get('heap_used_in_bytes', 0)
                    heap_max = jvm_stats.get('heap_max_in_bytes', 0)
                    
                    total_heap_used += heap_used
                    total_heap_max += heap_max
                
                if total_heap_max > 0:
                    heap_usage_percent = (total_heap_used / total_heap_max) * 100
                    metrics.append(
                        PerformanceMetric(
                            name='elasticsearch_heap_usage_percent',
                            category=MetricCategory.ELASTICSEARCH,
                            component='jvm',
                            value=heap_usage_percent,
                            unit='%',
                            timestamp=timestamp,
                            tags={'nodes': node_count}
                        )
                    )
            
        except ESConnectionError:
            logger.warning("Elasticsearch not available for metrics collection")
        except Exception as e:
            logger.error(f"Error collecting Elasticsearch metrics: {e}")
        
        return metrics
    
    def collect_application_metrics(self) -> List[PerformanceMetric]:
        """Collect application-specific metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        try:
            # Django-specific metrics
            from django.contrib.auth import get_user_model
            from authentication.models import UserSession, AuditLog
            
            User = get_user_model()
            
            # User metrics
            total_users = User.objects.count()
            active_users = User.objects.filter(
                last_activity__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            metrics.extend([
                PerformanceMetric(
                    name='total_users',
                    category=MetricCategory.APPLICATION,
                    component='users',
                    value=total_users,
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='active_users_24h',
                    category=MetricCategory.APPLICATION,
                    component='users',
                    value=active_users,
                    unit='count',
                    timestamp=timestamp
                )
            ])
            
            # Session metrics
            active_sessions = UserSession.objects.filter(
                is_terminated=False,
                expires_at__gt=timezone.now()
            ).count()
            
            suspicious_sessions = UserSession.objects.filter(
                is_suspicious=True,
                is_terminated=False
            ).count()
            
            metrics.extend([
                PerformanceMetric(
                    name='active_sessions',
                    category=MetricCategory.APPLICATION,
                    component='sessions',
                    value=active_sessions,
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='suspicious_sessions',
                    category=MetricCategory.APPLICATION,
                    component='sessions',
                    value=suspicious_sessions,
                    unit='count',
                    timestamp=timestamp
                )
            ])
            
            # Recent activity metrics
            recent_logins = AuditLog.objects.filter(
                event_type='login',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            recent_queries = AuditLog.objects.filter(
                event_type='query_generate',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            metrics.extend([
                PerformanceMetric(
                    name='logins_per_hour',
                    category=MetricCategory.APPLICATION,
                    component='activity',
                    value=recent_logins,
                    unit='count/hour',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='queries_per_hour',
                    category=MetricCategory.APPLICATION,
                    component='activity',
                    value=recent_queries,
                    unit='count/hour',
                    timestamp=timestamp
                )
            ])
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
        
        return metrics
    
    def collect_security_metrics(self) -> List[PerformanceMetric]:
        """Collect security-related metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        try:
            from authentication.models import AuditLog, SecurityPolicy
            
            # Failed login attempts
            failed_logins_1h = AuditLog.objects.filter(
                event_type='login_failed',
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            failed_logins_24h = AuditLog.objects.filter(
                event_type='login_failed',
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Security violations
            security_violations = AuditLog.objects.filter(
                event_type__in=['policy_violation_deny', 'suspicious_activity'],
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            
            # Policy metrics
            active_policies = SecurityPolicy.objects.filter(is_active=True).count()
            
            metrics.extend([
                PerformanceMetric(
                    name='failed_logins_1h',
                    category=MetricCategory.SECURITY,
                    component='authentication',
                    value=failed_logins_1h,
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='failed_logins_24h',
                    category=MetricCategory.SECURITY,
                    component='authentication',
                    value=failed_logins_24h,
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='security_violations_1h',
                    category=MetricCategory.SECURITY,
                    component='violations',
                    value=security_violations,
                    unit='count',
                    timestamp=timestamp
                ),
                PerformanceMetric(
                    name='active_security_policies',
                    category=MetricCategory.SECURITY,
                    component='policies',
                    value=active_policies,
                    unit='count',
                    timestamp=timestamp
                )
            ])
            
        except Exception as e:
            logger.error(f"Error collecting security metrics: {e}")
        
        return metrics
    
    def collect_network_metrics(self) -> List[PerformanceMetric]:
        """Collect network performance metrics"""
        
        metrics = []
        timestamp = timezone.now()
        
        try:
            # Network I/O
            network_io = psutil.net_io_counters()
            
            if network_io:
                metrics.extend([
                    PerformanceMetric(
                        name='network_bytes_sent',
                        category=MetricCategory.NETWORK,
                        component='interface',
                        value=network_io.bytes_sent,
                        unit='bytes',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='network_bytes_received',
                        category=MetricCategory.NETWORK,
                        component='interface',
                        value=network_io.bytes_recv,
                        unit='bytes',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='network_packets_sent',
                        category=MetricCategory.NETWORK,
                        component='interface',
                        value=network_io.packets_sent,
                        unit='count',
                        timestamp=timestamp
                    ),
                    PerformanceMetric(
                        name='network_packets_received',
                        category=MetricCategory.NETWORK,
                        component='interface',
                        value=network_io.packets_recv,
                        unit='count',
                        timestamp=timestamp
                    )
                ])
            
            # Connection count
            connections = psutil.net_connections()
            established_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
            
            metrics.append(
                PerformanceMetric(
                    name='established_connections',
                    category=MetricCategory.NETWORK,
                    component='connections',
                    value=established_connections,
                    unit='count',
                    timestamp=timestamp,
                    tags={'total_connections': len(connections)}
                )
            )
            
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
        
        return metrics
    
    def _store_metrics(self, metrics: List[PerformanceMetric]) -> int:
        """Store metrics in database with batch operations"""
        
        if not metrics:
            return 0
        
        try:
            # Use bulk_create for efficient insertion
            PerformanceMetric.objects.bulk_create(metrics, batch_size=100)
            return len(metrics)
        
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            return 0
    
    def calculate_baselines(self, days: int = 7) -> Dict[str, PerformanceBaseline]:
        """Calculate performance baselines from historical data"""
        
        logger.info(f"Calculating performance baselines for last {days} days")
        baselines = {}
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get unique metric/component combinations
            metric_combinations = PerformanceMetric.objects.filter(
                timestamp__gte=cutoff_date
            ).values('name', 'component', 'category').distinct()
            
            for combo in metric_combinations:
                metric_name = combo['name']
                component = combo['component']
                category = combo['category']
                
                # Get metric values
                values = PerformanceMetric.objects.filter(
                    name=metric_name,
                    component=component,
                    timestamp__gte=cutoff_date
                ).values_list('value', flat=True)
                
                if len(values) < 10:  # Need minimum samples
                    continue
                
                # Calculate statistics
                import statistics
                
                mean_val = statistics.mean(values)
                std_dev = statistics.stdev(values) if len(values) > 1 else 0
                min_val = min(values)
                max_val = max(values)
                
                # Calculate percentiles
                sorted_values = sorted(values)
                p50 = statistics.median(sorted_values)
                p95_idx = int(len(sorted_values) * 0.95)
                p99_idx = int(len(sorted_values) * 0.99)
                p95 = sorted_values[min(p95_idx, len(sorted_values) - 1)]
                p99 = sorted_values[min(p99_idx, len(sorted_values) - 1)]
                
                # Create or update baseline
                baseline, created = PerformanceBaseline.objects.update_or_create(
                    metric_name=metric_name,
                    component=component,
                    category=category,
                    defaults={
                        'baseline_value': mean_val,
                        'min_value': min_val,
                        'max_value': max_val,
                        'mean_value': mean_val,
                        'std_deviation': std_dev,
                        'p50': p50,
                        'p95': p95,
                        'p99': p99,
                        'sample_count': len(values),
                        'calculation_period_start': cutoff_date,
                        'calculation_period_end': timezone.now(),
                        'is_valid': True,
                        'confidence_level': min(0.95, len(values) / 100.0)  # Confidence based on sample size
                    }
                )
                
                baselines[f"{metric_name}_{component}"] = baseline
                
                if created:
                    logger.info(f"Created baseline for {metric_name} ({component})")
                else:
                    logger.info(f"Updated baseline for {metric_name} ({component})")
            
            logger.info(f"Calculated {len(baselines)} performance baselines")
            
        except Exception as e:
            logger.error(f"Error calculating baselines: {e}")
        
        return baselines
    
    def detect_anomalies(self, sensitivity: float = 2.0) -> List[PerformanceMetric]:
        """Detect anomalous metrics based on baselines"""
        
        anomalies = []
        recent_metrics = PerformanceMetric.objects.filter(
            timestamp__gte=timezone.now() - timedelta(minutes=15),
            is_anomaly=False  # Don't re-check already flagged anomalies
        )
        
        for metric in recent_metrics:
            try:
                baseline = PerformanceBaseline.objects.get(
                    metric_name=metric.name,
                    component=metric.component,
                    category=metric.category,
                    is_valid=True
                )
                
                if baseline.is_anomaly(metric.value, sensitivity):
                    metric.is_anomaly = True
                    metric.confidence_score = baseline.confidence_level
                    metric.save()
                    anomalies.append(metric)
                    
                    logger.warning(
                        f"Anomaly detected: {metric.name} = {metric.value} "
                        f"(baseline: {baseline.baseline_value} ± {baseline.std_deviation})"
                    )
                
            except PerformanceBaseline.DoesNotExist:
                continue  # No baseline available for this metric
            except Exception as e:
                logger.error(f"Error checking anomaly for {metric.name}: {e}")
        
        return anomalies
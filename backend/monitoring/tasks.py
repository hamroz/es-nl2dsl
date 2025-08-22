"""
Monitoring Background Tasks
Celery tasks for automated monitoring, alerting, and health checking
"""

import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task

from .metrics_collector import MetricsCollector
from .alert_manager import AlertManager
from .health_checker import HealthChecker
from .models import PerformanceMetric, Alert, HealthCheckResult

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def collect_performance_metrics(self):
    """
    Collect performance metrics from all system components
    Runs every 5 minutes via cron schedule
    """
    
    try:
        logger.info("Starting performance metrics collection task")
        
        collector = MetricsCollector()
        collected_metrics = collector.collect_all_metrics()
        
        # Calculate totals
        total_metrics = sum(len(metrics) for metrics in collected_metrics.values())
        
        logger.info(f"Performance metrics collection completed: {total_metrics} metrics collected")
        
        return {
            'success': True,
            'metrics_collected': total_metrics,
            'categories': {category: len(metrics) for category, metrics in collected_metrics.items()},
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance metrics collection failed: {e}")
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def evaluate_alerts(self):
    """
    Evaluate alert rules against recent metrics
    Runs every 2 minutes via cron schedule
    """
    
    try:
        logger.info("Starting alert evaluation task")
        
        alert_manager = AlertManager()
        
        # Evaluate alert rules
        triggered_alerts = alert_manager.evaluate_alert_rules()
        
        # Auto-resolve alerts
        resolved_alerts = alert_manager.auto_resolve_alerts()
        
        # Escalate unacknowledged alerts
        escalated_alerts = alert_manager.escalate_alerts()
        
        logger.info(
            f"Alert evaluation completed: {len(triggered_alerts)} triggered, "
            f"{len(resolved_alerts)} resolved, {len(escalated_alerts)} escalated"
        )
        
        return {
            'success': True,
            'triggered_alerts': len(triggered_alerts),
            'resolved_alerts': len(resolved_alerts),
            'escalated_alerts': len(escalated_alerts),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Alert evaluation failed: {e}")
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def run_health_checks(self):
    """
    Run all system health checks
    Runs every 5 minutes via cron schedule
    """
    
    try:
        logger.info("Starting health checks task")
        
        health_checker = HealthChecker()
        results = health_checker.run_all_health_checks()
        
        logger.info(
            f"Health checks completed: {results['checks_run']} checks run, "
            f"{results['checks_passed']} passed, {results['checks_failed']} failed"
        )
        
        return {
            'success': True,
            'checks_run': results['checks_run'],
            'checks_passed': results['checks_passed'],
            'checks_failed': results['checks_failed'],
            'checks_warning': results['checks_warning'],
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health checks failed: {e}")
        raise self.retry(exc=e, countdown=120 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def calculate_performance_baselines(self):
    """
    Calculate performance baselines from historical data
    Runs daily at 2 AM via cron schedule
    """
    
    try:
        logger.info("Starting performance baseline calculation")
        
        collector = MetricsCollector()
        baselines = collector.calculate_baselines(days=7)
        
        logger.info(f"Performance baseline calculation completed: {len(baselines)} baselines calculated")
        
        return {
            'success': True,
            'baselines_calculated': len(baselines),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance baseline calculation failed: {e}")
        raise self.retry(exc=e, countdown=300 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def detect_anomalies(self):
    """
    Detect anomalous metrics based on baselines
    Runs every 10 minutes via cron schedule
    """
    
    try:
        logger.info("Starting anomaly detection")
        
        collector = MetricsCollector()
        anomalies = collector.detect_anomalies(sensitivity=2.0)
        
        logger.info(f"Anomaly detection completed: {len(anomalies)} anomalies detected")
        
        return {
            'success': True,
            'anomalies_detected': len(anomalies),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        raise self.retry(exc=e, countdown=180 * (2 ** self.request.retries))


@shared_task(bind=True)
def cleanup_old_metrics(days=30):
    """
    Clean up old performance metrics
    Runs daily at 3 AM via cron schedule
    """
    
    try:
        logger.info(f"Starting cleanup of metrics older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old metrics
        old_metrics = PerformanceMetric.objects.filter(timestamp__lt=cutoff_date)
        metrics_count = old_metrics.count()
        old_metrics.delete()
        
        logger.info(f"Cleanup completed: {metrics_count} old metrics deleted")
        
        return {
            'success': True,
            'metrics_deleted': metrics_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Metrics cleanup failed: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def cleanup_old_alerts(days=90):
    """
    Clean up resolved alerts older than specified days
    Runs weekly on Sunday at 4 AM via cron schedule
    """
    
    try:
        logger.info(f"Starting cleanup of resolved alerts older than {days} days")
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Delete old resolved alerts
        old_alerts = Alert.objects.filter(
            status='resolved',
            resolved_at__lt=cutoff_date
        )
        alerts_count = old_alerts.count()
        old_alerts.delete()
        
        logger.info(f"Alert cleanup completed: {alerts_count} old alerts deleted")
        
        return {
            'success': True,
            'alerts_deleted': alerts_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Alert cleanup failed: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True)
def cleanup_old_health_results(days=7):
    """
    Clean up old health check results
    Runs daily at 4 AM via cron schedule
    """
    
    try:
        logger.info(f"Starting cleanup of health check results older than {days} days")
        
        health_checker = HealthChecker()
        deleted_count = health_checker.cleanup_old_results(days)
        
        logger.info(f"Health results cleanup completed: {deleted_count} old results deleted")
        
        return {
            'success': True,
            'results_deleted': deleted_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health results cleanup failed: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=1)
def generate_monitoring_report(self):
    """
    Generate daily monitoring summary report
    Runs daily at 8 AM via cron schedule
    """
    
    try:
        logger.info("Starting monitoring report generation")
        
        # Calculate time ranges
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        
        # Collect statistics
        metrics_collected = PerformanceMetric.objects.filter(
            timestamp__gte=yesterday
        ).count()
        
        alerts_triggered = Alert.objects.filter(
            triggered_at__gte=yesterday
        ).count()
        
        alerts_resolved = Alert.objects.filter(
            resolved_at__gte=yesterday
        ).count()
        
        health_checks_run = HealthCheckResult.objects.filter(
            executed_at__gte=yesterday
        ).count()
        
        health_checks_failed = HealthCheckResult.objects.filter(
            executed_at__gte=yesterday,
            status__in=['warning', 'critical']
        ).count()
        
        anomalies_detected = PerformanceMetric.objects.filter(
            timestamp__gte=yesterday,
            is_anomaly=True
        ).count()
        
        # Generate report
        report = {
            'date': yesterday.date().isoformat(),
            'period': '24_hours',
            'metrics': {
                'metrics_collected': metrics_collected,
                'anomalies_detected': anomalies_detected,
            },
            'alerts': {
                'alerts_triggered': alerts_triggered,
                'alerts_resolved': alerts_resolved,
                'open_alerts': Alert.objects.filter(status='open').count(),
            },
            'health_checks': {
                'checks_run': health_checks_run,
                'checks_failed': health_checks_failed,
                'success_rate': round((health_checks_run - health_checks_failed) / health_checks_run * 100, 2) if health_checks_run > 0 else 0
            },
            'system_status': 'healthy' if health_checks_failed == 0 and alerts_triggered == 0 else 'degraded' if health_checks_failed < 5 else 'critical',
            'generated_at': now.isoformat()
        }
        
        logger.info(f"Monitoring report generated for {yesterday.date()}")
        
        # Here you could store the report or send it via email/notification
        # For now, we'll just return it
        
        return {
            'success': True,
            'report': report,
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Monitoring report generation failed: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True)
def test_notification_channels(self):
    """
    Test all configured notification channels
    Runs weekly on Monday at 9 AM via cron schedule
    """
    
    try:
        logger.info("Starting notification channel tests")
        
        from .models import NotificationChannel
        
        alert_manager = AlertManager()
        channels = NotificationChannel.objects.filter(is_active=True)
        
        test_results = []
        
        for channel in channels:
            try:
                # Create a test alert
                from .models import AlertRule, AlertSeverity
                
                test_alert = Alert(
                    id='test-alert-' + str(timezone.now().timestamp()),
                    title=f"Test Alert for {channel.name}",
                    description="This is a test alert to verify notification channel functionality.",
                    severity=AlertSeverity.INFO,
                    component='monitoring_system',
                    metric_value=0,
                    threshold_value=0,
                    triggered_at=timezone.now(),
                    status='open'
                )
                
                # Send test notification
                success = alert_manager._send_notification(channel, test_alert)
                
                test_results.append({
                    'channel_name': channel.name,
                    'channel_type': channel.channel_type,
                    'success': success
                })
                
                logger.info(f"Notification test for {channel.name}: {'SUCCESS' if success else 'FAILED'}")
                
            except Exception as e:
                test_results.append({
                    'channel_name': channel.name,
                    'channel_type': channel.channel_type,
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"Notification test for {channel.name} failed: {e}")
        
        successful_tests = sum(1 for result in test_results if result['success'])
        
        logger.info(f"Notification channel tests completed: {successful_tests}/{len(test_results)} successful")
        
        return {
            'success': True,
            'channels_tested': len(test_results),
            'successful_tests': successful_tests,
            'test_results': test_results,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Notification channel testing failed: {e}")
        return {'success': False, 'error': str(e)}


# Periodic task definitions for celery beat
# Add this to your CELERY_BEAT_SCHEDULE in settings.py:
"""
CELERY_BEAT_SCHEDULE = {
    # Performance monitoring
    'collect-performance-metrics': {
        'task': 'monitoring.tasks.collect_performance_metrics',
        'schedule': 300.0,  # Every 5 minutes
    },
    'evaluate-alerts': {
        'task': 'monitoring.tasks.evaluate_alerts',
        'schedule': 120.0,  # Every 2 minutes
    },
    'run-health-checks': {
        'task': 'monitoring.tasks.run_health_checks',
        'schedule': 300.0,  # Every 5 minutes
    },
    'detect-anomalies': {
        'task': 'monitoring.tasks.detect_anomalies',
        'schedule': 600.0,  # Every 10 minutes
    },
    
    # Daily tasks
    'calculate-performance-baselines': {
        'task': 'monitoring.tasks.calculate_performance_baselines',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-metrics': {
        'task': 'monitoring.tasks.cleanup_old_metrics',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'cleanup-old-health-results': {
        'task': 'monitoring.tasks.cleanup_old_health_results',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    'generate-monitoring-report': {
        'task': 'monitoring.tasks.generate_monitoring_report',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    
    # Weekly tasks
    'cleanup-old-alerts': {
        'task': 'monitoring.tasks.cleanup_old_alerts',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Sunday at 4 AM
    },
    'test-notification-channels': {
        'task': 'monitoring.tasks.test_notification_channels',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday at 9 AM
    },
}
"""
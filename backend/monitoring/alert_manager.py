"""
Alert Management System
Handles alert generation, escalation, and notification
"""

import json
import logging
import smtplib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model

from .models import (
    Alert, AlertRule, AlertSeverity, AlertStatus,
    NotificationChannel, PerformanceMetric
)

User = get_user_model()
logger = logging.getLogger(__name__)


class AlertManager:
    """Comprehensive alert management and notification system"""
    
    def __init__(self):
        self.notification_handlers = {
            'email': self._send_email_notification,
            'slack': self._send_slack_notification,
            'webhook': self._send_webhook_notification,
            'discord': self._send_discord_notification,
            'teams': self._send_teams_notification,
        }
    
    def evaluate_alert_rules(self) -> List[Alert]:
        """Evaluate all active alert rules against recent metrics"""
        
        logger.info("Evaluating alert rules")
        triggered_alerts = []
        
        active_rules = AlertRule.objects.filter(is_active=True)
        
        for rule in active_rules:
            try:
                alerts = self._evaluate_single_rule(rule)
                triggered_alerts.extend(alerts)
                
                if alerts:
                    logger.info(f"Rule '{rule.name}' triggered {len(alerts)} alerts")
                
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.name}': {e}")
        
        logger.info(f"Alert evaluation complete: {len(triggered_alerts)} alerts triggered")
        return triggered_alerts
    
    def _evaluate_single_rule(self, rule: AlertRule) -> List[Alert]:
        """Evaluate a single alert rule"""
        
        # Check cooldown period
        if self._is_in_cooldown(rule):
            return []
        
        # Get recent metrics matching the rule
        lookback_time = timezone.now() - timedelta(seconds=rule.threshold_duration)
        
        metrics_query = PerformanceMetric.objects.filter(
            name=rule.metric_name,
            category=rule.metric_category,
            timestamp__gte=lookback_time
        )
        
        if rule.component_filter:
            metrics_query = metrics_query.filter(component=rule.component_filter)
        
        recent_metrics = list(metrics_query.order_by('-timestamp'))
        
        if not recent_metrics:
            return []
        
        # Check if condition is met for the duration
        violating_metrics = []
        for metric in recent_metrics:
            if rule.check_condition(metric.value):
                violating_metrics.append(metric)
            else:
                break  # Condition not continuously met
        
        # Check if violation duration threshold is met
        if violating_metrics:
            violation_duration = violating_metrics[0].timestamp - violating_metrics[-1].timestamp
            
            if violation_duration.total_seconds() >= rule.threshold_duration:
                # Create alert
                alert = self._create_alert(rule, violating_metrics[0])
                return [alert]
        
        return []
    
    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Check if rule is in cooldown period"""
        
        if not rule.last_triggered:
            return False
        
        cooldown_end = rule.last_triggered + timedelta(seconds=rule.cooldown_period)
        return timezone.now() < cooldown_end
    
    def _create_alert(self, rule: AlertRule, triggering_metric: PerformanceMetric) -> Alert:
        """Create a new alert"""
        
        # Check for existing open alert for this rule
        existing_alert = Alert.objects.filter(
            alert_rule=rule,
            status=AlertStatus.OPEN
        ).first()
        
        if existing_alert:
            # Update existing alert with new metric data
            existing_alert.metric_value = triggering_metric.value
            existing_alert.metadata['last_update'] = timezone.now().isoformat()
            existing_alert.metadata['update_count'] = existing_alert.metadata.get('update_count', 0) + 1
            existing_alert.save()
            return existing_alert
        
        # Create new alert
        alert = Alert.objects.create(
            alert_rule=rule,
            severity=rule.severity,
            title=f"{rule.name}: {rule.metric_name} {rule.threshold_operator} {rule.threshold_value}",
            description=self._generate_alert_description(rule, triggering_metric),
            metric_value=triggering_metric.value,
            threshold_value=rule.threshold_value,
            component=triggering_metric.component,
            tags=triggering_metric.tags,
            metadata={
                'triggering_metric_id': str(triggering_metric.id),
                'rule_configuration': {
                    'threshold_operator': rule.threshold_operator,
                    'threshold_duration': rule.threshold_duration,
                    'cooldown_period': rule.cooldown_period,
                },
                'created_at': timezone.now().isoformat()
            }
        )
        
        # Update rule's last triggered time
        rule.last_triggered = timezone.now()
        rule.save()
        
        # Send notifications
        self._send_alert_notifications(alert)
        
        logger.warning(f"Alert created: {alert.title} (ID: {alert.id})")
        
        return alert
    
    def _generate_alert_description(self, rule: AlertRule, metric: PerformanceMetric) -> str:
        """Generate descriptive alert message"""
        
        return (
            f"Metric '{rule.metric_name}' on component '{metric.component}' "
            f"has value {metric.value} {metric.unit}, which is {rule.threshold_operator} "
            f"the threshold of {rule.threshold_value} {metric.unit}. "
            f"This condition has been met for at least {rule.threshold_duration} seconds."
        )
    
    def _send_alert_notifications(self, alert: Alert) -> None:
        """Send notifications for an alert"""
        
        try:
            # Get notification channels for this alert
            channels = self._get_notification_channels(alert)
            
            for channel in channels:
                if channel.should_notify(alert):
                    self._send_notification(channel, alert)
            
        except Exception as e:
            logger.error(f"Error sending notifications for alert {alert.id}: {e}")
    
    def _get_notification_channels(self, alert: Alert) -> List[NotificationChannel]:
        """Get appropriate notification channels for alert"""
        
        # Get channels from alert rule configuration
        rule_channels = alert.alert_rule.notification_channels
        
        channels = NotificationChannel.objects.filter(
            is_active=True,
            name__in=rule_channels
        )
        
        # If no specific channels configured, get default channels
        if not channels.exists():
            channels = NotificationChannel.objects.filter(
                is_active=True,
                severity_filter__isnull=True  # Default channels
            )
        
        return list(channels)
    
    def _send_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send notification through specific channel"""
        
        try:
            handler = self.notification_handlers.get(channel.channel_type)
            if not handler:
                logger.error(f"No handler for channel type: {channel.channel_type}")
                return False
            
            # Check rate limiting
            if self._is_rate_limited(channel):
                logger.warning(f"Channel {channel.name} is rate limited")
                return False
            
            # Send notification
            success = handler(channel, alert)
            
            if success:
                # Update channel usage
                channel.last_used = timezone.now()
                channel.save()
                
                # Track notification in alert
                alert.notifications_sent.append({
                    'channel': channel.name,
                    'channel_type': channel.channel_type,
                    'sent_at': timezone.now().isoformat(),
                    'success': True
                })
                alert.save()
                
                logger.info(f"Notification sent via {channel.name} for alert {alert.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending notification via {channel.name}: {e}")
            return False
    
    def _is_rate_limited(self, channel: NotificationChannel) -> bool:
        """Check if channel is rate limited"""
        
        if not channel.last_used:
            return False
        
        time_window = timezone.now() - timedelta(seconds=channel.rate_limit_period)
        
        # Count recent notifications for this channel
        recent_count = Alert.objects.filter(
            triggered_at__gte=time_window,
            notifications_sent__icontains=channel.name
        ).count()
        
        return recent_count >= channel.rate_limit_count
    
    def _send_email_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send email notification"""
        
        try:
            config = channel.configuration
            
            # Email configuration
            smtp_server = config.get('smtp_server', 'localhost')
            smtp_port = config.get('smtp_port', 587)
            username = config.get('username')
            password = config.get('password')
            recipients = config.get('recipients', [])
            
            if not recipients:
                logger.error(f"No recipients configured for email channel {channel.name}")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = config.get('from_address', 'es-nl2dsl@localhost')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[{alert.severity.upper()}] {alert.title}"
            
            # Email body
            body = self._format_alert_for_email(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)
                
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _send_slack_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Slack notification"""
        
        try:
            config = channel.configuration
            webhook_url = config.get('webhook_url')
            
            if not webhook_url:
                logger.error(f"No webhook URL configured for Slack channel {channel.name}")
                return False
            
            # Format message
            color_map = {
                AlertSeverity.INFO: 'good',
                AlertSeverity.WARNING: 'warning',
                AlertSeverity.ERROR: 'danger',
                AlertSeverity.CRITICAL: 'danger'
            }
            
            payload = {
                'attachments': [{
                    'color': color_map.get(alert.severity, 'warning'),
                    'title': alert.title,
                    'text': alert.description,
                    'fields': [
                        {
                            'title': 'Severity',
                            'value': alert.severity.upper(),
                            'short': True
                        },
                        {
                            'title': 'Component',
                            'value': alert.component,
                            'short': True
                        },
                        {
                            'title': 'Current Value',
                            'value': f"{alert.metric_value} (threshold: {alert.threshold_value})",
                            'short': True
                        },
                        {
                            'title': 'Triggered At',
                            'value': alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                            'short': True
                        }
                    ],
                    'ts': alert.triggered_at.timestamp()
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False
    
    def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send generic webhook notification"""
        
        try:
            config = channel.configuration
            url = config.get('url')
            method = config.get('method', 'POST')
            headers = config.get('headers', {})
            
            if not url:
                logger.error(f"No URL configured for webhook channel {channel.name}")
                return False
            
            # Prepare payload
            payload = {
                'alert_id': str(alert.id),
                'alert_rule': alert.alert_rule.name,
                'severity': alert.severity,
                'status': alert.status,
                'title': alert.title,
                'description': alert.description,
                'metric_value': alert.metric_value,
                'threshold_value': alert.threshold_value,
                'component': alert.component,
                'triggered_at': alert.triggered_at.isoformat(),
                'tags': alert.tags,
                'metadata': alert.metadata
            }
            
            # Send webhook
            if method.upper() == 'POST':
                response = requests.post(url, json=payload, headers=headers, timeout=10)
            else:
                response = requests.get(url, params=payload, headers=headers, timeout=10)
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
            return False
    
    def _send_discord_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Discord notification"""
        
        try:
            config = channel.configuration
            webhook_url = config.get('webhook_url')
            
            if not webhook_url:
                logger.error(f"No webhook URL configured for Discord channel {channel.name}")
                return False
            
            # Format message for Discord
            color_map = {
                AlertSeverity.INFO: 0x3498db,    # Blue
                AlertSeverity.WARNING: 0xf39c12, # Orange
                AlertSeverity.ERROR: 0xe74c3c,   # Red
                AlertSeverity.CRITICAL: 0x8e44ad # Purple
            }
            
            payload = {
                'embeds': [{
                    'title': alert.title,
                    'description': alert.description,
                    'color': color_map.get(alert.severity, 0xf39c12),
                    'fields': [
                        {
                            'name': 'Severity',
                            'value': alert.severity.upper(),
                            'inline': True
                        },
                        {
                            'name': 'Component',
                            'value': alert.component,
                            'inline': True
                        },
                        {
                            'name': 'Current Value',
                            'value': f"{alert.metric_value} (threshold: {alert.threshold_value})",
                            'inline': True
                        }
                    ],
                    'timestamp': alert.triggered_at.isoformat(),
                    'footer': {
                        'text': 'ES-NL2DSL Monitoring'
                    }
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False
    
    def _send_teams_notification(self, channel: NotificationChannel, alert: Alert) -> bool:
        """Send Microsoft Teams notification"""
        
        try:
            config = channel.configuration
            webhook_url = config.get('webhook_url')
            
            if not webhook_url:
                logger.error(f"No webhook URL configured for Teams channel {channel.name}")
                return False
            
            # Format message for Teams
            color_map = {
                AlertSeverity.INFO: '0078d4',
                AlertSeverity.WARNING: 'ff8c00',
                AlertSeverity.ERROR: 'd13438',
                AlertSeverity.CRITICAL: '8764b8'
            }
            
            payload = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'summary': alert.title,
                'themeColor': color_map.get(alert.severity, 'ff8c00'),
                'sections': [{
                    'activityTitle': alert.title,
                    'activitySubtitle': f"Severity: {alert.severity.upper()}",
                    'text': alert.description,
                    'facts': [
                        {
                            'name': 'Component',
                            'value': alert.component
                        },
                        {
                            'name': 'Current Value',
                            'value': f"{alert.metric_value} (threshold: {alert.threshold_value})"
                        },
                        {
                            'name': 'Triggered At',
                            'value': alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                        }
                    ]
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}")
            return False
    
    def _format_alert_for_email(self, alert: Alert) -> str:
        """Format alert for email body"""
        
        html_template = """
        <html>
        <body>
            <h2 style="color: {color};">[{severity}] {title}</h2>
            <p><strong>Description:</strong> {description}</p>
            <p><strong>Component:</strong> {component}</p>
            <p><strong>Current Value:</strong> {metric_value} (threshold: {threshold_value})</p>
            <p><strong>Triggered At:</strong> {triggered_at}</p>
            
            {tags_section}
            
            <hr>
            <p><small>This alert was generated by the ES-NL2DSL monitoring system.</small></p>
        </body>
        </html>
        """
        
        color_map = {
            AlertSeverity.INFO: '#3498db',
            AlertSeverity.WARNING: '#f39c12',
            AlertSeverity.ERROR: '#e74c3c',
            AlertSeverity.CRITICAL: '#8e44ad'
        }
        
        tags_section = ""
        if alert.tags:
            tags_section = "<p><strong>Tags:</strong> " + ", ".join([f"{k}={v}" for k, v in alert.tags.items()]) + "</p>"
        
        return html_template.format(
            color=color_map.get(alert.severity, '#f39c12'),
            severity=alert.severity.upper(),
            title=alert.title,
            description=alert.description,
            component=alert.component,
            metric_value=alert.metric_value,
            threshold_value=alert.threshold_value,
            triggered_at=alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            tags_section=tags_section
        )
    
    def auto_resolve_alerts(self) -> List[Alert]:
        """Auto-resolve alerts when conditions are no longer met"""
        
        logger.info("Checking for auto-resolvable alerts")
        resolved_alerts = []
        
        # Get open alerts that might be resolved
        open_alerts = Alert.objects.filter(status=AlertStatus.OPEN)
        
        for alert in open_alerts:
            try:
                if self._should_auto_resolve(alert):
                    alert.resolve(comment="Auto-resolved: condition no longer met")
                    resolved_alerts.append(alert)
                    logger.info(f"Auto-resolved alert: {alert.title}")
                
            except Exception as e:
                logger.error(f"Error checking auto-resolve for alert {alert.id}: {e}")
        
        return resolved_alerts
    
    def _should_auto_resolve(self, alert: Alert) -> bool:
        """Check if alert should be auto-resolved"""
        
        rule = alert.alert_rule
        
        # Get recent metrics
        recent_metrics = PerformanceMetric.objects.filter(
            name=rule.metric_name,
            component=alert.component,
            timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('-timestamp')[:5]
        
        if not recent_metrics:
            return False
        
        # Check if all recent metrics are within threshold
        for metric in recent_metrics:
            if rule.check_condition(metric.value):
                return False  # Condition still being violated
        
        return True
    
    def escalate_alerts(self) -> List[Alert]:
        """Escalate unacknowledged alerts"""
        
        logger.info("Checking for alerts to escalate")
        escalated_alerts = []
        
        # Get unacknowledged alerts older than escalation threshold
        escalation_threshold = timezone.now() - timedelta(hours=1)
        
        alerts_to_escalate = Alert.objects.filter(
            status=AlertStatus.OPEN,
            triggered_at__lt=escalation_threshold,
            escalation_level=0
        )
        
        for alert in alerts_to_escalate:
            try:
                escalation_config = alert.alert_rule.escalation_rules
                
                if escalation_config and 'escalation_channels' in escalation_config:
                    # Send escalated notifications
                    escalation_channels = escalation_config['escalation_channels']
                    
                    for channel_name in escalation_channels:
                        try:
                            channel = NotificationChannel.objects.get(
                                name=channel_name,
                                is_active=True
                            )
                            self._send_escalation_notification(channel, alert)
                            
                        except NotificationChannel.DoesNotExist:
                            logger.warning(f"Escalation channel not found: {channel_name}")
                    
                    # Update alert escalation level
                    alert.escalation_level += 1
                    alert.metadata['escalated_at'] = timezone.now().isoformat()
                    alert.save()
                    
                    escalated_alerts.append(alert)
                    logger.warning(f"Escalated alert: {alert.title}")
                
            except Exception as e:
                logger.error(f"Error escalating alert {alert.id}: {e}")
        
        return escalated_alerts
    
    def _send_escalation_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send escalation notification"""
        
        # Modify alert title to indicate escalation
        original_title = alert.title
        alert.title = f"[ESCALATED] {alert.title}"
        alert.description = f"ESCALATION: This alert has not been acknowledged.\n\n{alert.description}"
        
        # Send notification
        self._send_notification(channel, alert)
        
        # Restore original title
        alert.title = original_title
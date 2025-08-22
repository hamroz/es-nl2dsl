from django.db import models
from django.contrib.auth import get_user_model
import uuid
from django.utils import timezone

User = get_user_model()


class CustomMetric(models.Model):
    """Custom analytics metrics defined by users."""
    
    VISUALIZATION_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('number', 'Single Number'),
        ('gauge', 'Gauge'),
        ('table', 'Table'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField()
    
    # Metric configuration
    query = models.TextField(help_text="SQL or Elasticsearch query to fetch data")
    visualization_type = models.CharField(max_length=20, choices=VISUALIZATION_TYPES)
    refresh_interval = models.PositiveIntegerField(default=300, help_text="Refresh interval in seconds")
    
    # Access control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_metrics')
    tenant_id = models.UUIDField(null=True, blank=True)
    is_public = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_executed = models.DateTimeField(null=True, blank=True)
    execution_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'analytics_custom_metrics'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['created_by', 'is_active']),
            models.Index(fields=['is_public', 'is_active']),
        ]
    
    def __str__(self):
        return self.name


class MetricData(models.Model):
    """Cached metric data results."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    metric = models.ForeignKey(CustomMetric, on_delete=models.CASCADE, related_name='data_points')
    
    # Data
    timestamp = models.DateTimeField(auto_now_add=True)
    data = models.JSONField(help_text="Metric result data")
    current_value = models.FloatField(null=True, blank=True, help_text="Single numeric value for simple metrics")
    
    # Execution metadata
    execution_time_ms = models.PositiveIntegerField()
    record_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'analytics_metric_data'
        indexes = [
            models.Index(fields=['metric', 'timestamp']),
        ]
        ordering = ['-timestamp']


class AnalyticsSnapshot(models.Model):
    """Periodic snapshots of system analytics."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    active_users_24h = models.PositiveIntegerField(default=0)
    new_users_7d = models.PositiveIntegerField(default=0)
    user_growth_rate = models.FloatField(default=0.0)
    users_by_role = models.JSONField(default=dict)
    
    # Query metrics
    total_queries = models.PositiveIntegerField(default=0)
    queries_24h = models.PositiveIntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)
    success_rate = models.FloatField(default=100.0)
    queries_by_method = models.JSONField(default=dict)
    
    # Security metrics
    failed_logins_24h = models.PositiveIntegerField(default=0)
    locked_accounts = models.PositiveIntegerField(default=0)
    security_events = models.PositiveIntegerField(default=0)
    threat_level = models.CharField(max_length=10, default='low')
    
    # System metrics
    uptime_percentage = models.FloatField(default=100.0)
    avg_cpu_usage = models.FloatField(default=0.0)
    memory_usage_gb = models.FloatField(default=0.0)
    disk_usage_percentage = models.FloatField(default=0.0)
    active_sessions = models.PositiveIntegerField(default=0)
    error_rate = models.FloatField(default=0.0)
    
    # Business metrics
    tenant_count = models.PositiveIntegerField(default=0)
    workspace_count = models.PositiveIntegerField(default=0)
    data_processed_gb = models.FloatField(default=0.0)
    export_count_24h = models.PositiveIntegerField(default=0)
    
    # Additional data
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'analytics_snapshots'
        indexes = [
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']


class AlertRule(models.Model):
    """Configurable alerts for metric thresholds."""
    
    ALERT_TYPES = [
        ('threshold', 'Threshold Alert'),
        ('trend', 'Trend Alert'),
        ('anomaly', 'Anomaly Detection'),
    ]
    
    OPERATORS = [
        ('gt', 'Greater Than'),
        ('lt', 'Less Than'),
        ('eq', 'Equal To'),
        ('gte', 'Greater Than or Equal'),
        ('lte', 'Less Than or Equal'),
    ]
    
    SEVERITIES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Alert configuration
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    metric_name = models.CharField(max_length=200, help_text="Name of metric to monitor")
    operator = models.CharField(max_length=10, choices=OPERATORS)
    threshold_value = models.FloatField()
    severity = models.CharField(max_length=20, choices=SEVERITIES)
    
    # Notification settings
    notification_channels = models.JSONField(default=list, help_text="List of notification channels")
    cooldown_minutes = models.PositiveIntegerField(default=60, help_text="Cooldown period between alerts")
    
    # Access control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    tenant_id = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'analytics_alert_rules'
        indexes = [
            models.Index(fields=['tenant_id', 'is_active']),
            models.Index(fields=['metric_name', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.metric_name} {self.operator} {self.threshold_value}"


class Alert(models.Model):
    """Alert instances when rules are triggered."""
    
    STATUSES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    
    # Alert details
    status = models.CharField(max_length=20, choices=STATUSES, default='active')
    current_value = models.FloatField()
    message = models.TextField()
    
    # Timeline
    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Additional context
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'analytics_alerts'
        indexes = [
            models.Index(fields=['rule', 'status']),
            models.Index(fields=['triggered_at']),
        ]
        ordering = ['-triggered_at']
    
    def acknowledge(self, user):
        """Mark alert as acknowledged."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
    
    def resolve(self):
        """Mark alert as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save()
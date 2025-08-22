"""
Performance Monitoring and Alerting Models
Provides comprehensive system monitoring and alerting capabilities
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import json

User = get_user_model()


class MetricCategory(models.TextChoices):
    """Categories of system metrics"""
    SYSTEM = 'system', 'System Resources'
    DATABASE = 'database', 'Database Performance'
    ELASTICSEARCH = 'elasticsearch', 'Elasticsearch'
    APPLICATION = 'application', 'Application Performance'
    SECURITY = 'security', 'Security Metrics'
    NETWORK = 'network', 'Network Performance'
    CUSTOM = 'custom', 'Custom Metrics'


class AlertSeverity(models.TextChoices):
    """Alert severity levels"""
    INFO = 'info', 'Information'
    WARNING = 'warning', 'Warning'
    ERROR = 'error', 'Error'
    CRITICAL = 'critical', 'Critical'


class AlertStatus(models.TextChoices):
    """Alert status states"""
    OPEN = 'open', 'Open'
    ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
    RESOLVED = 'resolved', 'Resolved'
    SUPPRESSED = 'suppressed', 'Suppressed'


class PerformanceMetric(models.Model):
    """Store performance metrics with time series data"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metric identification
    name = models.CharField(max_length=100, help_text="Metric name (e.g., cpu_usage)")
    category = models.CharField(max_length=50, choices=MetricCategory.choices)
    component = models.CharField(max_length=100, help_text="System component (e.g., web_server)")
    
    # Metric value and metadata
    value = models.FloatField(help_text="Numeric value of the metric")
    unit = models.CharField(max_length=20, help_text="Unit of measurement (%, ms, MB, etc.)")
    tags = models.JSONField(default=dict, help_text="Additional tags for filtering")
    
    # Timing
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    collection_interval = models.PositiveIntegerField(default=60, help_text="Collection interval in seconds")
    
    # Quality indicators
    is_anomaly = models.BooleanField(default=False, help_text="Flagged as anomalous")
    confidence_score = models.FloatField(default=1.0, help_text="Confidence in measurement (0-1)")
    
    class Meta:
        db_table = 'monitoring_metrics'
        indexes = [
            models.Index(fields=['name', 'timestamp']),
            models.Index(fields=['category', 'timestamp']),
            models.Index(fields=['component', 'timestamp']),
            models.Index(fields=['is_anomaly', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.name}: {self.value} {self.unit} at {self.timestamp}"


class AlertRule(models.Model):
    """Define alerting rules for performance metrics"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Rule identification
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Rule conditions
    metric_name = models.CharField(max_length=100, help_text="Target metric name")
    metric_category = models.CharField(max_length=50, choices=MetricCategory.choices)
    component_filter = models.CharField(max_length=100, blank=True, help_text="Component filter (optional)")
    
    # Threshold conditions
    threshold_operator = models.CharField(max_length=10, choices=[
        ('gt', 'Greater than'),
        ('gte', 'Greater than or equal'),
        ('lt', 'Less than'),
        ('lte', 'Less than or equal'),
        ('eq', 'Equal to'),
        ('ne', 'Not equal to'),
    ])
    threshold_value = models.FloatField()
    threshold_duration = models.PositiveIntegerField(default=300, help_text="Threshold duration in seconds")
    
    # Alert configuration
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices, default=AlertSeverity.WARNING)
    cooldown_period = models.PositiveIntegerField(default=1800, help_text="Cooldown in seconds before re-alerting")
    
    # Notification settings
    notification_channels = models.JSONField(default=list, help_text="List of notification channels")
    escalation_rules = models.JSONField(default=dict, help_text="Escalation configuration")
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'monitoring_alert_rules'
        indexes = [
            models.Index(fields=['metric_name', 'is_active']),
            models.Index(fields=['metric_category', 'is_active']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.severity})"
    
    def check_condition(self, metric_value: float) -> bool:
        """Check if metric value meets alert condition"""
        operators = {
            'gt': lambda a, b: a > b,
            'gte': lambda a, b: a >= b,
            'lt': lambda a, b: a < b,
            'lte': lambda a, b: a <= b,
            'eq': lambda a, b: a == b,
            'ne': lambda a, b: a != b,
        }
        
        operator_func = operators.get(self.threshold_operator)
        if operator_func:
            return operator_func(metric_value, self.threshold_value)
        return False


class Alert(models.Model):
    """Store active and historical alerts"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Alert identification
    alert_rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    status = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.OPEN)
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices)
    
    # Alert details
    title = models.CharField(max_length=200)
    description = models.TextField()
    metric_value = models.FloatField(help_text="Value that triggered the alert")
    threshold_value = models.FloatField(help_text="Threshold that was exceeded")
    
    # Context information
    component = models.CharField(max_length=100)
    tags = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict, help_text="Additional context data")
    
    # Timing
    triggered_at = models.DateTimeField(default=timezone.now)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Assignment
    acknowledged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acknowledged_alerts'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_alerts'
    )
    
    # Notification tracking
    notifications_sent = models.JSONField(default=list, help_text="Track sent notifications")
    escalation_level = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'monitoring_alerts'
        indexes = [
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['triggered_at']),
            models.Index(fields=['alert_rule', 'status']),
            models.Index(fields=['component', 'status']),
        ]
        ordering = ['-triggered_at']
    
    def __str__(self):
        return f"{self.title} ({self.severity} - {self.status})"
    
    @property
    def is_open(self):
        return self.status == AlertStatus.OPEN
    
    @property
    def duration(self):
        """Get alert duration"""
        end_time = self.resolved_at or timezone.now()
        return end_time - self.triggered_at
    
    def acknowledge(self, user: User, comment: str = ""):
        """Acknowledge the alert"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        
        if comment:
            self.metadata['acknowledgment_comment'] = comment
        
        self.save()
    
    def resolve(self, user: User = None, comment: str = ""):
        """Resolve the alert"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = timezone.now()
        
        if user:
            self.metadata['resolved_by'] = str(user.id)
        if comment:
            self.metadata['resolution_comment'] = comment
        
        self.save()


class NotificationChannel(models.Model):
    """Configure notification channels for alerts"""
    
    CHANNEL_TYPES = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('webhook', 'Webhook'),
        ('sms', 'SMS'),
        ('discord', 'Discord'),
        ('teams', 'Microsoft Teams'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Channel identification
    name = models.CharField(max_length=100, unique=True)
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    is_active = models.BooleanField(default=True)
    
    # Configuration
    configuration = models.JSONField(help_text="Channel-specific configuration")
    
    # Filtering
    severity_filter = models.JSONField(
        default=list, 
        help_text="List of severities to notify for (empty = all)"
    )
    component_filter = models.JSONField(
        default=list,
        help_text="List of components to notify for (empty = all)"
    )
    
    # Rate limiting
    rate_limit_count = models.PositiveIntegerField(default=10, help_text="Max notifications per period")
    rate_limit_period = models.PositiveIntegerField(default=3600, help_text="Rate limit period in seconds")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'monitoring_notification_channels'
    
    def __str__(self):
        return f"{self.name} ({self.channel_type})"
    
    def should_notify(self, alert: Alert) -> bool:
        """Check if this channel should notify for the given alert"""
        
        # Check if channel is active
        if not self.is_active:
            return False
        
        # Check severity filter
        if self.severity_filter and alert.severity not in self.severity_filter:
            return False
        
        # Check component filter
        if self.component_filter and alert.component not in self.component_filter:
            return False
        
        return True


class SystemHealthCheck(models.Model):
    """Define system health checks and their results"""
    
    CHECK_TYPES = [
        ('http', 'HTTP Endpoint'),
        ('database', 'Database Query'),
        ('elasticsearch', 'Elasticsearch Health'),
        ('disk_space', 'Disk Space'),
        ('memory', 'Memory Usage'),
        ('process', 'Process Check'),
        ('custom', 'Custom Script'),
    ]
    
    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Check configuration
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    check_type = models.CharField(max_length=20, choices=CHECK_TYPES)
    is_active = models.BooleanField(default=True)
    
    # Check parameters
    configuration = models.JSONField(help_text="Check-specific configuration")
    check_interval = models.PositiveIntegerField(default=300, help_text="Check interval in seconds")
    timeout = models.PositiveIntegerField(default=30, help_text="Check timeout in seconds")
    
    # Thresholds
    warning_threshold = models.FloatField(null=True, blank=True)
    critical_threshold = models.FloatField(null=True, blank=True)
    
    # Current status
    current_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    last_check_time = models.DateTimeField(null=True, blank=True)
    last_success_time = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'monitoring_health_checks'
        indexes = [
            models.Index(fields=['current_status', 'is_active']),
            models.Index(fields=['last_check_time']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.current_status})"


class HealthCheckResult(models.Model):
    """Store health check execution results"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Check reference
    health_check = models.ForeignKey(SystemHealthCheck, on_delete=models.CASCADE, related_name='results')
    
    # Result data
    status = models.CharField(max_length=20, choices=SystemHealthCheck.STATUS_CHOICES)
    response_time = models.FloatField(help_text="Response time in milliseconds")
    value = models.FloatField(null=True, blank=True, help_text="Numeric result value")
    message = models.TextField(blank=True, help_text="Status message or error details")
    
    # Execution details
    executed_at = models.DateTimeField(default=timezone.now)
    execution_duration = models.FloatField(help_text="Execution duration in milliseconds")
    
    # Additional data
    metadata = models.JSONField(default=dict, help_text="Additional result data")
    
    class Meta:
        db_table = 'monitoring_health_check_results'
        indexes = [
            models.Index(fields=['health_check', 'executed_at']),
            models.Index(fields=['status', 'executed_at']),
        ]
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"{self.health_check.name} result: {self.status} at {self.executed_at}"


class PerformanceBaseline(models.Model):
    """Store performance baselines for comparison"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Baseline identification
    metric_name = models.CharField(max_length=100)
    component = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=MetricCategory.choices)
    
    # Statistical data
    baseline_value = models.FloatField(help_text="Baseline/expected value")
    min_value = models.FloatField(help_text="Historical minimum")
    max_value = models.FloatField(help_text="Historical maximum")
    mean_value = models.FloatField(help_text="Historical mean")
    std_deviation = models.FloatField(help_text="Standard deviation")
    
    # Percentiles
    p50 = models.FloatField(help_text="50th percentile")
    p95 = models.FloatField(help_text="95th percentile")
    p99 = models.FloatField(help_text="99th percentile")
    
    # Calculation metadata
    sample_count = models.PositiveIntegerField(help_text="Number of samples used")
    calculation_period_start = models.DateTimeField(help_text="Start of calculation period")
    calculation_period_end = models.DateTimeField(help_text="End of calculation period")
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    # Validity
    is_valid = models.BooleanField(default=True)
    confidence_level = models.FloatField(default=0.95, help_text="Statistical confidence level")
    
    class Meta:
        db_table = 'monitoring_performance_baselines'
        unique_together = ['metric_name', 'component', 'category']
        indexes = [
            models.Index(fields=['metric_name', 'component']),
            models.Index(fields=['calculated_at']),
        ]
    
    def __str__(self):
        return f"Baseline for {self.metric_name} ({self.component}): {self.baseline_value}"
    
    def is_anomaly(self, value: float, sensitivity: float = 2.0) -> bool:
        """Check if a value is anomalous compared to baseline"""
        if self.std_deviation == 0:
            return False  # No variation in baseline
        
        z_score = abs(value - self.mean_value) / self.std_deviation
        return z_score > sensitivity
from rest_framework import serializers
from .models import CustomMetric, MetricData, AlertRule, Alert, AnalyticsSnapshot


class CustomMetricSerializer(serializers.ModelSerializer):
    """Serializer for custom metrics."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    current_value = serializers.SerializerMethodField()
    last_data_point = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomMetric
        fields = [
            'id', 'name', 'description', 'query', 'visualization_type',
            'refresh_interval', 'is_public', 'is_active', 'created_by_username',
            'created_at', 'updated_at', 'last_executed', 'execution_count',
            'current_value', 'last_data_point'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_executed', 'execution_count']
    
    def get_current_value(self, obj):
        """Get the most recent value for this metric."""
        latest_data = obj.data_points.first()
        return latest_data.current_value if latest_data else None
    
    def get_last_data_point(self, obj):
        """Get the most recent data point."""
        latest_data = obj.data_points.first()
        if latest_data:
            return {
                'timestamp': latest_data.timestamp,
                'value': latest_data.current_value,
                'execution_time_ms': latest_data.execution_time_ms
            }
        return None
    
    def validate_query(self, value):
        """Validate the metric query."""
        if not value.strip():
            raise serializers.ValidationError("Query cannot be empty")
        
        # Basic security checks
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
        query_upper = value.upper()
        
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise serializers.ValidationError(f"Query contains forbidden keyword: {keyword}")
        
        return value


class MetricDataSerializer(serializers.ModelSerializer):
    """Serializer for metric data points."""
    
    metric_name = serializers.CharField(source='metric.name', read_only=True)
    
    class Meta:
        model = MetricData
        fields = [
            'id', 'metric_name', 'timestamp', 'data', 'current_value',
            'execution_time_ms', 'record_count'
        ]
        read_only_fields = ['id', 'timestamp']


class AlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for alert rules."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    active_alerts_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertRule
        fields = [
            'id', 'name', 'description', 'alert_type', 'metric_name',
            'operator', 'threshold_value', 'severity', 'notification_channels',
            'cooldown_minutes', 'is_active', 'created_by_username',
            'created_at', 'updated_at', 'last_triggered', 'trigger_count',
            'active_alerts_count'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'last_triggered', 'trigger_count'
        ]
    
    def get_active_alerts_count(self, obj):
        """Get count of active alerts for this rule."""
        return obj.alerts.filter(status='active').count()
    
    def validate_threshold_value(self, value):
        """Validate threshold value is reasonable."""
        if value < 0:
            raise serializers.ValidationError("Threshold value cannot be negative")
        return value
    
    def validate_cooldown_minutes(self, value):
        """Validate cooldown period."""
        if value < 1:
            raise serializers.ValidationError("Cooldown must be at least 1 minute")
        if value > 1440:  # 24 hours
            raise serializers.ValidationError("Cooldown cannot exceed 24 hours")
        return value


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for alerts."""
    
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    rule_severity = serializers.CharField(source='rule.severity', read_only=True)
    acknowledged_by_username = serializers.CharField(source='acknowledged_by.username', read_only=True)
    duration_minutes = serializers.SerializerMethodField()
    
    class Meta:
        model = Alert
        fields = [
            'id', 'rule_name', 'rule_severity', 'status', 'current_value',
            'message', 'triggered_at', 'acknowledged_at', 'acknowledged_by_username',
            'resolved_at', 'metadata', 'duration_minutes'
        ]
        read_only_fields = [
            'id', 'triggered_at', 'acknowledged_at', 'acknowledged_by_username', 'resolved_at'
        ]
    
    def get_duration_minutes(self, obj):
        """Calculate alert duration in minutes."""
        from django.utils import timezone
        
        end_time = obj.resolved_at or timezone.now()
        duration = end_time - obj.triggered_at
        return round(duration.total_seconds() / 60, 1)


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for analytics snapshots."""
    
    class Meta:
        model = AnalyticsSnapshot
        fields = '__all__'
        read_only_fields = ['id', 'timestamp']


class AnalyticsExportSerializer(serializers.Serializer):
    """Serializer for analytics export parameters."""
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('pdf', 'PDF'),
    ]
    
    RANGE_CHOICES = [
        ('1h', 'Last Hour'),
        ('24h', 'Last 24 Hours'),
        ('7d', 'Last 7 Days'),
        ('30d', 'Last 30 Days'),
        ('90d', 'Last 90 Days'),
    ]
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='csv')
    range = serializers.ChoiceField(choices=RANGE_CHOICES, default='7d')
    tenant_id = serializers.UUIDField(required=False, allow_null=True)
    include_trends = serializers.BooleanField(default=True)
    include_raw_data = serializers.BooleanField(default=False)


class MetricTrendSerializer(serializers.Serializer):
    """Serializer for metric trend data."""
    
    date = serializers.DateField()
    value = serializers.FloatField()
    metadata = serializers.JSONField(required=False)


class DashboardSummarySerializer(serializers.Serializer):
    """Serializer for dashboard summary data."""
    
    active_users = serializers.IntegerField()
    queries_today = serializers.IntegerField()
    success_rate = serializers.FloatField()
    threat_level = serializers.ChoiceField(choices=['low', 'medium', 'high'])
    uptime = serializers.FloatField()
    last_updated = serializers.DateTimeField()


class AlertRuleTestSerializer(serializers.Serializer):
    """Serializer for testing alert rules."""
    
    metric_name = serializers.CharField()
    operator = serializers.ChoiceField(choices=AlertRule.OPERATORS)
    threshold_value = serializers.FloatField()
    current_value = serializers.FloatField()
    
    def validate(self, attrs):
        """Validate the test parameters."""
        metric_name = attrs['metric_name']
        operator = attrs['operator']
        threshold = attrs['threshold_value']
        current = attrs['current_value']
        
        # Evaluate the condition
        operators = {
            'gt': current > threshold,
            'lt': current < threshold,
            'eq': current == threshold,
            'gte': current >= threshold,
            'lte': current <= threshold,
        }
        
        attrs['would_trigger'] = operators.get(operator, False)
        return attrs
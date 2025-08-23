from django.db import models
from django.utils import timezone
import uuid

class QueryTask(models.Model):
    """
    Represents a query generation task with status tracking
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    METHOD_CHOICES = [
        ('constrained', 'Constrained Generation'),
        ('rules', 'Rule-based'),
        ('zeroshot', 'Zero-shot'),
    ]
    
    task_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    prompt = models.TextField()
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    index = models.CharField(max_length=100, default='logs_net')
    model = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['method', '-created_at']),
            models.Index(fields=['index', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['task_id']),  # For fast UUID lookups
        ]
    
    def __str__(self):
        return f"QueryTask {self.task_id} - {self.status}"

class GeneratedQuery(models.Model):
    """
    Stores the generated Elasticsearch DSL query and validation results
    """
    VALIDATION_STATUS_CHOICES = [
        ('PASS', 'Pass'),
        ('FAIL', 'Fail'),
    ]
    
    task = models.OneToOneField(QueryTask, on_delete=models.CASCADE, related_name='generated_query')
    elasticsearch_dsl = models.JSONField()
    validation_status = models.CharField(max_length=20, choices=VALIDATION_STATUS_CHOICES)
    validation_errors = models.JSONField(default=list)
    generation_metrics = models.JSONField(default=dict)
    retry_count = models.IntegerField(default=0)
    file_path = models.CharField(max_length=500, blank=True, null=True)  # Path to generated file
    
    class Meta:
        indexes = [
            models.Index(fields=['validation_status']),
            models.Index(fields=['task']),  # Foreign key optimization
        ]
    
    def __str__(self):
        return f"GeneratedQuery for {self.task.task_id}"

class QueryExecution(models.Model):
    """
    Stores query execution results and performance metrics
    """
    task = models.ForeignKey(QueryTask, on_delete=models.CASCADE, related_name='executions')
    executed_at = models.DateTimeField(auto_now_add=True)
    total_hits = models.IntegerField()
    returned_hits = models.IntegerField()
    execution_time_ms = models.IntegerField()
    max_size = models.IntegerField(default=1000)
    results = models.JSONField(default=list)
    aggregations = models.JSONField(default=dict)
    export_csv_path = models.CharField(max_length=500, blank=True, null=True)
    export_json_path = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['task', '-executed_at']),
            models.Index(fields=['-executed_at']),
            models.Index(fields=['total_hits']),
            models.Index(fields=['execution_time_ms']),
        ]
    
    def __str__(self):
        return f"Execution for {self.task.task_id} - {self.total_hits} hits"

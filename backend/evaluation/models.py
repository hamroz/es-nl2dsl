from django.db import models
from django.utils import timezone
import uuid

class EvaluationScenario(models.Model):
    """
    Represents an evaluation scenario with ground truth query
    """
    scenario_id = models.CharField(max_length=50, unique=True)
    prompt = models.TextField()
    description = models.TextField()
    expert_query = models.JSONField()
    expected_result_count = models.IntegerField(default=0)
    index = models.CharField(max_length=100, default='logs_net')
    category = models.CharField(max_length=50, default='general')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['scenario_id']
    
    def __str__(self):
        return f"Scenario {self.scenario_id}: {self.description[:50]}"

class EvaluationRun(models.Model):
    """
    Represents a single evaluation run comparing generated vs expert query
    """
    run_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    scenario = models.ForeignKey(EvaluationScenario, on_delete=models.CASCADE, related_name='runs')
    method = models.CharField(max_length=20)  # constrained, rules, zeroshot
    model = models.CharField(max_length=100, blank=True, null=True)
    
    # Generated query info
    generated_query = models.JSONField()
    generation_time = models.FloatField()
    validation_passed = models.BooleanField()
    validation_errors = models.JSONField(default=list)
    
    # AST comparison metrics
    jaccard_similarity = models.FloatField(null=True, blank=True)
    structural_similarity = models.FloatField(null=True, blank=True)
    
    # Execution comparison metrics  
    expert_result_count = models.IntegerField(null=True, blank=True)
    generated_result_count = models.IntegerField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    
    # Timing info
    run_timestamp = models.DateTimeField(auto_now_add=True)
    execution_time_expert = models.IntegerField(null=True, blank=True)  # ms
    execution_time_generated = models.IntegerField(null=True, blank=True)  # ms
    
    # Status
    status = models.CharField(max_length=20, default='pending')  # pending, running, completed, failed
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-run_timestamp']
    
    def __str__(self):
        return f"Run {self.run_id} - {self.scenario.scenario_id} ({self.method})"

class EvaluationBatch(models.Model):
    """
    Represents a batch evaluation across multiple scenarios
    """
    batch_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    method = models.CharField(max_length=20)
    model = models.CharField(max_length=100, blank=True, null=True)
    
    # Aggregate metrics
    total_scenarios = models.IntegerField(default=0)
    completed_scenarios = models.IntegerField(default=0)
    average_f1_score = models.FloatField(null=True, blank=True)
    average_jaccard_similarity = models.FloatField(null=True, blank=True)
    validation_pass_rate = models.FloatField(null=True, blank=True)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Batch {self.batch_id}: {self.name}"

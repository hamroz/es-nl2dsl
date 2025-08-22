from django.db import models
from django.utils import timezone
import uuid

class SecurityTest(models.Model):
    """
    Represents a security test run with adversarial prompts
    """
    test_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    test_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Test configuration
    method = models.CharField(max_length=20)  # constrained, rules, zeroshot
    model = models.CharField(max_length=100, blank=True, null=True)
    
    # Test results
    total_prompts = models.IntegerField(default=0)
    abstain_count = models.IntegerField(default=0)
    malicious_count = models.IntegerField(default=0)
    valid_count = models.IntegerField(default=0)
    
    # Metrics
    abstain_rate = models.FloatField(null=True, blank=True)
    security_pass_rate = models.FloatField(null=True, blank=True)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')  # pending, running, completed, failed
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Security Test {self.test_id}: {self.test_name}"


class AdversarialPrompt(models.Model):
    """
    Individual adversarial prompt used in security testing
    """
    CATEGORY_CHOICES = [
        ('injection', 'Prompt Injection'),
        ('bypass', 'Security Bypass'),
        ('extraction', 'Data Extraction'),
        ('manipulation', 'Query Manipulation'),
        ('escalation', 'Privilege Escalation'),
        ('other', 'Other')
    ]
    
    prompt_id = models.CharField(max_length=50, unique=True)
    prompt_text = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    severity = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='medium')
    description = models.TextField()
    expected_behavior = models.TextField(help_text="Expected system behavior (abstain, reject, etc.)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['category', 'severity', 'prompt_id']
    
    def __str__(self):
        return f"Prompt {self.prompt_id}: {self.category} ({self.severity})"


class SecurityTestResult(models.Model):
    """
    Result of testing a single adversarial prompt
    """
    result_id = models.CharField(max_length=50, unique=True, default=uuid.uuid4)
    test = models.ForeignKey(SecurityTest, on_delete=models.CASCADE, related_name='results')
    prompt = models.ForeignKey(AdversarialPrompt, on_delete=models.CASCADE)
    
    # Generated response
    generated_query = models.JSONField(null=True, blank=True)
    generation_time = models.FloatField()
    abstained = models.BooleanField(default=False)
    
    # Validation results
    validation_passed = models.BooleanField()
    validation_errors = models.JSONField(default=list)
    
    # Security assessment
    is_malicious = models.BooleanField(default=False)
    security_risk_level = models.CharField(max_length=10, choices=[
        ('none', 'None'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], default='none')
    security_notes = models.TextField(blank=True)
    
    # Timing
    tested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed')
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-tested_at']
        unique_together = ['test', 'prompt']
    
    def __str__(self):
        return f"Result {self.result_id} - {self.prompt.prompt_id}"

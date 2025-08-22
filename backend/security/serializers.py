from rest_framework import serializers
from .models import SecurityTest, AdversarialPrompt, SecurityTestResult

class AdversarialPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdversarialPrompt
        fields = ['prompt_id', 'prompt_text', 'category', 'severity', 
                 'description', 'expected_behavior', 'created_at', 'is_active']

class SecurityTestResultSerializer(serializers.ModelSerializer):
    prompt_id = serializers.CharField(source='prompt.prompt_id', read_only=True)
    prompt_category = serializers.CharField(source='prompt.category', read_only=True)
    prompt_severity = serializers.CharField(source='prompt.severity', read_only=True)
    
    class Meta:
        model = SecurityTestResult
        fields = ['result_id', 'prompt_id', 'prompt_category', 'prompt_severity',
                 'generated_query', 'generation_time', 'abstained', 'validation_passed',
                 'validation_errors', 'is_malicious', 'security_risk_level', 
                 'security_notes', 'tested_at', 'status', 'error_message']

class SecurityTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityTest
        fields = ['test_id', 'test_name', 'description', 'method', 'model',
                 'total_prompts', 'abstain_count', 'malicious_count', 'valid_count',
                 'abstain_rate', 'security_pass_rate', 'started_at', 'completed_at', 'status']

class SecurityTestRequestSerializer(serializers.Serializer):
    test_name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    method = serializers.ChoiceField(choices=['constrained', 'rules', 'zeroshot'])
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    prompt_ids = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        help_text="List of prompt IDs to test. If empty, all active prompts will be used."
    )
    categories = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        help_text="Filter prompts by categories"
    )

class AdversarialPromptCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdversarialPrompt
        fields = ['prompt_id', 'prompt_text', 'category', 'severity', 
                 'description', 'expected_behavior']
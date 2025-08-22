from rest_framework import serializers
from .models import EvaluationScenario, EvaluationRun, EvaluationBatch

class EvaluationScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationScenario
        fields = ['scenario_id', 'prompt', 'description', 'expert_query', 
                 'expected_result_count', 'index', 'category', 'created_at', 'is_active']

class EvaluationRunSerializer(serializers.ModelSerializer):
    scenario_id = serializers.CharField(source='scenario.scenario_id', read_only=True)
    scenario_description = serializers.CharField(source='scenario.description', read_only=True)
    
    class Meta:
        model = EvaluationRun
        fields = ['run_id', 'scenario_id', 'scenario_description', 'method', 'model',
                 'generated_query', 'generation_time', 'validation_passed', 'validation_errors',
                 'jaccard_similarity', 'structural_similarity', 'expert_result_count',
                 'generated_result_count', 'f1_score', 'precision', 'recall',
                 'run_timestamp', 'execution_time_expert', 'execution_time_generated',
                 'status', 'error_message']

class EvaluationBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvaluationBatch
        fields = ['batch_id', 'name', 'description', 'method', 'model',
                 'total_scenarios', 'completed_scenarios', 'average_f1_score',
                 'average_jaccard_similarity', 'validation_pass_rate',
                 'started_at', 'completed_at', 'status']

class RunEvaluationRequestSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=['constrained', 'rules', 'zeroshot'])
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    index = serializers.CharField(max_length=100, required=False)

class BatchEvaluationRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    method = serializers.ChoiceField(choices=['constrained', 'rules', 'zeroshot'])
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    scenario_ids = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        help_text="List of scenario IDs to evaluate. If empty, all active scenarios will be used."
    )
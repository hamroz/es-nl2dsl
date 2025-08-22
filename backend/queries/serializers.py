from rest_framework import serializers
from .models import QueryTask, GeneratedQuery, QueryExecution

class QueryTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryTask
        fields = ['task_id', 'prompt', 'method', 'index', 'model', 'status', 
                 'created_at', 'completed_at', 'error_message']
        read_only_fields = ['task_id', 'status', 'created_at', 'completed_at', 'error_message']

class GeneratedQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedQuery
        fields = ['elasticsearch_dsl', 'validation_status', 'validation_errors', 
                 'generation_metrics', 'retry_count', 'file_path']

class QueryTaskDetailSerializer(serializers.ModelSerializer):
    generated_query = GeneratedQuerySerializer(read_only=True)
    
    class Meta:
        model = QueryTask
        fields = ['task_id', 'prompt', 'method', 'index', 'model', 'status', 
                 'created_at', 'completed_at', 'error_message', 'generated_query']

class QueryExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryExecution
        fields = ['executed_at', 'total_hits', 'returned_hits', 'execution_time_ms',
                 'max_size', 'results', 'aggregations', 'export_csv_path', 'export_json_path']

class QueryGenerationRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(max_length=1000, min_length=10)
    method = serializers.ChoiceField(choices=['constrained', 'rules', 'zeroshot'])
    index = serializers.CharField(max_length=100, default='logs_net')
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
class QueryExecutionRequestSerializer(serializers.Serializer):
    max_size = serializers.IntegerField(min_value=10, max_value=10000, default=1000)
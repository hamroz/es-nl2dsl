from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import get_object_or_404, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
import uuid
import os
import requests
import time
import json
import csv
from authentication.exceptions import ElasticsearchQueryValidator

from .models import QueryTask, GeneratedQuery, QueryExecution
from .serializers import (
    QueryGenerationRequestSerializer, 
    QueryTaskDetailSerializer,
    QueryExecutionRequestSerializer,
    QueryExecutionSerializer
)
from .tasks import generate_query_task, execute_query_task
from .pagination import QueryTaskPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

class QueryGenerationThrottle(UserRateThrottle):
    scope = 'query_generation'

class QueryExecutionThrottle(UserRateThrottle):
    scope = 'query_execution'

class QueryListCreateView(APIView):
    """
    Generate new queries from natural language prompts and list existing queries
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [QueryGenerationThrottle]
    
    @extend_schema(
        request=QueryGenerationRequestSerializer,
        responses={
            202: OpenApiResponse(description="Query generation started successfully"),
            400: OpenApiResponse(description="Invalid request data"),
            401: OpenApiResponse(description="Authentication required"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        description="Generate Elasticsearch DSL query from natural language prompt",
        tags=['Queries'],
        summary="Generate Query from Natural Language"
    )
    def post(self, request):
        serializer = QueryGenerationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Create QueryTask record
        task_id = str(uuid.uuid4())
        task = QueryTask.objects.create(
            task_id=task_id,
            prompt=serializer.validated_data['prompt'],
            method=serializer.validated_data['method'],
            index=serializer.validated_data.get('index', 'logs_net'),
            model=serializer.validated_data.get('model', '')
        )
        
        # Start async query generation
        generate_query_task.delay(task_id, task.prompt, task.method, task.index, task.model)
        
        # Estimated completion time
        estimated_completion = timezone.now() + timezone.timedelta(minutes=2)
        
        return Response({
            'task_id': task_id,
            'status': 'pending',
            'estimated_completion': estimated_completion.isoformat()
        }, status=status.HTTP_202_ACCEPTED)
    
    @extend_schema(
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="Filter by task status"),
            OpenApiParameter('method', OpenApiTypes.STR, description="Filter by generation method"),
            OpenApiParameter('page', OpenApiTypes.INT, description="Page number"),
            OpenApiParameter('page_size', OpenApiTypes.INT, description="Number of items per page"),
        ],
        responses={200: QueryTaskDetailSerializer(many=True)},
        description="List query generation tasks with pagination and filtering",
        tags=['Queries'],
        summary="List Query Tasks"
    )
    def get(self, request):
        """List recent query tasks with pagination, caching, and optimized queries"""
        # Generate cache key based on user and query parameters
        cache_params = {
            'user_id': request.user.id,
            'status': request.query_params.get('status', ''),
            'method': request.query_params.get('method', ''),
            'page': request.query_params.get('page', '1'),
            'page_size': request.query_params.get('page_size', '20'),
        }
        cache_key = f"query_list_{hash(frozenset(cache_params.items()))}"
        
        # Try to get from cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result)
        
        queryset = QueryTask.objects.select_related('generated_query').prefetch_related('executions')
        
        # Apply filters if provided
        if cache_params['status']:
            queryset = queryset.filter(status=cache_params['status'])
        
        if cache_params['method']:
            queryset = queryset.filter(method=cache_params['method'])
        
        # Paginate results
        paginator = QueryTaskPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = QueryTaskDetailSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data).data
            
            # Cache the results for 2 minutes
            cache.set(cache_key, response_data, timeout=120)
            return Response(response_data)
        
        # Fallback for non-paginated response
        serializer = QueryTaskDetailSerializer(queryset, many=True)
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=120)
        return Response(response_data)

class QueryDetailView(APIView):
    """
    Get details of a specific query generation task
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            200: QueryTaskDetailSerializer,
            404: OpenApiResponse(description="Task not found"),
        },
        description="Retrieve details of a specific query generation task",
        tags=['Queries'],
        summary="Get Query Task Details"
    )
    def get(self, request, task_id):
        # Try cache first for completed tasks
        cache_key = f"query_task_{task_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return Response(cached_result)
        
        task = get_object_or_404(
            QueryTask.objects.select_related('generated_query').prefetch_related('executions'), 
            task_id=task_id
        )
        serializer = QueryTaskDetailSerializer(task)
        
        # Format response to match expected API contract
        data = serializer.data
        response_data = {
            'task_id': data['task_id'],
            'status': data['status'],
            'prompt': data['prompt'],
            'method': data['method'],
            'index': data['index'],
            'created_at': data['created_at'],
            'completed_at': data['completed_at'],
            'error_message': data['error_message']
        }
        
        # Add generated query and validation if available
        if data['generated_query']:
            gq = data['generated_query']
            response_data.update({
                'query': gq['elasticsearch_dsl'],
                'validation': {
                    'status': gq['validation_status'],
                    'errors': gq['validation_errors']
                },
                'metrics': gq['generation_metrics']
            })
        
        # Cache completed tasks for longer (10 minutes)
        if task.status in ['completed', 'failed']:
            cache.set(cache_key, response_data, timeout=600)
        else:
            # Cache pending/running tasks for shorter time (30 seconds)
            cache.set(cache_key, response_data, timeout=30)
        
        return Response(response_data)

class QueryExecuteView(APIView):
    """
    Execute a generated query against Elasticsearch
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [QueryExecutionThrottle]
    
    @extend_schema(
        request=QueryExecutionRequestSerializer,
        responses={
            200: OpenApiResponse(description="Query executed successfully"),
            400: OpenApiResponse(description="Invalid request or query validation failed"),
            500: OpenApiResponse(description="Query execution failed"),
        },
        description="Execute a generated Elasticsearch query and return results with export URLs",
        tags=['Queries'],
        summary="Execute Generated Query"
    )
    def post(self, request, task_id):
        task = get_object_or_404(
            QueryTask.objects.select_related('generated_query'), 
            task_id=task_id
        )
        
        # Validate request
        serializer = QueryExecutionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if query is generated and valid
        if not hasattr(task, 'generated_query'):
            return Response({
                'error': 'Query not yet generated'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if task.generated_query.validation_status != 'PASS':
            return Response({
                'error': 'Query validation failed',
                'validation_errors': task.generated_query.validation_errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        max_size = serializer.validated_data['max_size']
        
        # Execute query directly and return results with export URLs
        try:
            result = self._execute_query_direct(
                task_id=task_id,
                query_data=task.generated_query.elasticsearch_dsl,
                index=task.index,
                max_size=max_size
            )
            
            if result.get('status') == 'failed':
                return Response({
                    'error': result.get('error', 'Query execution failed')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(result, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _execute_query_direct(self, task_id: str, query_data: dict, index: str, max_size: int = 1000):
        """
        Direct query execution without Celery (for development)
        """
        try:
            task = QueryTask.objects.get(task_id=task_id)
            
            # Validate query for security before execution
            try:
                ElasticsearchQueryValidator.validate_query(query_data)
            except ValidationError as e:
                return {
                    'task_id': task_id,
                    'status': 'failed',
                    'error': f'Query validation failed: {str(e)}'
                }
            
            # Prepare Elasticsearch query
            es_query = {
                "size": min(max_size, 10000),  # Cap at 10k results for safety
                **query_data
            }
            
            # Execute query against Elasticsearch
            es_url = f"http://{settings.ELASTICSEARCH_HOST}/{index}/_search"
            auth = (settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)
            
            start_time = time.time()
            response = requests.post(
                es_url,
                json=es_query,
                auth=auth,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            execution_time = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                raise RuntimeError(f"Elasticsearch error: {response.text}")
            
            es_result = response.json()
            
            # Extract results
            hits = es_result.get('hits', {})
            total_hits = hits.get('total', {}).get('value', 0)
            documents = hits.get('hits', [])
            returned_hits = len(documents)
            aggregations = es_result.get('aggregations', {})
            
            # Process documents - extract _source and flatten
            processed_results = []
            for doc in documents:
                source = doc.get('_source', {})
                source['_id'] = doc.get('_id')
                source['_score'] = doc.get('_score')
                processed_results.append(source)
            
            # Generate export files
            artifacts_path = settings.ARTIFACTS_PATH / "exports"
            artifacts_path.mkdir(parents=True, exist_ok=True)
            
            # Export as CSV
            csv_path = artifacts_path / f"{task_id}_results.csv"
            if processed_results:
                fieldnames = set()
                for result in processed_results:
                    fieldnames.update(result.keys())
                fieldnames = sorted(list(fieldnames))
                
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for result in processed_results:
                        writer.writerow(result)
            else:
                # Create empty CSV with headers
                with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['No results found'])
            
            # Export as JSON
            json_path = artifacts_path / f"{task_id}_results.json"
            with open(json_path, 'w', encoding='utf-8') as jsonfile:
                json.dump({
                    'total_hits': total_hits,
                    'returned_hits': returned_hits,
                    'execution_time_ms': execution_time,
                    'results': processed_results,
                    'aggregations': aggregations
                }, jsonfile, indent=2, default=str)
            
            # Create QueryExecution record
            execution = QueryExecution.objects.create(
                task=task,
                total_hits=total_hits,
                returned_hits=returned_hits,
                execution_time_ms=execution_time,
                max_size=max_size,
                results=processed_results,
                aggregations=aggregations,
                export_csv_path=str(csv_path),
                export_json_path=str(json_path)
            )
            
            return {
                'task_id': task_id,
                'total_hits': total_hits,
                'returned_hits': returned_hits,
                'took': execution_time,
                'results': processed_results,
                'aggregations': aggregations,
                'export_urls': {
                    'csv': f'/api/v1/queries/{task_id}/export/csv/',
                    'json': f'/api/v1/queries/{task_id}/export/json/'
                }
            }
            
        except Exception as e:
            return {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }

class QueryExportView(APIView):
    """
    Export query results as CSV or JSON
    """
    permission_classes = [IsAuthenticated]
    def get(self, request, task_id, format):
        task = get_object_or_404(
            QueryTask.objects.prefetch_related('executions'), 
            task_id=task_id
        )
        
        # Get the latest execution
        execution = task.executions.first()
        if not execution:
            raise Http404("No execution results found")
        
        if format == 'csv':
            file_path = execution.export_csv_path
            content_type = 'text/csv'
            filename = f'{task_id}_results.csv'
        elif format == 'json':
            file_path = execution.export_json_path
            content_type = 'application/json'
            filename = f'{task_id}_results.json'
        else:
            return Response({'error': 'Invalid format'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not file_path or not os.path.exists(file_path):
            return Response({'error': 'Export file not found'}, status=status.HTTP_404_NOT_FOUND)
        
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

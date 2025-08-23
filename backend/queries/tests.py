import pytest
import json
import uuid
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from freezegun import freeze_time
import responses

from queries.models import QueryTask, GeneratedQuery, QueryExecution
from queries.serializers import (
    QueryGenerationRequestSerializer, 
    QueryTaskDetailSerializer,
    QueryExecutionRequestSerializer,
    QueryExecutionSerializer
)
from queries.tasks import generate_query_task
from tests.factories import (
    UserFactory, 
    AdminUserFactory, 
    QueryTaskFactory, 
    CompletedQueryTaskFactory,
    FailedQueryTaskFactory,
    GeneratedQueryFactory,
    FailedGeneratedQueryFactory,
    QueryExecutionFactory,
    SampleDataMixin
)

User = get_user_model()


@pytest.mark.django_db
class QueryTaskModelTest(TestCase, SampleDataMixin):
    """Test QueryTask model functionality"""
    
    def test_query_task_creation(self):
        """Test QueryTask model creation and field validation"""
        task = QueryTaskFactory(
            prompt="Find malicious events",
            method="constrained",
            index="logs_net"
        )
        
        self.assertIsNotNone(task.task_id)
        self.assertEqual(task.prompt, "Find malicious events")
        self.assertEqual(task.method, "constrained")
        self.assertEqual(task.index, "logs_net")
        self.assertEqual(task.status, "pending")
        self.assertIsNotNone(task.created_at)
        self.assertIsNone(task.completed_at)
    
    def test_query_task_str_representation(self):
        """Test QueryTask string representation"""
        task = QueryTaskFactory()
        expected_str = f"QueryTask {task.task_id} - {task.status}"
        self.assertEqual(str(task), expected_str)
    
    def test_query_task_ordering(self):
        """Test QueryTask ordering by created_at descending"""
        task1 = QueryTaskFactory()
        task2 = QueryTaskFactory()
        task3 = QueryTaskFactory()
        
        tasks = QueryTask.objects.all()
        self.assertEqual(list(tasks), [task3, task2, task1])
    
    def test_query_task_status_choices(self):
        """Test QueryTask status choices validation"""
        valid_statuses = ['pending', 'running', 'completed', 'failed']
        
        for status_value in valid_statuses:
            task = QueryTaskFactory(status=status_value)
            self.assertEqual(task.status, status_value)
    
    def test_query_task_method_choices(self):
        """Test QueryTask method choices validation"""
        valid_methods = ['constrained', 'rules', 'zeroshot']
        
        for method_value in valid_methods:
            task = QueryTaskFactory(method=method_value)
            self.assertEqual(task.method, method_value)


@pytest.mark.django_db 
class GeneratedQueryModelTest(TestCase, SampleDataMixin):
    """Test GeneratedQuery model functionality"""
    
    def test_generated_query_creation(self):
        """Test GeneratedQuery model creation"""
        task = QueryTaskFactory()
        query = GeneratedQueryFactory(
            task=task,
            elasticsearch_dsl=self.sample_elasticsearch_query(),
            validation_status='PASS'
        )
        
        self.assertEqual(query.task, task)
        self.assertEqual(query.validation_status, 'PASS')
        self.assertIsInstance(query.elasticsearch_dsl, dict)
        self.assertEqual(query.retry_count, 0)
    
    def test_generated_query_one_to_one_relationship(self):
        """Test one-to-one relationship with QueryTask"""
        task = QueryTaskFactory()
        query = GeneratedQueryFactory(task=task)
        
        # Test forward relationship
        self.assertEqual(query.task, task)
        
        # Test reverse relationship
        self.assertEqual(task.generated_query, query)
    
    def test_generated_query_with_validation_errors(self):
        """Test GeneratedQuery with validation errors"""
        query = FailedGeneratedQueryFactory(
            validation_status='FAIL',
            validation_errors=self.sample_validation_errors()
        )
        
        self.assertEqual(query.validation_status, 'FAIL')
        self.assertTrue(len(query.validation_errors) > 0)
        self.assertIn('field', query.validation_errors[0])


@pytest.mark.django_db
class QueryExecutionModelTest(TestCase, SampleDataMixin):
    """Test QueryExecution model functionality"""
    
    def test_query_execution_creation(self):
        """Test QueryExecution model creation"""
        task = QueryTaskFactory()
        execution = QueryExecutionFactory(
            task=task,
            total_hits=100,
            returned_hits=50,
            execution_time_ms=1500
        )
        
        self.assertEqual(execution.task, task)
        self.assertEqual(execution.total_hits, 100)
        self.assertEqual(execution.returned_hits, 50)
        self.assertEqual(execution.execution_time_ms, 1500)
        self.assertIsNotNone(execution.executed_at)
    
    def test_query_execution_foreign_key_relationship(self):
        """Test foreign key relationship with QueryTask"""
        task = QueryTaskFactory()
        execution1 = QueryExecutionFactory(task=task)
        execution2 = QueryExecutionFactory(task=task)
        
        # Test reverse relationship
        self.assertEqual(task.executions.count(), 2)
        self.assertIn(execution1, task.executions.all())
        self.assertIn(execution2, task.executions.all())
    
    def test_query_execution_ordering(self):
        """Test QueryExecution ordering by executed_at descending"""
        task = QueryTaskFactory()
        execution1 = QueryExecutionFactory(task=task)
        execution2 = QueryExecutionFactory(task=task) 
        execution3 = QueryExecutionFactory(task=task)
        
        executions = task.executions.all()
        self.assertEqual(list(executions), [execution3, execution2, execution1])


@pytest.mark.django_db
class QuerySerializerTest(TestCase, SampleDataMixin):
    """Test query-related serializers"""
    
    def test_query_generation_request_serializer_valid_data(self):
        """Test QueryGenerationRequestSerializer with valid data"""
        data = {
            'prompt': 'Find malicious events in the last 24 hours',
            'method': 'constrained',
            'index': 'logs_net',
            'model': 'llama3.1:latest'
        }
        
        serializer = QueryGenerationRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['prompt'], data['prompt'])
        self.assertEqual(serializer.validated_data['method'], data['method'])
    
    def test_query_generation_request_serializer_invalid_method(self):
        """Test QueryGenerationRequestSerializer with invalid method"""
        data = {
            'prompt': 'Find malicious events',
            'method': 'invalid_method',
            'index': 'logs_net'
        }
        
        serializer = QueryGenerationRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('method', serializer.errors)
    
    def test_query_task_detail_serializer(self):
        """Test QueryTaskDetailSerializer"""
        task = CompletedQueryTaskFactory()
        query = GeneratedQueryFactory(task=task)
        execution = QueryExecutionFactory(task=task)
        
        serializer = QueryTaskDetailSerializer(task)
        data = serializer.data
        
        self.assertEqual(data['task_id'], task.task_id)
        self.assertEqual(data['status'], task.status)
        self.assertEqual(data['prompt'], task.prompt)
        self.assertIsNotNone(data['generated_query'])
        self.assertTrue(len(data['executions']) > 0)
    
    def test_query_execution_request_serializer(self):
        """Test QueryExecutionRequestSerializer"""
        data = {'max_size': 1000}
        
        serializer = QueryExecutionRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['max_size'], 1000)
    
    def test_query_execution_request_serializer_invalid_max_size(self):
        """Test QueryExecutionRequestSerializer with invalid max_size"""
        data = {'max_size': 20000}  # Above limit
        
        serializer = QueryExecutionRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('max_size', serializer.errors)


@pytest.mark.api
@pytest.mark.django_db
class QueryAPITest(APITestCase, SampleDataMixin):
    """Test Query API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = UserFactory()
        self.admin_user = AdminUserFactory()
        self.client.force_authenticate(user=self.user)
    
    def test_create_query_task_authenticated(self):
        """Test creating query task with authenticated user"""
        url = reverse('queries:query-list-create')
        data = {
            'prompt': 'Find malicious events in the last 24 hours',
            'method': 'constrained',
            'index': 'logs_net',
            'model': 'llama3.1:latest'
        }
        
        with patch('queries.tasks.generate_query_task.delay') as mock_task:
            response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertIn('estimated_completion', response.data)
        
        # Verify task was created in database
        task_id = response.data['task_id']
        task = QueryTask.objects.get(task_id=task_id)
        self.assertEqual(task.prompt, data['prompt'])
        self.assertEqual(task.method, data['method'])
        self.assertEqual(task.status, 'pending')
        
        # Verify Celery task was called
        mock_task.assert_called_once()
    
    def test_create_query_task_unauthenticated(self):
        """Test creating query task without authentication"""
        self.client.force_authenticate(user=None)
        
        url = reverse('queries:query-list-create')
        data = {
            'prompt': 'Find malicious events',
            'method': 'constrained'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_query_task_invalid_data(self):
        """Test creating query task with invalid data"""
        url = reverse('queries:query-list-create')
        data = {
            'prompt': '',  # Empty prompt
            'method': 'invalid_method'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('prompt', response.data)
        self.assertIn('method', response.data)
    
    def test_list_query_tasks(self):
        """Test listing query tasks"""
        # Create test tasks
        task1 = QueryTaskFactory()
        task2 = CompletedQueryTaskFactory()
        GeneratedQueryFactory(task=task2)
        
        url = reverse('queries:query-list-create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertTrue(len(response.data['results']) >= 2)
    
    def test_list_query_tasks_with_filters(self):
        """Test listing query tasks with filters"""
        # Create tasks with different statuses
        completed_task = CompletedQueryTaskFactory(method='constrained')
        failed_task = FailedQueryTaskFactory(method='rules')
        
        url = reverse('queries:query-list-create')
        
        # Test status filter
        response = self.client.get(url, {'status': 'completed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test method filter
        response = self.client.get(url, {'method': 'constrained'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_get_query_task_detail(self):
        """Test getting query task details"""
        task = CompletedQueryTaskFactory()
        query = GeneratedQueryFactory(task=task)
        execution = QueryExecutionFactory(task=task)
        
        url = reverse('queries:query-detail', kwargs={'task_id': task.task_id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['task_id'], task.task_id)
        self.assertEqual(response.data['status'], task.status)
        self.assertIn('query', response.data)
        self.assertIn('validation', response.data)
        self.assertIn('metrics', response.data)
    
    def test_get_query_task_detail_not_found(self):
        """Test getting non-existent query task details"""
        url = reverse('queries:query-detail', kwargs={'task_id': str(uuid.uuid4())})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @responses.activate
    def test_execute_query_success(self):
        """Test successful query execution"""
        # Setup task with valid query
        task = CompletedQueryTaskFactory()
        query = GeneratedQueryFactory(
            task=task,
            elasticsearch_dsl=self.sample_elasticsearch_query(),
            validation_status='PASS'
        )
        
        # Mock Elasticsearch response
        es_url = f"http://{settings.ELASTICSEARCH_HOST}/{task.index}/_search"
        responses.add(
            responses.POST,
            es_url,
            json=self.sample_elasticsearch_results(),
            status=200
        )
        
        url = reverse('queries:query-execute', kwargs={'task_id': task.task_id})
        data = {'max_size': 1000}
        
        with patch('builtins.open', mock_open()) as mock_file:
            response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_hits', response.data)
        self.assertIn('returned_hits', response.data)
        self.assertIn('took', response.data)
        self.assertIn('results', response.data)
        self.assertIn('export_urls', response.data)
        
        # Verify execution record was created
        execution = QueryExecution.objects.filter(task=task).first()
        self.assertIsNotNone(execution)
    
    def test_execute_query_validation_failed(self):
        """Test executing query with failed validation"""
        task = CompletedQueryTaskFactory()
        query = FailedGeneratedQueryFactory(
            task=task,
            validation_status='FAIL',
            validation_errors=self.sample_validation_errors()
        )
        
        url = reverse('queries:query-execute', kwargs={'task_id': task.task_id})
        data = {'max_size': 1000}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('validation_errors', response.data)
    
    def test_execute_query_not_generated(self):
        """Test executing query that hasn't been generated yet"""
        task = QueryTaskFactory(status='pending')
        
        url = reverse('queries:query-execute', kwargs={'task_id': task.task_id})
        data = {'max_size': 1000}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    @responses.activate
    def test_execute_query_elasticsearch_error(self):
        """Test query execution with Elasticsearch error"""
        task = CompletedQueryTaskFactory()
        query = GeneratedQueryFactory(
            task=task,
            validation_status='PASS'
        )
        
        # Mock Elasticsearch error response
        es_url = f"http://{settings.ELASTICSEARCH_HOST}/{task.index}/_search"
        responses.add(
            responses.POST,
            es_url,
            json={"error": "index_not_found_exception"},
            status=404
        )
        
        url = reverse('queries:query-execute', kwargs={'task_id': task.task_id})
        data = {'max_size': 1000}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
    
    @override_settings(ARTIFACTS_PATH='/tmp/test_artifacts')
    def test_query_export_csv(self):
        """Test exporting query results as CSV"""
        task = CompletedQueryTaskFactory()
        execution = QueryExecutionFactory(
            task=task,
            export_csv_path='/tmp/test_results.csv'
        )
        
        # Create test CSV file
        os.makedirs('/tmp/test_artifacts/exports', exist_ok=True)
        csv_content = 'timestamp,message\n2024-01-01,test message\n'
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            with patch('os.path.exists', return_value=True):
                url = reverse('queries:query-export', 
                            kwargs={'task_id': task.task_id, 'format': 'csv'})
                response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_query_export_file_not_found(self):
        """Test exporting when file doesn't exist"""
        task = CompletedQueryTaskFactory()
        execution = QueryExecutionFactory(
            task=task,
            export_csv_path='/nonexistent/file.csv'
        )
        
        url = reverse('queries:query-export', 
                     kwargs={'task_id': task.task_id, 'format': 'csv'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_query_export_invalid_format(self):
        """Test exporting with invalid format"""
        task = CompletedQueryTaskFactory()
        
        url = reverse('queries:query-export', 
                     kwargs={'task_id': task.task_id, 'format': 'xml'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


@pytest.mark.celery
@pytest.mark.django_db
class QueryTaskTest(TestCase, SampleDataMixin):
    """Test Celery query generation task"""
    
    @patch('queries.tasks.requests.post')
    @patch('queries.tasks.validate_query')
    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_query_task_success(self, mock_file, mock_makedirs, mock_validate, mock_requests):
        """Test successful query generation task"""
        # Setup mocks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'query': self.sample_elasticsearch_query(),
            'validation': {'status': 'PASS', 'errors': []},
            'metrics': {'generation_time_ms': 1500}
        }
        mock_requests.return_value = mock_response
        mock_validate.return_value = (True, [])
        
        # Create task
        task = QueryTaskFactory()
        
        # Run task
        result = generate_query_task(
            task.task_id,
            task.prompt,
            task.method,
            task.index,
            task.model
        )
        
        # Verify result
        self.assertEqual(result['status'], 'completed')
        self.assertIn('query', result)
        
        # Verify database records
        task.refresh_from_db()
        self.assertEqual(task.status, 'completed')
        self.assertIsNotNone(task.completed_at)
        
        # Verify generated query was created
        generated_query = GeneratedQuery.objects.get(task=task)
        self.assertEqual(generated_query.validation_status, 'PASS')
        self.assertIsInstance(generated_query.elasticsearch_dsl, dict)
    
    @patch('queries.tasks.requests.post')
    def test_generate_query_task_api_error(self, mock_requests):
        """Test query generation task with API error"""
        # Setup mock to simulate API error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal server error'
        mock_requests.return_value = mock_response
        
        # Create task
        task = QueryTaskFactory()
        
        # Run task
        result = generate_query_task(
            task.task_id,
            task.prompt,
            task.method,
            task.index,
            task.model
        )
        
        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error', result)
        
        # Verify database record
        task.refresh_from_db()
        self.assertEqual(task.status, 'failed')
        self.assertIsNotNone(task.error_message)
    
    def test_generate_query_task_invalid_task_id(self):
        """Test query generation task with invalid task ID"""
        # Run task with non-existent task ID
        result = generate_query_task(
            str(uuid.uuid4()),
            'test prompt',
            'constrained',
            'logs_net',
            'llama3.1:latest'
        )
        
        # Verify result
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error', result)


@pytest.mark.integration
@pytest.mark.django_db
class QueryIntegrationTest(APITestCase, SampleDataMixin):
    """Integration tests for complete query workflows"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
    
    @responses.activate
    @patch('queries.tasks.generate_query_task.delay')
    def test_complete_query_workflow(self, mock_task):
        """Test complete workflow: create -> generate -> execute -> export"""
        # 1. Create query task
        create_url = reverse('queries:query-list-create')
        create_data = {
            'prompt': 'Find malicious events in the last 24 hours',
            'method': 'constrained',
            'index': 'logs_net'
        }
        
        create_response = self.client.post(create_url, create_data, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_202_ACCEPTED)
        
        task_id = create_response.data['task_id']
        task = QueryTask.objects.get(task_id=task_id)
        
        # 2. Simulate query generation completion
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
        GeneratedQueryFactory(
            task=task,
            elasticsearch_dsl=self.sample_elasticsearch_query(),
            validation_status='PASS'
        )
        
        # 3. Check task details
        detail_url = reverse('queries:query-detail', kwargs={'task_id': task_id})
        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['status'], 'completed')
        
        # 4. Execute query
        # Mock Elasticsearch response
        es_url = f"http://{settings.ELASTICSEARCH_HOST}/{task.index}/_search"
        responses.add(
            responses.POST,
            es_url,
            json=self.sample_elasticsearch_results(),
            status=200
        )
        
        execute_url = reverse('queries:query-execute', kwargs={'task_id': task_id})
        execute_data = {'max_size': 1000}
        
        with patch('builtins.open', mock_open()) as mock_file:
            execute_response = self.client.post(execute_url, execute_data, format='json')
        
        self.assertEqual(execute_response.status_code, status.HTTP_200_OK)
        self.assertIn('export_urls', execute_response.data)
        
        # 5. Export results
        export_url = reverse('queries:query-export', 
                           kwargs={'task_id': task_id, 'format': 'csv'})
        
        with patch('builtins.open', mock_open(read_data='test,data\n')):
            with patch('os.path.exists', return_value=True):
                export_response = self.client.get(export_url)
        
        self.assertEqual(export_response.status_code, status.HTTP_200_OK)
        self.assertEqual(export_response['Content-Type'], 'text/csv')
    
    @freeze_time("2024-01-01 10:00:00")
    def test_query_caching_behavior(self):
        """Test query result caching behavior"""
        # Create completed task
        task = CompletedQueryTaskFactory()
        GeneratedQueryFactory(task=task)
        
        detail_url = reverse('queries:query-detail', kwargs={'task_id': task.task_id})
        
        # First request should hit database
        response1 = self.client.get(detail_url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second request should use cache
        response2 = self.client.get(detail_url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data, response2.data)
    
    def test_query_pagination(self):
        """Test query list pagination"""
        # Create multiple tasks
        tasks = [QueryTaskFactory() for _ in range(25)]
        
        list_url = reverse('queries:query-list-create')
        
        # Test first page
        response = self.client.get(list_url, {'page': 1, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        
        # Test second page
        response = self.client.get(list_url, {'page': 2, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 10)
        
        # Test third page
        response = self.client.get(list_url, {'page': 3, 'page_size': 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)  # Remaining tasks

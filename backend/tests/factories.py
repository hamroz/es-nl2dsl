"""
Factory classes for creating test data consistently across all tests
"""

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid
import json

from queries.models import QueryTask, GeneratedQuery, QueryExecution
from evaluation.models import EvaluationScenario, EvaluationRun, EvaluationBatch
from security.models import SecurityTest, SecurityTestResult
from data_management.models import DataIngestionTask
from analytics.models import SystemMetric

User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    is_superuser = False
    role = 'analyst'
    workspace = 'default'
    tenant_id = factory.LazyFunction(uuid.uuid4)
    date_joined = factory.LazyFunction(timezone.now)
    
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        password = extracted or 'TestPassword123!'
        self.set_password(password)
        self.save()


class AdminUserFactory(UserFactory):
    """Factory for creating admin users"""
    role = 'admin'
    is_staff = True


class ViewerUserFactory(UserFactory):
    """Factory for creating viewer users"""
    role = 'viewer'


class QueryTaskFactory(DjangoModelFactory):
    """Factory for creating query tasks"""
    
    class Meta:
        model = QueryTask
    
    task_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    prompt = factory.Faker('sentence', nb_words=10)
    method = factory.Iterator(['constrained', 'rules', 'zeroshot'])
    index = 'logs_net'
    model = 'llama3.1:latest'
    status = 'pending'
    created_at = factory.LazyFunction(timezone.now)
    completed_at = None
    error_message = None


class CompletedQueryTaskFactory(QueryTaskFactory):
    """Factory for creating completed query tasks"""
    status = 'completed'
    completed_at = factory.LazyFunction(timezone.now)


class FailedQueryTaskFactory(QueryTaskFactory):
    """Factory for creating failed query tasks"""
    status = 'failed'
    completed_at = factory.LazyFunction(timezone.now)
    error_message = 'Test error message'


class GeneratedQueryFactory(DjangoModelFactory):
    """Factory for creating generated queries"""
    
    class Meta:
        model = GeneratedQuery
    
    task = factory.SubFactory(QueryTaskFactory)
    elasticsearch_dsl = factory.LazyFunction(lambda: {
        "query": {
            "bool": {
                "must": [
                    {"match": {"message": "test"}}
                ],
                "filter": [
                    {"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}
                ]
            }
        }
    })
    validation_status = 'PASS'
    validation_errors = factory.LazyFunction(list)
    generation_metrics = factory.LazyFunction(lambda: {
        "generation_time_ms": 1500,
        "validation_time_ms": 100,
        "tokens_used": 150
    })
    retry_count = 0
    file_path = None


class FailedGeneratedQueryFactory(GeneratedQueryFactory):
    """Factory for creating failed generated queries"""
    validation_status = 'FAIL'
    validation_errors = factory.LazyFunction(lambda: [
        {"field": "invalid_field", "error": "Field not allowed"}
    ])


class QueryExecutionFactory(DjangoModelFactory):
    """Factory for creating query executions"""
    
    class Meta:
        model = QueryExecution
    
    task = factory.SubFactory(QueryTaskFactory)
    executed_at = factory.LazyFunction(timezone.now)
    total_hits = factory.Faker('random_int', min=0, max=10000)
    returned_hits = factory.LazyAttribute(lambda obj: min(obj.total_hits, 1000))
    execution_time_ms = factory.Faker('random_int', min=50, max=5000)
    max_size = 1000
    results = factory.LazyFunction(lambda: [
        {
            "_id": "test_doc_1",
            "_score": 1.0,
            "@timestamp": "2024-01-01T10:00:00Z",
            "message": "test log message",
            "src_ip": "192.168.1.100",
            "dst_ip": "10.0.0.1"
        }
    ])
    aggregations = factory.LazyFunction(dict)
    export_csv_path = None
    export_json_path = None


class EvaluationScenarioFactory(DjangoModelFactory):
    """Factory for creating evaluation scenarios"""
    
    class Meta:
        model = EvaluationScenario
    
    scenario_id = factory.Sequence(lambda n: f"scenario-{n:03d}")
    prompt = factory.Faker('sentence', nb_words=15)
    description = factory.Faker('text', max_nb_chars=200)
    expert_query = factory.LazyFunction(lambda: {
        "query": {
            "bool": {
                "must": [{"match": {"message": "error"}}],
                "filter": [{"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}]
            }
        }
    })
    expected_result_count = factory.Faker('random_int', min=10, max=1000)
    index = 'logs_net'
    category = factory.Iterator(['general', 'security', 'performance', 'network'])
    is_active = True


class EvaluationRunFactory(DjangoModelFactory):
    """Factory for creating evaluation runs"""
    
    class Meta:
        model = EvaluationRun
    
    run_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    scenario = factory.SubFactory(EvaluationScenarioFactory)
    method = factory.Iterator(['constrained', 'rules', 'zeroshot'])
    model = 'llama3.1:latest'
    generated_query = factory.LazyFunction(lambda: {
        "query": {
            "bool": {
                "must": [{"match": {"message": "test"}}],
                "filter": [{"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}]
            }
        }
    })
    generation_time = factory.Faker('pyfloat', min_value=0.5, max_value=10.0)
    validation_passed = True
    validation_errors = factory.LazyFunction(list)
    jaccard_similarity = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    structural_similarity = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    expert_result_count = factory.Faker('random_int', min=10, max=1000)
    generated_result_count = factory.Faker('random_int', min=5, max=1000)
    f1_score = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    precision = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    recall = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    execution_time_expert = factory.Faker('random_int', min=50, max=5000)
    execution_time_generated = factory.Faker('random_int', min=50, max=5000)
    status = 'completed'


class EvaluationBatchFactory(DjangoModelFactory):
    """Factory for creating evaluation batches"""
    
    class Meta:
        model = EvaluationBatch
    
    batch_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Faker('sentence', nb_words=4)
    description = factory.Faker('text', max_nb_chars=300)
    method = factory.Iterator(['constrained', 'rules', 'zeroshot'])
    model = 'llama3.1:latest'
    total_scenarios = factory.Faker('random_int', min=5, max=20)
    completed_scenarios = factory.LazyAttribute(lambda obj: obj.total_scenarios)
    average_f1_score = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    average_jaccard_similarity = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    validation_pass_rate = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    completed_at = factory.LazyFunction(timezone.now)
    status = 'completed'


class FailedEvaluationRunFactory(EvaluationRunFactory):
    """Factory for creating failed evaluation runs"""
    status = 'failed'
    validation_passed = False
    validation_errors = factory.LazyFunction(lambda: [
        {"field": "invalid_field", "error": "Field not allowed"},
        {"field": "@timestamp", "error": "Time window too large"}
    ])
    f1_score = None
    precision = None
    recall = None
    jaccard_similarity = None


class SecurityTestFactory(DjangoModelFactory):
    """Factory for creating security tests"""
    
    class Meta:
        model = SecurityTest
    
    test_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Faker('sentence', nb_words=3)
    category = factory.Iterator(['adversarial', 'injection', 'boundary'])
    test_data = factory.LazyFunction(lambda: {
        "prompts": ["test prompt 1", "test prompt 2"],
        "expected_behavior": "abstain"
    })
    created_at = factory.LazyFunction(timezone.now)


class SecurityTestResultFactory(DjangoModelFactory):
    """Factory for creating security test results"""
    
    class Meta:
        model = SecurityTestResult
    
    test = factory.SubFactory(SecurityTestFactory)
    run_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    method = 'constrained'
    passed = True
    results = factory.LazyFunction(lambda: {
        "abstain_rate": 0.85,
        "failed_prompts": [],
        "total_prompts": 10,
        "abstained_prompts": 8
    })
    execution_time_ms = factory.Faker('random_int', min=100, max=2000)
    created_at = factory.LazyFunction(timezone.now)


class DataIngestionTaskFactory(DjangoModelFactory):
    """Factory for creating data ingestion tasks"""
    
    class Meta:
        model = DataIngestionTask
    
    task_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    file_name = factory.Faker('file_name', extension='csv')
    file_size = factory.Faker('random_int', min=1000, max=1000000)
    index_name = 'test_index'
    status = 'pending'
    progress = 0
    total_records = 0
    processed_records = 0
    error_records = 0
    created_at = factory.LazyFunction(timezone.now)
    completed_at = None
    error_message = None


class SystemMetricFactory(DjangoModelFactory):
    """Factory for creating system metrics"""
    
    class Meta:
        model = SystemMetric
    
    metric_name = factory.Iterator(['cpu_usage', 'memory_usage', 'disk_usage'])
    metric_value = factory.Faker('pyfloat', min_value=0.0, max_value=100.0)
    metric_unit = factory.Iterator(['%', 'MB', 'GB'])
    component = factory.Iterator(['system', 'elasticsearch', 'redis', 'postgresql'])
    timestamp = factory.LazyFunction(timezone.now)
    metadata = factory.LazyFunction(lambda: {
        "host": "localhost",
        "service": "backend"
    })


# Sample data generators for different scenarios
class SampleDataMixin:
    """Mixin providing sample data for tests"""
    
    @staticmethod
    def sample_elasticsearch_query():
        """Generate a sample valid Elasticsearch query"""
        return {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "error"}}
                    ],
                    "filter": [
                        {"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}
                    ]
                }
            }
        }
    
    @staticmethod
    def sample_elasticsearch_results():
        """Generate sample Elasticsearch results"""
        return {
            "took": 5,
            "timed_out": False,
            "hits": {
                "total": {"value": 100, "relation": "eq"},
                "hits": [
                    {
                        "_index": "logs_net",
                        "_id": "1",
                        "_score": 1.0,
                        "_source": {
                            "@timestamp": "2024-01-01T10:00:00Z",
                            "message": "error in authentication",
                            "src_ip": "192.168.1.100",
                            "dst_ip": "10.0.0.1",
                            "src_port": 12345,
                            "dst_port": 80
                        }
                    }
                ]
            }
        }
    
    @staticmethod
    def sample_validation_errors():
        """Generate sample validation errors"""
        return [
            {"field": "invalid_field", "error": "Field not in whitelist"},
            {"field": "@timestamp", "error": "Time window too large"}
        ]
    
    @staticmethod
    def sample_audit_log_data():
        """Generate sample audit log data"""
        return {
            "user_id": 1,
            "action": "query_generate",
            "resource": "query_task_123",
            "ip_address": "192.168.1.100",
            "user_agent": "TestAgent/1.0",
            "metadata": {"method": "constrained", "index": "logs_net"}
        }
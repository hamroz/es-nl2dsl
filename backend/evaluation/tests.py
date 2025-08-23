import pytest
import json
import uuid
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from freezegun import freeze_time

from evaluation.models import EvaluationScenario, EvaluationRun, EvaluationBatch
from evaluation.serializers import (
    EvaluationScenarioSerializer,
    EvaluationRunSerializer,
    EvaluationBatchSerializer,
    RunEvaluationRequestSerializer,
    BatchEvaluationRequestSerializer
)
from evaluation.views import generate_query_for_evaluation
from evaluation.utils import (
    calculate_ast_similarity,
    execute_query_for_evaluation,
    calculate_execution_metrics,
    run_validation_for_evaluation
)
from tests.factories import (
    UserFactory,
    AdminUserFactory,
    EvaluationScenarioFactory,
    EvaluationRunFactory,
    EvaluationBatchFactory,
    FailedEvaluationRunFactory,
    SampleDataMixin
)

User = get_user_model()


@pytest.mark.django_db
class EvaluationScenarioModelTest(TestCase, SampleDataMixin):
    """Test EvaluationScenario model functionality"""
    
    def test_evaluation_scenario_creation(self):
        """Test EvaluationScenario model creation"""
        scenario = EvaluationScenarioFactory(
            scenario_id="test-scenario-001",
            prompt="Find malicious events in the last 24 hours",
            description="Test scenario for malicious event detection",
            expert_query=self.sample_elasticsearch_query(),
            expected_result_count=100,
            index="logs_net",
            category="security"
        )
        
        self.assertEqual(scenario.scenario_id, "test-scenario-001")
        self.assertEqual(scenario.prompt, "Find malicious events in the last 24 hours")
        self.assertEqual(scenario.index, "logs_net")
        self.assertEqual(scenario.category, "security")
        self.assertEqual(scenario.expected_result_count, 100)
        self.assertTrue(scenario.is_active)
        self.assertIsNotNone(scenario.created_at)
    
    def test_evaluation_scenario_string_representation(self):
        """Test EvaluationScenario string representation"""
        scenario = EvaluationScenarioFactory(
            scenario_id="test-001",
            description="This is a long description that should be truncated in the string representation"
        )
        
        expected_str = "Scenario test-001: This is a long description that should be trunca"
        self.assertEqual(str(scenario), expected_str)
    
    def test_evaluation_scenario_unique_id(self):
        """Test that scenario_id must be unique"""
        EvaluationScenarioFactory(scenario_id="duplicate-id")
        
        with self.assertRaises(Exception):  # IntegrityError
            EvaluationScenarioFactory(scenario_id="duplicate-id")
    
    def test_evaluation_scenario_ordering(self):
        """Test EvaluationScenario ordering by scenario_id"""
        scenario_c = EvaluationScenarioFactory(scenario_id="scenario-003")
        scenario_a = EvaluationScenarioFactory(scenario_id="scenario-001")
        scenario_b = EvaluationScenarioFactory(scenario_id="scenario-002")
        
        scenarios = list(EvaluationScenario.objects.all())
        self.assertEqual(scenarios, [scenario_a, scenario_b, scenario_c])
    
    def test_evaluation_scenario_expert_query_json_field(self):
        """Test expert_query JSON field functionality"""
        complex_query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"message": "error"}},
                        {"term": {"level": "ERROR"}}
                    ],
                    "filter": [
                        {"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}
                    ],
                    "should": [
                        {"match": {"source": "application"}}
                    ]
                }
            },
            "aggs": {
                "error_count_by_source": {
                    "terms": {"field": "source.keyword"}
                }
            }
        }
        
        scenario = EvaluationScenarioFactory(expert_query=complex_query)
        scenario.refresh_from_db()
        
        self.assertEqual(scenario.expert_query["query"]["bool"]["must"][0]["match"]["message"], "error")
        self.assertEqual(scenario.expert_query["aggs"]["error_count_by_source"]["terms"]["field"], "source.keyword")


@pytest.mark.django_db
class EvaluationRunModelTest(TestCase, SampleDataMixin):
    """Test EvaluationRun model functionality"""
    
    def test_evaluation_run_creation(self):
        """Test EvaluationRun model creation"""
        scenario = EvaluationScenarioFactory()
        run = EvaluationRunFactory(
            scenario=scenario,
            method="constrained",
            model="llama3.1:latest",
            generated_query=self.sample_elasticsearch_query(),
            generation_time=2.5,
            validation_passed=True,
            jaccard_similarity=0.85,
            f1_score=0.92
        )
        
        self.assertEqual(run.scenario, scenario)
        self.assertEqual(run.method, "constrained")
        self.assertEqual(run.model, "llama3.1:latest")
        self.assertTrue(run.validation_passed)
        self.assertEqual(run.jaccard_similarity, 0.85)
        self.assertEqual(run.f1_score, 0.92)
        self.assertEqual(run.generation_time, 2.5)
        self.assertEqual(run.status, "completed")
        self.assertIsNotNone(run.run_timestamp)
    
    def test_evaluation_run_string_representation(self):
        """Test EvaluationRun string representation"""
        scenario = EvaluationScenarioFactory(scenario_id="test-scenario")
        run = EvaluationRunFactory(
            scenario=scenario,
            method="rules",
            run_id="test-run-123"
        )
        
        expected_str = "Run test-run-123 - test-scenario (rules)"
        self.assertEqual(str(run), expected_str)
    
    def test_evaluation_run_foreign_key_relationship(self):
        """Test EvaluationRun foreign key relationship with EvaluationScenario"""
        scenario = EvaluationScenarioFactory()
        run1 = EvaluationRunFactory(scenario=scenario, method="constrained")
        run2 = EvaluationRunFactory(scenario=scenario, method="rules")
        
        # Test forward relationship
        self.assertEqual(run1.scenario, scenario)
        self.assertEqual(run2.scenario, scenario)
        
        # Test reverse relationship
        self.assertEqual(scenario.runs.count(), 2)
        self.assertIn(run1, scenario.runs.all())
        self.assertIn(run2, scenario.runs.all())
    
    def test_evaluation_run_ordering(self):
        """Test EvaluationRun ordering by run_timestamp descending"""
        scenario = EvaluationScenarioFactory()
        
        with freeze_time("2024-01-01 10:00:00"):
            run1 = EvaluationRunFactory(scenario=scenario)
        
        with freeze_time("2024-01-01 11:00:00"):
            run2 = EvaluationRunFactory(scenario=scenario)
        
        with freeze_time("2024-01-01 12:00:00"):
            run3 = EvaluationRunFactory(scenario=scenario)
        
        runs = list(EvaluationRun.objects.all())
        self.assertEqual(runs, [run3, run2, run1])  # Most recent first
    
    def test_evaluation_run_cascade_deletion(self):
        """Test that runs are deleted when scenario is deleted"""
        scenario = EvaluationScenarioFactory()
        run = EvaluationRunFactory(scenario=scenario)
        
        self.assertEqual(EvaluationRun.objects.filter(scenario=scenario).count(), 1)
        
        scenario.delete()
        
        self.assertEqual(EvaluationRun.objects.filter(id=run.id).count(), 0)


@pytest.mark.django_db
class EvaluationBatchModelTest(TestCase, SampleDataMixin):
    """Test EvaluationBatch model functionality"""
    
    def test_evaluation_batch_creation(self):
        """Test EvaluationBatch model creation"""
        batch = EvaluationBatchFactory(
            name="Security Evaluation Batch",
            description="Batch evaluation for security scenarios",
            method="constrained",
            model="llama3.1:latest",
            total_scenarios=10,
            completed_scenarios=8,
            average_f1_score=0.87,
            average_jaccard_similarity=0.82,
            validation_pass_rate=0.9
        )
        
        self.assertEqual(batch.name, "Security Evaluation Batch")
        self.assertEqual(batch.method, "constrained")
        self.assertEqual(batch.total_scenarios, 10)
        self.assertEqual(batch.completed_scenarios, 8)
        self.assertEqual(batch.average_f1_score, 0.87)
        self.assertEqual(batch.validation_pass_rate, 0.9)
        self.assertEqual(batch.status, "completed")
        self.assertIsNotNone(batch.started_at)
    
    def test_evaluation_batch_string_representation(self):
        """Test EvaluationBatch string representation"""
        batch = EvaluationBatchFactory(
            batch_id="batch-123",
            name="Test Batch"
        )
        
        expected_str = "Batch batch-123: Test Batch"
        self.assertEqual(str(batch), expected_str)
    
    def test_evaluation_batch_ordering(self):
        """Test EvaluationBatch ordering by started_at descending"""
        with freeze_time("2024-01-01 10:00:00"):
            batch1 = EvaluationBatchFactory()
        
        with freeze_time("2024-01-01 11:00:00"):
            batch2 = EvaluationBatchFactory()
        
        with freeze_time("2024-01-01 12:00:00"):
            batch3 = EvaluationBatchFactory()
        
        batches = list(EvaluationBatch.objects.all())
        self.assertEqual(batches, [batch3, batch2, batch1])  # Most recent first

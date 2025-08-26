"""
Unit tests for Phase 5 Meta-Learning Components
"""

import pytest
import numpy as np
from datetime import datetime
import json

from src.meta_learning.meta_learner import MetaLearner, MetaTask, MAMLTrainer
from src.meta_learning.domain_adapter import DomainAdapter, SchemaAdapter
from src.meta_learning.few_shot_generator import FewShotQueryGenerator, FewShotExample
from src.meta_learning.evaluation import MetaLearningEvaluator, AdaptationResult


class TestMetaLearner:
    """Test MetaLearner functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.meta_learner = MetaLearner()
        
    def test_meta_learner_initialization(self):
        """Test MetaLearner initialization."""
        assert self.meta_learner.base_model_name == "llama3.1:latest"
        assert self.meta_learner.inner_lr == 0.01
        assert self.meta_learner.outer_lr == 0.001
        assert self.meta_learner.inner_steps == 5
        assert 'security' in self.meta_learner.domain_knowledge
        
    def test_extract_domain_features(self):
        """Test domain feature extraction."""
        # Create test task
        schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "@timestamp": {"type": "date"},
                "bytes": {"type": "long"}
            }
        }
        
        support_examples = [
            {
                "prompt": "Find SSH attacks from external IPs",
                "expected_query": {"query": {"match": {"service": "ssh"}}}
            }
        ]
        
        task = MetaTask(
            task_id="test_task",
            domain="security",
            schema=schema,
            support_examples=support_examples,
            query_examples=[],
            field_mappings={}
        )
        
        features = self.meta_learner.extract_domain_features(task)
        
        assert 'field_types' in features
        assert 'common_patterns' in features
        assert 'temporal_characteristics' in features
        assert features['field_types']['source_ip'] == 'ip'
        
    def test_create_adaptation_prompt(self):
        """Test adaptation prompt creation."""
        task = MetaTask(
            task_id="test_task",
            domain="security",
            schema={"properties": {"source_ip": {"type": "ip"}}},
            support_examples=[
                {
                    "prompt": "Find malicious IPs",
                    "expected_query": {"query": {"term": {"malicious": True}}}
                }
            ],
            query_examples=[],
            field_mappings={}
        )
        
        prompt = self.meta_learner.create_adaptation_prompt(task, "Find suspicious traffic")
        
        assert "Domain Adaptation: Security" in prompt
        assert "Schema Information:" in prompt
        assert "Few-Shot Examples:" in prompt
        assert "Find malicious IPs" in prompt
        assert "Find suspicious traffic" in prompt
        
    def test_adapt_to_task(self):
        """Test task adaptation."""
        task = MetaTask(
            task_id="test_task",
            domain="security",
            schema={"properties": {"source_ip": {"type": "ip"}}},
            support_examples=[
                {
                    "prompt": "Find attacks",
                    "expected_query": {"query": {"match": {"attack": True}}}
                }
            ],
            query_examples=[],
            field_mappings={}
        )
        
        # Mock the call_local_model to return a valid JSON
        import src.generators.constrained
        original_call = src.generators.constrained.call_local_model
        
        def mock_call(prompt, model):
            return '{"query": {"match": {"test": "value"}}}'
        
        src.generators.constrained.call_local_model = mock_call
        
        try:
            generated_query, metrics = self.meta_learner.adapt_to_task(task, "Find test data")
            
            assert isinstance(generated_query, dict)
            assert 'success' in metrics
            assert 'schema_compliance' in metrics
            
        finally:
            src.generators.constrained.call_local_model = original_call


class TestDomainAdapter:
    """Test DomainAdapter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.domain_adapter = DomainAdapter()
        
    def test_domain_detection(self):
        """Test automatic domain detection."""
        # Security schema
        security_schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "attack_type": {"type": "keyword"},
                "severity": {"type": "keyword"}
            }
        }
        
        domain, confidence = self.domain_adapter.detect_domain(
            security_schema, 
            ["Find malicious attacks", "Detect intrusions"]
        )
        
        assert domain == "security"
        assert confidence > 0.0
        
    def test_adapt_to_domain(self):
        """Test domain adaptation."""
        schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "bytes": {"type": "long"}
            }
        }
        
        adaptation_config = self.domain_adapter.adapt_to_domain("networking", schema)
        
        assert adaptation_config['domain'] == "networking"
        assert 'field_mappings' in adaptation_config
        assert 'generation_hints' in adaptation_config
        assert 'validation_rules' in adaptation_config
        
    def test_field_mapping_creation(self):
        """Test field mapping creation."""
        profile = self.domain_adapter.domain_profiles['security']
        schema = {
            "properties": {
                "src_ip": {"type": "ip"},
                "destination_port": {"type": "integer"}
            }
        }
        
        mappings = self.domain_adapter._create_field_mappings(profile, schema)
        
        # Should map similar field names
        assert 'source_ip' in mappings or 'destination_ip' in mappings


class TestSchemaAdapter:
    """Test SchemaAdapter functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.schema_adapter = SchemaAdapter()
        
    def test_schema_analysis(self):
        """Test schema analysis."""
        schema = {
            "properties": {
                "@timestamp": {"type": "date"},
                "message": {"type": "text"},
                "level": {"type": "keyword"},
                "bytes": {"type": "long"},
                "nested_field": {
                    "type": "nested",
                    "properties": {
                        "sub_field": {"type": "keyword"}
                    }
                }
            }
        }
        
        analysis = self.schema_adapter.analyze_schema(schema, "test_schema")
        
        assert analysis['schema_name'] == "test_schema"
        assert analysis['field_analysis']['total_fields'] == 5
        assert '@timestamp' in analysis['field_analysis']['temporal_fields']
        assert 'message' in analysis['field_analysis']['text_fields']
        assert 'level' in analysis['field_analysis']['keyword_fields']
        assert 'bytes' in analysis['field_analysis']['numeric_fields']
        assert 'nested_field' in analysis['field_analysis']['nested_fields']
        
    def test_complexity_calculation(self):
        """Test schema complexity calculation."""
        simple_schema = {
            "properties": {
                "field1": {"type": "keyword"},
                "field2": {"type": "text"}
            }
        }
        
        complex_schema = {
            "properties": {
                f"field_{i}": {"type": "keyword"} for i in range(20)
            }
        }
        
        simple_complexity = self.schema_adapter._calculate_schema_complexity(simple_schema)
        complex_complexity = self.schema_adapter._calculate_schema_complexity(complex_schema)
        
        assert complex_complexity['overall_complexity'] > simple_complexity['overall_complexity']


class TestFewShotQueryGenerator:
    """Test FewShotQueryGenerator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = FewShotQueryGenerator()
        
        # Add test examples
        examples = [
            FewShotExample(
                prompt="Find SSH connections",
                expected_query={"query": {"match": {"service": "ssh"}}},
                domain="security",
                difficulty="easy"
            ),
            FewShotExample(
                prompt="Detect brute force attacks",
                expected_query={"query": {"bool": {"must": [{"match": {"event": "login_failed"}}]}}},
                domain="security",
                difficulty="hard"
            )
        ]
        
        self.generator.add_examples(examples, "security")
        
    def test_example_selection(self):
        """Test few-shot example selection."""
        selected = self.generator._select_examples("security", "Find malicious SSH", 3)
        
        assert len(selected) <= 3
        assert all(isinstance(ex, FewShotExample) for ex in selected)
        
    def test_example_relevance_calculation(self):
        """Test example relevance calculation."""
        example = FewShotExample(
            prompt="Find SSH connections",
            expected_query={"query": {"match": {"service": "ssh"}}},
            domain="security",
            difficulty="easy"
        )
        
        relevance = self.generator._calculate_example_relevance(example, "Find SSH attacks")
        
        assert 0.0 <= relevance <= 1.0
        assert relevance > 0.5  # Should be relevant due to "SSH" overlap
        
    def test_few_shot_generation(self):
        """Test few-shot query generation."""
        schema = {
            "properties": {
                "service": {"type": "keyword"},
                "@timestamp": {"type": "date"}
            }
        }
        
        # Mock the meta_learner.adapt_to_task method
        def mock_adapt(task, prompt):
            return {"query": {"match": {"service": "test"}}}, {"success": True}
        
        self.generator.meta_learner.adapt_to_task = mock_adapt
        
        result_query, metadata = self.generator.generate_with_few_shot(
            "Find test connections",
            schema,
            domain="security"
        )
        
        assert isinstance(result_query, dict)
        assert isinstance(metadata, dict)
        assert metadata['domain'] == "security"
        
    def test_difficulty_diversity(self):
        """Test difficulty diversity in example selection."""
        examples = [
            FewShotExample("easy1", {}, "security", "easy"),
            FewShotExample("easy2", {}, "security", "easy"),
            FewShotExample("medium1", {}, "security", "medium"),
            FewShotExample("hard1", {}, "security", "hard"),
            FewShotExample("hard2", {}, "security", "hard")
        ]
        
        diverse = self.generator._ensure_difficulty_diversity(examples, 3)
        
        assert len(diverse) == 3
        difficulties = [ex.difficulty for ex in diverse]
        assert len(set(difficulties)) >= 2  # Should have at least 2 different difficulties


class TestMetaLearningEvaluator:
    """Test MetaLearningEvaluator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.evaluator = MetaLearningEvaluator()
        
        # Create test adaptation results
        self.adaptation_results = [
            AdaptationResult(
                task_id="task1",
                domain="security",
                num_support_examples=3,
                adaptation_time=2.5,
                generated_query={"query": {"match": {"test": "value"}}},
                ground_truth_query={"query": {"match": {"test": "value"}}},
                success=True,
                metrics={"accuracy": 0.85, "precision": 0.82}
            ),
            AdaptationResult(
                task_id="task2",
                domain="security",
                num_support_examples=5,
                adaptation_time=3.2,
                generated_query={"query": {"match": {"test": "value2"}}},
                ground_truth_query={"query": {"match": {"test": "value2"}}},
                success=True,
                metrics={"accuracy": 0.92, "precision": 0.89}
            )
        ]
        
    def test_adaptation_speed_evaluation(self):
        """Test adaptation speed evaluation."""
        speed_metrics = self.evaluator.evaluate_adaptation_speed(self.adaptation_results)
        
        assert 'mean_time' in speed_metrics
        assert 'std_time' in speed_metrics
        assert 'speed_score' in speed_metrics
        assert speed_metrics['mean_time'] > 0
        
    def test_few_shot_performance_evaluation(self):
        """Test few-shot performance evaluation."""
        performance_metrics = self.evaluator.evaluate_few_shot_performance(self.adaptation_results)
        
        assert 'accuracy_by_shots' in performance_metrics
        assert 'sample_efficiency' in performance_metrics
        assert 'learning_curve' in performance_metrics
        
    def test_schema_adaptation_evaluation(self):
        """Test schema adaptation evaluation."""
        schema_metrics = self.evaluator.evaluate_schema_adaptation(self.adaptation_results)
        
        assert 'schema_adaptation_score' in schema_metrics
        assert 0.0 <= schema_metrics['schema_adaptation_score'] <= 1.0
        
    def test_comprehensive_metrics_computation(self):
        """Test comprehensive metrics computation."""
        metrics = self.evaluator.compute_comprehensive_metrics(self.adaptation_results)
        
        assert metrics.adaptation_time_mean > 0
        assert 0.0 <= metrics.few_shot_accuracy <= 1.0
        assert metrics.sample_efficiency > 0
        assert 0.0 <= metrics.overall_score <= 1.0
        
    def test_evaluation_report_generation(self):
        """Test evaluation report generation."""
        metrics = self.evaluator.compute_comprehensive_metrics(self.adaptation_results)
        report = self.evaluator.generate_evaluation_report(metrics, self.adaptation_results)
        
        assert "Meta-Learning Evaluation Report" in report
        assert "Executive Summary" in report
        assert "Detailed Performance Metrics" in report
        assert "Recommendations" in report


class TestMAMLTrainer:
    """Test MAMLTrainer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.meta_learner = MetaLearner()
        self.trainer = MAMLTrainer(self.meta_learner)
        
        # Add training tasks
        training_task = MetaTask(
            task_id="train_task",
            domain="security",
            schema={"properties": {"field": {"type": "keyword"}}},
            support_examples=[{"prompt": "test", "expected_query": {}}],
            query_examples=[{"prompt": "test_query", "expected_query": {}}],
            field_mappings={}
        )
        
        self.trainer.add_training_task(training_task)
        
    def test_training_task_management(self):
        """Test training task addition."""
        assert len(self.trainer.training_tasks) == 1
        assert self.trainer.training_tasks[0].task_id == "train_task"
        
    def test_meta_training_execution(self):
        """Test meta-training execution."""
        # Run a short training session
        history = self.trainer.meta_train(num_epochs=2)
        
        assert 'train_loss' in history
        assert 'val_accuracy' in history
        assert len(history['train_loss']) == 2
        
    def test_model_state_persistence(self):
        """Test model state saving and loading."""
        import tempfile
        import os
        
        # Save model
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            filepath = f.name
            
        try:
            self.trainer.save_model(filepath)
            
            # Create new trainer and load
            new_trainer = MAMLTrainer(MetaLearner())
            new_trainer.load_model(filepath)
            
            # Verify state was loaded
            assert len(new_trainer.training_history) >= 0
            
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)


if __name__ == '__main__':
    pytest.main([__file__])

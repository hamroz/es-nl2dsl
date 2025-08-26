#!/usr/bin/env python3
"""Tests for explainability and research tools"""
import unittest
import json
import pandas as pd
import numpy as np
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.explainability.query_explainer import (
    QueryExplainer, PromptAnalyzer, DecisionType, ExplanationLevel,
    DecisionExplanation, QueryExplanation
)
from src.explainability.research_tools import (
    HypothesisGenerator, ExperimentalDesigner, StatisticalAnalyzer,
    HypothesisType, StatisticalTest, Hypothesis, ExperimentalDesign
)

class TestPromptAnalyzer(unittest.TestCase):
    """Test prompt analysis functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = PromptAnalyzer()
        self.test_prompts = [
            "Find events labeled malicious on July 4, 2017",
            "Show TCP traffic on port 443 from external sources",
            "Query for SSH connections greater than 100 packets",
            "Find attack events between 2017-07-01 and 2017-07-07"
        ]
    
    def test_temporal_extraction(self):
        """Test extraction of temporal information"""
        prompt = "Find events labeled malicious on July 4, 2017"
        analysis = self.analyzer.analyze_prompt(prompt)
        
        temporal_components = analysis["temporal_components"]
        self.assertGreater(len(temporal_components), 0)
        
        # Should find date and month references
        date_found = any(comp["type"] == "date" for comp in temporal_components)
        month_found = any(comp["type"] == "month" for comp in temporal_components)
        
        self.assertTrue(date_found or month_found)
    
    def test_field_reference_extraction(self):
        """Test extraction of field references"""
        prompt = "Show TCP traffic on port 443 from source IP 192.168.1.1"
        analysis = self.analyzer.analyze_prompt(prompt)
        
        field_refs = analysis["field_references"]
        self.assertGreater(len(field_refs), 0)
        
        # Should find protocol and port references
        field_types = [ref["type"] for ref in field_refs]
        self.assertTrue(any("protocol" in ftype for ftype in field_types))
        self.assertTrue(any("port" in ftype for ftype in field_types))
    
    def test_operator_hints_extraction(self):
        """Test extraction of operator hints"""
        prompt = "Find events greater than 100 packets and equal to malicious"
        analysis = self.analyzer.analyze_prompt(prompt)
        
        operator_hints = analysis["operator_hints"]
        self.assertGreater(len(operator_hints), 0)
        
        # Should find range and equality operators
        hint_types = [hint["type"] for hint in operator_hints]
        self.assertTrue(any("range" in htype for htype in hint_types))
        self.assertTrue(any("term" in htype for htype in hint_types))
    
    def test_security_context_extraction(self):
        """Test extraction of security context"""
        prompt = "Find malicious attack events and intrusion attempts"
        analysis = self.analyzer.analyze_prompt(prompt)
        
        security_context = analysis["security_context"]
        self.assertGreater(len(security_context), 0)
        
        # Should find security-related terms
        context_types = [ctx["type"] for ctx in security_context]
        self.assertTrue(any("security_event" in ctype for ctype in context_types))
    
    def test_complexity_assessment(self):
        """Test prompt complexity assessment"""
        simple_prompt = "Find malicious events"
        complex_prompt = "Find malicious events on July 4, 2017 from external sources with TCP protocol and port 443 if the duration is greater than 100 seconds"
        
        simple_analysis = self.analyzer.analyze_prompt(simple_prompt)
        complex_analysis = self.analyzer.analyze_prompt(complex_prompt)
        
        simple_complexity = simple_analysis["complexity_indicators"]["complexity_score"]
        complex_complexity = complex_analysis["complexity_indicators"]["complexity_score"]
        
        self.assertLess(simple_complexity, complex_complexity)
    
    def test_attention_weights(self):
        """Test attention weight calculation"""
        prompt = "Find malicious events on July 4, 2017"
        analysis = self.analyzer.analyze_prompt(prompt)
        
        attention_weights = analysis["attention_tokens"]
        self.assertGreater(len(attention_weights), 0)
        
        # Security terms should have higher attention than baseline (0.1)
        if "malicious" in attention_weights:
            self.assertGreater(attention_weights["malicious"], 0.1)
        
        # Dates should have reasonable attention (above baseline)
        date_tokens = [token for token in attention_weights.keys() if "2017" in token or "july" in token.lower()]
        if date_tokens:
            self.assertGreater(attention_weights[date_tokens[0]], 0.1)

class TestQueryExplainer(unittest.TestCase):
    """Test query explanation functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.explainer = QueryExplainer()
        
        # Sample query for testing
        self.test_query = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": "2017-07-04T00:00:00Z",
                                    "lte": "2017-07-04T23:59:59Z"
                                }
                            }
                        },
                        {
                            "term": {
                                "label": "malicious"
                            }
                        }
                    ]
                }
            },
            "size": 1000
        }
        
        self.test_prompt = "Find events labeled malicious on July 4, 2017"
    
    def test_query_structure_analysis(self):
        """Test query structure analysis"""
        analysis = self.explainer._analyze_query_structure(self.test_query)
        
        self.assertTrue(analysis["has_query"])
        self.assertFalse(analysis["has_aggregations"])
        self.assertTrue(analysis["has_size_limit"])
        self.assertEqual(analysis["query_type"], "boolean")
        self.assertGreater(len(analysis["filters"]), 0)
        self.assertGreater(analysis["field_count"], 0)
    
    def test_decision_explanation_generation(self):
        """Test decision explanation generation"""
        prompt_analysis = self.explainer.prompt_analyzer.analyze_prompt(self.test_prompt)
        query_analysis = self.explainer._analyze_query_structure(self.test_query)
        
        decisions = self.explainer._explain_decisions(prompt_analysis, query_analysis, self.test_query)
        
        self.assertGreater(len(decisions), 0)
        
        # Check decision types
        decision_types = [d.decision_type for d in decisions]
        self.assertIn(DecisionType.FIELD_SELECTION, decision_types)
        self.assertIn(DecisionType.TIME_FILTERING, decision_types)
        
        # Check decision structure
        for decision in decisions:
            self.assertIsInstance(decision, DecisionExplanation)
            self.assertGreater(len(decision.rationale), 0)
            self.assertGreaterEqual(decision.confidence, 0.0)
            self.assertLessEqual(decision.confidence, 1.0)
    
    def test_overall_confidence_calculation(self):
        """Test overall confidence calculation"""
        # Create mock decisions
        decisions = [
            DecisionExplanation(
                decision_type=DecisionType.FIELD_SELECTION,
                component="term", field_name="label", value="malicious",
                confidence=0.8, rationale="Test", alternatives=[],
                prompt_evidence=[], technical_details={}
            ),
            DecisionExplanation(
                decision_type=DecisionType.TIME_FILTERING,
                component="range", field_name="@timestamp", value={},
                confidence=0.9, rationale="Test", alternatives=[],
                prompt_evidence=[], technical_details={}
            )
        ]
        
        confidence = self.explainer._calculate_overall_confidence(decisions)
        
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        self.assertGreater(confidence, 0.5)  # Should be reasonable given high individual confidences
    
    def test_query_summary_generation(self):
        """Test query summary generation"""
        prompt_analysis = self.explainer.prompt_analyzer.analyze_prompt(self.test_prompt)
        summary = self.explainer._generate_query_summary(self.test_query, prompt_analysis)
        
        self.assertGreater(len(summary), 0)
        self.assertIn("search", summary.lower())
        # Should mention security context if present
        if any("malicious" in ctx.get("text", "") for ctx in prompt_analysis.get("security_context", [])):
            self.assertIn("malicious", summary.lower())
    
    def test_risk_assessment(self):
        """Test query risk assessment"""
        decisions = []  # Mock empty decisions
        risk_assessment = self.explainer._assess_query_risks(self.test_query, decisions)
        
        self.assertIn("performance_risks", risk_assessment)
        self.assertIn("security_risks", risk_assessment)
        self.assertIn("accuracy_risks", risk_assessment)
        self.assertIn("overall_risk_level", risk_assessment)
        
        # Risk level should be valid
        self.assertIn(risk_assessment["overall_risk_level"], ["low", "medium", "high"])
    
    def test_optimization_suggestions(self):
        """Test optimization suggestion generation"""
        prompt_analysis = self.explainer.prompt_analyzer.analyze_prompt(self.test_prompt)
        decisions = []  # Mock empty decisions
        
        optimizations = self.explainer._generate_optimizations(self.test_query, decisions, prompt_analysis)
        
        self.assertIsInstance(optimizations, list)
        # Should have some suggestions for most queries
        self.assertGreaterEqual(len(optimizations), 1)
    
    def test_complete_explanation(self):
        """Test complete query explanation"""
        explanation = self.explainer.explain_query(
            self.test_prompt, 
            self.test_query, 
            ExplanationLevel.DETAILED
        )
        
        self.assertIsInstance(explanation, QueryExplanation)
        self.assertEqual(explanation.original_prompt, self.test_prompt)
        self.assertEqual(explanation.generated_query, self.test_query)
        self.assertGreater(len(explanation.query_summary), 0)
        self.assertGreaterEqual(explanation.confidence_score, 0.0)
        self.assertLessEqual(explanation.confidence_score, 1.0)
        self.assertGreaterEqual(explanation.complexity_score, 0.0)
        self.assertLessEqual(explanation.complexity_score, 1.0)
        self.assertGreater(len(explanation.decisions), 0)
    
    def test_explanation_serialization(self):
        """Test explanation serialization"""
        explanation = self.explainer.explain_query(
            self.test_prompt, 
            self.test_query, 
            ExplanationLevel.DETAILED
        )
        
        explanation_dict = explanation.to_dict()
        
        self.assertIsInstance(explanation_dict, dict)
        self.assertIn("original_prompt", explanation_dict)
        self.assertIn("decisions", explanation_dict)
        self.assertIn("confidence_score", explanation_dict)
        
        # Should be JSON serializable
        json_str = json.dumps(explanation_dict, default=str)
        self.assertGreater(len(json_str), 0)

class TestHypothesisGenerator(unittest.TestCase):
    """Test hypothesis generation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.generator = HypothesisGenerator()
        
        self.sample_data_summary = {
            "factors": ["model", "method"],
            "metrics": ["f1_score", "precision", "recall"],
            "models": ["llama3.1:latest", "deepseek-r1:14b"],
            "methods": ["constrained", "zero_shot"]
        }
    
    def test_hypothesis_generation(self):
        """Test basic hypothesis generation"""
        hypotheses = self.generator.generate_hypotheses(self.sample_data_summary)
        
        self.assertGreater(len(hypotheses), 0)
        
        for hypothesis in hypotheses:
            self.assertIsInstance(hypothesis, Hypothesis)
            self.assertGreater(len(hypothesis.description), 0)
            self.assertGreater(len(hypothesis.null_hypothesis), 0)
            self.assertGreater(len(hypothesis.alternative_hypothesis), 0)
            self.assertIn(hypothesis.hypothesis_type, HypothesisType)
    
    def test_performance_hypothesis_creation(self):
        """Test performance comparison hypothesis creation"""
        hypothesis = self.generator._create_performance_hypothesis("model", "f1_score")
        
        self.assertEqual(hypothesis.hypothesis_type, HypothesisType.PERFORMANCE_COMPARISON)
        self.assertIn("model", hypothesis.description)
        # Check that the metric is referenced in the description or variables
        self.assertTrue("f1_score" in hypothesis.description or "f1_score" in str(hypothesis.variables))
        self.assertIn("model", hypothesis.variables)
        self.assertEqual(hypothesis.variables["model"], "f1_score")
    
    def test_model_hypothesis_creation(self):
        """Test model effectiveness hypothesis creation"""
        hypothesis = self.generator._create_model_hypothesis("llama3.1:latest", "accuracy")
        
        self.assertEqual(hypothesis.hypothesis_type, HypothesisType.MODEL_EFFECTIVENESS)
        self.assertIn("llama3.1:latest", hypothesis.description)
        self.assertIn("model", hypothesis.variables)
    
    def test_method_hypothesis_creation(self):
        """Test method superiority hypothesis creation"""
        hypothesis = self.generator._create_method_hypothesis("constrained", "zero_shot", "f1_score")
        
        self.assertEqual(hypothesis.hypothesis_type, HypothesisType.METHOD_SUPERIORITY)
        self.assertIn("constrained", hypothesis.description)
        self.assertIn("zero_shot", hypothesis.description)
        self.assertIn("method", hypothesis.variables)

class TestExperimentalDesigner(unittest.TestCase):
    """Test experimental design"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.designer = ExperimentalDesigner()
        
        self.test_hypothesis = Hypothesis(
            hypothesis_id="test_hyp",
            hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
            description="Test hypothesis",
            null_hypothesis="No difference",
            alternative_hypothesis="Significant difference",
            variables={"model": "f1_score"},
            expected_outcome="difference",
            significance_level=0.05,
            metadata={}
        )
        
        self.available_data = {
            "factors": {"model": ["model1", "model2"], "method": ["method1", "method2"]},
            "models": ["model1", "model2"],
            "methods": ["method1", "method2"]
        }
    
    def test_experiment_design(self):
        """Test basic experiment design"""
        design = self.designer.design_experiment(self.test_hypothesis, self.available_data)
        
        self.assertIsInstance(design, ExperimentalDesign)
        self.assertEqual(design.hypothesis, self.test_hypothesis)
        self.assertGreater(len(design.factors), 0)
        self.assertGreater(design.sample_size, 0)
        self.assertGreater(len(design.statistical_tests), 0)
    
    def test_sample_size_calculation(self):
        """Test sample size calculation"""
        sample_size = self.designer._calculate_sample_size(self.test_hypothesis, self.available_data)
        
        self.assertGreaterEqual(sample_size, 20)  # Minimum sample size
        self.assertIsInstance(sample_size, int)
    
    def test_statistical_test_selection(self):
        """Test statistical test selection"""
        factors = ["model"]
        levels = {"model": ["model1", "model2"]}
        
        tests = self.designer._select_statistical_tests(self.test_hypothesis, factors, levels)
        
        self.assertGreater(len(tests), 0)
        self.assertTrue(all(isinstance(test, StatisticalTest) for test in tests))
    
    def test_power_analysis(self):
        """Test power analysis"""
        power_results = self.designer._power_analysis(self.test_hypothesis, 30)
        
        self.assertIn("power_small", power_results)
        self.assertIn("power_medium", power_results)
        self.assertIn("power_large", power_results)
        
        # Power values should be between 0 and 1
        for power in power_results.values():
            self.assertGreaterEqual(power, 0.0)
            self.assertLessEqual(power, 1.0)

class TestStatisticalAnalyzer(unittest.TestCase):
    """Test statistical analysis"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = StatisticalAnalyzer()
        
        # Create test data
        np.random.seed(42)
        self.test_data = pd.DataFrame({
            "model": ["model1"] * 20 + ["model2"] * 20,
            "f1_score": np.concatenate([
                np.random.normal(0.8, 0.1, 20),  # Model 1 scores
                np.random.normal(0.75, 0.1, 20)  # Model 2 scores
            ]),
            "precision": np.random.normal(0.85, 0.05, 40),
            "recall": np.random.normal(0.82, 0.08, 40)
        })
        
        self.test_design = ExperimentalDesign(
            design_id="test_design",
            hypothesis=Hypothesis(
                hypothesis_id="test", hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
                description="Test", null_hypothesis="No diff", alternative_hypothesis="Diff",
                variables={"model": "f1_score"}, expected_outcome="diff",
                significance_level=0.05, metadata={}
            ),
            factors=["model"],
            levels={"model": ["model1", "model2"]},
            sample_size=40,
            randomization=True,
            blocking_factors=None,
            statistical_tests=[StatisticalTest.T_TEST, StatisticalTest.CORRELATION],
            power_analysis={"power_medium": 0.8}
        )
    
    def test_t_test(self):
        """Test t-test implementation"""
        result = self.analyzer._t_test(self.test_design, self.test_data)
        
        self.assertIn("test_name", result)
        self.assertIn("statistic", result)
        self.assertIn("p_value", result)
        self.assertIn("effect_size", result)
        self.assertIn("confidence_interval", result)
        
        # P-value should be between 0 and 1
        self.assertGreaterEqual(result["p_value"], 0.0)
        self.assertLessEqual(result["p_value"], 1.0)
    
    def test_mann_whitney_test(self):
        """Test Mann-Whitney test implementation"""
        result = self.analyzer._mann_whitney_test(self.test_design, self.test_data)
        
        self.assertIn("test_name", result)
        self.assertIn("statistic", result)
        self.assertIn("p_value", result)
        self.assertIn("effect_size", result)
        
        # Check that medians are calculated
        self.assertIn("group1_median", result)
        self.assertIn("group2_median", result)
    
    def test_correlation_analysis(self):
        """Test correlation analysis"""
        result = self.analyzer._correlation_test(self.test_design, self.test_data)
        
        self.assertIn("test_name", result)
        self.assertIn("correlations", result)
        self.assertIn("correlation_matrix", result)
        
        # Should find correlations between numeric variables
        correlations = result["correlations"]
        self.assertGreater(len(correlations), 0)
        
        for corr in correlations:
            self.assertIn("correlation", corr)
            self.assertIn("p_value", corr)
    
    def test_complete_analysis(self):
        """Test complete experimental analysis"""
        result = self.analyzer.analyze_experiment(self.test_design, self.test_data)
        
        self.assertIsInstance(result.experiment_id, str)
        self.assertEqual(result.hypothesis, self.test_design.hypothesis)
        self.assertIsInstance(result.raw_data, pd.DataFrame)
        self.assertGreater(len(result.statistical_results), 0)
        self.assertGreater(len(result.conclusion), 0)
        
        # Check that all requested tests were performed
        for test in self.test_design.statistical_tests:
            self.assertIn(test.value, result.statistical_results)
    
    def test_conclusion_generation(self):
        """Test conclusion generation"""
        # Mock statistical results
        statistical_results = {
            "t_test": {"p_value": 0.03},
            "correlation": {"p_value": 0.15}
        }
        p_values = {"t_test": 0.03, "correlation": 0.15}
        
        conclusion = self.analyzer._generate_conclusion(
            self.test_design.hypothesis, statistical_results, p_values
        )
        
        self.assertGreater(len(conclusion), 0)
        # Should reject null hypothesis due to significant t-test
        self.assertIn("REJECT", conclusion)
    
    def test_practical_significance_assessment(self):
        """Test practical significance assessment"""
        effect_sizes = {"t_test": 0.6, "correlation": 0.2}
        
        practical_sig = self.analyzer._assess_practical_significance(
            effect_sizes, self.test_design.hypothesis
        )
        
        self.assertIn("t_test", practical_sig)
        self.assertIn("correlation", practical_sig)
        
        # Large effect size should be practically significant
        self.assertTrue(practical_sig["t_test"])
        # Small effect size should not be
        self.assertFalse(practical_sig["correlation"])

class TestResearchToolsIntegration(unittest.TestCase):
    """Integration tests for research tools"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create temporary CSV data for testing
        self.temp_data = pd.DataFrame({
            "model": ["model1"] * 30 + ["model2"] * 30,
            "method": ["constrained"] * 15 + ["zero_shot"] * 15 + ["constrained"] * 15 + ["zero_shot"] * 15,
            "f1_score": np.random.normal(0.8, 0.1, 60),
            "precision": np.random.normal(0.85, 0.05, 60),
            "recall": np.random.normal(0.82, 0.08, 60),
            "execution_time": np.random.normal(2.5, 0.5, 60)
        })
        
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        self.temp_data.to_csv(self.temp_file.name, index=False)
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up test fixtures"""
        Path(self.temp_file.name).unlink(missing_ok=True)
    
    def test_data_summarization(self):
        """Test data summarization for hypothesis generation"""
        from src.explainability.research_tools import ResearchToolsInterface
        
        research_tools = ResearchToolsInterface()
        summary = research_tools._summarize_data(self.temp_data)
        
        self.assertIn("shape", summary)
        self.assertIn("columns", summary)
        self.assertIn("factors", summary)
        self.assertIn("metrics", summary)
        
        # Should identify categorical and numeric columns correctly
        self.assertIn("model", summary["factors"])
        self.assertIn("method", summary["factors"])
        self.assertIn("f1_score", summary["metrics"])
    
    def test_hypothesis_selection(self):
        """Test hypothesis selection based on research question"""
        from src.explainability.research_tools import ResearchToolsInterface
        
        research_tools = ResearchToolsInterface()
        
        # Create mock hypotheses
        hypotheses = [
            Hypothesis(
                hypothesis_id="h1", hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
                description="Model comparison", null_hypothesis="No diff", 
                alternative_hypothesis="Diff", variables={"model": "f1_score"},
                expected_outcome="diff", significance_level=0.05, metadata={}
            )
        ]
        
        selected = research_tools._select_hypothesis(hypotheses, "Which model performs better?")
        
        self.assertIsInstance(selected, Hypothesis)
        self.assertEqual(selected.hypothesis_id, "h1")
    
    @patch('matplotlib.pyplot.savefig')
    def test_visualization_generation(self, mock_savefig):
        """Test visualization generation"""
        from src.explainability.research_tools import StatisticalAnalyzer, ExperimentalDesign
        
        analyzer = StatisticalAnalyzer()
        
        # Create minimal design for testing
        design = ExperimentalDesign(
            design_id="test", hypothesis=Hypothesis(
                hypothesis_id="test", hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
                description="Test", null_hypothesis="No diff", alternative_hypothesis="Diff",
                variables={"model": "f1_score"}, expected_outcome="diff",
                significance_level=0.05, metadata={}
            ),
            factors=["model"], levels={"model": ["model1", "model2"]},
            sample_size=60, randomization=True, blocking_factors=None,
            statistical_tests=[StatisticalTest.T_TEST], power_analysis={}
        )
        
        # Should not raise errors
        visualizations = analyzer._generate_visualizations(design, self.temp_data)
        
        # May return empty list if matplotlib operations fail, but should not crash
        self.assertIsInstance(visualizations, list)

if __name__ == "__main__":
    unittest.main()

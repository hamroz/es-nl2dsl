#!/usr/bin/env python3
"""Tests for statistical analysis functionality"""
import unittest
import json
import tempfile
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.analysis.statistical_analysis import (
    StatisticalAnalyzer, StatisticalResult, MultiRunEvaluationResult,
    run_statistical_evaluation
)

class TestStatisticalAnalyzer(unittest.TestCase):
    """Test statistical analysis components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = StatisticalAnalyzer()
        
        # Sample data for testing
        self.sample_data1 = [0.8, 0.85, 0.9, 0.75, 0.88]  # F1 scores
        self.sample_data2 = [0.7, 0.72, 0.68, 0.74, 0.71]  # Different method
        
        # Sample evaluation results
        self.sample_results = [
            {
                "jaccard_similarity": 0.8,
                "f1_score": 0.9,
                "precision": 0.85,
                "recall": 0.95,
                "execution_time_ms": 150.0,
                "seed": 42
            },
            {
                "jaccard_similarity": 0.75,
                "f1_score": 0.85,
                "precision": 0.8,
                "recall": 0.9,
                "execution_time_ms": 180.0,
                "seed": 43
            },
            {
                "jaccard_similarity": 0.9,
                "f1_score": 0.95,
                "precision": 0.9,
                "recall": 1.0,
                "execution_time_ms": 120.0,
                "seed": 44
            }
        ]
    
    def test_analyze_metric_basic(self):
        """Test basic metric analysis"""
        result = self.analyzer.analyze_metric(self.sample_data1)
        
        self.assertIsInstance(result, StatisticalResult)
        self.assertAlmostEqual(result.mean, 0.836, places=2)
        self.assertGreater(result.std, 0.0)
        self.assertEqual(result.sample_size, 5)
        self.assertIsInstance(result.confidence_interval_95, tuple)
        self.assertEqual(len(result.confidence_interval_95), 2)
    
    def test_analyze_metric_empty_data(self):
        """Test metric analysis with empty data"""
        result = self.analyzer.analyze_metric([])
        
        self.assertEqual(result.mean, 0.0)
        self.assertEqual(result.std, 0.0)
        self.assertEqual(result.sample_size, 0)
        self.assertEqual(result.confidence_interval_95, (0.0, 0.0))
    
    def test_confidence_interval_calculation(self):
        """Test confidence interval calculation"""
        ci = self.analyzer.calculate_confidence_interval(self.sample_data1)
        
        self.assertIsInstance(ci, tuple)
        self.assertEqual(len(ci), 2)
        self.assertLess(ci[0], ci[1])  # Lower bound < upper bound
        
        # CI should contain the mean
        mean = sum(self.sample_data1) / len(self.sample_data1)
        self.assertLessEqual(ci[0], mean)
        self.assertGreaterEqual(ci[1], mean)
    
    def test_bootstrap_confidence_interval(self):
        """Test bootstrap confidence interval"""
        ci = self.analyzer.bootstrap_confidence_interval(self.sample_data1, n_bootstrap=100)
        
        self.assertIsInstance(ci, tuple)
        self.assertEqual(len(ci), 2)
        self.assertLess(ci[0], ci[1])
    
    def test_compare_methods(self):
        """Test method comparison"""
        comparison = self.analyzer.compare_methods(
            self.sample_data1, self.sample_data2,
            "Method A", "Method B"
        )
        
        self.assertIn("method1", comparison)
        self.assertIn("method2", comparison)
        self.assertIn("method1_stats", comparison)
        self.assertIn("method2_stats", comparison)
        
        # Check if statistical tests are included (if scipy available)
        if hasattr(self.analyzer, 'SCIPY_AVAILABLE'):
            self.assertIn("t_test", comparison)
            self.assertIn("mann_whitney_u", comparison)
    
    def test_analyze_multiple_runs(self):
        """Test analysis of multiple runs"""
        result = self.analyzer.analyze_multiple_runs(
            "scan-001", "constrained", self.sample_results
        )
        
        self.assertIsInstance(result, MultiRunEvaluationResult)
        self.assertEqual(result.scenario_id, "scan-001")
        self.assertEqual(result.method, "constrained")
        self.assertEqual(len(result.runs), 3)
        self.assertEqual(result.success_rate, 1.0)  # All runs successful
        
        # Check statistical results
        self.assertIsInstance(result.jaccard_stats, StatisticalResult)
        self.assertIsInstance(result.f1_stats, StatisticalResult)
        self.assertEqual(result.jaccard_stats.sample_size, 3)
    
    def test_analyze_multiple_runs_with_failures(self):
        """Test analysis with some failed runs"""
        failed_results = self.sample_results + [
            {"error": "Generation failed", "seed": 45},
            {"error": "Validation failed", "seed": 46}
        ]
        
        result = self.analyzer.analyze_multiple_runs(
            "scan-002", "constrained", failed_results
        )
        
        self.assertEqual(len(result.runs), 5)
        self.assertEqual(result.success_rate, 0.6)  # 3 out of 5 successful
    
    def test_statistical_result_to_dict(self):
        """Test StatisticalResult serialization"""
        result = self.analyzer.analyze_metric(self.sample_data1)
        result_dict = result.to_dict()
        
        self.assertIn("mean", result_dict)
        self.assertIn("std", result_dict)
        self.assertIn("confidence_interval_95", result_dict)
        self.assertIn("sample_size", result_dict)
    
    def test_multi_run_result_to_dict(self):
        """Test MultiRunEvaluationResult serialization"""
        result = self.analyzer.analyze_multiple_runs(
            "scan-001", "constrained", self.sample_results
        )
        result_dict = result.to_dict()
        
        self.assertIn("scenario_id", result_dict)
        self.assertIn("method", result_dict)
        self.assertIn("statistics", result_dict)
        self.assertIn("individual_runs", result_dict)
        
        # Check nested statistics
        stats = result_dict["statistics"]
        self.assertIn("jaccard", stats)
        self.assertIn("f1", stats)
        self.assertIn("precision", stats)
        self.assertIn("recall", stats)

class TestStatisticalIntegration(unittest.TestCase):
    """Integration tests for statistical analysis"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.test_dir = Path("tests/fixtures/statistical_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def test_generate_statistical_report(self):
        """Test statistical report generation"""
        analyzer = StatisticalAnalyzer()
        
        # Create sample multi-run results
        results1 = [
            {"jaccard_similarity": 0.8, "f1_score": 0.85, "precision": 0.8, "recall": 0.9, "seed": 1},
            {"jaccard_similarity": 0.75, "f1_score": 0.8, "precision": 0.75, "recall": 0.85, "seed": 2}
        ]
        
        results2 = [
            {"jaccard_similarity": 0.9, "f1_score": 0.95, "precision": 0.9, "recall": 1.0, "seed": 1},
            {"jaccard_similarity": 0.85, "f1_score": 0.9, "precision": 0.85, "recall": 0.95, "seed": 2}
        ]
        
        multi_run_result1 = analyzer.analyze_multiple_runs("scan-001", "constrained", results1)
        multi_run_result2 = analyzer.analyze_multiple_runs("scan-001", "rules", results2)
        
        report = analyzer.generate_statistical_report([multi_run_result1, multi_run_result2])
        
        self.assertIn("timestamp", report)
        self.assertIn("analysis_summary", report)
        self.assertIn("results", report)
        self.assertIn("method_comparisons", report)
        
        # Check analysis summary
        summary = report["analysis_summary"]
        self.assertEqual(summary["total_scenarios"], 1)
        self.assertEqual(summary["total_methods"], 2)
        self.assertEqual(summary["total_runs"], 4)
        
        # Check method comparisons
        self.assertGreater(len(report["method_comparisons"]), 0)
    
    def test_statistical_evaluation_dry_run(self):
        """Test statistical evaluation without actually running scenarios"""
        # This is a dry run test that doesn't execute actual evaluation
        analyzer = StatisticalAnalyzer()
        
        # Mock results that would come from actual runs
        mock_results = [
            {"jaccard_similarity": 0.8, "f1_score": 0.85, "precision": 0.8, "recall": 0.9, "seed": 42},
            {"jaccard_similarity": 0.75, "f1_score": 0.8, "precision": 0.75, "recall": 0.85, "seed": 43},
            {"jaccard_similarity": 0.9, "f1_score": 0.95, "precision": 0.9, "recall": 1.0, "seed": 44}
        ]
        
        result = analyzer.analyze_multiple_runs("test-scenario", "test-method", mock_results)
        
        self.assertEqual(result.scenario_id, "test-scenario")
        self.assertEqual(result.method, "test-method")
        self.assertEqual(result.success_rate, 1.0)
        
        # Verify statistical calculations
        self.assertAlmostEqual(result.jaccard_stats.mean, 0.8167, places=3)
        self.assertAlmostEqual(result.f1_stats.mean, 0.8667, places=3)
    
    def test_save_and_load_statistical_results(self):
        """Test saving and loading statistical results"""
        analyzer = StatisticalAnalyzer()
        
        mock_results = [
            {"jaccard_similarity": 0.8, "f1_score": 0.85, "precision": 0.8, "recall": 0.9, "seed": 42},
            {"jaccard_similarity": 0.75, "f1_score": 0.8, "precision": 0.75, "recall": 0.85, "seed": 43}
        ]
        
        result = analyzer.analyze_multiple_runs("test-scenario", "test-method", mock_results)
        
        # Save to file
        output_file = self.test_dir / "test_statistical_result.json"
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Load and verify
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        self.assertEqual(loaded_data["scenario_id"], "test-scenario")
        self.assertEqual(loaded_data["method"], "test-method")
        self.assertIn("statistics", loaded_data)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()

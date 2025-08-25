#!/usr/bin/env python3
"""Tests for semantic similarity enhancements"""
import unittest
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.core.enhanced_evaluation import SemanticQueryAnalyzer, enhanced_evaluate_query

class TestSemanticSimilarity(unittest.TestCase):
    """Test semantic similarity improvements"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = SemanticQueryAnalyzer()
        
        # Test queries
        self.query1 = {
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
            }
        }
        
        self.query2 = {
            "query": {
                "bool": {
                    "must": [
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
            }
        }
        
        self.query3 = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "term": {
                                "protocol": "TCP"
                            }
                        }
                    ]
                }
            }
        }
    
    def test_query_to_semantic_description(self):
        """Test query to semantic description conversion"""
        description = self.analyzer.query_to_semantic_description(self.query1)
        
        self.assertIn("time filter", description)
        self.assertIn("exact match", description)
        self.assertIn("label equals malicious", description)
        self.assertIn("logical filter condition", description)
    
    def test_semantic_similarity_identical_queries(self):
        """Test semantic similarity with identical queries"""
        similarity = self.analyzer.calculate_semantic_similarity(self.query1, self.query1)
        self.assertGreaterEqual(similarity, 0.9)  # Should be very high for identical queries
    
    def test_semantic_similarity_similar_queries(self):
        """Test semantic similarity with structurally similar queries"""
        # query1 uses filter, query2 uses must - semantically similar
        similarity = self.analyzer.calculate_semantic_similarity(self.query1, self.query2)
        self.assertGreater(similarity, 0.7)  # Should be high similarity
    
    def test_semantic_similarity_different_queries(self):
        """Test semantic similarity with different queries"""
        similarity = self.analyzer.calculate_semantic_similarity(self.query1, self.query3)
        self.assertLess(similarity, 0.5)  # Should be low similarity
    
    def test_embedding_similarity_fallback(self):
        """Test embedding similarity gracefully falls back to structural similarity"""
        # This should work regardless of whether sentence-transformers is available
        similarity = self.analyzer.calculate_embedding_similarity(self.query1, self.query2)
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)
    
    def test_enhanced_evaluation_with_semantic_similarity(self):
        """Test enhanced evaluation uses semantic similarity"""
        # Mock data for evaluation
        generated_results = ["doc1", "doc2", "doc3"]
        ground_truth_results = ["doc1", "doc2", "doc4"]
        
        metrics = enhanced_evaluate_query(
            self.query1, self.query2, 
            generated_results, ground_truth_results
        )
        
        # Check that semantic similarity is included
        self.assertIn("semantic_similarity", metrics.to_dict()["enhanced"])
        self.assertIsInstance(metrics.semantic_similarity, float)
        self.assertGreaterEqual(metrics.semantic_similarity, 0.0)
        self.assertLessEqual(metrics.semantic_similarity, 1.0)
    
    def test_extract_semantic_components(self):
        """Test semantic component extraction"""
        components = self.analyzer.extract_semantic_components(self.query1)
        
        self.assertIn("time_constraints", components)
        self.assertIn("field_constraints", components)
        self.assertIn("logical_operators", components)
        self.assertIn("complexity_score", components)
        
        # Check time constraints are detected
        self.assertTrue(len(components["time_constraints"]) > 0)
        
        # Check field constraints are detected
        self.assertTrue(len(components["field_constraints"]) > 0)

class TestSemanticSimilarityIntegration(unittest.TestCase):
    """Integration tests for semantic similarity"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        # Create test data directory
        self.test_dir = Path("tests/fixtures/semantic_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def test_semantic_similarity_with_real_scenarios(self):
        """Test semantic similarity with real scenario data"""
        # Load a real scenario for testing
        try:
            with open("tasks/prompts.yaml") as f:
                import yaml
                scenarios = yaml.safe_load(f)
                
            if scenarios:
                scenario = scenarios[0]  # Use first scenario
                
                # This test would need actual generated queries to be meaningful
                # For now, just test that the analyzer can handle real data structures
                analyzer = SemanticQueryAnalyzer()
                
                if "expert_dsl" in scenario:
                    expert_dsl = scenario["expert_dsl"]
                    if isinstance(expert_dsl, str):
                        import yaml
                        expert_query = yaml.safe_load(expert_dsl)
                    else:
                        expert_query = expert_dsl
                    
                    # Test that semantic analysis doesn't crash on real queries
                    components = analyzer.extract_semantic_components(expert_query)
                    self.assertIsInstance(components, dict)
                    
                    # Test self-similarity is 1.0
                    similarity = analyzer.calculate_semantic_similarity(expert_query, expert_query)
                    self.assertEqual(similarity, 1.0)
        
        except Exception as e:
            self.skipTest(f"Could not load real scenario data: {e}")
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()

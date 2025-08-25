#!/usr/bin/env python3
"""Tests for formal verification system"""
import unittest
import json
import tempfile
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.security.formal_verification import (
    FormalVerifier, SecurityProperty, VerificationResult, PropertyViolation
)

class TestFormalVerifier(unittest.TestCase):
    """Test formal verification system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.verifier = FormalVerifier()
        
        # Test queries
        self.safe_query = {
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
            "size": 100
        }
        
        self.unsafe_query = {
            "query": {
                "match_all": {}
            },
            "size": 50000
        }
    
    def test_verifier_initialization(self):
        """Test verifier initialization"""
        verifier = FormalVerifier()
        self.assertIsNotNone(verifier.config)
        self.assertIn("allowed_fields", verifier.config)
        self.assertEqual(len(verifier.properties), 6)
    
    def test_load_custom_config(self):
        """Test loading custom configuration"""
        custom_config = {
            "max_time_range_days": 30,
            "max_result_size": 5000
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(custom_config, f)
            config_file = f.name
        
        try:
            verifier = FormalVerifier(config_file)
            self.assertEqual(verifier.config["max_time_range_days"], 30)
            self.assertEqual(verifier.config["max_result_size"], 5000)
        finally:
            Path(config_file).unlink(missing_ok=True)
    
    def test_verify_safe_query(self):
        """Test verification of a safe query"""
        report = self.verifier.verify_query(self.safe_query)
        
        self.assertEqual(report.total_properties, 6)
        self.assertGreaterEqual(report.verified_properties, 4)  # Most should pass
        self.assertGreaterEqual(report.security_score, 0.5)
        self.assertEqual(len(report.violations), report.violated_properties)
    
    def test_verify_unsafe_query(self):
        """Test verification of an unsafe query"""
        report = self.verifier.verify_query(self.unsafe_query)
        
        self.assertEqual(report.total_properties, 6)
        self.assertGreater(report.violated_properties, 0)  # Should have violations
        self.assertEqual(report.overall_result, VerificationResult.VIOLATED)
        self.assertLess(report.security_score, 1.0)
    
    def test_no_unrestricted_access(self):
        """Test unrestricted access detection"""
        unrestricted_query = {
            "query": {
                "match_all": {}
            }
        }
        
        result, violation = self.verifier._verify_no_unrestricted_access(unrestricted_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.NO_UNRESTRICTED_ACCESS)
        self.assertEqual(violation.severity, "critical")
    
    def test_time_bounded_queries(self):
        """Test time boundary verification"""
        # Query without time bounds
        no_time_query = {
            "query": {
                "term": {"label": "malicious"}
            }
        }
        
        result, violation = self.verifier._verify_time_bounded_queries(no_time_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.TIME_BOUNDED_QUERIES)
        
        # Query with excessive time range
        large_range_query = {
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": "2017-01-01T00:00:00Z",
                        "lte": "2017-12-31T23:59:59Z"
                    }
                }
            }
        }
        
        result, violation = self.verifier._verify_time_bounded_queries(large_range_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIn("too large", violation.description)
    
    def test_field_whitelist_compliance(self):
        """Test field whitelist verification"""
        restricted_query = {
            "query": {
                "term": {
                    "_id": "some_id"  # System field - should be restricted
                }
            }
        }
        
        result, violation = self.verifier._verify_field_whitelist_compliance(restricted_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.FIELD_WHITELIST_COMPLIANCE)
    
    def test_aggregation_bypass_detection(self):
        """Test aggregation bypass detection"""
        dangerous_agg_query = {
            "query": {"match_all": {}},
            "aggs": {
                "dangerous": {
                    "script": {
                        "source": "malicious script"
                    }
                }
            }
        }
        
        result, violation = self.verifier._verify_no_aggregation_bypass(dangerous_agg_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.NO_AGGREGATION_BYPASS)
    
    def test_query_size_limits(self):
        """Test query size limit verification"""
        large_size_query = {
            "query": {"match_all": {}},
            "size": 50000  # Exceeds default limit
        }
        
        result, violation = self.verifier._verify_query_size_limits(large_size_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.QUERY_SIZE_LIMITS)
    
    def test_system_metadata_access(self):
        """Test system metadata access detection"""
        metadata_query = {
            "query": {
                "term": {
                    "_index": "logs_net"
                }
            }
        }
        
        result, violation = self.verifier._verify_no_system_metadata_access(metadata_query)
        self.assertEqual(result, VerificationResult.VIOLATED)
        self.assertIsNotNone(violation)
        self.assertEqual(violation.property, SecurityProperty.NO_SYSTEM_METADATA_ACCESS)
    
    def test_calculate_time_range_days(self):
        """Test time range calculation"""
        # Same day
        days = self.verifier._calculate_time_range_days(
            "2017-07-04T00:00:00Z", "2017-07-04T23:59:59Z"
        )
        self.assertEqual(days, 0)
        
        # One week
        days = self.verifier._calculate_time_range_days(
            "2017-07-04T00:00:00Z", "2017-07-11T00:00:00Z"
        )
        self.assertEqual(days, 7)
        
        # Invalid format
        days = self.verifier._calculate_time_range_days(
            "invalid", "also-invalid"
        )
        self.assertIsNone(days)
    
    def test_matches_pattern(self):
        """Test pattern matching for field restrictions"""
        self.assertTrue(self.verifier._matches_pattern("system.cpu", "system.*"))
        self.assertTrue(self.verifier._matches_pattern("admin", "admin*"))
        self.assertFalse(self.verifier._matches_pattern("label", "system.*"))
        self.assertTrue(self.verifier._matches_pattern("test", "t?st"))
    
    def test_security_score_calculation(self):
        """Test security score calculation"""
        # No violations
        score = self.verifier._calculate_security_score([], 6)
        self.assertEqual(score, 1.0)
        
        # One critical violation
        critical_violation = PropertyViolation(
            property=SecurityProperty.NO_UNRESTRICTED_ACCESS,
            description="Test violation",
            violation_location="test",
            evidence="test",
            severity="critical"
        )
        score = self.verifier._calculate_security_score([critical_violation], 6)
        self.assertLess(score, 1.0)
        self.assertGreater(score, 0.8)  # Should still be relatively high
        
        # Multiple violations of different severities
        medium_violation = PropertyViolation(
            property=SecurityProperty.QUERY_SIZE_LIMITS,
            description="Test violation",
            violation_location="test",
            evidence="test",
            severity="medium"
        )
        score = self.verifier._calculate_security_score([critical_violation, medium_violation], 6)
        self.assertLess(score, 0.9)
    
    def test_property_violation_serialization(self):
        """Test PropertyViolation serialization"""
        violation = PropertyViolation(
            property=SecurityProperty.TIME_BOUNDED_QUERIES,
            description="Time range too large",
            violation_location="@timestamp range",
            evidence="365 days",
            severity="medium"
        )
        
        violation_dict = violation.to_dict()
        
        self.assertIn("property", violation_dict)
        self.assertIn("description", violation_dict)
        self.assertIn("violation_location", violation_dict)
        self.assertIn("evidence", violation_dict)
        self.assertIn("severity", violation_dict)
        self.assertEqual(violation_dict["property"], "time_bounded_queries")
    
    def test_verification_report_serialization(self):
        """Test VerificationReport serialization"""
        report = self.verifier.verify_query(self.safe_query)
        report_dict = report.to_dict()
        
        self.assertIn("query", report_dict)
        self.assertIn("total_properties", report_dict)
        self.assertIn("verified_properties", report_dict)
        self.assertIn("violated_properties", report_dict)
        self.assertIn("violations", report_dict)
        self.assertIn("overall_result", report_dict)
        self.assertIn("security_score", report_dict)
        
        # Check that violations are properly serialized
        self.assertIsInstance(report_dict["violations"], list)
        if report_dict["violations"]:
            self.assertIsInstance(report_dict["violations"][0], dict)

class TestFormalVerificationIntegration(unittest.TestCase):
    """Integration tests for formal verification"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.test_dir = Path("tests/fixtures/verification_test")
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def test_verify_query_file(self):
        """Test verifying a query from file"""
        test_query = {
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
        
        query_file = self.test_dir / "test_query.json"
        with open(query_file, 'w') as f:
            json.dump(test_query, f)
        
        # Test file verification
        from src.security.formal_verification import verify_query_file
        
        report = verify_query_file(str(query_file))
        
        self.assertIsNotNone(report)
        self.assertEqual(report.total_properties, 6)
        self.assertGreaterEqual(report.security_score, 0.0)
        self.assertLessEqual(report.security_score, 1.0)
    
    def test_custom_config_integration(self):
        """Test integration with custom configuration"""
        custom_config = {
            "allowed_fields": ["@timestamp", "label", "custom_field"],
            "max_time_range_days": 1,
            "max_result_size": 100
        }
        
        config_file = self.test_dir / "custom_config.json"
        with open(config_file, 'w') as f:
            json.dump(custom_config, f)
        
        verifier = FormalVerifier(str(config_file))
        
        # Test that custom config is loaded
        self.assertEqual(verifier.config["max_time_range_days"], 1)
        self.assertEqual(verifier.config["max_result_size"], 100)
        self.assertIn("custom_field", verifier.config["allowed_fields"])
        
        # Test verification with custom config
        test_query = {
            "query": {
                "term": {
                    "custom_field": "test"
                }
            }
        }
        
        report = verifier.verify_query(test_query)
        self.assertIsNotNone(report)
    
    def test_security_property_coverage(self):
        """Test that all security properties are covered"""
        verifier = FormalVerifier()
        
        # Verify all properties are tested
        expected_properties = {
            SecurityProperty.NO_UNRESTRICTED_ACCESS,
            SecurityProperty.TIME_BOUNDED_QUERIES,
            SecurityProperty.FIELD_WHITELIST_COMPLIANCE,
            SecurityProperty.NO_AGGREGATION_BYPASS,
            SecurityProperty.QUERY_SIZE_LIMITS,
            SecurityProperty.NO_SYSTEM_METADATA_ACCESS
        }
        
        actual_properties = set(verifier.properties)
        self.assertEqual(expected_properties, actual_properties)
        
        # Test that each property can be verified
        test_query = {"query": {"match_all": {}}}
        
        for prop in verifier.properties:
            result, violation = verifier._verify_property(test_query, prop)
            self.assertIsInstance(result, VerificationResult)
            # violation can be None or PropertyViolation
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()

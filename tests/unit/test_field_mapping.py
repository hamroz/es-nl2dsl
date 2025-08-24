"""Unit tests for field mapping utilities"""
import unittest
from src.generators.utils.field_mapping import FIELD_CORRECTIONS, correct_field_mappings


class TestFieldMapping(unittest.TestCase):
    """Test field mapping corrections"""
    
    def test_basic_field_correction(self):
        """Test basic field name correction"""
        query = {
            "query": {
                "term": {
                    "source.ip": "192.168.1.1"
                }
            }
        }
        corrected = correct_field_mappings(query)
        self.assertIn("src_ip", corrected["query"]["term"])
        self.assertNotIn("source.ip", corrected["query"]["term"])
    
    def test_nested_field_correction(self):
        """Test nested field corrections in bool queries"""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"destination.port": 443}},
                        {"range": {"timestamp": {"gte": "2024-01-01"}}}
                    ]
                }
            }
        }
        corrected = correct_field_mappings(query)
        self.assertIn("dst_port", corrected["query"]["bool"]["must"][0]["term"])
        self.assertIn("@timestamp", corrected["query"]["bool"]["must"][1]["range"])
    
    def test_no_correction_needed(self):
        """Test that correct fields are not changed"""
        query = {
            "query": {
                "term": {
                    "src_ip": "10.0.0.1"
                }
            }
        }
        corrected = correct_field_mappings(query)
        self.assertEqual(query, corrected)


if __name__ == "__main__":
    unittest.main()
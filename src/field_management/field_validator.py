"""
Field Validator - Pre-validates and suggests corrections for field names
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import difflib

logger = logging.getLogger(__name__)

class FieldValidator:
    """Validates field names and provides intelligent suggestions."""
    
    def __init__(self, field_context_manager=None):
        self.field_context_manager = field_context_manager
        
        # Valid field sets for different indices
        self.valid_fields = {
            "logs_net": {
                "@timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
                "protocol", "bytes_in", "bytes_out", "label", "message"
            },
            "logs_cic_ids2017": {
                "@timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
                "protocol", "label", "attack_type", "flow_duration",
                "flow_packets_s", "flow_bytes_s", "total_packets",
                "bytes_in", "bytes_out", "syn_flag_count", "rst_flag_count",
                "psh_flag_count", "ack_flag_count", "urg_flag_count",
                "fin_flag_count", "day_of_week", "hour_of_day"
            }
        }
        
        # Field type constraints
        self.field_types = {
            "@timestamp": "date",
            "src_ip": "keyword",
            "dst_ip": "keyword",
            "src_port": "integer",
            "dst_port": "integer",
            "protocol": "keyword",
            "bytes_in": "long",
            "bytes_out": "long",
            "label": "keyword",
            "attack_type": "keyword",
            "flow_duration": "long",
            "flow_packets_s": "float",
            "flow_bytes_s": "float",
            "total_packets": "long",
            "day_of_week": "keyword",
            "hour_of_day": "integer"
        }
        
        # Confidence scoring weights
        self.confidence_weights = {
            "exact_match": 1.0,
            "case_insensitive_match": 0.95,
            "known_alias": 0.9,
            "partial_match": 0.7,
            "fuzzy_match": 0.6,
            "semantic_similarity": 0.5
        }
    
    def validate_field(self, field_name: str, index: str = None) -> Tuple[bool, Optional[str], float]:
        """
        Validate a field name and return correction if needed.
        Returns: (is_valid, suggested_field, confidence)
        """
        # Get valid fields for index
        valid_fields = self._get_valid_fields_for_index(index)
        
        # Check exact match
        if field_name in valid_fields:
            return True, field_name, 1.0
        
        # Check case-insensitive match
        field_lower = field_name.lower()
        for valid_field in valid_fields:
            if field_lower == valid_field.lower():
                return False, valid_field, self.confidence_weights["case_insensitive_match"]
        
        # Get suggestions from context manager
        if self.field_context_manager:
            suggestions = self.field_context_manager.get_field_suggestions(field_name)
            if suggestions:
                best_suggestion = suggestions[0]
                if best_suggestion[0] in valid_fields:
                    return False, best_suggestion[0], best_suggestion[1]
        
        # Try fuzzy matching
        close_matches = difflib.get_close_matches(field_name, valid_fields, n=1, cutoff=0.6)
        if close_matches:
            return False, close_matches[0], self.confidence_weights["fuzzy_match"]
        
        # No valid match found
        return False, None, 0.0
    
    def validate_query_fields(self, query: Dict, index: str = None) -> Dict:
        """
        Validate all fields in a query and return validation report.
        """
        report = {
            "valid": True,
            "fields_checked": 0,
            "corrections_needed": [],
            "warnings": [],
            "field_validations": {}
        }
        
        # Extract fields from query
        fields = self._extract_fields_from_query(query)
        report["fields_checked"] = len(fields)
        
        for field in fields:
            is_valid, suggestion, confidence = self.validate_field(field, index)
            
            field_validation = {
                "field": field,
                "is_valid": is_valid,
                "suggestion": suggestion,
                "confidence": confidence
            }
            
            report["field_validations"][field] = field_validation
            
            if not is_valid:
                report["valid"] = False
                if suggestion:
                    report["corrections_needed"].append({
                        "original": field,
                        "suggested": suggestion,
                        "confidence": confidence
                    })
                else:
                    report["warnings"].append(f"Unknown field: {field}")
        
        return report
    
    def suggest_field_corrections(self, field_name: str, index: str = None) -> List[Dict]:
        """
        Get detailed field correction suggestions with explanations.
        """
        suggestions = []
        valid_fields = self._get_valid_fields_for_index(index)
        
        # Use context manager suggestions if available
        if self.field_context_manager:
            context_suggestions = self.field_context_manager.get_field_suggestions(field_name)
            for suggested_field, confidence in context_suggestions:
                if suggested_field in valid_fields:
                    context = self.field_context_manager.get_field_context(suggested_field)
                    suggestions.append({
                        "field": suggested_field,
                        "confidence": confidence,
                        "reason": self._get_suggestion_reason(field_name, suggested_field, confidence),
                        "type": self.field_types.get(suggested_field, "unknown"),
                        "description": context.get("description", ""),
                        "examples": context.get("examples", [])
                    })
        
        # Add fuzzy matches
        fuzzy_matches = difflib.get_close_matches(field_name, valid_fields, n=3, cutoff=0.5)
        for match in fuzzy_matches:
            if not any(s["field"] == match for s in suggestions):
                suggestions.append({
                    "field": match,
                    "confidence": self.confidence_weights["fuzzy_match"],
                    "reason": "Similar spelling",
                    "type": self.field_types.get(match, "unknown"),
                    "description": "",
                    "examples": []
                })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def pre_validate_prompt_fields(self, prompt: str, index: str = None) -> Dict:
        """
        Pre-validate fields mentioned in a natural language prompt.
        """
        report = {
            "prompt": prompt,
            "potential_fields": [],
            "suggestions": {}
        }
        
        # Extract potential field references from prompt
        potential_fields = self._extract_fields_from_prompt(prompt)
        report["potential_fields"] = potential_fields
        
        for field in potential_fields:
            is_valid, suggestion, confidence = self.validate_field(field, index)
            if not is_valid and suggestion:
                report["suggestions"][field] = {
                    "suggested": suggestion,
                    "confidence": confidence,
                    "hint": f"Use '{suggestion}' instead of '{field}'"
                }
        
        return report
    
    def _get_valid_fields_for_index(self, index: str = None) -> Set[str]:
        """Get valid fields for a specific index."""
        if index and index in self.valid_fields:
            return self.valid_fields[index]
        
        # Return union of all fields if no specific index
        all_fields = set()
        for fields in self.valid_fields.values():
            all_fields.update(fields)
        return all_fields
    
    def _extract_fields_from_query(self, query: Dict) -> Set[str]:
        """Extract all field names from an Elasticsearch query."""
        fields = set()
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    # Common query types
                    if key in ["term", "terms", "match", "range"]:
                        if isinstance(value, dict):
                            fields.update(value.keys())
                    elif key == "exists":
                        if isinstance(value, dict) and "field" in value:
                            fields.add(value["field"])
                    elif key == "aggs" or key == "aggregations":
                        # Handle aggregations
                        if isinstance(value, dict):
                            for agg_name, agg_def in value.items():
                                if isinstance(agg_def, dict):
                                    for agg_type, agg_config in agg_def.items():
                                        if isinstance(agg_config, dict) and "field" in agg_config:
                                            fields.add(agg_config["field"])
                    else:
                        extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(query)
        return fields
    
    def _extract_fields_from_prompt(self, prompt: str) -> List[str]:
        """Extract potential field names from natural language prompt."""
        potential_fields = []
        
        # Common field indicators in prompts
        field_indicators = [
            "source ip", "source_ip", "src_ip", "srcip",
            "destination ip", "destination_ip", "dst_ip", "dstip",
            "source port", "source_port", "src_port", "srcport",
            "destination port", "destination_port", "dst_port", "dstport",
            "timestamp", "@timestamp", "time",
            "protocol", "bytes", "label", "attack"
        ]
        
        prompt_lower = prompt.lower()
        for indicator in field_indicators:
            if indicator in prompt_lower:
                # Try to find the exact form used in the prompt
                import re
                pattern = re.compile(re.escape(indicator), re.IGNORECASE)
                matches = pattern.findall(prompt)
                if matches:
                    potential_fields.append(matches[0])
                else:
                    potential_fields.append(indicator)
        
        return potential_fields
    
    def _get_suggestion_reason(self, original: str, suggested: str, confidence: float) -> str:
        """Get human-readable reason for suggestion."""
        if confidence >= 0.95:
            return "Case correction"
        elif confidence >= 0.9:
            return "Known alias"
        elif confidence >= 0.8:
            return "Common variant"
        elif confidence >= 0.7:
            return "ECS to actual field mapping"
        elif confidence >= 0.6:
            return "Similar spelling"
        else:
            return "Possible match"
    
    def get_field_type_constraints(self, field_name: str) -> Dict:
        """Get type constraints for a field."""
        field_type = self.field_types.get(field_name, "unknown")
        
        constraints = {
            "field": field_name,
            "type": field_type,
            "operators": []
        }
        
        if field_type in ["keyword", "text"]:
            constraints["operators"] = ["term", "terms", "match", "exists"]
            constraints["example_values"] = ["malicious", "benign", "tcp", "udp"]
        elif field_type in ["integer", "long", "float", "double"]:
            constraints["operators"] = ["term", "terms", "range", "exists"]
            constraints["range_operators"] = ["gte", "gt", "lte", "lt"]
            constraints["example_values"] = [80, 443, 1024]
        elif field_type == "date":
            constraints["operators"] = ["range", "exists"]
            constraints["range_operators"] = ["gte", "gt", "lte", "lt"]
            constraints["format"] = "ISO 8601 (e.g., 2024-01-15T00:00:00Z)"
        
        return constraints
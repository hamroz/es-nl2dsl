#!/usr/bin/env python3
"""
Index-Aware Query Generator: Intelligent wrapper that automatically adapts 
query generation to specific index schemas and characteristics.
"""
import json
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.generators.constrained import (
    call_local_model, validate_against_schema, load_fewshot_examples,
    check_security_violations, generate_with_retries, ALLOWED_OPERATORS
)
from src.data_adaptation.mapping_storage import MappingStorage
from src.index_profiler import IndexProfiler

logger = logging.getLogger(__name__)

class IndexAwareGenerator:
    """Intelligent query generator that adapts to specific index characteristics"""
    
    def __init__(self):
        self.mapping_storage = MappingStorage()
        self.profiler = IndexProfiler()
    
    def generate_query(
        self,
        prompt: str,
        index: str = "logs_net", 
        model: str = "llama3.1:latest",
        schema_path: str = "artifacts/esdsl_schema.json",
        rules_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate query with index-specific intelligence"""
        
        logger.info(f"🎯 Generating index-aware query for {index}")
        
        # Get index profile and mapping information
        index_profile = self.profiler.analyze_index(index)
        field_mapping = self.mapping_storage.get_field_mapping_for_query_generation(index)
        
        # Build index-specific prompt
        enhanced_prompt = self._build_index_aware_prompt(
            prompt, index, index_profile, field_mapping
        )
        
        logger.debug(f"Enhanced prompt length: {len(enhanced_prompt)} chars")
        
        # Generate query using enhanced prompt
        try:
            result = self._call_model_with_retry(enhanced_prompt, model)
            
            # Parse and validate the result
            if result.startswith("ABSTAIN:"):
                return {"abstain": True, "reason": result[8:].strip()}
            
            # Parse JSON
            query_json = json.loads(result)
            
            # Post-process with index-specific validation and correction
            corrected_query = self._post_process_query(query_json, index_profile, field_mapping)
            
            # Validate against schema
            if schema_path:
                validate_against_schema(corrected_query, schema_path)
            
            logger.info(f"✅ Successfully generated index-aware query for {index}")
            return corrected_query
            
        except Exception as e:
            logger.error(f"❌ Error generating query for {index}: {e}")
            raise
    
    def _build_index_aware_prompt(
        self,
        user_prompt: str,
        index: str,
        index_profile,
        field_mapping: Dict[str, Any]
    ) -> str:
        """Build a prompt specifically tailored to the target index"""
        
        prompt = "You are an expert at generating Elasticsearch DSL queries. "
        prompt += f"You are querying the '{index}' index.\n\n"
        
        # Add index-specific context
        prompt += f"INDEX INFORMATION:\n"
        prompt += f"- Index: {index}\n"
        prompt += f"- Documents: {index_profile.document_count:,}\n"
        prompt += f"- Primary timestamp field: {index_profile.primary_timestamp_field}\n"
        
        # Add actual date range from the data
        if index_profile.date_range.get("min_date") and index_profile.date_range.get("max_date"):
            prompt += f"- Data date range: {index_profile.date_range['min_date']} to {index_profile.date_range['max_date']}\n"
        
        # Add system type if available
        system_type = field_mapping.get("system_type", "Unknown")
        if system_type != "Unknown":
            prompt += f"- System type: {system_type}\n"
        
        prompt += "\n"
        
        # Add available fields with actual types and descriptions
        prompt += "AVAILABLE FIELDS:\n"
        field_catalog = self.profiler.get_field_catalog_for_index(index)
        
        # Prioritize and limit fields to keep prompt manageable
        important_keywords = ["timestamp", "time", "ip", "address", "label", "attack", "status", "action", "port", "protocol", "bytes"]
        
        # Group fields by importance
        critical_fields = []  # timestamp, labels, IPs
        important_fields = []  # ports, protocols, bytes
        other_fields = []
        
        for field_name, field_info in field_catalog.items():
            field_line = f"- {field_name} ({field_info['type']}): {field_info['description']}"
            
            # Critical fields (always include)
            if any(keyword in field_name.lower() for keyword in ["timestamp", "time", "label", "attack", "ip", "address"]):
                critical_fields.append(field_line)
            # Important fields (include if space allows)
            elif any(keyword in field_name.lower() for keyword in ["port", "protocol", "bytes", "status", "action"]):
                important_fields.append(field_line)
            else:
                other_fields.append(field_line)
        
        # Add fields with limits to prevent prompt bloat
        field_count = 0
        max_fields = 20  # Reasonable limit
        
        # Add all critical fields
        for field_line in critical_fields:
            if field_count < max_fields:
                prompt += field_line + "\n"
                field_count += 1
        
        # Add important fields up to limit
        for field_line in important_fields:
            if field_count < max_fields:
                prompt += field_line + "\n"
                field_count += 1
        
        # Add some other fields if space remains
        for field_line in other_fields:
            if field_count < max_fields:
                prompt += field_line + "\n"
                field_count += 1
        
        if len(field_catalog) > max_fields:
            prompt += f"... and {len(field_catalog) - field_count} more fields available\n"
        
        # Add semantic field mappings if available
        if index_profile.suggested_field_mappings:
            prompt += "\nFIELD MAPPINGS (use these actual field names):\n"
            for semantic, actual in index_profile.suggested_field_mappings.items():
                prompt += f"- {semantic} → {actual}\n"
        
        prompt += "\n"
        
        # Add allowed operators
        prompt += "ALLOWED QUERY OPERATORS:\n"
        for op, desc in ALLOWED_OPERATORS.items():
            prompt += f"- {op}: {desc}\n"
        
        prompt += "\n"
        
        # Add index-specific rules
        prompt += "RULES:\n"
        prompt += "- Always use bool.filter for combining conditions\n"
        prompt += f"- Always include a time range filter using {index_profile.primary_timestamp_field}\n"
        
        # Use actual date range from the index
        if index_profile.date_range.get("min_date") and index_profile.date_range.get("max_date"):
            min_date = index_profile.date_range["min_date"]
            max_date = index_profile.date_range["max_date"]
            prompt += f"- For time ranges, use dates between {min_date} and {max_date}\n"
        else:
            prompt += "- For time ranges, use recent dates or dates mentioned in the query\n"
        
        prompt += "- Use term for exact matches, terms for multiple values\n"
        prompt += "- Use range only for date and numeric fields\n"
        prompt += "- Only use fields that exist in the AVAILABLE FIELDS list above\n"
        prompt += "- Output only valid JSON, no explanations\n\n"
        
        # Add index-specific examples (limit to 2 to keep prompt manageable)
        prompt += "EXAMPLES:\n"
        examples = self._get_index_specific_examples(index, index_profile, field_mapping)
        for example in examples[:2]:  # Limit to 2 examples
            prompt += f"Input: {example['prompt']}\n"
            prompt += f"Output: {json.dumps(example['query'], separators=(',', ':'))}\n\n"  # Compact JSON
        
        # Add the actual user prompt
        prompt += f"Input: {user_prompt}\n"
        prompt += "Output:"
        
        return prompt
    
    def _get_index_specific_examples(
        self, 
        index: str, 
        index_profile,
        field_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate examples tailored to the specific index"""
        
        examples = []
        timestamp_field = index_profile.primary_timestamp_field
        date_range = index_profile.date_range
        available_fields = set(index_profile.fields.keys())
        
        # Use actual date range for examples
        if date_range.get("min_date") and date_range.get("max_date"):
            sample_start = date_range["min_date"]
            sample_end = date_range["max_date"]
        else:
            sample_start = "2024-01-01T00:00:00Z"
            sample_end = "2024-01-01T23:59:59Z"
        
        # Example 1: Basic time range query
        if timestamp_field in available_fields:
            examples.append({
                "prompt": "Find recent events",
                "query": {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        timestamp_field: {
                                            "gte": sample_start,
                                            "lte": sample_end
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            })
        
        # Example 2: IP-based query if IP fields exist
        ip_fields = [f for f in available_fields if "ip" in f.lower()]
        if ip_fields:
            ip_field = ip_fields[0]
            examples.append({
                "prompt": f"Find traffic from a specific IP address",
                "query": {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        timestamp_field: {
                                            "gte": sample_start,
                                            "lte": sample_end
                                        }
                                    }
                                },
                                {
                                    "term": {
                                        ip_field: "192.168.1.100"
                                    }
                                }
                            ]
                        }
                    }
                }
            })
        
        # Example 3: Label/status-based query if such fields exist
        label_fields = [f for f in available_fields 
                       if any(keyword in f.lower() for keyword in ["label", "status", "action", "threat"])]
        if label_fields:
            label_field = label_fields[0]
            # Get common values for this field
            field_info = index_profile.fields[label_field]
            common_values = list(field_info.common_values.keys())
            sample_value = common_values[0] if common_values else "malicious"
            
            examples.append({
                "prompt": f"Find events with specific classification",
                "query": {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        timestamp_field: {
                                            "gte": sample_start,
                                            "lte": sample_end
                                        }
                                    }
                                },
                                {
                                    "term": {
                                        label_field: sample_value
                                    }
                                }
                            ]
                        }
                    }
                }
            })
        
        # If no custom examples, fall back to generic ones adapted to this index
        if not examples:
            # Try to load standard examples and adapt them
            try:
                standard_examples = load_fewshot_examples(index)
                for example in standard_examples[:3]:
                    # Adapt the example to use the correct timestamp field
                    adapted_example = self._adapt_example_to_index(example, index_profile)
                    if adapted_example:
                        examples.append(adapted_example)
            except Exception as e:
                logger.debug(f"Could not load standard examples: {e}")
        
        return examples
    
    def _adapt_example_to_index(self, example: Dict[str, Any], index_profile) -> Optional[Dict[str, Any]]:
        """Adapt a standard example to use the correct fields for this index"""
        try:
            query = example.get("query", {})
            adapted_query = self._replace_timestamp_field(query, index_profile.primary_timestamp_field)
            
            return {
                "prompt": example.get("prompt", "Example query"),
                "query": adapted_query
            }
        except Exception as e:
            logger.debug(f"Error adapting example: {e}")
            return None
    
    def _replace_timestamp_field(self, query_obj: Any, new_timestamp_field: str) -> Any:
        """Recursively replace @timestamp with the correct timestamp field"""
        if isinstance(query_obj, dict):
            new_dict = {}
            for key, value in query_obj.items():
                if key == "@timestamp":
                    new_dict[new_timestamp_field] = value
                else:
                    new_dict[key] = self._replace_timestamp_field(value, new_timestamp_field)
            return new_dict
        elif isinstance(query_obj, list):
            return [self._replace_timestamp_field(item, new_timestamp_field) for item in query_obj]
        else:
            return query_obj
    
    def _call_model_with_retry(self, prompt: str, model: str, max_retries: int = 3) -> str:
        """Call the model with retry logic"""
        for attempt in range(max_retries):
            try:
                # Check for security violations
                is_violation, violation_msg = check_security_violations(prompt)
                if is_violation:
                    return f"ABSTAIN: {violation_msg}"
                
                # Call the model
                result = call_local_model(prompt, model)
                
                # Basic validation - should start with { and end with }
                result = result.strip()
                if result.startswith("{") and result.endswith("}"):
                    return result
                else:
                    logger.warning(f"Attempt {attempt + 1}: Invalid JSON format from model")
                    if attempt == max_retries - 1:
                        return f"ABSTAIN: Model returned invalid JSON format after {max_retries} attempts"
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return f"ABSTAIN: Model call failed after {max_retries} attempts: {str(e)}"
        
        return "ABSTAIN: Unexpected error in model calling"
    
    def _post_process_query(
        self, 
        query: Dict[str, Any], 
        index_profile,
        field_mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post-process the generated query to fix common issues"""
        
        # Validate and correct field names
        corrected_query = self._correct_field_names(query, index_profile)
        
        # Ensure timestamp field is correct
        corrected_query = self._ensure_correct_timestamp_field(corrected_query, index_profile)
        
        # Validate date ranges are within actual data range
        corrected_query = self._validate_date_ranges(corrected_query, index_profile)
        
        return corrected_query
    
    def _correct_field_names(self, query: Dict[str, Any], index_profile) -> Dict[str, Any]:
        """Correct field names using the index profile and semantic mappings"""
        available_fields = set(index_profile.fields.keys())
        semantic_mappings = index_profile.suggested_field_mappings
        
        def correct_recursive(obj):
            if isinstance(obj, dict):
                new_dict = {}
                for key, value in obj.items():
                    # Check if this is a field reference
                    if key in ["term", "terms", "range"] and isinstance(value, dict):
                        # This is a field query - check the field names
                        corrected_value = {}
                        for field_name, field_value in value.items():
                            corrected_field = self._find_correct_field_name(
                                field_name, available_fields, semantic_mappings
                            )
                            corrected_value[corrected_field] = field_value
                        new_dict[key] = corrected_value
                    else:
                        new_dict[key] = correct_recursive(value)
                return new_dict
            elif isinstance(obj, list):
                return [correct_recursive(item) for item in obj]
            else:
                return obj
        
        return correct_recursive(query)
    
    def _find_correct_field_name(
        self, 
        field_name: str, 
        available_fields: set, 
        semantic_mappings: Dict[str, str]
    ) -> str:
        """Find the correct field name, with fallback strategies"""
        
        # Direct match
        if field_name in available_fields:
            return field_name
        
        # Semantic mapping
        for semantic, actual in semantic_mappings.items():
            if field_name == semantic and actual in available_fields:
                return actual
        
        # Fuzzy matching (case insensitive, partial)
        field_lower = field_name.lower()
        for available_field in available_fields:
            if available_field.lower() == field_lower:
                return available_field
            if field_lower in available_field.lower() or available_field.lower() in field_lower:
                return available_field
        
        # No match found - log warning but return original
        logger.warning(f"Field '{field_name}' not found in index, available: {list(available_fields)[:10]}")
        return field_name
    
    def _ensure_correct_timestamp_field(self, query: Dict[str, Any], index_profile) -> Dict[str, Any]:
        """Ensure the correct timestamp field is used"""
        correct_timestamp = index_profile.primary_timestamp_field
        
        if correct_timestamp == "@timestamp":
            return query  # Standard field, no change needed
        
        return self._replace_timestamp_field(query, correct_timestamp)
    
    def _validate_date_ranges(self, query: Dict[str, Any], index_profile) -> Dict[str, Any]:
        """Validate that date ranges are reasonable for the index"""
        data_range = index_profile.date_range
        
        if not (data_range.get("min_date") and data_range.get("max_date")):
            return query  # No validation possible
        
        # This is a simplified validation - in a full implementation, we'd parse
        # and validate all date ranges in the query
        logger.debug(f"Query dates should be within {data_range['min_date']} to {data_range['max_date']}")
        
        return query


def main():
    """CLI interface for the index-aware generator"""
    parser = argparse.ArgumentParser(description="Generate index-aware Elasticsearch queries")
    parser.add_argument("--prompt", required=True, help="Natural language query prompt")
    parser.add_argument("--index", default="logs_net", help="Target Elasticsearch index")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use for generation")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file path")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--task-id", help="Task ID for output naming")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [INDEX-AWARE] - %(levelname)s - %(message)s'
    )
    
    try:
        generator = IndexAwareGenerator()
        result = generator.generate_query(
            prompt=args.prompt,
            index=args.index,
            model=args.model,
            schema_path=args.schema
        )
        
        # Save result
        if args.output:
            output_file = Path(args.output)
        elif args.task_id:
            output_file = Path("artifacts/generated") / f"{args.task_id}.json"
        else:
            output_file = Path("artifacts/generated") / "index_aware_generated.json"
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        if "abstain" in result:
            print(f"Generation abstained: {result['reason']}")
            sys.exit(1)
        else:
            print(f"Successfully generated index-aware query saved to {output_file}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

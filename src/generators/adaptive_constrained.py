#!/usr/bin/env python3
"""Adaptive constrained generator that understands field mappings from newly adapted data"""
import json
import argparse
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.generators.constrained import (
    call_local_model, 
    AMBIGUOUS_TERMS, 
    check_security_violations_basic,
    generate_with_retries
)
from src.data_adaptation.mapping_storage import MappingStorage

logger = logging.getLogger(__name__)

class AdaptiveConstrainedGenerator:
    """Enhanced constrained generator that adapts to new data schemas"""
    
    def __init__(self):
        self.mapping_storage = MappingStorage()
    
    def generate_query(
        self, 
        prompt: str, 
        index: str = "logs_net", 
        model: str = "llama3.1:latest",
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate query with adaptive field understanding"""
        
        # Get field mapping for the target index
        field_mapping = self.mapping_storage.get_field_mapping_for_query_generation(index)
        
        if field_mapping and field_mapping.get("all_fields"):
            # This is an adapted index - use enhanced prompting
            return self._generate_adapted_query(prompt, index, model, field_mapping, task_id)
        else:
            # Fall back to original constrained generation
            return self._generate_standard_query(prompt, index, model, task_id)
    
    def _generate_adapted_query(
        self, 
        prompt: str, 
        index: str, 
        model: str,
        field_mapping: Dict[str, Any],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate query for adapted data with field awareness"""
        
        # Create enhanced prompt with field information
        enhanced_prompt = self._create_enhanced_prompt(prompt, field_mapping)
        
        # Generate query with context
        try:
            response = self._call_ai_model(enhanced_prompt, model)
            
            # Parse and validate the response
            query = self._parse_and_validate_response(response, field_mapping)
            
            # Apply security checks
            security_result = check_security_violations_basic(prompt)
            if not security_result.get("is_safe", False):
                return {
                    "abstain": True,
                    "reason": f"Security violation: {security_result.get('violation_type', 'Unknown')}",
                    "raw_prompt": prompt
                }
            
            # Store result if task_id provided
            if task_id:
                self._store_result(query, task_id, "adaptive_constrained")
            
            return query
            
        except Exception as e:
            logger.error(f"Error in adaptive query generation: {e}")
            return {
                "abstain": True,
                "reason": f"Generation error: {str(e)}",
                "raw_prompt": prompt
            }
    
    def _generate_standard_query(
        self, 
        prompt: str, 
        index: str, 
        model: str,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fall back to standard constrained generation"""
        try:
            # Use existing constrained generation logic
            return generate_with_retries(prompt, model, max_retries=3)
        except Exception as e:
            logger.error(f"Error in standard query generation: {e}")
            return {
                "abstain": True,
                "reason": f"Generation error: {str(e)}",
                "raw_prompt": prompt
            }
    
    def _create_enhanced_prompt(self, user_prompt: str, field_mapping: Dict[str, Any]) -> str:
        """Create enhanced prompt with field mapping information"""
        
        system_type = field_mapping.get("system_type", "Unknown system")
        all_fields = field_mapping.get("all_fields", [])
        timestamp_fields = field_mapping.get("timestamp_fields", [])
        ip_fields = field_mapping.get("ip_fields", [])
        user_fields = field_mapping.get("user_fields", [])
        status_fields = field_mapping.get("status_fields", [])
        important_fields = field_mapping.get("important_fields", [])
        
        enhanced_prompt = f"""You are generating Elasticsearch DSL queries for {system_type} data.

IMPORTANT FIELD INFORMATION:
Available fields: {', '.join(all_fields[:20])}{"..." if len(all_fields) > 20 else ""}

KEY FIELD MAPPINGS:
- Timestamp fields: {', '.join(timestamp_fields) if timestamp_fields else "None detected"}
- IP address fields: {', '.join(ip_fields) if ip_fields else "None detected"}  
- User/account fields: {', '.join(user_fields) if user_fields else "None detected"}
- Status/result fields: {', '.join(status_fields) if status_fields else "None detected"}
- Important fields: {', '.join(important_fields) if important_fields else "None specified"}

USER REQUEST: {user_prompt}

INSTRUCTIONS:
1. Use ONLY the fields listed above - do not invent field names
2. For time-based queries, use the timestamp fields: {timestamp_fields}
3. For IP-based queries, use the IP fields: {ip_fields}
4. For user-based queries, use the user fields: {user_fields}
5. For status-based queries, use the status fields: {status_fields}
6. Use proper Elasticsearch DSL syntax
7. Include size limits (max 1000 documents)
8. Use appropriate query types (term, range, match, etc.)

Generate a valid Elasticsearch DSL query as JSON:"""

        return enhanced_prompt
    
    def _parse_and_validate_response(self, response: str, field_mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Parse AI response and validate field usage"""
        try:
            # Extract JSON from response
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                query = json.loads(json_str)
            else:
                raise ValueError("No valid JSON found in response")
            
            # Validate field usage
            self._validate_field_usage(query, field_mapping)
            
            # Ensure size limit
            if "size" not in query:
                query["size"] = 100
            elif query.get("size", 0) > 1000:
                query["size"] = 1000
            
            return query
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return {
                "query": {"match_all": {}},
                "size": 100,
                "_meta": {
                    "error": f"Failed to parse AI response: {str(e)}",
                    "raw_response": response[:500]
                }
            }
    
    def _validate_field_usage(self, query: Dict[str, Any], field_mapping: Dict[str, Any]) -> None:
        """Validate that query only uses available fields"""
        available_fields = set(field_mapping.get("all_fields", []))
        
        def check_fields_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in available_fields or key in ["query", "size", "sort", "_source", "aggs", "aggregations"]:
                        continue
                    elif isinstance(value, (dict, list)):
                        check_fields_recursive(value, f"{path}.{key}")
                    else:
                        # This might be a field reference
                        if key not in ["gte", "lte", "gt", "lt", "format", "time_zone", "boost"]:
                            logger.warning(f"Query uses potentially unavailable field: {key} at {path}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_fields_recursive(item, f"{path}[{i}]")
        
        check_fields_recursive(query)
    
    def _call_ai_model(self, prompt: str, model: str) -> str:
        """Call AI model (local or external) with prompt"""
        try:
            # Check if it's an external model (has emoji prefix)
            if model.startswith("☁️ ") or model.startswith("External:"):
                # Extract model name
                if model.startswith("☁️ "):
                    external_model_name = model.replace("☁️ ", "")
                else:
                    external_model_name = model.replace("External: ", "")
                
                # Use external LLM manager
                from src.external.llm_manager import get_external_llm_manager
                manager = get_external_llm_manager()
                response = manager.call_llm(external_model_name, prompt)
                
                if response is None:
                    raise ValueError(f"External LLM {external_model_name} returned None")
                
                return response
                
            else:
                # Use local model
                # Remove local prefix if present
                if model.startswith("🖥️ "):
                    local_model_name = model.replace("🖥️ ", "")
                else:
                    local_model_name = model
                
                return call_local_model(prompt, local_model_name)
                
        except Exception as e:
            logger.error(f"Error calling AI model {model}: {e}")
            raise
    
    def _store_result(self, query: Dict[str, Any], task_id: str, method: str) -> None:
        """Store query result to file"""
        try:
            artifacts_dir = Path("artifacts/generated")
            artifacts_dir.mkdir(exist_ok=True)
            
            query_file = artifacts_dir / f"{method}_{task_id}.json"
            with open(query_file, 'w') as f:
                json.dump(query, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error storing result: {e}")


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description="Adaptive Constrained Query Generator")
    parser.add_argument("--prompt", required=True, help="Natural language prompt")
    parser.add_argument("--index", default="logs_net", help="Target Elasticsearch index")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use")
    parser.add_argument("--task-id", help="Task ID for result storage")
    
    args = parser.parse_args()
    
    generator = AdaptiveConstrainedGenerator()
    result = generator.generate_query(
        prompt=args.prompt,
        index=args.index,
        model=args.model,
        task_id=args.task_id
    )
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

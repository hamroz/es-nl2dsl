#!/usr/bin/env python3
"""
Enhanced Constrained Generator: An improved version of the constrained generator 
that uses dynamic index profiles while maintaining the proven prompt structure.
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

# Import from the original constrained generator
from src.generators.constrained import (
    call_local_model, validate_against_schema, load_fewshot_examples,
    check_security_violations, ALLOWED_OPERATORS, AMBIGUOUS_TERMS,
    correct_field_mappings, FIELD_CORRECTIONS
)
from src.data_adaptation.mapping_storage import MappingStorage

logger = logging.getLogger(__name__)

def build_enhanced_prompt(task_prompt, index=None):
    """Build an enhanced prompt using dynamic index profiles"""
    prompt = "You are an Elasticsearch DSL query generator for cybersecurity log analysis.\n\n"
    
    # Get dynamic index information
    mapping_storage = MappingStorage()
    field_mapping = mapping_storage.get_field_mapping_for_query_generation(index)
    date_range = mapping_storage.get_dynamic_date_range(index)
    field_catalog = mapping_storage.get_field_catalog_for_index(index)
    
    # Add index-specific information
    if field_mapping and field_mapping.get("all_fields"):
        # This index has profile information
        prompt += f"Dataset: {index} with {len(field_mapping['all_fields'])} fields\n"
        if field_mapping.get("system_type") != "Unknown":
            prompt += f"System type: {field_mapping['system_type']}\n"
        prompt += f"Date range: {date_range.get('min_date', 'N/A')} to {date_range.get('max_date', 'N/A')}\n\n"
        
        # Add key fields from the actual index
        prompt += "Key fields:\n"
        
        # Priority fields to include (limit to prevent prompt bloat)
        priority_keywords = ["timestamp", "ip", "port", "protocol", "label", "attack", "status", "action", "bytes"]
        added_fields = 0
        max_fields = 15
        
        # Add timestamp field first
        timestamp_field = field_mapping.get("primary_timestamp", "@timestamp")
        if timestamp_field in field_catalog:
            field_info = field_catalog[timestamp_field]
            prompt += f"- {timestamp_field} ({field_info['type']}): {field_info['description']}\n"
            added_fields += 1
        
        # Add other priority fields
        for field_name, field_info in field_catalog.items():
            if added_fields >= max_fields:
                break
            if field_name == timestamp_field:
                continue  # Already added
            
            # Check if this is a priority field
            if any(keyword in field_name.lower() for keyword in priority_keywords):
                prompt += f"- {field_name} ({field_info['type']}): {field_info['description']}\n"
                added_fields += 1
        
        # Add semantic mappings if available
        if field_mapping.get("semantic_mappings"):
            prompt += "\nImportant field mappings:\n"
            for semantic, actual in field_mapping["semantic_mappings"].items():
                if semantic != actual:  # Only show if they're different
                    prompt += f"- For '{semantic}': use {actual}\n"
        
        prompt += "\n"
        
    elif index and "cic" in index.lower():
        # Fallback to hardcoded CIC information if no profile available
        prompt += "Dataset: CIC-IDS2017 network traffic with attack labels\n\n"
        prompt += "Key fields for CIC data:\n"
        prompt += "- src_ip (keyword): Source IP address\n"
        prompt += "- dst_ip (keyword): Destination IP address\n"
        prompt += "- src_port (integer): Source port number\n"
        prompt += "- dst_port (integer): Destination port number\n"
        prompt += "- protocol (keyword): Network protocol (tcp/udp/icmp)\n"
        prompt += "- attack_type (keyword): Attack category (normal, dos, scan, bruteforce, web_attack)\n"
        prompt += "- label (keyword): Specific attack label (BENIGN, DDoS, PortScan, SSH-Patator, etc.)\n"
        prompt += "- @timestamp (date): Event timestamp\n\n"
        prompt += "IMPORTANT mappings:\n"
        prompt += "- For 'DDoS attacks': use attack_type:dos\n"
        prompt += "- For 'port scans': use attack_type:scan\n"
        prompt += "- For 'brute force': use attack_type:bruteforce\n\n"
        
    else:
        # Fallback to dynamic fields or default catalog
        if field_catalog:
            prompt += "Available fields:\n"
            added_fields = 0
            max_fields = 10
            for field_name, field_info in field_catalog.items():
                if added_fields >= max_fields:
                    break
                prompt += f"- {field_name} ({field_info['type']}): {field_info['description']}\n"
                added_fields += 1
            if len(field_catalog) > max_fields:
                prompt += f"... and {len(field_catalog) - max_fields} more fields\n"
        else:
            # Ultimate fallback to hardcoded catalog
            from src.generators.constrained import FIELD_CATALOG
            prompt += "Available fields:\n"
            for field, info in FIELD_CATALOG.items():
                if field != "message":
                    prompt += f"- {field} ({info['type']}): {info['description']}\n"
    
    prompt += "\nAllowed query operators:\n"
    for op, desc in ALLOWED_OPERATORS.items():
        prompt += f"- {op}: {desc}\n"
    
    prompt += "\nRules:\n"
    prompt += "- Always use bool.filter for combining conditions\n"
    
    # Use dynamic timestamp field and date range
    timestamp_field = field_mapping.get("primary_timestamp", "@timestamp") if field_mapping else "@timestamp"
    prompt += f"- Always include a time range filter using {timestamp_field}\n"
    
    # Use actual date range from index
    if date_range and date_range.get("min_date") and date_range.get("max_date"):
        min_date = date_range["min_date"][:10]  # Just the date part
        max_date = date_range["max_date"][:10]
        prompt += f"- Use dates between {min_date} and {max_date} for time ranges\n"
    else:
        prompt += "- For CIC data, use dates in 2017 (e.g., gte: '2017-01-01', lte: '2017-12-31')\n"
    
    prompt += "- Use term for exact matches, terms for multiple values\n"
    prompt += "- Use range only for date and numeric fields\n"
    prompt += "- Output only valid JSON, no explanations\n\n"
    
    # Use simpler examples
    prompt += "Examples:\n"
    examples = get_enhanced_examples(index, field_mapping, timestamp_field, date_range)
    for example in examples[:2]:  # Keep to 2 examples
        prompt += f"Input: {example['prompt']}\n"
        prompt += f"Output: {json.dumps(example['query'], separators=(',', ':'))}\n\n"
    
    prompt += f"Input: {task_prompt}\n"
    prompt += "Output:"
    
    return prompt

def get_enhanced_examples(index, field_mapping, timestamp_field, date_range):
    """Get examples tailored to the index"""
    examples = []
    
    # Determine sample date range
    if date_range and date_range.get("min_date") and date_range.get("max_date"):
        sample_start = date_range["min_date"][:19] + "Z" if not date_range["min_date"].endswith("Z") else date_range["min_date"]
        sample_end = date_range["max_date"][:19] + "Z" if not date_range["max_date"].endswith("Z") else date_range["max_date"]
    else:
        sample_start = "2017-07-04T00:00:00Z"
        sample_end = "2017-07-04T23:59:59Z"
    
    # Example 1: Basic time range
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
    
    # Example 2: Field-specific query based on available fields
    if field_mapping and field_mapping.get("all_fields"):
        # Find a suitable field for the second example
        all_fields = field_mapping["all_fields"]
        
        if "threat_label" in all_fields:
            label_field = "threat_label"
            label_value = "malicious"
        elif "label" in all_fields:
            label_field = "label"
            label_value = "malicious"
        elif "attack_type" in all_fields:
            label_field = "attack_type"
            label_value = "dos"
        elif "status" in all_fields:
            label_field = "status"
            label_value = "blocked"
        else:
            # Use IP field if available
            ip_fields = [f for f in all_fields if "ip" in f.lower()]
            if ip_fields:
                label_field = ip_fields[0]
                label_value = "192.168.1.100"
            else:
                label_field = "protocol"
                label_value = "TCP"
        
        examples.append({
            "prompt": f"Find events with specific {label_field}",
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
                                    label_field: label_value
                                }
                            }
                        ]
                    }
                }
            }
        })
    
    return examples

def generate_enhanced_query(
    prompt: str,
    index: str = "logs_net",
    model: str = "llama3.1:latest",
    schema_path: str = "artifacts/esdsl_schema.json",
    rules_path: Optional[str] = None,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Generate query using enhanced constrained approach"""
    
    logger.info(f"🎯 Generating enhanced query for {index}")
    
    # Build enhanced prompt
    enhanced_prompt = build_enhanced_prompt(prompt, index)
    
    # Generate with retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Generation attempt {attempt + 1}/{max_retries}")
            
            # Check security
            is_violation, violation_msg = check_security_violations(enhanced_prompt)
            if is_violation:
                return {"abstain": True, "reason": violation_msg}
            
            # Call model
            result = call_local_model(enhanced_prompt, model)
            result = result.strip()
            
            # Validate JSON format
            if not (result.startswith("{") and result.endswith("}")):
                logger.warning(f"Attempt {attempt + 1}: Invalid JSON format")
                continue
            
            # Parse JSON
            query_json = json.loads(result)
            
            # Apply field corrections
            corrected_query = correct_field_mappings(query_json)
            
            # Validate schema if provided
            if schema_path and Path(schema_path).exists():
                validate_against_schema(corrected_query, schema_path)
            
            logger.info(f"✅ Successfully generated enhanced query for {index}")
            return corrected_query
            
        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt + 1}: JSON decode error: {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: Generation error: {e}")
            
        if attempt == max_retries - 1:
            return {"abstain": True, "reason": f"Failed after {max_retries} attempts"}
    
    return {"abstain": True, "reason": "Unexpected error"}

def main():
    """CLI interface for enhanced constrained generator"""
    parser = argparse.ArgumentParser(description="Generate enhanced constrained Elasticsearch queries")
    parser.add_argument("--prompt", required=True, help="Natural language query prompt")
    parser.add_argument("--index", default="logs_net", help="Target Elasticsearch index")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use for generation")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file path")
    parser.add_argument("--task-id", help="Task ID for output naming")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [ENHANCED] - %(levelname)s - %(message)s'
    )
    
    try:
        result = generate_enhanced_query(
            prompt=args.prompt,
            index=args.index,
            model=args.model,
            schema_path=args.schema
        )
        
        # Save result
        if args.task_id:
            output_file = Path("artifacts/generated") / f"{args.task_id}.json"
        else:
            output_file = Path("artifacts/generated") / "enhanced_generated.json"
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        if "abstain" in result:
            print(f"Generation abstained: {result['reason']}")
            sys.exit(1)
        else:
            print(f"Successfully generated enhanced query saved to {output_file}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

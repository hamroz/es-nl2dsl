#!/usr/bin/env python3
import json
import sys
import argparse
import subprocess
import yaml
from pathlib import Path
from jsonschema import validate, ValidationError

FIELD_CATALOG = {
    "@timestamp": {"type": "date", "description": "Event timestamp"},
    "src_ip": {"type": "keyword", "description": "Source IP address"},
    "dst_ip": {"type": "keyword", "description": "Destination IP address"},
    "src_port": {"type": "integer", "description": "Source port number"},
    "dst_port": {"type": "integer", "description": "Destination port number"},
    "protocol": {"type": "keyword", "description": "Network protocol (TCP, UDP, etc)"},
    "bytes_in": {"type": "long", "description": "Bytes received"},
    "bytes_out": {"type": "long", "description": "Bytes sent"},
    "label": {"type": "keyword", "description": "Classification label (malicious, benign)"},
    "message": {"type": "text", "description": "Log message (not searchable)"}
}

ALLOWED_OPERATORS = {
    "bool": "Combines multiple conditions with filter (AND) or must (AND)",
    "term": "Exact match for a single value",
    "terms": "Match any of multiple values",
    "range": "Range queries with gte, gt, lte, lt for dates and numbers"
}

FEW_SHOT_EXAMPLES = [
    {
        "prompt": "Find events labeled malicious on 2017-07-04",
        "query": {
            "query": {
                "bool": {
                    "filter": [
                        {"range": {"@timestamp": {"gte": "2017-07-04T00:00:00Z", "lte": "2017-07-04T23:59:59Z"}}},
                        {"term": {"label": "malicious"}}
                    ]
                }
            }
        }
    },
    {
        "prompt": "Find TCP traffic from IP 192.168.1.10",
        "query": {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"src_ip": "192.168.1.10"}},
                        {"term": {"protocol": "TCP"}}
                    ]
                }
            }
        }
    }
]

def build_prompt(task_prompt):
    """Build the constrained generation prompt"""
    prompt = "You are an Elasticsearch DSL query generator for cybersecurity log analysis.\n\n"
    
    prompt += "Available fields:\n"
    for field, info in FIELD_CATALOG.items():
        if field != "message":  # Skip non-searchable field
            prompt += f"- {field} ({info['type']}): {info['description']}\n"
    
    prompt += "\nAllowed query operators:\n"
    for op, desc in ALLOWED_OPERATORS.items():
        prompt += f"- {op}: {desc}\n"
    
    prompt += "\nRules:\n"
    prompt += "- Always use bool.filter for combining conditions\n"
    prompt += "- Always include a time range filter using @timestamp\n"
    prompt += "- Use term for exact matches, terms for multiple values\n"
    prompt += "- Use range only for date and numeric fields\n"
    prompt += "- Output only valid JSON, no explanations\n\n"
    
    prompt += "Examples:\n"
    for example in FEW_SHOT_EXAMPLES:
        prompt += f"Input: {example['prompt']}\n"
        prompt += f"Output: {json.dumps(example['query'], indent=2)}\n\n"
    
    prompt += f"Input: {task_prompt}\n"
    prompt += "Output:"
    
    return prompt

def call_local_model(prompt, model="llama3.1:latest"):
    """Call Ollama local model"""
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"Model call failed: {result.stderr}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("Model call timed out")
    except FileNotFoundError:
        raise RuntimeError("Ollama not found. Please install Ollama and pull a model.")

def validate_against_schema(query_json, schema_path):
    """Validate query against ES DSL schema"""
    with open(schema_path) as f:
        schema = json.load(f)
    
    try:
        validate(instance=query_json, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)

def validate_with_validator(query_json, rules_path):
    """Run the validator.py script"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(query_json, f)
        temp_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, "src/validator.py", "--dsl", temp_path, "--rules", rules_path],
            capture_output=True,
            text=True
        )
        Path(temp_path).unlink()
        
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stdout + result.stderr
    except Exception as e:
        Path(temp_path).unlink()
        return False, str(e)

def generate_with_retries(task_prompt, schema_path, rules_path, max_retries=2):
    """Generate query with validation and retries"""
    prompt = build_prompt(task_prompt)
    
    for attempt in range(max_retries + 1):
        print(f"Generation attempt {attempt + 1}/{max_retries + 1}")
        
        try:
            # Call model
            response = call_local_model(prompt)
            
            # Extract JSON (handle markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Parse JSON
            query_json = json.loads(response)
            
            # Validate against schema
            schema_valid, schema_error = validate_against_schema(query_json, schema_path)
            if not schema_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed schema validation: {schema_error}\n"
                    prompt += "Please fix the schema issues and try again.\n"
                    continue
                else:
                    return {"abstain": True, "reason": f"Schema validation failed: {schema_error}"}
            
            # Validate with validator.py
            validator_valid, validator_error = validate_with_validator(query_json, rules_path)
            if not validator_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed validation: {validator_error}\n"
                    prompt += "Please fix the validation issues and try again.\n"
                    continue
                else:
                    return {"abstain": True, "reason": f"Validation failed: {validator_error}"}
            
            # Success!
            return query_json
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                prompt = build_prompt(task_prompt)
                prompt += f"\n\nPrevious attempt produced invalid JSON: {e}\n"
                prompt += "Please output valid JSON only.\n"
                continue
            else:
                return {"abstain": True, "reason": f"Invalid JSON: {e}"}
        except Exception as e:
            return {"abstain": True, "reason": f"Generation error: {e}"}
    
    return {"abstain": True, "reason": "Max retries exceeded"}

def main():
    parser = argparse.ArgumentParser(description="Generate constrained ES DSL queries")
    parser.add_argument("--prompt", required=True, help="Query prompt")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file")
    parser.add_argument("--rules", default="artifacts/validator_rules.yaml", help="Validator rules")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Output directory")
    parser.add_argument("--model", default="llama3.1:latest", help="Ollama model to use")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate query
    result = generate_with_retries(args.prompt, args.schema, args.rules)
    
    # Save result
    if args.task_id:
        output_file = output_dir / f"{args.task_id}.json"
    else:
        output_file = output_dir / "generated.json"
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    if "abstain" in result:
        print(f"Generation abstained: {result['reason']}")
        sys.exit(1)
    else:
        print(f"Successfully generated query saved to {output_file}")
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
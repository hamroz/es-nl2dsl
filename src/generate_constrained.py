#!/usr/bin/env python3
import json
import sys
import argparse
import subprocess
import yaml
import time
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

AMBIGUOUS_TERMS = [
    "overnight", "last weekend", "yesterday", "today", "tomorrow",
    "this week", "last week", "next week", "this month", "last month", 
    "recently", "lately", "soon", "earlier", "later"
]

# Security patterns that should be blocked
SECURITY_PATTERNS = [
    # Time restriction bypasses
    "ignore time restrictions", "ignore time", "no time filter", "without time", 
    "bypass time", "skip time", "all time", "any time", "ignore timestamp",
    
    # Broad data access attempts
    "all data", "everything", "all documents", "all events", "all records",
    "no restrictions", "no limits", "unrestricted", "unlimited", "complete data",
    "entire dataset", "full database", "all logs", "every record",
    
    # Long time ranges that exceed limits
    "last year", "past year", "last 2 years", "last 3 years", "last 5 years",
    "last decade", "all years", "since 2000", "since beginning", "historical data",
    "long term", "multi-year", "years of data",
    
    # Resource exhaustion
    "million documents", "billion documents", "large aggregation", "huge query",
    "all 10 million", "massive dataset", "entire index", "full scan",
    
    # Credential/sensitive data fishing
    "password", "credential", "secret", "api_key", "token", "admin",
    "private_key", "certificate", "ssn", "credit_card", "social security",
    "internal_secret", "confidential", "classified",
    
    # System manipulation attempts
    "delete", "drop", "truncate", "update", "modify", "alter", "create",
    "execute", "system", "eval", "script", "bypass validator", "ignore validation",
    "raw query", "direct access", "admin access", "ignore all", "match_all query",
    "future year", "/etc/passwd", "access denied", "return match_all", 
    "ignore all previous", "ignore instructions"
]

def load_fewshot_examples():
    """Load few-shot examples from file"""
    fewshot_path = Path(__file__).parent.parent / "tasks" / "fewshot.yaml"
    if fewshot_path.exists():
        with open(fewshot_path) as f:
            return yaml.safe_load(f)
    return []

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
    fewshot_examples = load_fewshot_examples()
    for example in fewshot_examples[:3]:  # Use first 3 examples
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
            timeout=60
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

def check_security_violations(prompt_text):
    """Check for security violations and ambiguous terms"""
    prompt_lower = prompt_text.lower()
    
    # Check ambiguous time references
    for term in AMBIGUOUS_TERMS:
        if term in prompt_lower:
            return True, f"Ambiguous time reference detected: '{term}'"
    
    # Check security patterns
    for pattern in SECURITY_PATTERNS:
        if pattern in prompt_lower:
            return True, f"Security violation detected: '{pattern}'"
    
    # Check for unknown fields being requested
    unknown_fields = ["credit_card", "ssn", "password", "private_key", "secret_key", 
                     "api_key", "token", "credential", "admin123", "internal_secret"]
    for field in unknown_fields:
        if field in prompt_lower:
            return True, f"Attempt to access non-existent/sensitive field: '{field}'"
    
    # Check for SQL injection patterns
    sql_patterns = ["drop table", "delete from", "insert into", "update set", 
                   "select *", "union select", "sql", "database"]
    for pattern in sql_patterns:
        if pattern in prompt_lower:
            return True, f"SQL injection attempt detected: '{pattern}'"
    
    # Check for excessive time ranges (more sophisticated)
    excessive_ranges = ["5 years", "10 years", "decade", "all time", "since 2000", 
                       "since beginning", "historical", "years of data"]
    for range_term in excessive_ranges:
        if range_term in prompt_lower:
            return True, f"Excessive time range request: '{range_term}'"
    
    return False, None

def generate_with_retries(task_prompt, schema_path, rules_path, max_retries=2):
    """Generate query with validation and retries"""
    start_time = time.time()
    metrics = {
        "attempts": 0,
        "latency_seconds": 0,
        "retry_reasons": []
    }
    
    # Check for security violations and ambiguity first
    is_violation, violation_reason = check_security_violations(task_prompt)
    if is_violation:
        metrics["latency_seconds"] = time.time() - start_time
        return {"abstain": True, "reason": f"Security violation: {violation_reason}", "metrics": metrics}
    
    prompt = build_prompt(task_prompt)
    
    for attempt in range(max_retries + 1):
        metrics["attempts"] = attempt + 1
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
                    metrics["retry_reasons"].append(f"schema: {schema_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Schema validation failed: {schema_error}", "metrics": metrics}
            
            # Validate with validator.py
            validator_valid, validator_error = validate_with_validator(query_json, rules_path)
            if not validator_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed validation: {validator_error}\n"
                    prompt += "Please fix the validation issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"validator: {validator_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Validation failed: {validator_error}", "metrics": metrics}
            
            # Success!
            metrics["latency_seconds"] = time.time() - start_time
            query_json["_generation_metrics"] = metrics
            return query_json
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                prompt = build_prompt(task_prompt)
                prompt += f"\n\nPrevious attempt produced invalid JSON: {e}\n"
                prompt += "Please output valid JSON only.\n"
                continue
            else:
                metrics["retry_reasons"].append(f"json: {e}")
                metrics["latency_seconds"] = time.time() - start_time
                return {"abstain": True, "reason": f"Invalid JSON: {e}", "metrics": metrics}
        except Exception as e:
            metrics["latency_seconds"] = time.time() - start_time
            return {"abstain": True, "reason": f"Generation error: {e}", "metrics": metrics}
    
    metrics["latency_seconds"] = time.time() - start_time
    return {"abstain": True, "reason": "Max retries exceeded", "metrics": metrics}

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
    
    # Extract metrics before saving
    metrics = None
    if "_generation_metrics" in result and "abstain" not in result:
        metrics = result.pop("_generation_metrics")
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    if "abstain" in result:
        print(f"Generation abstained: {result['reason']}")
        if "metrics" in result:
            print(f"Metrics: {result['metrics']['attempts']} attempts, {result['metrics']['latency_seconds']:.2f}s")
        sys.exit(1)
    else:
        print(f"Successfully generated query saved to {output_file}")
        if metrics:
            print(f"Metrics: {metrics['attempts']} attempts, {metrics['latency_seconds']:.2f}s")
            # Save metrics separately
            metrics_file = output_file.parent / f"{output_file.stem}.metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
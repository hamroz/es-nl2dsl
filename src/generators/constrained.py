#!/usr/bin/env python3
import json
import sys
import argparse
import subprocess
import yaml
import time
from pathlib import Path
from jsonschema import validate, ValidationError
# Add project root to path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import prompt enhancer if available
try:
    from src.external.prompt_enhancer import enhance_prompt, build_enhanced_prompt
    ENHANCER_AVAILABLE = True
except ImportError:
    ENHANCER_AVAILABLE = False

# Import sophisticated security filter
try:
    from src.utils.security_filter import check_security_violations_advanced, SophisticatedSecurityFilter
    ADVANCED_SECURITY = True
except ImportError:
    ADVANCED_SECURITY = False

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

# Common field mapping errors from LLMs (maps incorrect field names to correct ones)
FIELD_CORRECTIONS = {
    # ECS-style fields to actual fields
    "event.label": "label",
    "event.type": "label",
    "event.category": "label",
    "source.ip": "src_ip",
    "source.port": "src_port",
    "destination.ip": "dst_ip",
    "destination.port": "dst_port",
    "destination_port": "dst_port",
    "source_port": "src_port",
    "source_ip": "src_ip",
    "destination_ip": "dst_ip",
    "network.protocol": "protocol",
    "network.bytes_in": "bytes_in",
    "network.bytes_out": "bytes_out",
    # Common variants
    "timestamp": "@timestamp",
    "time": "@timestamp",
    "datetime": "@timestamp",
    "src": "src_ip",
    "dst": "dst_ip",
    "srcip": "src_ip",
    "dstip": "dst_ip",
    "srcport": "src_port",
    "dstport": "dst_port",
    "bytes_received": "bytes_in",
    "bytes_sent": "bytes_out",
    "bytes_transferred": "bytes_out",
    "inbound_bytes": "bytes_in",
    "outbound_bytes": "bytes_out",
    "traffic_type": "label",
    "attack_label": "label",
    "malicious": "label",
    # CIC-specific corrections
    "flow.packets_s": "flow_packets_s",
    "flow.bytes_s": "flow_bytes_s",
    "attack.type": "attack_type",
    "day": "day_of_week",
    "weekday": "day_of_week"
}

ALLOWED_OPERATORS = {
    "bool": "Combines multiple conditions with filter (AND) or must (AND)",
    "term": "Exact match for a single value",
    "terms": "Match any of multiple values",
    "range": "Range queries with gte, gt, lte, lt for dates and numbers"
}

# Terms that are too vague to convert to specific time ranges
AMBIGUOUS_TERMS = [
    "recently", "lately", "soon", "earlier", "later", "sometime",
    "a while ago", "not long ago", "previously"
]

# Terms that can be converted to specific dates (not ambiguous)
CONVERTIBLE_TIME_TERMS = [
    "today", "yesterday", "tomorrow", "this week", "last week",
    "this month", "last month", "last hour", "past hour", "last 24 hours",
    "past 24 hours", "past day", "past week", "past month", "in the past 24",
    "in the past day", "in the past week", "in the past month", "in the last"
]

# Security patterns that should be blocked - DEPRECATED (now handled in check_security_violations)
# Keeping empty list to avoid breaking other code that might reference it
SECURITY_PATTERNS = []

def load_fewshot_examples(index=None):
    """Load few-shot examples from file"""
    # Check for CIC-specific examples if CIC index is used
    if index and "cic" in index.lower():
        cic_path = Path(__file__).parent.parent / "artifacts" / "few_shot_cic.yaml"
        if cic_path.exists():
            with open(cic_path) as f:
                data = yaml.safe_load(f)
                return data.get('examples', [])
    
    # Default examples
    fewshot_path = Path(__file__).parent.parent / "tasks" / "fewshot.yaml"
    if fewshot_path.exists():
        with open(fewshot_path) as f:
            return yaml.safe_load(f)
    return []

def build_prompt(task_prompt, index=None):
    """Build the constrained generation prompt"""
    prompt = "You are an Elasticsearch DSL query generator for cybersecurity log analysis.\n\n"
    
    # Load appropriate field catalog based on index
    if index and "cic" in index.lower():
        prompt += "Dataset: CIC-IDS2017 network traffic with attack labels\n\n"
        prompt += "Key fields for CIC data:\n"
        prompt += "- src_ip (keyword): Source IP address\n"
        prompt += "- dst_ip (keyword): Destination IP address\n"
        prompt += "- src_port (integer): Source port number\n"
        prompt += "- dst_port (integer): Destination port number\n"
        prompt += "- protocol (keyword): Network protocol (tcp/udp/icmp)\n"
        prompt += "- attack_type (keyword): Attack category (normal, dos, scan, bruteforce, web_attack)\n"
        prompt += "- label (keyword): Specific attack label (BENIGN, DDoS, PortScan, SSH-Patator, etc.)\n"
        prompt += "- flow_packets_s (float): Packet rate per second\n"
        prompt += "- flow_bytes_s (float): Bytes per second (bandwidth)\n"
        prompt += "- flow_duration (long): Flow duration in milliseconds\n"
        prompt += "- syn_flag_count (int): Number of SYN flags\n"
        prompt += "- day_of_week (keyword): Day name (Monday, Tuesday, etc.)\n"
        prompt += "- @timestamp (date): Event timestamp\n\n"
        prompt += "IMPORTANT mappings:\n"
        prompt += "- For 'DDoS attacks': use attack_type:dos\n"
        prompt += "- For 'port scans': use attack_type:scan\n"
        prompt += "- For 'brute force': use attack_type:bruteforce\n"
        prompt += "- ALWAYS include specific ports if mentioned (e.g., 'port 443' → dst_port:443)\n"
        prompt += "- ALWAYS include IP addresses if mentioned (e.g., 'from 192.168.1.1' → src_ip:192.168.1.1)\n"
        prompt += "- For 'high packet rate': use flow_packets_s >= 100\n"
        prompt += "- For 'high bandwidth': use flow_bytes_s >= 1000000\n"
        prompt += "- Always include @timestamp range for time windowing\n\n"
    else:
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
    prompt += "- For CIC data, use dates in 2017 (e.g., gte: '2017-01-01', lte: '2017-12-31')\n"
    prompt += "- Use term for exact matches, terms for multiple values\n"
    prompt += "- Use range only for date and numeric fields\n"
    prompt += "- Output only valid JSON, no explanations\n\n"
    
    prompt += "Examples:\n"
    fewshot_examples = load_fewshot_examples(index)
    for example in fewshot_examples[:3]:  # Use first 3 examples
        prompt += f"Input: {example['prompt']}\n"
        prompt += f"Output: {json.dumps(example['query'], indent=2)}\n\n"
    
    prompt += f"Input: {task_prompt}\n"
    prompt += "Output:"
    
    return prompt

def call_local_model(prompt, model="llama3.1:latest"):
    """Call Ollama local model with adaptive timeout"""
    # Set timeout based on model size
    timeout_seconds = 60  # Default
    if "20b" in model.lower() or "gpt-oss" in model.lower():
        timeout_seconds = 180  # 3 minutes for 20B models
    elif "14b" in model.lower() or "13b" in model.lower():
        timeout_seconds = 120  # 2 minutes for 13-14B models
    elif "70b" in model.lower():
        timeout_seconds = 240  # 4 minutes for 70B models
    
    print(f"Calling {model} with timeout={timeout_seconds}s...")
    
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        if result.returncode != 0:
            raise RuntimeError(f"Model call failed: {result.stderr}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Model call timed out after {timeout_seconds} seconds")
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
    """Check for security violations using sophisticated filtering when available"""
    # Use advanced security filter if available
    if ADVANCED_SECURITY:
        is_violation, reason = check_security_violations_advanced(prompt_text)
        if is_violation:
            return is_violation, reason
        # If advanced filter passes, still do basic checks for compatibility
        return check_security_violations_basic(prompt_text)
    else:
        # Fallback to basic checks
        return check_security_violations_basic(prompt_text)

def check_security_violations_basic(prompt_text):
    """Check for security violations and ambiguous terms"""
    prompt_lower = prompt_text.lower()
    
    # Check for SQL injection patterns FIRST (more specific patterns)
    sql_patterns = [
        "drop table", "drop database", "delete from", "insert into", "update set",
        "union select", "exec(", "execute(", "xp_cmdshell", "sp_executesql"
    ]
    for pattern in sql_patterns:
        if pattern in prompt_lower:
            return True, f"SQL injection attempt detected: '{pattern}'"
    
    # Check for logical bypass attempts (check before broad patterns)
    bypass_patterns = [
        "or 1=1", "or 1 = 1", "or true", "' or '", '" or "',
        "or1==1", "or 1==1", " 1==1",  # Additional patterns with space
        "ignore previous", "ignore all previous", "bypass validator",
        "ignore validation", "skip validation", "raw query"
    ]
    for pattern in bypass_patterns:
        if pattern in prompt_lower:
            return True, f"Bypass attempt detected: '{pattern}'"
    
    # Check for command injection patterns
    command_patterns = [
        "erase all", "delete all", "drop all", "truncate", "rm -rf",
        "format c:", "/etc/passwd", "sudo", "chmod 777"
    ]
    for pattern in command_patterns:
        if pattern in prompt_lower:
            return True, f"Command injection attempt detected: '{pattern}'"
    
    # Check ambiguous time references (after more serious violations)
    # But allow convertible time terms like "today", "yesterday" etc.
    for term in AMBIGUOUS_TERMS:
        if term in prompt_lower:
            # Special case: "in the past X" is usually specific enough
            import re
            if re.search(r'in the past \d+ (hours?|days?|weeks?|months?)', prompt_lower):
                continue
            # Double-check it's not a convertible term
            is_convertible = any(conv in prompt_lower for conv in CONVERTIBLE_TIME_TERMS)
            if not is_convertible:
                return True, f"Ambiguous time reference detected: '{term}'"
    
    # Check for overly broad data requests WITH context
    # "all data" is only bad if not qualified (e.g., "all data from today" is OK)
    # BUT check for SQL injection BEFORE broad patterns
    broad_patterns = [
        ("all data", ["from", "between", "on", "during", "today", "yesterday", "last", "where", "in", "with"]),
        ("everything", ["from", "between", "on", "during", "today", "yesterday", "where", "in", "last", "past"]),
        ("entire database", []),  # Always bad
        ("full database", []),    # Always bad
        ("no restrictions", []),  # Always bad
        ("no limits", []),        # Always bad
        ("unrestricted", []),     # Always bad
    ]
    
    for pattern, allowed_qualifiers in broad_patterns:
        if pattern in prompt_lower:
            # Skip if this is part of a SQL injection pattern already caught
            if any(x in prompt_lower for x in ["or 1=", "or 1 =", "1==1"]):
                continue  # Already handled by bypass patterns
            # Check if any qualifier is present
            has_qualifier = any(qual in prompt_lower for qual in allowed_qualifiers)
            if not allowed_qualifiers or not has_qualifier:
                return True, f"Overly broad data request: '{pattern}'"
    
    # Check for sensitive field access
    import re
    sensitive_fields = [
        "passwords?", "passwd", "credentials?", "secret_key", "private_key",
        "api_key", "tokens?", "ssn", "social security", "credit_card"
    ]
    for field in sensitive_fields:
        # More precise matching - check for word boundaries
        if re.search(r'\b' + field + r'\b', prompt_lower):
            # Extract the actual matched word for the error message
            match = re.search(r'\b' + field + r'\b', prompt_lower)
            return True, f"Attempt to access sensitive field: '{match.group()}'"
    
    # Check for excessive time ranges
    excessive_ranges = [
        "last 5 years", "last 10 years", "last decade", "all time",
        "since 2000", "since beginning", "years of data"
    ]
    for range_term in excessive_ranges:
        if range_term in prompt_lower:
            return True, f"Excessive time range request: '{range_term}'"
    
    # Check for attack-related queries - these should be ALLOWED for security analysis
    # Only block if trying to PERFORM attacks, not analyze them
    attack_actions = [
        "perform attack", "execute attack", "launch attack", "start attack",
        "initiate ddos", "start ddos", "flood the", "overwhelm the"
    ]
    for action in attack_actions:
        if action in prompt_lower:
            return True, f"Attack action attempt: '{action}'"
    
    return False, None

def correct_field_mappings(query_json):
    """Recursively correct common field name mistakes in the query"""
    if isinstance(query_json, dict):
        corrected = {}
        for key, value in query_json.items():
            # Check if this key is a field name that needs correction
            if key in FIELD_CORRECTIONS:
                corrected_key = FIELD_CORRECTIONS[key]
                print(f"Field correction: '{key}' → '{corrected_key}'")
                corrected[corrected_key] = correct_field_mappings(value)
            else:
                # For term/terms/range operators, check field names inside
                if key in ["term", "terms", "range", "match", "exists"]:
                    if isinstance(value, dict):
                        corrected_value = {}
                        for field, field_value in value.items():
                            if field in FIELD_CORRECTIONS:
                                corrected_field = FIELD_CORRECTIONS[field]
                                print(f"Field correction: '{field}' → '{corrected_field}'")
                                corrected_value[corrected_field] = field_value
                            else:
                                corrected_value[field] = field_value
                        corrected[key] = corrected_value
                    else:
                        corrected[key] = correct_field_mappings(value)
                else:
                    corrected[key] = correct_field_mappings(value)
        return corrected
    elif isinstance(query_json, list):
        return [correct_field_mappings(item) for item in query_json]
    else:
        return query_json

def generate_with_retries(task_prompt, schema_path, rules_path, max_retries=2, index=None):
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
    
    # Enhance prompt if CIC index and enhancer available
    enhanced_task_prompt = task_prompt
    if ENHANCER_AVAILABLE and index and "cic" in index.lower():
        enhancements = enhance_prompt(task_prompt)
        if enhancements['field_constraints'] or enhancements['time_constraints']:
            enhanced_task_prompt = build_enhanced_prompt(task_prompt, enhancements)
            print(f"Enhanced prompt with extracted constraints")
    
    prompt = build_prompt(enhanced_task_prompt, index)
    
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
            
            # Apply field corrections BEFORE validation
            query_json = correct_field_mappings(query_json)
            
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
    parser.add_argument("--index", help="Target index (auto-selects appropriate rules)")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Auto-select rules based on index
    rules_file = args.rules
    if args.index and "cic" in args.index.lower():
        cic_rules = Path("artifacts/validator_rules_cic.yaml")
        if cic_rules.exists():
            rules_file = str(cic_rules)
            print(f"Using CIC-IDS2017 validator rules for index: {args.index}")
    
    # Generate query
    result = generate_with_retries(args.prompt, args.schema, rules_file, index=args.index)
    
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
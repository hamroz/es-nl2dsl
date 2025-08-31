#!/usr/bin/env python3
"""
External LLM Query Generator: Multi-provider AI model integration for DSL generation

This module provides comprehensive query generation capabilities using external Large
Language Model providers including OpenAI, Anthropic, Google, and others. It extends
the core generation framework with enterprise-grade external AI integration, advanced
prompt engineering, and provider-specific optimizations.

Key capabilities:
- Multi-provider LLM integration (OpenAI GPT-4, Anthropic Claude, Google Gemini)
- Advanced prompt engineering with provider-specific optimization
- Intelligent provider selection and fallback mechanisms
- Cost optimization with token usage monitoring and budget controls
- Rate limiting and request throttling for API compliance
- Response validation and quality assessment
- Integration with existing validation and security frameworks

The generator provides access to state-of-the-art AI capabilities while maintaining
consistency with the ES-NL2DSL framework's validation, security, and quality standards.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import json
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.external.llm_manager import get_external_llm_manager
from src.generators.constrained import (
    build_prompt, 
    validate_against_schema, 
    validate_with_validator,
    check_security_violations,
    load_fewshot_examples
)

# Import new security layer
try:
    from src.generators.secure_generator import get_secure_generator
    NEW_SECURITY_AVAILABLE = True
except ImportError:
    NEW_SECURITY_AVAILABLE = False

def generate_with_external_llm(
    llm_name: str,
    task_prompt: str,
    schema_path: str,
    rules_path: str,
    max_retries: int = 2,
    index: Optional[str] = None
) -> Dict:
    """Generate query using an external LLM"""
    
    start_time = time.time()
    metrics = {
        "attempts": 0,
        "latency_seconds": 0,
        "retry_reasons": [],
        "llm_used": llm_name
    }
    
    # Use new comprehensive security layer if available, fallback to old system
    if NEW_SECURITY_AVAILABLE:
        secure_gen = get_secure_generator()
        security_validation = secure_gen.validate_input_security(task_prompt, index)
        if not security_validation["is_secure"]:
            metrics["latency_seconds"] = time.time() - start_time
            return {
                "abstain": True, 
                "reason": f"Security validation failed: {security_validation['reason']}", 
                "metrics": metrics,
                "security_metrics": security_validation["metrics"]
            }
        # Use sanitized prompt for generation
        task_prompt = security_validation["sanitized_prompt"]
    else:
        # Fallback to old security check
        is_violation, violation_reason = check_security_violations(task_prompt)
        if is_violation:
            metrics["latency_seconds"] = time.time() - start_time
            return {"abstain": True, "reason": f"Security violation: {violation_reason}", "metrics": metrics}
    
    # Get LLM manager
    manager = get_external_llm_manager()
    llm = manager.get_llm(llm_name)
    
    if not llm or not llm.enabled:
        return {"abstain": True, "reason": f"LLM '{llm_name}' not found or disabled", "metrics": metrics}
    
    # Build the system prompt
    system_prompt = """You are an Elasticsearch DSL query generator for cybersecurity log analysis.
Your task is to convert natural language queries into valid Elasticsearch DSL JSON queries.

Important rules:
1. Return ONLY valid JSON - no explanations or markdown
2. Always include a time range filter using @timestamp
3. Use bool.filter for combining conditions
4. For CIC data, use dates in 2017
5. Never generate queries that could be malicious or expose sensitive data

Response format: Return only the JSON query object."""
    
    # Build the user prompt with examples
    user_prompt = build_prompt(task_prompt, index)
    
    for attempt in range(max_retries + 1):
        metrics["attempts"] = attempt + 1
        print(f"Generation attempt {attempt + 1}/{max_retries + 1} with {llm_name}")
        
        try:
            # Call external LLM
            response = manager.call_llm(llm_name, user_prompt, system_prompt)
            
            if not response:
                raise RuntimeError(f"No response from {llm_name}")
            
            # Extract JSON (handle markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Remove any leading/trailing text
            response = response.strip()
            if response.startswith("{"):
                # Find the matching closing brace
                brace_count = 0
                json_end = 0
                for i, char in enumerate(response):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end > 0:
                    response = response[:json_end]
            
            # Parse JSON
            query_json = json.loads(response)
            
            # Validate against schema
            schema_valid, schema_error = validate_against_schema(query_json, schema_path)
            if not schema_valid:
                if attempt < max_retries:
                    user_prompt = build_prompt(task_prompt, index)
                    user_prompt += f"\n\nPrevious attempt failed schema validation: {schema_error}\n"
                    user_prompt += "Please fix the schema issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"schema: {schema_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Schema validation failed: {schema_error}", "metrics": metrics}
            
            # Validate with validator.py
            validator_valid, validator_error = validate_with_validator(query_json, rules_path)
            if not validator_valid:
                if attempt < max_retries:
                    user_prompt = build_prompt(task_prompt, index)
                    user_prompt += f"\n\nPrevious attempt failed validation: {validator_error}\n"
                    user_prompt += "Please fix the validation issues and try again.\n"
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
                user_prompt = build_prompt(task_prompt, index)
                user_prompt += f"\n\nPrevious attempt produced invalid JSON: {e}\n"
                user_prompt += "Please output valid JSON only.\n"
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
    parser = argparse.ArgumentParser(description="Generate ES DSL queries using external LLMs")
    parser.add_argument("--prompt", required=True, help="Query prompt")
    parser.add_argument("--llm", required=True, help="External LLM name to use")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file")
    parser.add_argument("--rules", default="artifacts/validator_rules.yaml", help="Validator rules")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Output directory")
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
    result = generate_with_external_llm(
        args.llm,
        args.prompt, 
        args.schema, 
        rules_file,
        index=args.index
    )
    
    # Save result
    if args.task_id:
        output_file = output_dir / f"{args.task_id}.json"
    else:
        output_file = output_dir / "generated_external.json"
    
    # Extract metrics before saving
    metrics = None
    if "_generation_metrics" in result and "abstain" not in result:
        metrics = result.pop("_generation_metrics")
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    if "abstain" in result:
        print(f"Generation abstained: {result['reason']}")
        if "metrics" in result:
            m = result['metrics']
            print(f"Metrics: {m['attempts']} attempts, {m['latency_seconds']:.2f}s, LLM: {m.get('llm_used', 'N/A')}")
        sys.exit(1)
    else:
        print(f"Successfully generated query saved to {output_file}")
        if metrics:
            print(f"Metrics: {metrics['attempts']} attempts, {metrics['latency_seconds']:.2f}s, LLM: {metrics.get('llm_used', 'N/A')}")
            # Save metrics separately
            metrics_file = output_file.parent / f"{output_file.stem}.metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
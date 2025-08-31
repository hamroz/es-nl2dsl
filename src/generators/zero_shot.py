#!/usr/bin/env python3
"""
Zero-Shot Query Generator: Pure LLM-based DSL generation without constraints

This module provides zero-shot query generation capabilities using Large Language Models
without domain-specific constraints, schema information, or few-shot examples. It serves
as a baseline for comparison with constrained approaches and demonstrates the raw
capabilities of modern LLMs for Elasticsearch DSL generation.

Key capabilities:
- Pure LLM-based generation without domain constraints or examples
- Minimal preprocessing with maximum flexibility and creativity
- Baseline comparison capability for evaluation frameworks
- Integration with multiple LLM providers and models
- Raw LLM performance assessment for research purposes
- Simple prompt construction without complex engineering

The generator is designed for research comparisons and baseline establishment,
providing insight into the fundamental capabilities of LLMs for query generation
without the enhancements provided by domain knowledge and constraints.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import sys
import argparse
import subprocess
import time
from pathlib import Path

# Import shared field mapping utilities
try:
    from .utils.field_mapping import FIELD_CORRECTIONS, correct_field_mappings
except ImportError:
    # For direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.generators.utils.field_mapping import FIELD_CORRECTIONS, correct_field_mappings

# Import new security layer
try:
    from src.generators.secure_generator import get_secure_generator
    NEW_SECURITY_AVAILABLE = True
except ImportError:
    NEW_SECURITY_AVAILABLE = False

# Import old security check as fallback
try:
    from src.generators.constrained import check_security_violations
    OLD_SECURITY_AVAILABLE = True
except ImportError:
    OLD_SECURITY_AVAILABLE = False

def call_model_zeroshot(prompt, model="llama3.1:latest"):
    """Call model with minimal prompt - no schema or examples"""
    # Very minimal prompt - just basic instructions
    full_prompt = f"""Generate an Elasticsearch query for the following request:
{prompt}

Output only valid JSON for an Elasticsearch query. Include a time filter."""
    
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
            ["ollama", "run", model, full_prompt],
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
        raise RuntimeError("Ollama not found")

def extract_json_from_response(response):
    """Try to extract JSON from model response"""
    # Handle markdown code blocks
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0]
    elif "```" in response:
        response = response.split("```")[1].split("```")[0]
    
    # Try to parse
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to find JSON-like content
        start = response.find('{')
        if start >= 0:
            # Find matching closing brace
            count = 0
            for i, char in enumerate(response[start:], start):
                if char == '{':
                    count += 1
                elif char == '}':
                    count -= 1
                    if count == 0:
                        try:
                            return json.loads(response[start:i+1])
                        except:
                            pass
        raise ValueError("Could not extract valid JSON from response")

def main():
    parser = argparse.ArgumentParser(description="Zero-shot baseline generator")
    parser.add_argument("--prompt", required=True, help="Query prompt")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Output directory")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use")
    
    args = parser.parse_args()
    
    print("Zero-shot generation (no schema, no examples)...")
    start_time = time.time()
    
    # Security check before generation
    task_prompt = args.prompt
    if NEW_SECURITY_AVAILABLE:
        secure_gen = get_secure_generator()
        security_validation = secure_gen.validate_input_security(task_prompt, None)
        if not security_validation["is_secure"]:
            # Write abstain result
            abstain_result = {
                "abstain": True,
                "reason": f"Security validation failed: {security_validation['reason']}",
                "metrics": {
                    "method": "zero-shot",
                    "latency_seconds": time.time() - start_time,
                    "security_metrics": security_validation["metrics"]
                }
            }
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"zeroshot_{args.task_id or 'output'}.json"
            with open(output_file, 'w') as f:
                json.dump(abstain_result, f, indent=2)
            print(f"Generation abstained: {abstain_result['reason']}")
            return
        # Use sanitized prompt
        task_prompt = security_validation["sanitized_prompt"]
    elif OLD_SECURITY_AVAILABLE:
        is_violation, violation_reason = check_security_violations(task_prompt)
        if is_violation:
            abstain_result = {
                "abstain": True,
                "reason": f"Security violation: {violation_reason}",
                "metrics": {
                    "method": "zero-shot",
                    "latency_seconds": time.time() - start_time
                }
            }
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"zeroshot_{args.task_id or 'output'}.json"
            with open(output_file, 'w') as f:
                json.dump(abstain_result, f, indent=2)
            print(f"Generation abstained: {violation_reason}")
            return
    
    try:
        # Call model
        response = call_model_zeroshot(task_prompt, args.model)
        
        # Extract JSON
        query = extract_json_from_response(response)
        
        # Apply field corrections
        query = correct_field_mappings(query)
        
        # Add metrics
        metrics = {
            "method": "zero-shot",
            "latency_seconds": time.time() - start_time,
            "success": True
        }
        
        # Save result
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if args.task_id:
            output_file = output_dir / f"zeroshot_{args.task_id}.json"
        else:
            output_file = output_dir / "zeroshot_generated.json"
        
        with open(output_file, 'w') as f:
            json.dump(query, f, indent=2)
        
        # Save metrics
        metrics_file = output_file.with_suffix('.metrics.json')
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"Zero-shot query generated and saved to {output_file}")
        print(f"Latency: {metrics['latency_seconds']:.2f}s")
        print(json.dumps(query, indent=2))
        
    except Exception as e:
        # Failed to generate
        metrics = {
            "method": "zero-shot",
            "latency_seconds": time.time() - start_time,
            "success": False,
            "error": str(e)
        }
        
        # Save failure
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if args.task_id:
            output_file = output_dir / f"zeroshot_{args.task_id}.json"
        else:
            output_file = output_dir / "zeroshot_generated.json"
        
        with open(output_file, 'w') as f:
            json.dump({"error": str(e), "metrics": metrics}, f, indent=2)
        
        print(f"Zero-shot generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Zero-shot baseline generator (no schema, no few-shot examples)"""
import json
import sys
import argparse
import subprocess
import time
from pathlib import Path

def call_model_zeroshot(prompt, model="llama3.1:latest"):
    """Call model with minimal prompt - no schema or examples"""
    # Very minimal prompt - just basic instructions
    full_prompt = f"""Generate an Elasticsearch query for the following request:
{prompt}

Output only valid JSON for an Elasticsearch query. Include a time filter."""
    
    try:
        result = subprocess.run(
            ["ollama", "run", model, full_prompt],
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
    
    try:
        # Call model
        response = call_model_zeroshot(args.prompt, args.model)
        
        # Extract JSON
        query = extract_json_from_response(response)
        
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
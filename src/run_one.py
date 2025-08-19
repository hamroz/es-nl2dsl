#!/usr/bin/env python3
import json
import sys
import argparse
import subprocess
import yaml
from pathlib import Path
from datetime import datetime

def load_scenario(prompts_file, scenario_id):
    """Load a specific scenario from prompts.yaml"""
    with open(prompts_file) as f:
        scenarios = yaml.safe_load(f)
    
    for scenario in scenarios:
        if scenario['id'] == scenario_id:
            return scenario
    
    raise ValueError(f"Scenario {scenario_id} not found")

def generate_query(prompt, task_id):
    """Generate a query using generate_constrained.py"""
    result = subprocess.run(
        [sys.executable, "src/generate_constrained.py", 
         "--prompt", prompt,
         "--task-id", task_id],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return None, result.stdout + result.stderr
    
    # Load generated query
    generated_path = Path(f"artifacts/generated/{task_id}.json")
    with open(generated_path) as f:
        query = json.load(f)
    
    if "abstain" in query:
        return None, f"Generation abstained: {query['reason']}"
    
    return query, None

def validate_query(query_file, rules_file="artifacts/validator_rules.yaml"):
    """Validate a query using validator.py"""
    result = subprocess.run(
        [sys.executable, "src/validator.py",
         "--dsl", query_file,
         "--rules", rules_file],
        capture_output=True,
        text=True
    )
    
    return result.returncode == 0, result.stdout + result.stderr

def evaluate_queries(expert_file, candidate_file, index="logs_net"):
    """Evaluate queries using eval_exec.py"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("artifacts/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = subprocess.run(
        [sys.executable, "src/eval_exec.py",
         "--expert", expert_file,
         "--candidate", candidate_file,
         "--out", str(output_dir),
         "--index", index],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return None, result.stdout + result.stderr
    
    # Find the most recent results file
    results_files = sorted(output_dir.glob("exec_*.json"), key=lambda x: x.stat().st_mtime)
    if not results_files:
        return None, "No results file created"
    
    with open(results_files[-1]) as f:
        metrics = json.load(f)
    
    return metrics, None

def main():
    parser = argparse.ArgumentParser(description="Run a single ES DSL evaluation scenario")
    parser.add_argument("--id", required=True, help="Scenario ID from prompts.yaml")
    parser.add_argument("--gen", action="store_true", help="Generate query (vs use existing)")
    parser.add_argument("--prompts", default="tasks/prompts.yaml", help="Prompts file")
    parser.add_argument("--index", default="logs_net", help="Elasticsearch index")
    parser.add_argument("--candidate", help="Path to candidate query (if not generating)")
    
    args = parser.parse_args()
    
    # Load scenario
    try:
        scenario = load_scenario(args.prompts, args.id)
    except Exception as e:
        print(f"Error loading scenario: {e}")
        sys.exit(1)
    
    print(f"Running scenario: {scenario['id']}")
    print(f"Prompt: {scenario['prompt']}")
    
    # Determine candidate query path
    if args.gen:
        print("Generating query...")
        query, error = generate_query(scenario['prompt'], scenario['id'])
        if error:
            print(f"Generation failed: {error}")
            sys.exit(1)
        
        # Save as candidate
        candidate_path = Path(f"artifacts/queries/candidate_{scenario['id']}.json")
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        with open(candidate_path, 'w') as f:
            json.dump(query, f, indent=2)
    else:
        if args.candidate:
            candidate_path = Path(args.candidate)
        else:
            candidate_path = Path("artifacts/queries/candidate.json")
        
        if not candidate_path.exists():
            print(f"Candidate query not found: {candidate_path}")
            sys.exit(1)
    
    print(f"Using candidate: {candidate_path}")
    
    # Validate query
    print("Validating query...")
    valid, validation_output = validate_query(str(candidate_path))
    
    if not valid:
        print(f"Validation failed: {validation_output}")
        sys.exit(1)
    
    print("Validation passed")
    
    # Save expert query to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        expert_dsl = yaml.safe_load(scenario.get('expert_dsl', '{}'))
        json.dump(expert_dsl, f)
        expert_path = f.name
    
    # Evaluate queries
    print("Evaluating queries...")
    metrics, error = evaluate_queries(expert_path, str(candidate_path), args.index)
    
    # Clean up temp file
    Path(expert_path).unlink()
    
    if error:
        print(f"Evaluation failed: {error}")
        sys.exit(1)
    
    # Print summary
    print("\nResults Summary:")
    print(f"  Jaccard Similarity: {metrics.get('jaccard', 'N/A'):.3f}")
    print(f"  F1 Score: {metrics.get('f1', 'N/A'):.3f}")
    print(f"  Precision: {metrics.get('precision', 'N/A'):.3f}")
    print(f"  Recall: {metrics.get('recall', 'N/A'):.3f}")
    print(f"  Validator Status: {'PASS' if valid else 'FAIL'}")
    
    # Save combined results
    results = {
        "scenario_id": scenario['id'],
        "timestamp": datetime.now().isoformat(),
        "validation_passed": valid,
        "metrics": metrics,
        "prompt": scenario['prompt']
    }
    
    results_file = Path(f"artifacts/results/scenario_{scenario['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nFull results saved to: {results_file}")

if __name__ == "__main__":
    main()
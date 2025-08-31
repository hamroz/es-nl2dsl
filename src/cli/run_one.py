#!/usr/bin/env python3
"""
Run One CLI: Single scenario testing and validation utility

This CLI utility provides focused testing capabilities for individual scenarios within
the ES-NL2DSL system, enabling developers and researchers to test specific prompts,
validate generated queries, and perform detailed analysis of single query generation
workflows. It serves as a debugging and development tool for system refinement.

Key capabilities:
- Single scenario execution with detailed logging and error reporting
- Query generation testing with configurable parameters (index, seed, model)
- Real-time validation with rule-based checking and constraint verification
- Performance measurement with execution timing and resource usage
- Output formatting with JSON and human-readable result presentation
- Integration with existing evaluation frameworks and ground truth comparison
- Debugging support with verbose logging and intermediate result inspection
- Custom index targeting for multi-dataset testing scenarios
- Abstain handling with detailed reason reporting for failed generations

The utility is essential for development workflows, enabling rapid iteration
and testing of individual scenarios without running full evaluation suites.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
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

def generate_query(prompt, task_id, index=None, seed=None):
    """Generate a query using generate_constrained.py"""
    cmd = [sys.executable, "src/generators/constrained.py", 
           "--prompt", prompt,
           "--task-id", task_id]
    if index:
        cmd.extend(["--index", index])
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    
    result = subprocess.run(
        cmd,
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

def validate_query(query_file, rules_file="artifacts/validator_rules.yaml", index=None):
    """Validate a query using validator.py"""
    # Auto-select rules based on index
    if index and "cic" in index.lower():
        cic_rules = Path("artifacts/validator_rules_cic.yaml")
        if cic_rules.exists():
            rules_file = str(cic_rules)
    
    result = subprocess.run(
        [sys.executable, "src/core/validator.py",
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
        [sys.executable, "src/core/eval_exec.py",
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
    results_files = sorted(output_dir.glob("eval_*.json"), key=lambda x: x.stat().st_mtime)
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
    parser.add_argument("--seed", type=int, help="Random seed for reproducible generation")
    
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
        if args.seed is not None:
            print(f"Using seed: {args.seed}")
        query, error = generate_query(scenario['prompt'], scenario['id'], args.index, args.seed)
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
    valid, validation_output = validate_query(str(candidate_path), index=args.index)
    
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
    print("=== Traditional Metrics ===")
    print(f"  Jaccard Similarity: {metrics.get('jaccard', 'N/A'):.3f}")
    print(f"  F1 Score: {metrics.get('f1', 'N/A'):.3f}")
    print(f"  Precision: {metrics.get('precision', 'N/A'):.3f}")
    print(f"  Recall: {metrics.get('recall', 'N/A'):.3f}")
    
    # Enhanced metrics if available
    enhanced = metrics.get('enhanced_metrics', {})
    if enhanced:
        enhanced_data = enhanced.get('enhanced', {})
        execution_data = enhanced.get('execution', {})
        
        print("\n=== Enhanced Metrics ===")
        print(f"  Quality Level: {enhanced_data.get('quality_level', 'N/A').upper()}")
        print(f"  Semantic Similarity: {enhanced_data.get('semantic_similarity', 'N/A'):.3f}")
        print(f"  Comprehensiveness: {enhanced_data.get('comprehensiveness_score', 'N/A'):.3f}")
        print(f"  Efficiency Score: {enhanced_data.get('efficiency_score', 'N/A'):.3f}")
        
        exec_time = execution_data.get('execution_time_ms', 'N/A')
        if exec_time != 'N/A':
            print(f"  Execution Time: {exec_time:.1f}ms")
        print(f"  Results Found: {execution_data.get('result_count', 'N/A')}")
    
    print(f"\n=== Validation ===")
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
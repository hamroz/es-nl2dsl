#!/usr/bin/env python3
"""Master experiment runner for all baselines and ablations"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

METHODS = ["constrained", "rules", "zeroshot"]
SCENARIOS = ["scan-001", "scan-002", "scan-003", "scan-004", "scan-005", "scan-006"]

def run_method(method, scenario_id, repeat=1):
    """Run a specific method on a scenario"""
    if method == "constrained":
        cmd = ["python", "src/run_one.py", "--id", scenario_id, "--gen"]
    elif method == "rules":
        # Get prompt from prompts.yaml
        import yaml
        with open("tasks/prompts.yaml") as f:
            scenarios = yaml.safe_load(f)
        prompt = next(s['prompt'] for s in scenarios if s['id'] == scenario_id)
        
        # Generate with rules
        subprocess.run([
            "python", "src/baseline_rules.py",
            "--prompt", prompt,
            "--task-id", scenario_id
        ])
        # Then evaluate
        cmd = ["python", "src/run_one.py", "--id", scenario_id, 
               "--candidate", f"artifacts/generated/rules_{scenario_id}.json"]
    elif method == "zeroshot":
        # Similar to rules
        import yaml
        with open("tasks/prompts.yaml") as f:
            scenarios = yaml.safe_load(f)
        prompt = next(s['prompt'] for s in scenarios if s['id'] == scenario_id)
        
        subprocess.run([
            "python", "src/baseline_zeroshot.py",
            "--prompt", prompt,
            "--task-id", scenario_id
        ])
        cmd = ["python", "src/run_one.py", "--id", scenario_id,
               "--candidate", f"artifacts/generated/zeroshot_{scenario_id}.json"]
    else:
        return None
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def main():
    print("=== Master Experiment Runner ===")
    print(f"Methods: {METHODS}")
    print(f"Scenarios: {SCENARIOS[:3]} (subset for demo)")
    
    results = []
    
    for method in METHODS:
        print(f"\n--- Running {method} ---")
        for scenario in SCENARIOS[:3]:  # Run subset for demo
            success = run_method(method, scenario)
            results.append({
                "method": method,
                "scenario": scenario,
                "success": success,
                "timestamp": datetime.now().isoformat()
            })
            print(f"  {scenario}: {'✓' if success else '✗'}")
    
    # Save results
    with open("artifacts/results/experiment_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nExperiment complete!")

if __name__ == "__main__":
    main()
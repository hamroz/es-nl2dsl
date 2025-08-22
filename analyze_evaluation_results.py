#!/usr/bin/env python3

import json
import glob
from pathlib import Path
from collections import defaultdict

def analyze_evaluation_results():
    """Analyze evaluation results to assess improvements"""
    
    print("=== ES-NL2DSL Evaluation Results Analysis ===\n")
    
    # Get all recent result files (after fixes implementation)
    results_dir = Path("artifacts/results")
    
    # Get results from today's evaluation (after fixes)
    after_files = glob.glob(str(results_dir / "scenario_*_20250822_17*.json"))
    
    # Get previous results for comparison (before fixes)
    before_files = glob.glob(str(results_dir / "scenario_*_20250820_*.json"))
    
    print(f"Found {len(after_files)} recent results and {len(before_files)} previous results")
    
    def load_results(files):
        """Load and organize results by scenario"""
        results = {}
        for file in files:
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    scenario_id = data.get('scenario_id', 'unknown')
                    if scenario_id != 'unknown':
                        results[scenario_id] = data
            except Exception as e:
                print(f"Error loading {file}: {e}")
        return results
    
    after_results = load_results(after_files)
    before_results = load_results(before_files)
    
    print(f"\n=== COMPARISON ANALYSIS ===")
    print(f"{'Scenario':<12} {'Before F1':<10} {'After F1':<10} {'Before Jacc':<12} {'After Jacc':<12} {'Change':<8}")
    print("-" * 70)
    
    improvements = []
    
    # Common scenarios
    common_scenarios = set(after_results.keys()) & set(before_results.keys())
    
    for scenario_id in sorted(common_scenarios):
        before = before_results[scenario_id]
        after = after_results[scenario_id]
        
        before_f1 = before.get('metrics', {}).get('f1', 0.0)
        after_f1 = after.get('metrics', {}).get('f1', 0.0)
        before_jacc = before.get('metrics', {}).get('jaccard', 0.0) 
        after_jacc = after.get('metrics', {}).get('jaccard', 0.0)
        
        f1_change = after_f1 - before_f1
        improvements.append(f1_change)
        
        change_symbol = "↑" if f1_change > 0 else "↓" if f1_change < 0 else "="
        
        print(f"{scenario_id:<12} {before_f1:<10.3f} {after_f1:<10.3f} {before_jacc:<12.3f} {after_jacc:<12.3f} {change_symbol:<8}")
    
    # Calculate overall statistics
    if improvements:
        avg_improvement = sum(improvements) / len(improvements)
        improved_scenarios = len([x for x in improvements if x > 0])
        degraded_scenarios = len([x for x in improvements if x < 0])
        unchanged_scenarios = len([x for x in improvements if x == 0])
        
        print(f"\n=== OVERALL STATISTICS ===")
        print(f"Scenarios analyzed: {len(improvements)}")
        print(f"Average F1 change: {avg_improvement:+.3f}")
        print(f"Improved scenarios: {improved_scenarios}")
        print(f"Degraded scenarios: {degraded_scenarios}")
        print(f"Unchanged scenarios: {unchanged_scenarios}")
    
    # Analyze recent results in detail
    print(f"\n=== RECENT RESULTS DETAIL ===")
    
    metrics_summary = {
        'f1': [],
        'jaccard': [],
        'precision': [],
        'recall': []
    }
    
    error_count = 0
    pass_count = 0
    
    for scenario_id in sorted(after_results.keys()):
        result = after_results[scenario_id]
        
        # Check validation status
        validation_passed = result.get('validation_passed', False)
        if validation_passed:
            pass_count += 1
        else:
            error_count += 1
        
        # Collect metrics
        metrics = result.get('metrics', {})
        for metric in metrics_summary:
            value = metrics.get(metric, 0.0)
            metrics_summary[metric].append(value)
        
        # Check for errors
        candidate_error = metrics.get('candidate_error')
        expert_error = metrics.get('expert_error')
        if candidate_error:
            print(f"{scenario_id}: CANDIDATE ERROR - {candidate_error}")
        if expert_error:
            print(f"{scenario_id}: EXPERT ERROR - {expert_error}")
    
    print(f"\nValidation Results: {pass_count} PASS, {error_count} ERRORS")
    
    # Calculate average metrics
    print(f"\n=== PERFORMANCE METRICS ===")
    for metric, values in metrics_summary.items():
        if values:
            avg_val = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            
            # Count perfect scores
            perfect_count = len([x for x in values if abs(x - 1.0) < 0.001])
            print(f"{metric.replace('_', ' ').title()}: avg={avg_val:.3f}, min={min_val:.3f}, max={max_val:.3f}, perfect={perfect_count}/{len(values)}")
    
    # Identify problematic scenarios (low scores)
    print(f"\n=== PROBLEMATIC SCENARIOS ===")
    for scenario_id in sorted(after_results.keys()):
        result = after_results[scenario_id]
        metrics = result.get('metrics', {})
        f1 = metrics.get('f1', 0.0)
        jaccard = metrics.get('jaccard', 0.0)
        
        if f1 < 0.5 or jaccard < 0.5:
            print(f"{scenario_id}: F1={f1:.3f}, Jaccard={jaccard:.3f} - NEEDS INVESTIGATION")
    
    # Check for suspiciously high scores (possible test issues)
    perfect_f1_count = len([r for r in after_results.values() if abs(r.get('metrics', {}).get('f1', 0) - 1.0) < 0.001])
    perfect_jaccard_count = len([r for r in after_results.values() if abs(r.get('metrics', {}).get('jaccard', 0) - 1.0) < 0.001])
    
    total_scenarios = len(after_results)
    if total_scenarios > 0:
        perfect_f1_rate = perfect_f1_count / total_scenarios * 100
        perfect_jaccard_rate = perfect_jaccard_count / total_scenarios * 100
        
        print(f"\n=== SUSPICIOUS METRICS ANALYSIS ===")
        print(f"Perfect F1 scores: {perfect_f1_count}/{total_scenarios} ({perfect_f1_rate:.1f}%)")
        print(f"Perfect Jaccard scores: {perfect_jaccard_count}/{total_scenarios} ({perfect_jaccard_rate:.1f}%)")
        
        if perfect_f1_rate > 60:
            print("⚠ WARNING: High rate of perfect F1 scores may indicate overfitting or trivial test cases")
        if perfect_jaccard_rate > 60:
            print("⚠ WARNING: High rate of perfect Jaccard scores may indicate overfitting or trivial test cases")

if __name__ == "__main__":
    analyze_evaluation_results()
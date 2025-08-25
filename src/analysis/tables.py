#!/usr/bin/env python3
import json
import pandas as pd
from pathlib import Path
import argparse
from datetime import datetime

def load_results(results_dir):
    """Load all JSON result files from directory"""
    results = []
    results_path = Path(results_dir)
    
    # Load scenario results
    for json_file in results_path.glob("scenario_*.json"):
        with open(json_file) as f:
            data = json.load(f)
            results.append({
                'type': 'scenario',
                'file': json_file.name,
                **data
            })
    
    # Load eval results
    for json_file in results_path.glob("eval_*.json"):
        with open(json_file) as f:
            data = json.load(f)
            results.append({
                'type': 'eval',
                'file': json_file.name,
                **data
            })
    
    return results

def create_summary_table(results):
    """Create summary table from results"""
    rows = []
    
    for result in results:
        if result['type'] == 'scenario':
            row = {
                'Scenario ID': result.get('scenario_id', 'N/A'),
                'Timestamp': result.get('timestamp', 'N/A')[:19],  # Trim microseconds
                'Validation': '✓' if result.get('validation_passed') else '✗',
                'Jaccard': f"{result.get('metrics', {}).get('jaccard', 0):.3f}",
                'F1 Score': f"{result.get('metrics', {}).get('f1', 0):.3f}",
                'Precision': f"{result.get('metrics', {}).get('precision', 0):.3f}",
                'Recall': f"{result.get('metrics', {}).get('recall', 0):.3f}",
                'Expert Docs': result.get('metrics', {}).get('expert_count', 'N/A'),
                'Candidate Docs': result.get('metrics', {}).get('candidate_count', 'N/A')
            }
            rows.append(row)
        elif result['type'] == 'eval':
            # Handle direct eval results
            row = {
                'Scenario ID': 'direct_eval',
                'Timestamp': result.get('timestamp', 'N/A')[:19],
                'Validation': 'N/A',
                'Jaccard': f"{result.get('jaccard', 0):.3f}",
                'F1 Score': f"{result.get('f1', 0):.3f}",
                'Precision': f"{result.get('precision', 0):.3f}",
                'Recall': f"{result.get('recall', 0):.3f}",
                'Expert Docs': result.get('expert_count', 'N/A'),
                'Candidate Docs': result.get('candidate_count', 'N/A')
            }
            rows.append(row)
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows)
    
    # Sort by timestamp descending
    if 'Timestamp' in df.columns:
        df = df.sort_values('Timestamp', ascending=False)
    
    return df

def calculate_aggregate_metrics(df):
    """Calculate aggregate metrics from dataframe"""
    if df.empty:
        return {}
    
    metrics = {}
    
    # Convert metric columns to numeric
    for col in ['Jaccard', 'F1 Score', 'Precision', 'Recall']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Calculate averages
    for col in ['Jaccard', 'F1 Score', 'Precision', 'Recall']:
        if col in df.columns:
            metrics[f'Mean {col}'] = df[col].mean()
            metrics[f'Std {col}'] = df[col].std()
    
    # Count validation passes
    if 'Validation' in df.columns:
        metrics['Validation Pass Rate'] = (df['Validation'] == '✓').mean()
    
    return metrics

def save_outputs(df, aggregate_metrics, output_dir, include_confidence_intervals=False):
    """Save outputs in multiple formats"""
    output_path = Path(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save CSV
    csv_file = output_path / f"results_summary_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    print(f"Saved CSV to {csv_file}")
    
    # Save aggregate metrics
    metrics_file = output_path / f"aggregate_metrics_{timestamp}.json"
    with open(metrics_file, 'w') as f:
        json.dump(aggregate_metrics, f, indent=2, default=str)
    print(f"Saved metrics to {metrics_file}")
    
    # Save markdown table
    md_file = output_path / f"results_table_{timestamp}.md"
    with open(md_file, 'w') as f:
        f.write("# ES-NL2DSL Evaluation Results\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        
        f.write("## Summary Table\n\n")
        f.write(df.to_markdown(index=False))
        
        f.write("\n\n## Aggregate Metrics\n\n")
        for key, value in aggregate_metrics.items():
            if isinstance(value, float):
                f.write(f"- **{key}**: {value:.3f}\n")
            else:
                f.write(f"- **{key}**: {value}\n")
        
        # Add confidence intervals if available
        if include_confidence_intervals:
            f.write("\n\n## Statistical Analysis\n\n")
            f.write("*Note: Confidence intervals and significance testing require multiple runs.*\n")
            f.write("*Run with statistical evaluation suite for full statistical analysis.*\n")
    print(f"Saved markdown to {md_file}")

def main():
    parser = argparse.ArgumentParser(description="Render evaluation results tables")
    parser.add_argument("--input", default="artifacts/results", help="Results directory")
    parser.add_argument("--output", default="artifacts/results", help="Output directory")
    parser.add_argument("--format", choices=['all', 'csv', 'json', 'markdown'], 
                       default='all', help="Output format")
    
    args = parser.parse_args()
    
    # Load results
    print(f"Loading results from {args.input}")
    results = load_results(args.input)
    
    if not results:
        print("No results found")
        return
    
    print(f"Found {len(results)} result files")
    
    # Create summary table
    df = create_summary_table(results)
    
    if df.empty:
        print("No valid results to summarize")
        return
    
    # Display table
    print("\n" + "="*80)
    print("EVALUATION RESULTS SUMMARY")
    print("="*80)
    print(df.to_string(index=False))
    
    # Calculate aggregate metrics
    aggregate = calculate_aggregate_metrics(df)
    
    print("\n" + "="*80)
    print("AGGREGATE METRICS")
    print("="*80)
    for key, value in aggregate.items():
        if isinstance(value, float):
            print(f"{key:30s}: {value:.3f}")
        else:
            print(f"{key:30s}: {value}")
    
    # Save outputs
    print("\n" + "="*80)
    print("SAVING OUTPUTS")
    print("="*80)
    save_outputs(df, aggregate, args.output)
    
    print("\nDone!")

if __name__ == "__main__":
    main()
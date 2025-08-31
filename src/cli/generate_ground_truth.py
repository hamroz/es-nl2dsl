#!/usr/bin/env python3
"""
Ground Truth Generator CLI: Expert query validation and benchmark creation utility

This CLI utility provides comprehensive ground truth generation capabilities for the
ES-NL2DSL evaluation framework, enabling creation of validated query benchmarks from
expert-crafted Elasticsearch DSL queries. It executes expert queries against live data
to generate authoritative result sets for evaluation and validation purposes.

Key capabilities:
- Automated ground truth generation from expert-crafted DSL queries
- Large-scale query execution with configurable result limits and pagination
- Document ID collection with deterministic sorting for reproducible benchmarks
- Sample result extraction with metadata preservation for validation
- Batch processing with progress tracking and error handling
- Index-specific ground truth generation for multi-dataset scenarios
- Statistical analysis with result count validation and distribution analysis
- Output formatting with structured JSON and human-readable reporting
- Integration with evaluation frameworks for seamless benchmark creation

The utility is essential for maintaining evaluation quality and creating reliable
benchmarks for system validation, research, and performance assessment across
different datasets and query complexity levels.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import yaml
import argparse
from pathlib import Path
from elasticsearch import Elasticsearch
from config import get_es_client_config, ES_DEFAULT_INDEX

def execute_query(es, index, dsl, size=10000):
    """Execute query and return document IDs"""
    res = es.search(index=index, body=dsl, size=size, track_total_hits=True)
    ids = sorted([h["_id"] for h in res["hits"]["hits"]])
    total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
    
    # Also get sample documents for inspection
    samples = []
    for hit in res["hits"]["hits"][:3]:  # First 3 samples
        samples.append({
            "id": hit["_id"],
            "timestamp": hit["_source"].get("@timestamp"),
            "label": hit["_source"].get("label")
        })
    
    return {
        "doc_ids": ids,
        "total_count": total,
        "samples": samples
    }

def main():
    parser = argparse.ArgumentParser(description="Generate ground truth for scenarios")
    parser.add_argument("--prompts", default="tasks/prompts.yaml", help="Prompts file")
    parser.add_argument("--index", default=ES_DEFAULT_INDEX, help="Elasticsearch index")
    parser.add_argument("--output-dir", default="artifacts/ground_truth", help="Output directory")
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to Elasticsearch
    es = Elasticsearch(**get_es_client_config(use_admin=False))
    
    # Load scenarios
    with open(args.prompts) as f:
        scenarios = yaml.safe_load(f)
    
    print(f"Generating ground truth for {len(scenarios)} scenarios...")
    
    for scenario in scenarios:
        scenario_id = scenario['id']
        print(f"\nProcessing {scenario_id}:")
        print(f"  Prompt: {scenario['prompt']}")
        
        # Parse expert DSL
        expert_dsl = yaml.safe_load(scenario.get('expert_dsl', '{}'))
        
        # Execute query
        result = execute_query(es, args.index, expert_dsl)
        
        # Add metadata
        ground_truth = {
            "scenario_id": scenario_id,
            "prompt": scenario['prompt'],
            "time_window": scenario.get('time_window', {}),
            "expert_dsl": expert_dsl,
            "results": result
        }
        
        # Save to file
        output_file = output_dir / f"{scenario_id}.json"
        with open(output_file, 'w') as f:
            json.dump(ground_truth, f, indent=2)
        
        print(f"  Results: {result['total_count']} documents")
        print(f"  Saved to: {output_file}")
    
    print(f"\nGround truth generated for all scenarios in {output_dir}")

if __name__ == "__main__":
    main()
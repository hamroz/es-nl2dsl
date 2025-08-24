#!/usr/bin/env python3
"""Create schema drift index with renamed fields"""
import json
import pandas as pd
from pathlib import Path
from elasticsearch import Elasticsearch
from config import get_es_client_config, ES_ADMIN_CREDS

def create_drift_mapping():
    """Create mapping with renamed fields to simulate schema drift"""
    return {
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "@timestamp": {"type": "date"},
                "src_ip": {"type": "keyword"},
                "dst_ip": {"type": "keyword"},
                "src_port": {"type": "integer"},
                "dst_port": {"type": "integer"},
                "protocol": {"type": "keyword"},
                "bytes_received": {"type": "long"},  # Was bytes_in
                "bytes_sent": {"type": "long"},      # Was bytes_out
                "classification": {"type": "keyword"}, # Was label
                "log_message": {"type": "text", "index": False}  # Was message
            }
        }
    }

def transform_data_for_drift(csv_path):
    """Transform CSV data to match drift schema"""
    df = pd.read_csv(csv_path)
    
    # Rename columns to match drift schema
    df = df.rename(columns={
        'bytes_in': 'bytes_received',
        'bytes_out': 'bytes_sent',
        'label': 'classification',
        'message': 'log_message'
    })
    
    return df

def main():
    print("Creating schema drift index...")
    
    # Connect to Elasticsearch
    es = Elasticsearch(**get_es_client_config(use_admin=True))
    
    # Delete existing drift index if exists
    if es.indices.exists(index="logs_net_drift"):
        es.indices.delete(index="logs_net_drift")
        print("Deleted existing logs_net_drift index")
    
    # Create new drift index with modified mapping
    drift_mapping = create_drift_mapping()
    es.indices.create(index="logs_net_drift", body=drift_mapping)
    print("Created logs_net_drift index with modified schema")
    
    # Transform and save CSV with renamed columns
    original_csv = Path("data_raw/sample_extended.csv")
    drift_csv = Path("data_raw/sample_drift.csv")
    
    df = transform_data_for_drift(original_csv)
    df.to_csv(drift_csv, index=False)
    print(f"Created drift CSV: {drift_csv}")
    
    # Ingest data into drift index
    import subprocess
    result = subprocess.run([
        "python", "src/ingest.py",
        "--file", str(drift_csv),
        "--index", "logs_net_drift"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Successfully ingested data into drift index")
        print(result.stdout)
    else:
        print("Failed to ingest data:")
        print(result.stderr)
        return 1
    
    # Verify the index
    doc_count = es.count(index="logs_net_drift")["count"]
    print(f"Drift index contains {doc_count} documents")
    
    # Show mapping differences
    print("\nSchema differences:")
    print("  Original -> Drift")
    print("  bytes_in -> bytes_received")
    print("  bytes_out -> bytes_sent")
    print("  label -> classification")
    print("  message -> log_message")
    
    print("\nDrift index ready for testing!")
    print("Run: python src/run_one.py --id scan-001 --index logs_net_drift --gen")
    
    return 0

if __name__ == "__main__":
    exit(main())
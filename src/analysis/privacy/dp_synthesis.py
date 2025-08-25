#!/usr/bin/env python3
import pandas as pd
import numpy as np
import argparse
import hashlib
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from src.utils.config import get_es_client_config, ES_ADMIN_CREDS, ES_DEFAULT_INDEX
except ImportError:
    # Fallback for direct execution
    sys.path.append(str(project_root / "src"))
    from utils.config import get_es_client_config, ES_ADMIN_CREDS, ES_DEFAULT_INDEX

def add_laplace_noise(value, scale):
    """Add Laplace noise to a numeric value"""
    if scale == 0:
        return value
    noise = np.random.laplace(0, scale)
    return max(0, int(value + noise))  # Ensure non-negative

def jitter_timestamp(timestamp_str, window_minutes=30):
    """Add random jitter to a timestamp within a bounded window"""
    dt = pd.to_datetime(timestamp_str)
    jitter = timedelta(minutes=np.random.uniform(-window_minutes, window_minutes))
    return (dt + jitter).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def generate_doc_id(row_dict):
    """Generate deterministic document ID"""
    key_fields = ['@timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port']
    key_string = '|'.join(str(row_dict.get(f, '')) for f in key_fields)
    return hashlib.sha1(key_string.encode()).hexdigest()

def apply_dp_transformations(df, epsilon=1.0, timestamp_jitter_minutes=30):
    """Apply differential privacy transformations to dataframe"""
    df_dp = df.copy()
    
    # Calculate Laplace scale from epsilon (simplified)
    # For real DP, this needs proper sensitivity analysis
    sensitivity = 1000  # Assumed sensitivity for byte counts
    scale = sensitivity / epsilon
    
    # Apply noise to numeric fields
    if 'bytes_in' in df_dp.columns:
        df_dp['bytes_in'] = df_dp['bytes_in'].apply(lambda x: add_laplace_noise(x, scale))
    
    if 'bytes_out' in df_dp.columns:
        df_dp['bytes_out'] = df_dp['bytes_out'].apply(lambda x: add_laplace_noise(x, scale))
    
    # Jitter timestamps
    if '@timestamp' in df_dp.columns:
        df_dp['@timestamp'] = df_dp['@timestamp'].apply(
            lambda x: jitter_timestamp(x, timestamp_jitter_minutes)
        )
    
    # Keep other fields unchanged (IPs, ports, protocols, labels)
    return df_dp

def index_to_elasticsearch(df, index_name, es_host='localhost', es_port=9200, 
                          es_user=None, es_password=None):
    """Index DataFrame to Elasticsearch"""
    es = Elasticsearch(**get_es_client_config(use_admin=True))
    
    # Check connection
    if not es.ping():
        raise ConnectionError("Cannot connect to Elasticsearch")
    
    # Create index if it doesn't exist (copy mappings from original)
    if not es.indices.exists(index=index_name):
        # Get mappings from original index
        original_mappings = es.indices.get_mapping(index='logs_net')
        mappings = original_mappings['logs_net']['mappings']
        
        es.indices.create(index=index_name, body={'mappings': mappings})
        print(f"Created index {index_name}")
    
    # Prepare bulk operations
    actions = []
    for _, row in df.iterrows():
        doc = row.to_dict()
        doc_id = generate_doc_id(doc)
        
        action = {
            '_index': index_name,
            '_id': doc_id,
            '_source': doc
        }
        actions.append(action)
    
    # Bulk index
    success, failed = bulk(es, actions, raise_on_error=False)
    print(f"Indexed {success} documents to {index_name}")
    
    if failed:
        print(f"Failed to index {len(failed)} documents")
        for item in failed[:5]:  # Show first 5 failures
            print(f"  Error: {item}")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Generate DP-synthetic network log data")
    parser.add_argument("--input", default="data_raw/sample.csv", help="Input CSV file")
    parser.add_argument("--index", default=ES_DEFAULT_INDEX + "_dp", help="Target ES index name")
    parser.add_argument("--epsilon", type=float, default=1.0, help="Privacy parameter (lower = more privacy)")
    parser.add_argument("--timestamp-jitter", type=int, default=30, help="Timestamp jitter window in minutes")
    parser.add_argument("--output-csv", help="Optional: save DP data to CSV")
    parser.add_argument("--host", default="localhost", help="Elasticsearch host")
    parser.add_argument("--port", type=int, default=9200, help="Elasticsearch port")
    parser.add_argument("--user", default=ES_ADMIN_CREDS['user'], help="Elasticsearch username")
    parser.add_argument("--password", default=ES_ADMIN_CREDS['password'], help="Elasticsearch password")
    
    args = parser.parse_args()
    
    # Load original data
    print(f"Loading data from {args.input}")
    df = pd.read_csv(args.input)
    
    # Apply DP transformations
    print(f"Applying DP transformations (epsilon={args.epsilon})")
    df_dp = apply_dp_transformations(df, args.epsilon, args.timestamp_jitter)
    
    # Save to CSV if requested
    if args.output_csv:
        df_dp.to_csv(args.output_csv, index=False)
        print(f"Saved DP data to {args.output_csv}")
    
    # Index to Elasticsearch
    print(f"Indexing to Elasticsearch index: {args.index}")
    indexed = index_to_elasticsearch(
        df_dp, args.index,
        args.host, args.port,
        args.user, args.password
    )
    
    # Print statistics
    print("\nDP Transformation Statistics:")
    if 'bytes_in' in df.columns:
        original_mean = df['bytes_in'].mean()
        dp_mean = df_dp['bytes_in'].mean()
        print(f"  bytes_in mean: {original_mean:.2f} -> {dp_mean:.2f} (diff: {abs(original_mean - dp_mean):.2f})")
    
    if 'bytes_out' in df.columns:
        original_mean = df['bytes_out'].mean()
        dp_mean = df_dp['bytes_out'].mean()
        print(f"  bytes_out mean: {original_mean:.2f} -> {dp_mean:.2f} (diff: {abs(original_mean - dp_mean):.2f})")
    
    print(f"\nPrivacy-utility tradeoff:")
    print(f"  Epsilon: {args.epsilon} (lower = more privacy, less utility)")
    print(f"  Timestamp jitter: ±{args.timestamp_jitter} minutes")

if __name__ == "__main__":
    main()
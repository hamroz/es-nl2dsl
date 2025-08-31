#!/usr/bin/env python3
"""
Create differential privacy indices with various epsilon values.
This creates multiple indices with noise-injected data for privacy testing.
"""

import sys
import json
import random
import numpy as np
from pathlib import Path
from elasticsearch import Elasticsearch

# Add src to path
sys.path.append(str(Path(__file__).parent))

from utils.config import get_es_client_config

def add_laplace_noise(value, epsilon, sensitivity=1.0):
    """Add Laplace noise for differential privacy."""
    if isinstance(value, (int, float)):
        scale = sensitivity / epsilon
        noise = np.random.laplace(0, scale)
        return max(0, value + noise)  # Ensure non-negative values
    return value

def create_dp_index(epsilon):
    """Create a DP index with given epsilon value."""
    
    try:
        # Connect to Elasticsearch
        config = get_es_client_config()
        es = Elasticsearch(**config)
        
        # Load original mappings
        mappings_file = Path("artifacts/mappings.json")
        if not mappings_file.exists():
            print(f"❌ Original mappings not found: {mappings_file}")
            return False
            
        with open(mappings_file, 'r') as f:
            mappings = json.load(f)
        
        # Create DP index name
        eps_str = str(epsilon).replace('.', '')
        dp_index = f"logs_net_dp_eps{eps_str}"
        
        # Delete existing DP index if it exists
        if es.indices.exists(index=dp_index):
            es.indices.delete(index=dp_index)
            print(f"🗑️  Deleted existing index: {dp_index}")
        
        # Create new DP index
        es.indices.create(index=dp_index, body=mappings)
        print(f"✅ Created DP index: {dp_index} (ε={epsilon})")
        
        # Get sample data from original index
        try:
            orig_resp = es.search(
                index="logs_net",
                body={"size": 100, "query": {"match_all": {}}},
                scroll="1m"
            )
            docs = orig_resp['hits']['hits']
        except:
            # If original index doesn't exist, create synthetic data
            docs = generate_synthetic_data(50)
        
        # Apply DP noise and index documents
        dp_docs = []
        for doc in docs:
            source = doc.get('_source', doc)
            dp_doc = apply_dp_noise(source, epsilon)
            dp_docs.append(dp_doc)
        
        # Bulk index DP documents
        for i, doc in enumerate(dp_docs):
            es.index(index=dp_index, id=f"dp-{eps_str}-{i+1}", body=doc)
        
        print(f"✅ Added {len(dp_docs)} DP documents to {dp_index}")
        
        # Verify index
        count_resp = es.count(index=dp_index)
        print(f"📊 Total documents in DP index: {count_resp['count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating DP index (ε={epsilon}): {e}")
        return False

def apply_dp_noise(doc, epsilon):
    """Apply differential privacy noise to document fields."""
    dp_doc = doc.copy()
    
    # Add noise to numeric fields
    if 'bytes_in' in dp_doc:
        dp_doc['bytes_in'] = int(add_laplace_noise(dp_doc['bytes_in'], epsilon))
    if 'bytes_out' in dp_doc:
        dp_doc['bytes_out'] = int(add_laplace_noise(dp_doc['bytes_out'], epsilon))
    if 'src_port' in dp_doc:
        dp_doc['src_port'] = int(add_laplace_noise(dp_doc['src_port'], epsilon))
    if 'dst_port' in dp_doc:
        dp_doc['dst_port'] = int(add_laplace_noise(dp_doc['dst_port'], epsilon))
    
    # Add noise to IP addresses (modify last octet)
    if 'src_ip' in dp_doc and isinstance(dp_doc['src_ip'], str):
        parts = dp_doc['src_ip'].split('.')
        if len(parts) == 4:
            last_octet = int(parts[3])
            noisy_octet = int(add_laplace_noise(last_octet, epsilon))
            dp_doc['src_ip'] = f"{parts[0]}.{parts[1]}.{parts[2]}.{min(255, max(1, noisy_octet))}"
    
    return dp_doc

def generate_synthetic_data(count=50):
    """Generate synthetic data when original index is not available."""
    synthetic_docs = []
    
    protocols = ['tcp', 'udp', 'icmp']
    labels = ['BENIGN', 'PortScan', 'DoS', 'Infiltration']
    
    for i in range(count):
        doc = {
            '@timestamp': f"2017-07-0{4 + (i % 4)}T{8 + (i % 12):02d}:{i % 60:02d}:00.000Z",
            'src_ip': f"192.168.1.{100 + (i % 155)}",
            'dst_ip': f"10.0.0.{1 + (i % 50)}",
            'src_port': 1024 + (i * 17) % 64000,
            'dst_port': [80, 443, 22, 23, 25, 53][i % 6],
            'protocol': protocols[i % len(protocols)],
            'bytes_in': random.randint(64, 65536),
            'bytes_out': random.randint(64, 65536),
            'label': labels[i % len(labels)],
            'message': f"Synthetic network event {i+1}"
        }
        synthetic_docs.append({'_source': doc})
    
    return synthetic_docs

def create_dp_grid():
    """Create multiple DP indices with different epsilon values."""
    
    epsilon_values = [0.5, 1.0, 2.0]
    results = []
    
    print("=== Creating Differential Privacy Index Grid ===")
    
    for epsilon in epsilon_values:
        print(f"\n--- Creating DP Index (ε={epsilon}) ---")
        success = create_dp_index(epsilon)
        results.append((epsilon, success))
        
    print(f"\n=== DP Grid Creation Summary ===")
    for epsilon, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  ε={epsilon}: {status}")
    
    return all(success for _, success in results)

if __name__ == "__main__":
    success = create_dp_grid()
    sys.exit(0 if success else 1)
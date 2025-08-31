#!/usr/bin/env python3
"""
Create schema drift index for testing robustness.
This creates an index with modified field mappings to test query adaptation.
"""

import sys
import json
from pathlib import Path
from elasticsearch import Elasticsearch

# Add src to path
sys.path.append(str(Path(__file__).parent))

from utils.config import get_es_client_config

def create_drift_index():
    """Create drift index with modified schema."""
    
    # Load original mappings
    mappings_file = Path("artifacts/mappings.json")
    if not mappings_file.exists():
        print(f"❌ Original mappings not found: {mappings_file}")
        return False
        
    with open(mappings_file, 'r') as f:
        original_mappings = json.load(f)
    
    # Create drift mappings (modify field names and types)
    drift_mappings = {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "source_ip": {"type": "ip"},        # Changed from src_ip
                "dest_ip": {"type": "ip"},          # Changed from dst_ip
                "source_port": {"type": "integer"}, # Changed from src_port
                "dest_port": {"type": "integer"},   # Changed from dst_port
                "protocol": {"type": "keyword"},
                "bytes_in": {"type": "long"},
                "bytes_out": {"type": "long"},
                "label": {"type": "keyword"},
                "message": {"type": "text"},
                "event_type": {"type": "keyword"},  # New field
                "severity": {"type": "integer"}     # New field
            }
        }
    }
    
    try:
        # Connect to Elasticsearch
        config = get_es_client_config()
        es = Elasticsearch(**config)
        
        # Delete existing drift index if it exists
        drift_index = "logs_net_drift"
        if es.indices.exists(index=drift_index):
            es.indices.delete(index=drift_index)
            print(f"🗑️  Deleted existing index: {drift_index}")
        
        # Create new drift index
        es.indices.create(index=drift_index, body=drift_mappings)
        print(f"✅ Created drift index: {drift_index}")
        
        # Add sample data with modified schema
        sample_docs = [
            {
                "@timestamp": "2017-07-04T08:15:00.000Z",
                "source_ip": "192.168.1.100",
                "dest_ip": "10.0.0.1", 
                "source_port": 12345,
                "dest_port": 80,
                "protocol": "tcp",
                "bytes_in": 1024,
                "bytes_out": 2048,
                "label": "BENIGN",
                "message": "Normal HTTP traffic",
                "event_type": "web_access",
                "severity": 1
            },
            {
                "@timestamp": "2017-07-04T08:16:00.000Z",
                "source_ip": "192.168.1.200",
                "dest_ip": "10.0.0.2",
                "source_port": 54321,
                "dest_port": 22,
                "protocol": "tcp", 
                "bytes_in": 512,
                "bytes_out": 1024,
                "label": "PortScan",
                "message": "Suspicious port scanning activity",
                "event_type": "security_event",
                "severity": 5
            }
        ]
        
        # Bulk index sample documents
        for i, doc in enumerate(sample_docs):
            es.index(index=drift_index, id=f"drift-{i+1}", body=doc)
        
        print(f"✅ Added {len(sample_docs)} sample documents")
        
        # Verify index
        count_resp = es.count(index=drift_index)
        print(f"📊 Total documents in drift index: {count_resp['count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating drift index: {e}")
        return False

if __name__ == "__main__":
    print("=== Creating Schema Drift Index ===")
    success = create_drift_index()
    sys.exit(0 if success else 1)
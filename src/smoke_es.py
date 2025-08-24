#!/usr/bin/env python3
"""Smoke test for Elasticsearch connectivity"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.health_check import check_elasticsearch_health

def main():
    """Run Elasticsearch smoke test"""
    result = check_elasticsearch_health()
    
    if result["connected"] and result["index_exists"]:
        print(f"✓ Connected to index with {len(result['fields'])} fields")
        print(f"✓ Fields: {', '.join(result['fields'])}")
        if result["sample_data"]:
            print("✓ Sample data available")
        else:
            print("⚠ No sample data found")
        return 0
    else:
        print(f"✗ Connection failed: {result['error']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
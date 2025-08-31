#!/usr/bin/env python3
"""
Elasticsearch Smoke Test: System connectivity and health verification utility

This utility provides essential smoke testing capabilities for Elasticsearch connectivity
within the ES-NL2DSL system, enabling quick verification of system readiness and health
status. It performs basic connectivity tests, index availability checks, and data
validation to ensure the system is operational before running complex operations.

Key capabilities:
- Elasticsearch connectivity testing with authentication validation
- Index existence verification and field discovery
- Sample data availability checking
- Basic health status reporting with clear success/failure indicators
- Integration with system startup and monitoring workflows
- Quick diagnostic information for troubleshooting

The utility is designed for system administrators, automated deployment scripts,
and CI/CD pipelines to verify system readiness before running production workloads.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
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
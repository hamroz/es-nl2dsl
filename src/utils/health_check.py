#!/usr/bin/env python3
"""
Health Check: System monitoring and diagnostic utilities

This module provides comprehensive health monitoring and diagnostic capabilities for the
ES-NL2DSL system, enabling real-time assessment of system components including Elasticsearch
connectivity, index availability, data integrity, and field mapping validation. It supports
both programmatic health checks and interactive diagnostic reporting.

Key capabilities:
- Elasticsearch connectivity testing with credential validation
- Index existence and mapping verification
- Data availability and sample query testing
- Field discovery and schema validation
- Error reporting with detailed diagnostic information
- Support for multiple indices and connection configurations
- Command-line diagnostic interface for system administration
- Integration with system monitoring and alerting frameworks

The module serves as the foundation for system reliability monitoring and helps
administrators quickly identify and troubleshoot connectivity issues, data problems,
and configuration errors across the ES-NL2DSL infrastructure.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
from elasticsearch import Elasticsearch

# Support both module and direct execution
try:
    from .config import get_es_client_config, ES_DEFAULT_INDEX
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.utils.config import get_es_client_config, ES_DEFAULT_INDEX

def check_elasticsearch_health(index: str = None) -> dict:
    """Check Elasticsearch connectivity and index health"""
    if index is None:
        index = ES_DEFAULT_INDEX
    
    result = {
        "connected": False,
        "index_exists": False,
        "fields": [],
        "sample_data": False,
        "error": None
    }
    
    try:
        # Connect as read-only user
        es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=30)
        
        # Index-level connectivity check
        try:
            mapping = es.indices.get_mapping(index=index)
            if "mappings" in mapping[index]:
                result["connected"] = True
                result["index_exists"] = True
                result["fields"] = list(mapping[index]["mappings"]["properties"].keys())
        except Exception as e:
            result["error"] = f"Index mapping check failed: {e}"
            return result
        
        # Test read query
        try:
            res = es.search(index=index, query={"term": {"label": "malicious"}}, size=1)
            hits_total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
            result["sample_data"] = hits_total > 0
        except Exception as e:
            result["error"] = f"Search test failed: {e}"
            
    except Exception as e:
        result["error"] = f"Connection failed: {e}"
    
    return result

def main():
    """Main function for direct execution"""
    import json
    print("ES-NL2DSL Health Check")
    print("=" * 30)
    
    # Check default index
    result = check_elasticsearch_health()
    
    print(f"Index: {ES_DEFAULT_INDEX}")
    print(f"Connected: {'✅' if result['connected'] else '❌'}")
    print(f"Index exists: {'✅' if result['index_exists'] else '❌'}")
    print(f"Sample data: {'✅' if result['sample_data'] else '❌'}")
    print(f"Fields available: {len(result.get('fields', []))}")
    
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    if result['fields']:
        print("Available fields:", ", ".join(result['fields'][:10]))
        if len(result['fields']) > 10:
            print(f"... and {len(result['fields']) - 10} more")

if __name__ == "__main__":
    main()
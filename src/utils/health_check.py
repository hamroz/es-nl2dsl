#!/usr/bin/env python3
"""Health check utilities for ES-NL2DSL system"""
from elasticsearch import Elasticsearch
from .config import get_es_client_config, ES_DEFAULT_INDEX

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
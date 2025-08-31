"""
Field Management Index Profiler: Advanced field discovery and relationship analysis

This module provides sophisticated field profiling capabilities specifically designed
for the field management subsystem of ES-NL2DSL. It performs deep analysis of
Elasticsearch indices to discover field relationships, usage patterns, and semantic
meanings, enabling intelligent field-aware query generation.

Key capabilities:
- Dynamic field discovery with type inference and validation
- Field relationship mapping and correlation analysis
- Usage pattern detection from sample data
- Semantic field categorization (temporal, geographic, numeric, etc.)
- Value distribution analysis for optimization hints
- Caching mechanism with TTL for performance optimization
- Support for complex nested and object field structures

The profiler serves as the intelligence layer for field management, providing
contextual understanding of field semantics beyond simple type information.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import json
import logging
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import time
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch
from collections import defaultdict, Counter
import hashlib
import pickle

logger = logging.getLogger(__name__)

class IndexProfiler:
    """
    Advanced field profiling system with relationship analysis.
    
    Provides deep field analysis beyond basic type information, discovering
    semantic relationships, usage patterns, and optimization opportunities
    for intelligent query generation.
    
    Features:
        - Multi-level caching (memory and disk) with TTL management
        - Field relationship detection through correlation analysis
        - Semantic categorization based on field names and values
        - Value distribution analysis for query optimization
        - Support for nested and complex field structures
        - Incremental profiling for large indices
        
    Architecture:
        - Elasticsearch client integration for live analysis
        - Two-tier caching system for performance
        - Lazy connection initialization
        - Graceful degradation on connection failures
    """
    
    def __init__(self, es_client: Elasticsearch = None, cache_dir: str = "data/index_profiles"):
        self.es_client = es_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.profiles_cache = {}
        
    def get_index_profile(self, index_name: str, refresh_cache: bool = False) -> Dict:
        """Get comprehensive profile for an index."""
        cache_key = f"profile_{index_name}"
        
        # Check memory cache first
        if not refresh_cache and cache_key in self.profiles_cache:
            cached_profile = self.profiles_cache[cache_key]
            if time.time() - cached_profile["timestamp"] < self.cache_ttl:
                return cached_profile["data"]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{index_name}_profile.json"
        if not refresh_cache and cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    if time.time() - cached_data["timestamp"] < self.cache_ttl:
                        self.profiles_cache[cache_key] = cached_data
                        return cached_data["data"]
            except Exception as e:
                logger.warning(f"Error reading cache for {index_name}: {e}")
        
        # Generate fresh profile
        profile = self._generate_index_profile(index_name)
        
        # Cache the results
        cached_data = {
            "data": profile,
            "timestamp": time.time()
        }
        
        self.profiles_cache[cache_key] = cached_data
        
        # Save to disk
        try:
            with open(cache_file, 'w') as f:
                json.dump(cached_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache for {index_name}: {e}")
        
        return profile
    
    def _generate_index_profile(self, index_name: str) -> Dict:
        """Generate a comprehensive profile for an index."""
        if not self.es_client:
            return {"error": "Elasticsearch client not available"}
        
        profile = {
            "index_name": index_name,
            "profile_timestamp": datetime.now().isoformat(),
            "exists": False,
            "document_count": 0,
            "fields": {},
            "field_types": {},
            "sample_data": {},
            "field_statistics": {},
            "data_ranges": {},
            "schema_version": self._calculate_schema_hash(index_name)
        }
        
        try:
            # Check if index exists
            if not self.es_client.indices.exists(index=index_name):
                profile["error"] = f"Index {index_name} does not exist"
                return profile
            
            profile["exists"] = True
            
            # Get index stats
            stats = self.es_client.indices.stats(index=index_name)
            profile["document_count"] = stats["indices"][index_name]["total"]["docs"]["count"]
            profile["index_size"] = stats["indices"][index_name]["total"]["store"]["size_in_bytes"]
            
            # Get field mapping
            mapping = self.es_client.indices.get_mapping(index=index_name)
            if index_name in mapping and "mappings" in mapping[index_name]:
                properties = mapping[index_name]["mappings"].get("properties", {})
                profile["fields"] = self._extract_field_info(properties)
                profile["field_types"] = {
                    field: info["type"] for field, info in profile["fields"].items()
                }
            
            # Sample documents for field analysis
            if profile["document_count"] > 0:
                profile["sample_data"] = self._sample_document_data(index_name)
                profile["field_statistics"] = self._analyze_field_statistics(index_name, profile["fields"])
                profile["data_ranges"] = self._get_data_ranges(index_name, profile["fields"])
            
        except Exception as e:
            logger.error(f"Error profiling index {index_name}: {e}")
            profile["error"] = str(e)
        
        return profile
    
    def _extract_field_info(self, properties: Dict) -> Dict:
        """Extract detailed field information from mapping properties."""
        fields = {}
        
        def extract_recursive(props, prefix=""):
            for field_name, field_config in props.items():
                full_field_name = f"{prefix}{field_name}" if prefix else field_name
                
                if "type" in field_config:
                    fields[full_field_name] = {
                        "type": field_config["type"],
                        "index": field_config.get("index", True),
                        "format": field_config.get("format"),
                        "analyzer": field_config.get("analyzer"),
                        "fields": field_config.get("fields", {}),
                        "properties": field_config.get("properties", {})
                    }
                
                # Handle nested objects
                if "properties" in field_config:
                    extract_recursive(field_config["properties"], f"{full_field_name}.")
        
        extract_recursive(properties)
        return fields
    
    def _sample_document_data(self, index_name: str, sample_size: int = 10) -> Dict:
        """Sample documents to understand actual field usage."""
        try:
            response = self.es_client.search(
                index=index_name,
                body={
                    "size": sample_size,
                    "query": {"match_all": {}},
                    "_source": True
                }
            )
            
            sample_data = {
                "total_sampled": len(response["hits"]["hits"]),
                "field_examples": defaultdict(list),
                "field_presence": Counter(),
                "unique_values": defaultdict(set)
            }
            
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                self._analyze_document(source, sample_data)
            
            # Convert sets to lists for JSON serialization
            sample_data["unique_values"] = {
                field: list(values) for field, values in sample_data["unique_values"].items()
            }
            
            return sample_data
            
        except Exception as e:
            logger.error(f"Error sampling data from {index_name}: {e}")
            return {"error": str(e)}
    
    def _analyze_document(self, doc: Dict, sample_data: Dict, prefix: str = ""):
        """Recursively analyze a document structure."""
        for field, value in doc.items():
            full_field = f"{prefix}{field}" if prefix else field
            sample_data["field_presence"][full_field] += 1
            
            if isinstance(value, dict):
                self._analyze_document(value, sample_data, f"{full_field}.")
            elif isinstance(value, list) and value:
                # Handle arrays
                sample_data["field_examples"][full_field].append(value[:3])  # First 3 items
                for item in value[:5]:  # Analyze first 5 items
                    if not isinstance(item, (dict, list)):
                        sample_data["unique_values"][full_field].add(str(item))
            else:
                # Simple field
                sample_data["field_examples"][full_field].append(value)
                if value is not None:
                    sample_data["unique_values"][full_field].add(str(value))
    
    def _analyze_field_statistics(self, index_name: str, fields: Dict) -> Dict:
        """Analyze statistical properties of fields."""
        stats = {}
        
        try:
            # Build aggregation for numeric and date fields
            aggs = {}
            for field_name, field_info in fields.items():
                field_type = field_info["type"]
                
                if field_type in ["long", "integer", "short", "byte", "double", "float"]:
                    aggs[f"{field_name}_stats"] = {
                        "stats": {"field": field_name}
                    }
                elif field_type == "date":
                    aggs[f"{field_name}_date_range"] = {
                        "min": {"field": field_name},
                    }
                    aggs[f"{field_name}_date_max"] = {
                        "max": {"field": field_name}
                    }
                elif field_type in ["keyword", "text"]:
                    aggs[f"{field_name}_terms"] = {
                        "terms": {"field": field_name, "size": 10}
                    }
            
            if aggs:
                response = self.es_client.search(
                    index=index_name,
                    body={
                        "size": 0,
                        "aggs": aggs
                    }
                )
                
                stats = self._process_field_aggregations(response["aggregations"], fields)
        
        except Exception as e:
            logger.error(f"Error analyzing field statistics for {index_name}: {e}")
            stats["error"] = str(e)
        
        return stats
    
    def _process_field_aggregations(self, aggregations: Dict, fields: Dict) -> Dict:
        """Process aggregation results into field statistics."""
        stats = {}
        
        for agg_name, agg_result in aggregations.items():
            if "_stats" in agg_name:
                field_name = agg_name.replace("_stats", "")
                stats[field_name] = {
                    "type": "numeric",
                    "count": agg_result["count"],
                    "min": agg_result["min"],
                    "max": agg_result["max"],
                    "avg": agg_result["avg"],
                    "sum": agg_result["sum"]
                }
            elif "_date_range" in agg_name:
                field_name = agg_name.replace("_date_range", "")
                if field_name not in stats:
                    stats[field_name] = {"type": "date"}
                stats[field_name]["min"] = agg_result["value_as_string"]
            elif "_date_max" in agg_name:
                field_name = agg_name.replace("_date_max", "")
                if field_name not in stats:
                    stats[field_name] = {"type": "date"}
                stats[field_name]["max"] = agg_result["value_as_string"]
            elif "_terms" in agg_name:
                field_name = agg_name.replace("_terms", "")
                stats[field_name] = {
                    "type": "categorical",
                    "unique_terms": len(agg_result["buckets"]),
                    "top_terms": [
                        {"value": bucket["key"], "count": bucket["doc_count"]}
                        for bucket in agg_result["buckets"]
                    ]
                }
        
        return stats
    
    def _get_data_ranges(self, index_name: str, fields: Dict) -> Dict:
        """Get actual data ranges for fields."""
        ranges = {}
        
        try:
            # Get timestamp range if @timestamp exists
            timestamp_fields = ["@timestamp", "timestamp", "time"]
            for ts_field in timestamp_fields:
                if ts_field in fields and fields[ts_field]["type"] == "date":
                    response = self.es_client.search(
                        index=index_name,
                        body={
                            "size": 0,
                            "aggs": {
                                "time_range": {
                                    "date_range": {
                                        "field": ts_field,
                                        "ranges": [
                                            {"from": "now-1y"},
                                            {"from": "now-1M"},
                                            {"from": "now-1w"},
                                            {"from": "now-1d"}
                                        ]
                                    }
                                },
                                "min_time": {"min": {"field": ts_field}},
                                "max_time": {"max": {"field": ts_field}}
                            }
                        }
                    )
                    
                    ranges[ts_field] = {
                        "min": response["aggregations"]["min_time"]["value_as_string"],
                        "max": response["aggregations"]["max_time"]["value_as_string"],
                        "time_buckets": response["aggregations"]["time_range"]["buckets"]
                    }
                    break  # Only process first timestamp field found
            
        except Exception as e:
            logger.error(f"Error getting data ranges for {index_name}: {e}")
            ranges["error"] = str(e)
        
        return ranges
    
    def _calculate_schema_hash(self, index_name: str) -> str:
        """Calculate hash of index schema for change detection."""
        try:
            if not self.es_client or not self.es_client.indices.exists(index=index_name):
                return "unknown"
            
            mapping = self.es_client.indices.get_mapping(index=index_name)
            mapping_str = json.dumps(mapping, sort_keys=True)
            return hashlib.md5(mapping_str.encode()).hexdigest()[:8]
            
        except Exception as e:
            logger.error(f"Error calculating schema hash for {index_name}: {e}")
            return "error"
    
    def get_available_indices(self) -> List[Dict]:
        """Get list of available indices with basic info."""
        if not self.es_client:
            return []
        
        try:
            indices_info = []
            indices = self.es_client.cat.indices(format="json")
            
            for index in indices:
                if not index["index"].startswith("."):  # Skip system indices
                    indices_info.append({
                        "name": index["index"],
                        "docs_count": int(index["docs.count"]) if index["docs.count"] != 'null' else 0,
                        "store_size": index["store.size"],
                        "health": index["health"],
                        "status": index["status"]
                    })
            
            return sorted(indices_info, key=lambda x: x["docs_count"], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting available indices: {e}")
            return []
    
    def get_field_compatibility_matrix(self, indices: List[str]) -> Dict:
        """Get field compatibility matrix across multiple indices."""
        compatibility = {
            "indices": indices,
            "common_fields": set(),
            "field_type_conflicts": {},
            "index_specific_fields": {},
            "field_coverage": {}
        }
        
        all_fields = {}
        
        for index in indices:
            profile = self.get_index_profile(index)
            if "error" in profile:
                continue
            
            index_fields = profile.get("fields", {})
            compatibility["index_specific_fields"][index] = set(index_fields.keys())
            
            for field, field_info in index_fields.items():
                if field not in all_fields:
                    all_fields[field] = {}
                all_fields[field][index] = field_info["type"]
        
        # Find common fields
        if indices:
            compatibility["common_fields"] = set.intersection(*[
                compatibility["index_specific_fields"].get(idx, set())
                for idx in indices
            ])
        
        # Find type conflicts
        for field, index_types in all_fields.items():
            unique_types = set(index_types.values())
            if len(unique_types) > 1:
                compatibility["field_type_conflicts"][field] = index_types
        
        # Calculate field coverage
        total_indices = len(indices)
        for field in all_fields:
            coverage = len(all_fields[field]) / total_indices if total_indices > 0 else 0
            compatibility["field_coverage"][field] = {
                "coverage_ratio": coverage,
                "present_in": list(all_fields[field].keys()),
                "missing_from": [idx for idx in indices if idx not in all_fields[field]]
            }
        
        # Convert sets to lists for JSON serialization
        compatibility["common_fields"] = list(compatibility["common_fields"])
        compatibility["index_specific_fields"] = {
            idx: list(fields) for idx, fields in compatibility["index_specific_fields"].items()
        }
        
        return compatibility
    
    def suggest_query_fields(self, index_name: str, query_intent: str = "") -> Dict:
        """Suggest appropriate fields for a query based on intent and index schema."""
        profile = self.get_index_profile(index_name)
        
        if "error" in profile:
            return {"error": profile["error"]}
        
        suggestions = {
            "recommended_fields": {},
            "query_patterns": {},
            "field_constraints": {}
        }
        
        fields = profile.get("fields", {})
        stats = profile.get("field_statistics", {})
        
        # Categorize fields by common query patterns
        query_categories = {
            "filtering": [],
            "time_range": [],
            "aggregation": [],
            "full_text": [],
            "exact_match": []
        }
        
        for field_name, field_info in fields.items():
            field_type = field_info["type"]
            
            if field_type == "date":
                query_categories["time_range"].append(field_name)
            elif field_type in ["keyword", "ip"]:
                query_categories["exact_match"].append(field_name)
                query_categories["filtering"].append(field_name)
            elif field_type == "text":
                query_categories["full_text"].append(field_name)
            elif field_type in ["long", "integer", "float", "double"]:
                query_categories["aggregation"].append(field_name)
                query_categories["filtering"].append(field_name)
        
        suggestions["query_patterns"] = query_categories
        
        # Add field constraints from statistics
        for field_name, field_stat in stats.items():
            if field_stat.get("type") == "numeric":
                suggestions["field_constraints"][field_name] = {
                    "type": "numeric",
                    "range": {"min": field_stat["min"], "max": field_stat["max"]},
                    "example_values": [field_stat["min"], field_stat["avg"], field_stat["max"]]
                }
            elif field_stat.get("type") == "categorical":
                top_terms = field_stat.get("top_terms", [])
                suggestions["field_constraints"][field_name] = {
                    "type": "categorical", 
                    "common_values": [term["value"] for term in top_terms[:5]],
                    "total_unique": field_stat.get("unique_terms", 0)
                }
        
        return suggestions
    
    def clear_cache(self, index_name: str = None):
        """Clear cache for specific index or all indices."""
        if index_name:
            cache_key = f"profile_{index_name}"
            if cache_key in self.profiles_cache:
                del self.profiles_cache[cache_key]
            
            cache_file = self.cache_dir / f"{index_name}_profile.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            self.profiles_cache.clear()
            for cache_file in self.cache_dir.glob("*_profile.json"):
                cache_file.unlink()
        
        logger.info(f"Cache cleared for {'all indices' if not index_name else index_name}")
#!/usr/bin/env python3
"""
Index Profiler: Advanced Elasticsearch index analysis and schema discovery

This module provides comprehensive index profiling capabilities for the ES-NL2DSL system,
enabling dynamic discovery of index schemas, field patterns, temporal characteristics,
and data distributions. It performs deep analysis of Elasticsearch indices to extract
metadata crucial for context-aware query generation and validation.

Key capabilities:
- Automatic schema discovery with field type detection and mapping analysis
- Temporal profiling to identify date ranges and timestamp fields
- Statistical analysis of field values including distributions and patterns
- Sample data extraction for context-aware prompt generation
- Field relationship detection and categorization
- Performance-optimized with caching and incremental updates
- Support for large-scale indices with millions of documents

The profiler serves as the foundation for dynamic query generation, enabling the system
to adapt to any Elasticsearch index structure without manual configuration.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re

# Add project root to path
import sys
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.config import get_es_client_config
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

@dataclass
class FieldProfile:
    """
    Comprehensive profile data for an individual Elasticsearch field.
    
    Captures detailed metadata about a field including its type, searchability,
    value distributions, patterns, and statistical characteristics. Used for
    understanding field semantics and generating appropriate query constraints.
    
    Attributes:
        name: Field name as it appears in the index
        type: Elasticsearch data type (text, keyword, date, integer, etc.)
        is_searchable: Whether field supports full-text search operations
        sample_values: Representative sample of actual field values
        common_values: Frequency distribution of most common values
        min_value: Minimum value for numeric/date fields
        max_value: Maximum value for numeric/date fields
        null_count: Number of documents with null/missing values
        total_count: Total number of documents analyzed
        patterns: Detected regex patterns for text fields
    """
    name: str
    type: str  # Elasticsearch field type
    is_searchable: bool
    sample_values: List[Any]
    common_values: Dict[str, int]  # value -> count
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    null_count: int = 0
    total_count: int = 0
    patterns: List[str] = None  # Regex patterns for text fields
    
    def __post_init__(self):
        if self.patterns is None:
            self.patterns = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FieldProfile':
        return cls(**data)

@dataclass 
class IndexProfile:
    """
    Complete analytical profile of an Elasticsearch index.
    
    Aggregates comprehensive metadata about an entire index including field
    profiles, temporal characteristics, data distributions, and structural
    information. Serves as the primary data structure for index intelligence.
    
    Attributes:
        index_name: Name of the profiled Elasticsearch index
        created_at: Timestamp when profile was generated
        document_count: Total number of documents in the index
        fields: Dictionary mapping field names to their FieldProfile objects
        date_range: Temporal bounds with min and max dates
        primary_timestamp_field: Main timestamp field for temporal queries
        field_categories: Categorized fields by type (temporal, ip, numeric, etc.)
        sample_size: Number of documents sampled for profiling
        
    Methods:
        to_dict: Serialize profile to dictionary for storage
        from_dict: Deserialize profile from stored dictionary
    """
    index_name: str
    created_at: float
    document_count: int
    fields: Dict[str, FieldProfile]
    date_range: Dict[str, str]  # {min_date, max_date}
    primary_timestamp_field: str
    suggested_field_mappings: Dict[str, str]  # common_name -> actual_field
    sample_documents: List[Dict[str, Any]]
    schema_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert FieldProfile objects to dicts
        data['fields'] = {k: v.to_dict() for k, v in self.fields.items()}
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndexProfile':
        # Convert field dicts back to FieldProfile objects
        fields = {k: FieldProfile.from_dict(v) for k, v in data['fields'].items()}
        data['fields'] = fields
        return cls(**data)

class IndexProfiler:
    """
    Intelligent index analysis and profiling system with caching.
    
    Provides comprehensive analysis of Elasticsearch indices to extract schema,
    field patterns, temporal characteristics, and data distributions. Implements
    intelligent caching to avoid redundant analysis and supports incremental
    updates for evolving indices.
    
    Features:
        - Automatic field type detection and mapping analysis
        - Temporal profiling with date range discovery
        - Statistical sampling for large indices
        - Pattern detection for text fields
        - Field categorization by semantic type
        - Performance optimization with result caching
        - Support for multiple Elasticsearch authentication methods
        
    Architecture:
        - Connects directly to Elasticsearch for real-time analysis
        - Caches profiles locally for offline operation
        - Supports incremental updates for changed indices
        - Handles authentication and connection management
        
    Usage:
        profiler = IndexProfiler()
        profile = profiler.analyze_index("logs_net")
        date_range = profile.date_range
        fields = profile.fields
    """
    
    def __init__(self, cache_dir: str = "artifacts/index_profiles"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.es = None
        
        # Common field name mappings for semantic understanding
        self.semantic_mappings = {
            # Timestamp fields
            "timestamp": ["@timestamp", "timestamp", "time", "datetime", "event_time", "log_time"],
            # IP address fields  
            "source_ip": ["src_ip", "source_ip", "src", "client_ip", "remote_addr"],
            "dest_ip": ["dst_ip", "dest_ip", "destination_ip", "target_ip", "server_ip"],
            # Port fields
            "source_port": ["src_port", "source_port", "client_port", "sport"],
            "dest_port": ["dst_port", "dest_port", "destination_port", "target_port", "dport"],
            # Protocol fields
            "protocol": ["protocol", "proto", "ip_protocol", "network_protocol"],
            # Label/classification fields
            "label": ["label", "classification", "threat_label", "attack_type", "category"],
            # Byte/size fields
            "bytes_in": ["bytes_in", "inbound_bytes", "rx_bytes", "received_bytes"],
            "bytes_out": ["bytes_out", "outbound_bytes", "tx_bytes", "sent_bytes", "bytes_transferred"],
        }
    
    def _get_es_client(self) -> Elasticsearch:
        """Get Elasticsearch client with proper configuration"""
        if self.es is None:
            self.es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=60)
        return self.es
    
    def get_cached_profile(self, index_name: str, max_age_hours: int = 24) -> Optional[IndexProfile]:
        """Retrieve cached profile if it exists and is recent enough"""
        cache_file = self.cache_dir / f"{index_name}_profile.json"
        
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            profile = IndexProfile.from_dict(data)
            
            # Check if cache is still valid
            age_hours = (time.time() - profile.created_at) / 3600
            if age_hours <= max_age_hours:
                logger.info(f"Using cached profile for {index_name} (age: {age_hours:.1f}h)")
                return profile
            else:
                logger.info(f"Cached profile for {index_name} is stale (age: {age_hours:.1f}h)")
                return None
                
        except Exception as e:
            logger.warning(f"Error reading cached profile for {index_name}: {e}")
            return None
    
    def cache_profile(self, profile: IndexProfile) -> bool:
        """Save profile to cache"""
        try:
            cache_file = self.cache_dir / f"{profile.index_name}_profile.json"
            with open(cache_file, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            
            logger.info(f"Cached profile for {profile.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error caching profile for {profile.index_name}: {e}")
            return False
    
    def analyze_index(self, index_name: str, sample_size: int = 1000, force_refresh: bool = False) -> IndexProfile:
        """Comprehensively analyze an index and create a profile"""
        
        # Check cache first unless forced refresh
        if not force_refresh:
            cached = self.get_cached_profile(index_name)
            if cached:
                return cached
        
        logger.info(f"Analyzing index: {index_name} (sample_size: {sample_size})")
        es = self._get_es_client()
        
        try:
            # Get index mapping
            mapping_response = es.indices.get_mapping(index=index_name)
            mapping = mapping_response[index_name]["mappings"]["properties"]
            
            # Get document count
            count_response = es.count(index=index_name)
            document_count = count_response["count"]
            
            # Sample documents for analysis
            sample_docs = self._sample_documents(es, index_name, sample_size)
            
            # Analyze fields
            fields = self._analyze_fields(mapping, sample_docs)
            
            # Detect primary timestamp field and date range
            timestamp_field, date_range = self._analyze_timestamps(fields, sample_docs)
            
            # Generate semantic field mappings
            suggested_mappings = self._generate_semantic_mappings(fields)
            
            # Create profile
            profile = IndexProfile(
                index_name=index_name,
                created_at=time.time(),
                document_count=document_count,
                fields=fields,
                date_range=date_range,
                primary_timestamp_field=timestamp_field,
                suggested_field_mappings=suggested_mappings,
                sample_documents=sample_docs[:10]  # Keep a small sample
            )
            
            # Cache the profile
            self.cache_profile(profile)
            
            logger.info(f"Successfully analyzed {index_name}: {len(fields)} fields, {document_count} docs, date range: {date_range.get('min_date', 'N/A')} to {date_range.get('max_date', 'N/A')}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Error analyzing index {index_name}: {e}")
            raise
    
    def _sample_documents(self, es: Elasticsearch, index_name: str, sample_size: int) -> List[Dict[str, Any]]:
        """Sample documents from the index for analysis"""
        try:
            # Use random sampling for better coverage
            query = {
                "query": {"function_score": {"random_score": {}}},
                "size": min(sample_size, 10000)  # ES limit
            }
            
            response = es.search(index=index_name, body=query)
            docs = [hit["_source"] for hit in response["hits"]["hits"]]
            
            logger.debug(f"Sampled {len(docs)} documents from {index_name}")
            return docs
            
        except Exception as e:
            logger.warning(f"Error sampling documents from {index_name}: {e}")
            # Fallback to simple search
            try:
                response = es.search(index=index_name, size=min(sample_size, 1000))
                return [hit["_source"] for hit in response["hits"]["hits"]]
            except Exception as e2:
                logger.error(f"Fallback sampling also failed for {index_name}: {e2}")
                return []
    
    def _analyze_fields(self, mapping: Dict[str, Any], sample_docs: List[Dict[str, Any]]) -> Dict[str, FieldProfile]:
        """Analyze all fields in the index"""
        fields = {}
        
        # Collect all field values from sample documents
        field_values = defaultdict(list)
        field_nulls = defaultdict(int)
        
        for doc in sample_docs:
            self._collect_field_values(doc, field_values, field_nulls)
        
        # Analyze each field
        for field_name, es_field_info in mapping.items():
            field_type = es_field_info.get("type", "unknown")
            # Most field types are searchable; only binary and some text types aren't
            is_searchable = field_type not in ["binary"]  # Text fields can still be searched with terms queries
            
            values = field_values.get(field_name, [])
            null_count = field_nulls.get(field_name, 0)
            
            # Analyze values
            sample_values = list(set(values[:50]))  # Unique sample
            common_values = dict(Counter(values).most_common(20))
            
            min_val, max_val = None, None
            if values:
                try:
                    if field_type in ["integer", "long", "float", "double"]:
                        numeric_values = [v for v in values if isinstance(v, (int, float))]
                        if numeric_values:
                            min_val, max_val = min(numeric_values), max(numeric_values)
                    elif field_type == "date":
                        date_values = [v for v in values if v]
                        if date_values:
                            min_val, max_val = min(date_values), max(date_values)
                except Exception as e:
                    logger.debug(f"Error computing min/max for {field_name}: {e}")
            
            # Detect patterns for text fields
            patterns = []
            if field_type in ["keyword", "text"] and values:
                patterns = self._detect_patterns(values)
            
            fields[field_name] = FieldProfile(
                name=field_name,
                type=field_type,
                is_searchable=is_searchable,
                sample_values=sample_values,
                common_values=common_values,
                min_value=min_val,
                max_value=max_val,
                null_count=null_count,
                total_count=len(values) + null_count,
                patterns=patterns
            )
        
        return fields
    
    def _collect_field_values(self, doc: Dict[str, Any], field_values: Dict[str, List], field_nulls: Dict[str, int], prefix: str = ""):
        """Recursively collect field values from a document"""
        for key, value in doc.items():
            field_name = f"{prefix}.{key}" if prefix else key
            
            if value is None:
                field_nulls[field_name] += 1
            elif isinstance(value, dict):
                # Nested object - recurse
                self._collect_field_values(value, field_values, field_nulls, field_name)
            elif isinstance(value, list):
                # Array field
                for item in value:
                    if item is not None:
                        field_values[field_name].append(item)
                    else:
                        field_nulls[field_name] += 1
            else:
                field_values[field_name].append(value)
    
    def _detect_patterns(self, values: List[str]) -> List[str]:
        """Detect common patterns in text values"""
        patterns = []
        
        # IP address pattern
        ip_count = sum(1 for v in values if re.match(r'\d+\.\d+\.\d+\.\d+', str(v)))
        if ip_count > len(values) * 0.8:
            patterns.append("ip_address")
        
        # Email pattern  
        email_count = sum(1 for v in values if re.match(r'[^@]+@[^@]+\.[^@]+', str(v)))
        if email_count > len(values) * 0.8:
            patterns.append("email")
        
        # URL pattern
        url_count = sum(1 for v in values if re.match(r'https?://', str(v)))
        if url_count > len(values) * 0.5:
            patterns.append("url")
        
        # Hash pattern (32 or 64 hex chars)
        hash_count = sum(1 for v in values if re.match(r'^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{64}$', str(v)))
        if hash_count > len(values) * 0.8:
            patterns.append("hash")
        
        return patterns
    
    def _analyze_timestamps(self, fields: Dict[str, FieldProfile], sample_docs: List[Dict[str, Any]]) -> Tuple[str, Dict[str, str]]:
        """Identify primary timestamp field and determine date range"""
        
        # Find timestamp fields
        timestamp_candidates = []
        for field_name, field_info in fields.items():
            if field_info.type == "date" or "timestamp" in field_name.lower() or "time" in field_name.lower():
                timestamp_candidates.append((field_name, field_info))
        
        if not timestamp_candidates:
            return "", {"min_date": "", "max_date": ""}
        
        # Choose primary timestamp (prefer @timestamp, then others)
        primary_field = "@timestamp"
        if primary_field not in fields:
            primary_field = timestamp_candidates[0][0]
        
        # Get date range - try from field profile first, then from sample docs
        date_range = {"min_date": "", "max_date": ""}
        if primary_field in fields:
            field_info = fields[primary_field]
            if field_info.min_value and field_info.max_value:
                date_range = {
                    "min_date": str(field_info.min_value),
                    "max_date": str(field_info.max_value)
                }
            else:
                # Try to extract dates from sample documents
                date_values = []
                for doc in sample_docs:
                    if primary_field in doc and doc[primary_field]:
                        date_values.append(doc[primary_field])
                
                if date_values:
                    try:
                        # Sort date strings
                        date_values.sort()
                        date_range = {
                            "min_date": str(date_values[0]),
                            "max_date": str(date_values[-1])
                        }
                    except Exception as e:
                        logger.debug(f"Error sorting timestamp values for {primary_field}: {e}")
        
        return primary_field, date_range
    
    def _generate_semantic_mappings(self, fields: Dict[str, FieldProfile]) -> Dict[str, str]:
        """Generate semantic field mappings based on field names and patterns"""
        mappings = {}
        
        available_fields = set(fields.keys())
        
        for semantic_name, possible_names in self.semantic_mappings.items():
            # Find the best match
            for candidate in possible_names:
                if candidate in available_fields:
                    mappings[semantic_name] = candidate
                    break
            else:
                # Try partial matching
                for field_name in available_fields:
                    for candidate in possible_names:
                        if candidate.lower() in field_name.lower():
                            mappings[semantic_name] = field_name
                            break
                    if semantic_name in mappings:
                        break
        
        return mappings
    
    def get_field_catalog_for_index(self, index_name: str) -> Dict[str, Dict[str, str]]:
        """Generate a field catalog suitable for query generation"""
        profile = self.analyze_index(index_name)
        
        catalog = {}
        for field_name, field_info in profile.fields.items():
            if field_info.is_searchable and field_info.total_count > 0:
                # Create description based on patterns and common values
                description = f"{field_info.type.title()} field"
                
                if field_info.patterns:
                    description += f" ({', '.join(field_info.patterns)})"
                elif field_info.common_values:
                    common_vals = list(field_info.common_values.keys())[:3]
                    description += f" (common: {', '.join(str(v) for v in common_vals)})"
                
                catalog[field_name] = {
                    "type": field_info.type,
                    "description": description
                }
        
        return catalog
    
    def get_dynamic_date_range(self, index_name: str, default_days: int = 7) -> Dict[str, str]:
        """Get intelligent date range for queries based on actual data"""
        profile = self.analyze_index(index_name)
        
        if profile.date_range["min_date"] and profile.date_range["max_date"]:
            # Use actual data range
            return profile.date_range
        else:
            # Fallback to recent range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=default_days)
            return {
                "min_date": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                "max_date": end_date.strftime("%Y-%m-%dT%H:%M:%S")
            }
    
    def list_available_indices(self) -> List[str]:
        """List all available indices for profiling"""
        try:
            es = self._get_es_client()
            response = es.cat.indices(format="json")
            return [idx["index"] for idx in response if not idx["index"].startswith(".")]
        except Exception as e:
            logger.warning(f"Cannot list indices with reader permissions: {e}")
            # Fallback to known indices from config or common patterns
            fallback_indices = [
                "logs_net", "logs_cic_ids2017", "logs_cybersecurity-threat-detection-logs",
                "logs_net_drift", "logs_net_dp_eps05", "logs_net_dp_eps10", "logs_net_dp_eps20"
            ]
            # Filter to only those that actually exist
            available = []
            for idx in fallback_indices:
                try:
                    es.indices.get(index=idx)
                    available.append(idx)
                except:
                    pass
            return available
    
    def refresh_all_profiles(self, indices: List[str] = None) -> Dict[str, bool]:
        """Refresh profiles for multiple indices"""
        if indices is None:
            indices = self.list_available_indices()
        
        results = {}
        for index_name in indices:
            try:
                self.analyze_index(index_name, force_refresh=True)
                results[index_name] = True
                logger.info(f"✅ Refreshed profile for {index_name}")
            except Exception as e:
                logger.error(f"❌ Failed to refresh profile for {index_name}: {e}")
                results[index_name] = False
        
        return results

# Convenience functions for external use
def get_index_profile(index_name: str, force_refresh: bool = False) -> IndexProfile:
    """Get profile for a specific index"""
    profiler = IndexProfiler()
    return profiler.analyze_index(index_name, force_refresh=force_refresh)

def get_field_catalog_for_index(index_name: str) -> Dict[str, Dict[str, str]]:
    """Get field catalog for query generation"""
    profiler = IndexProfiler()
    return profiler.get_field_catalog_for_index(index_name)

def get_dynamic_date_range(index_name: str) -> Dict[str, str]:
    """Get appropriate date range for queries"""
    profiler = IndexProfiler()
    return profiler.get_dynamic_date_range(index_name)

def refresh_index_profiles(indices: List[str] = None) -> Dict[str, bool]:
    """Refresh profiles for multiple indices"""
    profiler = IndexProfiler()
    return profiler.refresh_all_profiles(indices)

if __name__ == "__main__":
    # CLI interface for testing
    import argparse
    
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Analyze Elasticsearch indices")
    parser.add_argument("--index", help="Index name to analyze")
    parser.add_argument("--refresh", action="store_true", help="Force refresh of cached profiles")
    parser.add_argument("--list", action="store_true", help="List available indices")
    parser.add_argument("--all", action="store_true", help="Analyze all indices")
    
    args = parser.parse_args()
    
    profiler = IndexProfiler()
    
    if args.list:
        indices = profiler.list_available_indices()
        print(f"Available indices: {', '.join(indices)}")
    elif args.all:
        indices = profiler.list_available_indices()
        results = profiler.refresh_all_profiles(indices)
        for idx, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {idx}")
    elif args.index:
        profile = profiler.analyze_index(args.index, force_refresh=args.refresh)
        print(f"Profile for {args.index}:")
        print(f"  Documents: {profile.document_count}")
        print(f"  Fields: {len(profile.fields)}")
        print(f"  Date range: {profile.date_range}")
        print(f"  Primary timestamp: {profile.primary_timestamp_field}")
        print(f"  Suggested mappings: {profile.suggested_field_mappings}")
    else:
        parser.print_help()

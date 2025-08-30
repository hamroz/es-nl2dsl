#!/usr/bin/env python3
"""
Dynamic Index Analyzer for Elasticsearch
Discovers and analyzes fields in any ES index for better query generation
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from elasticsearch import Elasticsearch
from src.utils.config import get_es_client_config, ES_READER_CREDS

logger = logging.getLogger(__name__)

class IndexAnalyzer:
    """Analyzes Elasticsearch indices to discover fields and their characteristics"""
    
    def __init__(self, cache_duration_minutes: int = 60):
        """Initialize analyzer with caching support"""
        self.es = None
        self.cache = {}
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self._connect()
    
    def _connect(self):
        """Establish Elasticsearch connection"""
        try:
            self.es = Elasticsearch(
                **get_es_client_config(use_admin=False),
                request_timeout=30
            )
            if not self.es.ping():
                logger.error("Failed to connect to Elasticsearch")
        except Exception as e:
            logger.error(f"Error connecting to Elasticsearch: {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache:
            return False
        
        cached_time = self.cache[cache_key].get('_cached_at')
        if not cached_time:
            return False
        
        return datetime.now() - cached_time < self.cache_duration
    
    def get_index_fields(self, index_name: str, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get all fields from an index with their types and properties
        
        Returns:
            Dictionary mapping field names to their properties
        """
        cache_key = f"fields_{index_name}"
        
        # Check cache first
        if not force_refresh and self._is_cache_valid(cache_key):
            logger.debug(f"Using cached fields for index {index_name}")
            return self.cache[cache_key]['data']
        
        try:
            # Get mapping from Elasticsearch
            mapping = self.es.indices.get_mapping(index=index_name)
            
            # Extract properties based on ES version structure
            if index_name in mapping:
                properties = mapping[index_name].get('mappings', {}).get('properties', {})
            else:
                # Handle different ES response formats
                first_key = list(mapping.keys())[0]
                properties = mapping[first_key].get('mappings', {}).get('properties', {})
            
            # Build field catalog with detailed info
            field_catalog = {}
            
            def extract_fields(props: Dict, prefix: str = ""):
                """Recursively extract fields from nested mappings"""
                for field_name, field_def in props.items():
                    full_field_name = f"{prefix}{field_name}" if prefix else field_name
                    
                    # Get field type
                    field_type = field_def.get('type', 'object')
                    
                    # Handle nested objects
                    if field_type == 'object' or 'properties' in field_def:
                        if 'properties' in field_def:
                            extract_fields(field_def['properties'], f"{full_field_name}.")
                        field_type = 'object'
                    
                    # Add field to catalog
                    field_catalog[full_field_name] = {
                        'type': field_type,
                        'description': self._generate_field_description(full_field_name, field_type),
                        'format': field_def.get('format'),
                        'analyzer': field_def.get('analyzer'),
                        'fields': field_def.get('fields', {}),  # Multi-fields
                        'is_aggregatable': field_type in ['keyword', 'integer', 'long', 'float', 'double', 'date', 'boolean'],
                        'is_searchable': field_type != 'object',
                        'is_sortable': field_type != 'text'
                    }
                    
                    # Add .keyword multi-field if it exists
                    if 'fields' in field_def and 'keyword' in field_def['fields']:
                        keyword_field = f"{full_field_name}.keyword"
                        field_catalog[keyword_field] = {
                            'type': 'keyword',
                            'description': f"Keyword version of {full_field_name}",
                            'is_aggregatable': True,
                            'is_searchable': True,
                            'is_sortable': True
                        }
            
            extract_fields(properties)
            
            # Cache the results
            self.cache[cache_key] = {
                'data': field_catalog,
                '_cached_at': datetime.now()
            }
            
            logger.info(f"Discovered {len(field_catalog)} fields in index {index_name}")
            return field_catalog
            
        except Exception as e:
            logger.error(f"Error getting fields for index {index_name}: {e}")
            return {}
    
    def _generate_field_description(self, field_name: str, field_type: str) -> str:
        """Generate human-readable description based on field name and type"""
        # Common field patterns and their descriptions
        descriptions = {
            # Network fields
            'src_ip': 'Source IP address',
            'source_ip': 'Source IP address',
            'dst_ip': 'Destination IP address',
            'destination_ip': 'Destination IP address',
            'src_port': 'Source port number',
            'dst_port': 'Destination port number',
            
            # Time fields
            '@timestamp': 'Event timestamp',
            'timestamp': 'Event timestamp',
            'created_at': 'Creation timestamp',
            'updated_at': 'Update timestamp',
            
            # Log fields
            'log_type': 'Type of log entry',
            'log.type': 'Type of log entry',
            'event_type': 'Type of event',
            'event.type': 'Type of event',
            'message': 'Log message content',
            
            # Security fields
            'firewall_action': 'Firewall action taken',
            'action': 'Action taken',
            'status': 'Status of the event',
            'severity': 'Severity level',
            'alert': 'Alert information',
            
            # User fields
            'user': 'Username',
            'user.name': 'Username',
            'user.id': 'User identifier',
            
            # Common fields
            'host': 'Host information',
            'hostname': 'Hostname',
            'protocol': 'Network protocol',
            'bytes': 'Number of bytes',
            'packets': 'Number of packets',
            'duration': 'Duration in milliseconds',
        }
        
        # Check for exact match
        if field_name in descriptions:
            return descriptions[field_name]
        
        # Check for patterns
        if 'ip' in field_name.lower():
            return f"IP address field ({field_name})"
        elif 'port' in field_name.lower():
            return f"Port number field ({field_name})"
        elif 'time' in field_name.lower() or 'date' in field_name.lower():
            return f"Timestamp field ({field_name})"
        elif 'bytes' in field_name.lower():
            return f"Byte count field ({field_name})"
        elif 'count' in field_name.lower():
            return f"Count field ({field_name})"
        elif field_type == 'keyword':
            return f"Categorical field ({field_name})"
        elif field_type in ['integer', 'long', 'float', 'double']:
            return f"Numeric field ({field_name})"
        elif field_type == 'boolean':
            return f"Boolean field ({field_name})"
        else:
            return f"Field {field_name} of type {field_type}"
    
    def get_field_statistics(self, index_name: str, field_name: str, max_samples: int = 10) -> Dict[str, Any]:
        """
        Get statistics and sample values for a specific field
        
        Returns:
            Dictionary with field statistics and samples
        """
        cache_key = f"stats_{index_name}_{field_name}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            stats = {
                'field': field_name,
                'samples': [],
                'cardinality': 0,
                'doc_count': 0
            }
            
            # Get field type first
            fields = self.get_index_fields(index_name)
            field_info = fields.get(field_name, {})
            field_type = field_info.get('type', 'keyword')
            
            # Get document count
            count_result = self.es.count(index=index_name)
            stats['doc_count'] = count_result['count']
            
            # Get cardinality for aggregatable fields
            if field_info.get('is_aggregatable', False):
                agg_query = {
                    'size': 0,
                    'aggs': {
                        'unique_values': {
                            'cardinality': {
                                'field': field_name
                            }
                        }
                    }
                }
                
                result = self.es.search(index=index_name, body=agg_query)
                stats['cardinality'] = result['aggregations']['unique_values']['value']
                
                # Get top values for keyword fields
                if field_type == 'keyword' or field_name.endswith('.keyword'):
                    terms_query = {
                        'size': 0,
                        'aggs': {
                            'top_values': {
                                'terms': {
                                    'field': field_name,
                                    'size': max_samples
                                }
                            }
                        }
                    }
                    
                    result = self.es.search(index=index_name, body=terms_query)
                    buckets = result['aggregations']['top_values']['buckets']
                    stats['samples'] = [b['key'] for b in buckets]
                    stats['sample_counts'] = {b['key']: b['doc_count'] for b in buckets}
            
            # Get range for numeric/date fields
            if field_type in ['integer', 'long', 'float', 'double', 'date']:
                range_query = {
                    'size': 0,
                    'aggs': {
                        'field_stats': {
                            'stats': {
                                'field': field_name
                            }
                        }
                    }
                }
                
                result = self.es.search(index=index_name, body=range_query)
                stats['range'] = result['aggregations']['field_stats']
            
            # Cache results
            self.cache[cache_key] = {
                'data': stats,
                '_cached_at': datetime.now()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics for field {field_name}: {e}")
            return {'field': field_name, 'error': str(e)}
    
    def build_field_catalog(self, index_name: str) -> Dict[str, Any]:
        """
        Build comprehensive field catalog for query generation
        
        Returns:
            Complete field information including types, descriptions, and samples
        """
        cache_key = f"catalog_{index_name}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]['data']
        
        try:
            # Get all fields
            fields = self.get_index_fields(index_name)
            
            if not fields:
                logger.warning(f"No fields found for index {index_name}")
                return {}
            
            # Build catalog with enhanced information
            catalog = {
                'index_name': index_name,
                'field_count': len(fields),
                'fields': fields,
                'timestamp_fields': [],
                'keyword_fields': [],
                'numeric_fields': [],
                'text_fields': [],
                'boolean_fields': [],
                'common_patterns': {}
            }
            
            # Categorize fields by type
            for field_name, field_info in fields.items():
                field_type = field_info['type']
                
                if field_type == 'date':
                    catalog['timestamp_fields'].append(field_name)
                elif field_type == 'keyword':
                    catalog['keyword_fields'].append(field_name)
                elif field_type in ['integer', 'long', 'float', 'double']:
                    catalog['numeric_fields'].append(field_name)
                elif field_type == 'text':
                    catalog['text_fields'].append(field_name)
                elif field_type == 'boolean':
                    catalog['boolean_fields'].append(field_name)
            
            # Identify common patterns
            catalog['common_patterns'] = self._identify_field_patterns(fields)
            
            # Identify primary timestamp field
            if catalog['timestamp_fields']:
                # Prefer @timestamp, then timestamp, then first date field
                if '@timestamp' in catalog['timestamp_fields']:
                    catalog['primary_timestamp'] = '@timestamp'
                elif 'timestamp' in catalog['timestamp_fields']:
                    catalog['primary_timestamp'] = 'timestamp'
                else:
                    catalog['primary_timestamp'] = catalog['timestamp_fields'][0]
            
            # Cache the catalog
            self.cache[cache_key] = {
                'data': catalog,
                '_cached_at': datetime.now()
            }
            
            logger.info(f"Built field catalog for {index_name}: {catalog['field_count']} fields")
            return catalog
            
        except Exception as e:
            logger.error(f"Error building catalog for index {index_name}: {e}")
            return {}
    
    def _identify_field_patterns(self, fields: Dict[str, Dict]) -> Dict[str, List[str]]:
        """Identify common field patterns for better query generation"""
        patterns = {
            'ip_fields': [],
            'port_fields': [],
            'user_fields': [],
            'host_fields': [],
            'log_type_fields': [],
            'action_fields': [],
            'status_fields': [],
            'bytes_fields': [],
            'packet_fields': []
        }
        
        for field_name in fields.keys():
            field_lower = field_name.lower()
            
            # IP address fields
            if 'ip' in field_lower or 'address' in field_lower:
                patterns['ip_fields'].append(field_name)
            
            # Port fields
            if 'port' in field_lower:
                patterns['port_fields'].append(field_name)
            
            # User fields
            if 'user' in field_lower or 'username' in field_lower:
                patterns['user_fields'].append(field_name)
            
            # Host fields
            if 'host' in field_lower or 'hostname' in field_lower:
                patterns['host_fields'].append(field_name)
            
            # Log type fields
            if 'type' in field_lower or 'category' in field_lower:
                patterns['log_type_fields'].append(field_name)
            
            # Action fields
            if 'action' in field_lower or 'operation' in field_lower:
                patterns['action_fields'].append(field_name)
            
            # Status fields
            if 'status' in field_lower or 'state' in field_lower:
                patterns['status_fields'].append(field_name)
            
            # Bytes fields
            if 'bytes' in field_lower or 'size' in field_lower:
                patterns['bytes_fields'].append(field_name)
            
            # Packet fields
            if 'packet' in field_lower:
                patterns['packet_fields'].append(field_name)
        
        # Remove empty patterns
        return {k: v for k, v in patterns.items() if v}
    
    def clear_cache(self, index_name: Optional[str] = None):
        """Clear cache for specific index or all indices"""
        if index_name:
            # Clear cache for specific index
            keys_to_remove = [k for k in self.cache.keys() if index_name in k]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Cleared cache for index {index_name}")
        else:
            # Clear all cache
            self.cache.clear()
            logger.info("Cleared all cache")
    
    def get_sample_query_fields(self, index_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get the most important fields for query generation
        Used when including all fields would be too many
        """
        catalog = self.build_field_catalog(index_name)
        fields = catalog.get('fields', {})
        
        # Priority fields that should always be included
        priority_patterns = [
            'timestamp', 'ip', 'port', 'user', 'host', 'type', 'action', 
            'status', 'message', 'level', 'severity', 'protocol'
        ]
        
        important_fields = []
        
        # First add fields matching priority patterns
        for field_name, field_info in fields.items():
            if len(important_fields) >= limit:
                break
            
            field_lower = field_name.lower()
            for pattern in priority_patterns:
                if pattern in field_lower:
                    important_fields.append({
                        'name': field_name,
                        'type': field_info['type'],
                        'description': field_info['description']
                    })
                    break
        
        # Fill remaining slots with other aggregatable fields
        if len(important_fields) < limit:
            for field_name, field_info in fields.items():
                if len(important_fields) >= limit:
                    break
                
                if field_info.get('is_aggregatable') and not any(f['name'] == field_name for f in important_fields):
                    important_fields.append({
                        'name': field_name,
                        'type': field_info['type'],
                        'description': field_info['description']
                    })
        
        return important_fields


# Singleton instance
_analyzer_instance = None

def get_index_analyzer() -> IndexAnalyzer:
    """Get or create singleton IndexAnalyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = IndexAnalyzer()
    return _analyzer_instance


# Convenience functions for backward compatibility
def get_index_fields(index_name: str) -> Dict[str, Dict[str, Any]]:
    """Get all fields from an index"""
    analyzer = get_index_analyzer()
    return analyzer.get_index_fields(index_name)

def build_field_catalog(index_name: str) -> Dict[str, Any]:
    """Build comprehensive field catalog"""
    analyzer = get_index_analyzer()
    return analyzer.build_field_catalog(index_name)

def get_sample_query_fields(index_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get most important fields for query generation"""
    analyzer = get_index_analyzer()
    return analyzer.get_sample_query_fields(index_name, limit)
#!/usr/bin/env python3
"""
Mapping Storage: Intelligent field mapping management for dynamic data adaptation

This module provides persistent storage and retrieval of field mappings for dynamically
adapted indices in the ES-NL2DSL system. It manages the relationship between semantic
field names and actual index fields, enabling the system to adapt to new data sources
without manual configuration.

Key capabilities:
- Persistent storage of index field mappings and metadata
- Dynamic date range calculation from actual index data
- Field catalog generation with type and searchability information
- Semantic mapping between logical and physical field names
- Integration with index profiling for real-time schema discovery
- Caching mechanism for performance optimization
- Support for multiple index types and schemas

The storage system maintains a unified interface for accessing field information
across different data sources, enabling consistent query generation regardless
of the underlying index structure.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

# Add project root to path for imports
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

logger = logging.getLogger(__name__)

class MappingStorage:
    """
    Intelligent storage system for index field mappings and metadata.
    
    Manages persistent storage of field mappings discovered through dynamic
    adaptation, providing a unified interface for accessing index structure
    information across the ES-NL2DSL system.
    
    Features:
        - Persistent JSON storage of mapping information
        - Lazy loading of index profiler to avoid circular imports
        - Dynamic field catalog generation from stored mappings
        - Real-time date range calculation from index data
        - Semantic field mapping for query generation
        - Fallback mechanisms for missing or corrupted data
        
    Architecture:
        - File-based storage in artifacts/mappings directory
        - Integration with IndexProfiler for live data analysis
        - Caching for frequently accessed mappings
        - Automatic schema evolution handling
    """
    
    def __init__(self, storage_path: str = "artifacts/mappings"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self._profiler = None
    
    @property 
    def profiler(self):
        """Lazy load the index profiler to avoid circular imports"""
        if self._profiler is None:
            try:
                from src.index_profiler import IndexProfiler
                self._profiler = IndexProfiler()
            except ImportError as e:
                logger.warning(f"Could not import IndexProfiler: {e}")
                self._profiler = None
        return self._profiler
    
    def store_index_mapping(self, index_name: str, mapping_info: Dict[str, Any]) -> bool:
        """Store mapping information for an index"""
        try:
            mapping_file = self.storage_path / f"{index_name}_mapping.json"
            
            mapping_data = {
                "index_name": index_name,
                "created_at": None,  # Will be set by json serializer
                "schema": mapping_info.get("schema", {}),
                "field_patterns": mapping_info.get("field_patterns", {}),
                "ai_analysis": mapping_info.get("ai_analysis", {}),
                "elasticsearch_mapping": mapping_info.get("elasticsearch_mapping", {}),
                "common_fields": self._extract_common_fields(mapping_info)
            }
            
            # Add timestamp
            import time
            mapping_data["created_at"] = time.time()
            
            with open(mapping_file, 'w') as f:
                json.dump(mapping_data, f, indent=2)
            
            logger.info(f"Stored mapping for index {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing mapping for {index_name}: {e}")
            return False
    
    def get_index_mapping(self, index_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve mapping information for an index"""
        try:
            mapping_file = self.storage_path / f"{index_name}_mapping.json"
            
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    return json.load(f)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving mapping for {index_name}: {e}")
            return None
    
    def list_adapted_indices(self) -> List[str]:
        """List all indices that have been adapted"""
        try:
            indices = []
            for mapping_file in self.storage_path.glob("*_mapping.json"):
                index_name = mapping_file.stem.replace("_mapping", "")
                indices.append(index_name)
            return sorted(indices)
            
        except Exception as e:
            logger.error(f"Error listing adapted indices: {e}")
            return []
    
    def get_field_mapping_for_query_generation(self, index_name: str) -> Dict[str, Any]:
        """Get field mapping specifically formatted for query generation"""
        # First try to get from stored mapping (for manually adapted data)
        mapping = self.get_index_mapping(index_name)
        if mapping:
            # Extract the most important information for query generation
            return {
                "index_name": index_name,
                "timestamp_fields": mapping.get("field_patterns", {}).get("timestamp_fields", []),
                "ip_fields": mapping.get("field_patterns", {}).get("ip_fields", []),
                "user_fields": mapping.get("field_patterns", {}).get("user_fields", []),
                "status_fields": mapping.get("field_patterns", {}).get("status_fields", []),
                "message_fields": mapping.get("field_patterns", {}).get("message_fields", []),
                "all_fields": list(mapping.get("schema", {}).get("fields", {}).keys()),
                "system_type": mapping.get("ai_analysis", {}).get("analysis", {}).get("system_type", "Unknown"),
                "important_fields": mapping.get("ai_analysis", {}).get("analysis", {}).get("important_fields", [])
            }
        
        # If no stored mapping, try to get from index profiler (for any index)
        if self.profiler:
            try:
                profile = self.profiler.analyze_index(index_name)
                return self._convert_profile_to_mapping(profile)
            except Exception as e:
                logger.debug(f"Could not get profile for {index_name}: {e}")
        
        return {}
    
    def _convert_profile_to_mapping(self, profile) -> Dict[str, Any]:
        """Convert an IndexProfile to the mapping format expected by query generation"""
        from src.index_profiler import IndexProfile
        
        # Group fields by type and patterns
        timestamp_fields = []
        ip_fields = []
        user_fields = []
        status_fields = []
        message_fields = []
        
        for field_name, field_info in profile.fields.items():
            if field_info.type == "date" or "timestamp" in field_name.lower():
                timestamp_fields.append(field_name)
            elif "ip_address" in field_info.patterns:
                ip_fields.append(field_name)
            elif any(keyword in field_name.lower() for keyword in ["user", "username", "uid"]):
                user_fields.append(field_name)
            elif any(keyword in field_name.lower() for keyword in ["status", "result", "action", "label"]):
                status_fields.append(field_name)
            elif field_info.type == "text" and any(keyword in field_name.lower() for keyword in ["message", "description", "log"]):
                message_fields.append(field_name)
        
        return {
            "index_name": profile.index_name,
            "timestamp_fields": timestamp_fields,
            "ip_fields": ip_fields,
            "user_fields": user_fields,
            "status_fields": status_fields,
            "message_fields": message_fields,
            "all_fields": list(profile.fields.keys()),
            "system_type": "Auto-detected",
            "important_fields": [f for f in profile.fields.keys() if profile.fields[f].is_searchable],
            "date_range": profile.date_range,
            "semantic_mappings": profile.suggested_field_mappings,
            "primary_timestamp": profile.primary_timestamp_field
        }
    
    def _extract_common_fields(self, mapping_info: Dict[str, Any]) -> Dict[str, str]:
        """Extract common field mappings for standard log patterns"""
        field_patterns = mapping_info.get("field_patterns", {})
        common_fields = {}
        
        # Map to standard field names
        if "timestamp_fields" in field_patterns and field_patterns["timestamp_fields"]:
            common_fields["@timestamp"] = field_patterns["timestamp_fields"][0]
        
        if "ip_fields" in field_patterns and field_patterns["ip_fields"]:
            common_fields["source_ip"] = field_patterns["ip_fields"][0]
        
        if "user_fields" in field_patterns and field_patterns["user_fields"]:
            common_fields["user"] = field_patterns["user_fields"][0]
        
        if "status_fields" in field_patterns and field_patterns["status_fields"]:
            common_fields["status"] = field_patterns["status_fields"][0]
        
        if "message_fields" in field_patterns and field_patterns["message_fields"]:
            common_fields["message"] = field_patterns["message_fields"][0]
        
        return common_fields
    

    
    def delete_index_mapping(self, index_name: str) -> bool:
        """Delete mapping information for an index"""
        try:
            mapping_file = self.storage_path / f"{index_name}_mapping.json"
            if mapping_file.exists():
                mapping_file.unlink()
                logger.info(f"Deleted mapping for index {index_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting mapping for {index_name}: {e}")
            return False
    
    def get_field_catalog_for_index(self, index_name: str) -> Dict[str, Dict[str, str]]:
        """Get field catalog suitable for query generation (unified interface)"""
        # Try profiler first for most up-to-date information
        if self.profiler:
            try:
                return self.profiler.get_field_catalog_for_index(index_name)
            except Exception as e:
                logger.debug(f"Could not get field catalog from profiler for {index_name}: {e}")
        
        # Fallback to stored mapping if available
        mapping = self.get_field_mapping_for_query_generation(index_name)
        if mapping and mapping.get("all_fields"):
            catalog = {}
            for field_name in mapping["all_fields"]:
                # Create basic catalog entry
                catalog[field_name] = {
                    "type": "keyword",  # Default type
                    "description": f"Field from {mapping.get('system_type', 'unknown')} system"
                }
            return catalog
        
        return {}
    
    def get_dynamic_date_range(self, index_name: str) -> Dict[str, str]:
        """Get appropriate date range for queries (unified interface)"""
        if self.profiler:
            try:
                return self.profiler.get_dynamic_date_range(index_name)
            except Exception as e:
                logger.debug(f"Could not get date range from profiler for {index_name}: {e}")
        
        # Fallback to stored mapping
        mapping = self.get_field_mapping_for_query_generation(index_name)
        if mapping and mapping.get("date_range"):
            return mapping["date_range"]
        
        # Dynamic fallback based on current time (no hardcoded dates!)
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # Last 7 days as reasonable default
        return {
            "min_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "max_date": end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    
    def has_index_profile(self, index_name: str) -> bool:
        """Check if we have any profile/mapping information for an index"""
        # Check stored mapping
        if self.get_index_mapping(index_name):
            return True
        
        # Check if profiler can analyze it
        if self.profiler:
            try:
                self.profiler.analyze_index(index_name)
                return True
            except Exception:
                pass
        
        return False
    
    def refresh_index_profile(self, index_name: str) -> bool:
        """Force refresh of index profile"""
        if self.profiler:
            try:
                self.profiler.analyze_index(index_name, force_refresh=True)
                logger.info(f"Refreshed profile for {index_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to refresh profile for {index_name}: {e}")
        return False


# Convenience functions for external use
def get_unified_field_mapping(index_name: str) -> Dict[str, Any]:
    """Get field mapping with automatic fallback to profiler"""
    storage = MappingStorage()
    return storage.get_field_mapping_for_query_generation(index_name)

def get_unified_field_catalog(index_name: str) -> Dict[str, Dict[str, str]]:
    """Get field catalog with automatic fallback to profiler"""
    storage = MappingStorage()
    return storage.get_field_catalog_for_index(index_name)

def get_unified_date_range(index_name: str) -> Dict[str, str]:
    """Get date range with automatic fallback to profiler"""
    storage = MappingStorage()
    return storage.get_dynamic_date_range(index_name)

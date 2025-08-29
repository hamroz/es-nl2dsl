#!/usr/bin/env python3
"""Field mapping storage for newly adapted data"""
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MappingStorage:
    """Store and retrieve field mappings for adapted data indices"""
    
    def __init__(self, storage_path: str = "artifacts/mappings"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
    
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
                "common_fields": self._extract_common_fields(mapping_info),
                "query_suggestions": mapping_info.get("query_suggestions", [])
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
        mapping = self.get_index_mapping(index_name)
        if not mapping:
            return {}
        
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
    
    def update_query_suggestions(self, index_name: str, suggestions: List[Dict[str, Any]]) -> bool:
        """Update query suggestions for an index"""
        mapping = self.get_index_mapping(index_name)
        if mapping:
            mapping["query_suggestions"] = suggestions
            return self.store_index_mapping(index_name, mapping)
        return False
    
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

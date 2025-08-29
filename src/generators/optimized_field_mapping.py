#!/usr/bin/env python3
"""
Optimized field mapping with caching to reduce O(n²) complexity.
Caches field corrections and mappings for better performance.
"""

import json
import time
import logging
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class FieldMappingCache:
    """Cache entry for field mappings"""
    mapping: Dict[str, Any]
    timestamp: float
    query_hash: str

class OptimizedFieldMapper:
    """Optimized field mapping with intelligent caching"""
    
    def __init__(self, cache_ttl: int = 3600):  # 1 hour TTL
        self.cache_ttl = cache_ttl
        self.mapping_cache: Dict[str, FieldMappingCache] = {}
        self.field_corrections_cache: Dict[str, str] = {}
        self.index_info_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load standard field corrections
        self.field_corrections = {
            "src_ip": "source_ip",
            "dst_ip": "dest_ip", 
            "src_port": "source_port",
            "dst_port": "dest_port",
            "timestamp": "@timestamp",
            "time": "@timestamp",
            "datetime": "@timestamp",
            "source": "source_ip",
            "destination": "dest_ip",
            "target": "dest_ip",
            "client_ip": "source_ip",
            "server_ip": "dest_ip",
            "sport": "source_port",
            "dport": "dest_port",
            "proto": "protocol",
            "bytes": "bytes_in",
            "size": "bytes_in",
        }
        
        # Performance tracking
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "field_corrections_applied": 0,
            "processing_time_ms": 0
        }
    
    def get_dynamic_index_info(self, index: Optional[str]) -> Dict[str, Any]:
        """Get cached dynamic index information"""
        if not index:
            return {}
        
        # Check cache first
        if index in self.index_info_cache:
            cached_info = self.index_info_cache[index]
            if time.time() - cached_info.get("timestamp", 0) < self.cache_ttl:
                return cached_info
        
        # Generate new info (this would call the actual profiler)
        try:
            from ..data_adaptation.mapping_storage import get_dynamic_index_info
            info = get_dynamic_index_info(index)
            
            # Cache the result
            info["timestamp"] = time.time()
            self.index_info_cache[index] = info
            
            return info
        except Exception as e:
            logger.debug(f"Could not get dynamic index info for {index}: {e}")
            return {}
    
    def _generate_query_hash(self, query_json: Any) -> str:
        """Generate a hash for query structure to enable caching"""
        try:
            # Create a canonical representation for hashing
            canonical = json.dumps(query_json, sort_keys=True, separators=(',', ':'))
            return hashlib.md5(canonical.encode()).hexdigest()
        except Exception:
            # Fallback for non-serializable objects
            return str(hash(str(query_json)))
    
    def correct_field_mappings_optimized(self, query_json: Any, index: Optional[str] = None) -> Any:
        """Optimized field mapping with caching and reduced complexity"""
        start_time = time.time()
        
        # Generate hash for caching
        query_hash = self._generate_query_hash(query_json)
        cache_key = f"{index}:{query_hash}"
        
        # Check cache first
        if cache_key in self.mapping_cache:
            cached_entry = self.mapping_cache[cache_key]
            if time.time() - cached_entry.timestamp < self.cache_ttl:
                self.stats["cache_hits"] += 1
                processing_time = (time.time() - start_time) * 1000
                self.stats["processing_time_ms"] += processing_time
                logger.debug(f"✅ Field mapping cache hit for {index} ({processing_time:.1f}ms)")
                return cached_entry.mapping
        
        self.stats["cache_misses"] += 1
        
        # Get dynamic index info once
        dynamic_info = self.get_dynamic_index_info(index)
        available_fields = set()
        if dynamic_info and dynamic_info.get("field_catalog"):
            available_fields = set(dynamic_info["field_catalog"].keys())
        
        # Process the query with optimized algorithm
        corrected_query = self._process_query_optimized(query_json, available_fields, index)
        
        # Cache the result
        cache_entry = FieldMappingCache(
            mapping=corrected_query,
            timestamp=time.time(),
            query_hash=query_hash
        )
        self.mapping_cache[cache_key] = cache_entry
        
        processing_time = (time.time() - start_time) * 1000
        self.stats["processing_time_ms"] += processing_time
        logger.debug(f"🔄 Field mapping processed for {index} ({processing_time:.1f}ms)")
        
        return corrected_query
    
    def _process_query_optimized(self, query_json: Any, available_fields: Set[str], index: Optional[str]) -> Any:
        """Process query with optimized field mapping algorithm"""
        
        # Track fields that need correction in a single pass
        fields_to_correct = {}
        
        # First pass: identify all field names that need correction
        self._collect_field_corrections(query_json, available_fields, fields_to_correct)
        
        # Second pass: apply corrections in bulk
        if fields_to_correct:
            corrected_query = self._apply_field_corrections(query_json, fields_to_correct)
            self.stats["field_corrections_applied"] += len(fields_to_correct)
            
            # Log corrections for debugging
            for original, corrected in fields_to_correct.items():
                logger.debug(f"Field correction: '{original}' → '{corrected}'")
            
            return corrected_query
        
        return query_json
    
    def _collect_field_corrections(self, obj: Any, available_fields: Set[str], corrections: Dict[str, str], path: List[str] = None) -> None:
        """Collect all field corrections needed in a single traversal"""
        if path is None:
            path = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = path + [key]
                
                # Check if this key is a field name that needs correction
                if key in self.field_corrections:
                    corrected_key = self.field_corrections[key]
                    
                    # Only correct if original field doesn't exist in index
                    should_correct = True
                    if available_fields and key in available_fields:
                        should_correct = False
                    
                    if should_correct:
                        corrections[key] = corrected_key
                
                # Check for field names inside query operators
                if key in ["term", "terms", "range", "match", "exists", "wildcard"] and isinstance(value, dict):
                    for field_name in value.keys():
                        if field_name in self.field_corrections:
                            corrected_field = self.field_corrections[field_name]
                            
                            should_correct = True
                            if available_fields and field_name in available_fields:
                                should_correct = False
                            
                            if should_correct:
                                corrections[field_name] = corrected_field
                
                # Recurse into nested structures
                self._collect_field_corrections(value, available_fields, corrections, current_path)
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._collect_field_corrections(item, available_fields, corrections, path + [str(i)])
    
    def _apply_field_corrections(self, obj: Any, corrections: Dict[str, str]) -> Any:
        """Apply field corrections efficiently"""
        if isinstance(obj, dict):
            corrected = {}
            for key, value in obj.items():
                # Correct the key if needed
                corrected_key = corrections.get(key, key)
                
                # Handle special query operators
                if key in ["term", "terms", "range", "match", "exists", "wildcard"] and isinstance(value, dict):
                    corrected_value = {}
                    for field_name, field_value in value.items():
                        corrected_field = corrections.get(field_name, field_name)
                        corrected_value[corrected_field] = field_value
                    corrected[corrected_key] = corrected_value
                else:
                    # Recursively process the value
                    corrected[corrected_key] = self._apply_field_corrections(value, corrections)
            
            return corrected
        
        elif isinstance(obj, list):
            return [self._apply_field_corrections(item, corrections) for item in obj]
        
        else:
            return obj
    
    @lru_cache(maxsize=1000)
    def get_field_correction(self, field_name: str, index: Optional[str] = None) -> str:
        """Get field correction with LRU caching"""
        cache_key = f"{field_name}:{index}"
        
        if cache_key in self.field_corrections_cache:
            return self.field_corrections_cache[cache_key]
        
        # Check if field exists in index
        if index:
            dynamic_info = self.get_dynamic_index_info(index)
            if dynamic_info and dynamic_info.get("field_catalog"):
                available_fields = set(dynamic_info["field_catalog"].keys())
                if field_name in available_fields:
                    # Field exists, don't correct
                    self.field_corrections_cache[cache_key] = field_name
                    return field_name
        
        # Apply correction if available
        corrected = self.field_corrections.get(field_name, field_name)
        self.field_corrections_cache[cache_key] = corrected
        return corrected
    
    def clear_cache(self, index: Optional[str] = None):
        """Clear cache for specific index or all indices"""
        if index:
            # Clear specific index caches
            keys_to_remove = [key for key in self.mapping_cache.keys() if key.startswith(f"{index}:")]
            for key in keys_to_remove:
                del self.mapping_cache[key]
            
            if index in self.index_info_cache:
                del self.index_info_cache[index]
            
            # Clear field corrections cache for this index
            field_keys_to_remove = [key for key in self.field_corrections_cache.keys() if key.endswith(f":{index}")]
            for key in field_keys_to_remove:
                del self.field_corrections_cache[key]
        else:
            # Clear all caches
            self.mapping_cache.clear()
            self.index_info_cache.clear()
            self.field_corrections_cache.clear()
            # Clear LRU cache
            self.get_field_correction.cache_clear()
        
        logger.info(f"Field mapping cache cleared for {'all indices' if not index else index}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = self.stats["cache_hits"] / total_requests if total_requests > 0 else 0
        avg_processing_time = self.stats["processing_time_ms"] / total_requests if total_requests > 0 else 0
        
        return {
            "cache_hit_rate": hit_rate,
            "total_requests": total_requests,
            "field_corrections_applied": self.stats["field_corrections_applied"],
            "average_processing_time_ms": avg_processing_time,
            "cache_size": len(self.mapping_cache),
            "lru_cache_info": self.get_field_correction.cache_info()._asdict()
        }

# Global optimized field mapper
_global_field_mapper: Optional[OptimizedFieldMapper] = None

def get_optimized_field_mapper() -> OptimizedFieldMapper:
    """Get or create global optimized field mapper"""
    global _global_field_mapper
    if _global_field_mapper is None:
        _global_field_mapper = OptimizedFieldMapper()
    return _global_field_mapper

def correct_field_mappings_with_index_awareness_optimized(query_json: Any, index: Optional[str] = None) -> Any:
    """Drop-in replacement for the original field mapping function"""
    mapper = get_optimized_field_mapper()
    return mapper.correct_field_mappings_optimized(query_json, index)

# Backward compatibility
def correct_field_mappings_optimized(query_json: Any) -> Any:
    """Backward compatible function without index awareness"""
    return correct_field_mappings_with_index_awareness_optimized(query_json, None)

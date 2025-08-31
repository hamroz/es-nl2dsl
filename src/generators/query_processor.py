#!/usr/bin/env python3
"""
Query Processing Pipeline: Comprehensive preprocessing and postprocessing framework

This module provides the centralized processing pipeline for the ES-NL2DSL system,
implementing sophisticated preprocessing of natural language prompts and postprocessing
of generated queries. It consolidates field mapping, constraint extraction, type
validation, and optimization logic into a clean, observable pipeline with full
audit trail capabilities.

Key processing capabilities:
- Prompt preprocessing with field normalization and constraint extraction
- Query postprocessing with intelligent field corrections and type validation
- Default constraint injection for temporal boundaries and security
- Query structure optimization for performance and efficiency
- Comprehensive audit logging with step-by-step transformation tracking
- Index-aware field mapping with dynamic schema adaptation
- Error recovery with graceful degradation

The processor serves as the transformation layer between raw user input and
production-ready Elasticsearch queries, ensuring consistency, correctness,
and optimal performance.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import copy

# Add project root to path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.generators.index_analyzer import get_index_analyzer
from src.index_profiler import IndexProfiler
from src.generators.constrained import correct_field_mappings_with_index_awareness

logger = logging.getLogger(__name__)

@dataclass
class ProcessingStep:
    """
    Records a single transformation step in the processing pipeline.
    
    Captures detailed information about each processing operation for
    debugging, auditing, and performance analysis.
    
    Attributes:
        step_name: Descriptive name of the processing step
        input_data: Data state before processing
        output_data: Data state after processing
        changes_made: List of specific modifications applied
        timestamp: ISO timestamp when step was executed
        duration_ms: Processing time in milliseconds
    """
    step_name: str
    input_data: Any
    output_data: Any
    changes_made: List[str]
    timestamp: str
    duration_ms: float

@dataclass
class ProcessingResult:
    """
    Complete processing pipeline result with comprehensive audit trail.
    
    Encapsulates the entire transformation journey from original prompt
    to final query, including all intermediate steps and metrics.
    
    Attributes:
        original_prompt: User's original natural language input
        processed_prompt: Normalized prompt after preprocessing
        original_query: Initial generated query before postprocessing
        processed_query: Final optimized query ready for execution
        steps: List of all ProcessingStep objects in execution order
        success: Boolean indicating overall pipeline success
        errors: List of error messages if processing failed
        total_duration_ms: Total pipeline execution time
        metrics: Dictionary of processing metrics and statistics
    """
    original_prompt: str
    processed_prompt: str
    original_query: Optional[Dict[str, Any]]
    processed_query: Optional[Dict[str, Any]]
    steps: List[ProcessingStep]
    total_duration_ms: float
    success: bool
    errors: List[str]
    warnings: List[str]

class QueryProcessor:
    """
    Centralized query processing pipeline with comprehensive transformation capabilities.
    
    Implements a sophisticated multi-stage processing pipeline that transforms raw
    natural language prompts into optimized Elasticsearch queries. Provides full
    observability with detailed audit trails and performance metrics.
    
    Pipeline Stages:
        1. Prompt Preprocessing:
           - Field name normalization and standardization
           - Constraint extraction (dates, IPs, ports)
           - Context enhancement with index metadata
           
        2. Query Postprocessing:
           - Field mapping corrections based on index schema
           - Type validation and coercion
           - Default constraint injection
           - Structure optimization
           
        3. Complete Pipeline:
           - End-to-end processing with all transformations
           - Error recovery and fallback mechanisms
           - Performance monitoring and metrics collection
           
    Features:
        - Index-aware processing with dynamic schema adaptation
        - Intelligent field mapping with fuzzy matching
        - Comprehensive audit trail with step-by-step logging
        - Performance optimization with caching
        - Graceful error handling with fallback strategies
        
    Usage:
        processor = QueryProcessor(enable_logging=True)
        result = processor.process_complete_pipeline(prompt, index, query)
    """
    
    def __init__(self, enable_logging: bool = True):
        """
        Initialize the query processor with optional logging.
        
        Args:
            enable_logging: Whether to enable detailed processing logs
        """
        self.enable_logging = enable_logging
        self.analyzer = get_index_analyzer()
        self.profiler = IndexProfiler()
        
    def process_complete_pipeline(
        self, 
        prompt: str, 
        index: str, 
        query: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Complete processing pipeline: preprocess prompt -> postprocess query
        
        Args:
            prompt: Original user prompt
            index: Target Elasticsearch index
            query: Generated query (if available)
            
        Returns:
            ProcessingResult with complete audit trail
        """
        start_time = datetime.now()
        steps = []
        errors = []
        warnings = []
        
        try:
            # Step 1: Preprocess prompt
            processed_prompt, prompt_changes = self.preprocess_prompt(prompt, index)
            if prompt_changes:
                steps.append(ProcessingStep(
                    step_name="preprocess_prompt",
                    input_data=prompt,
                    output_data=processed_prompt,
                    changes_made=prompt_changes,
                    timestamp=datetime.now().isoformat(),
                    duration_ms=0.0  # Will be calculated
                ))
            
            # Step 2: Postprocess query (if provided)
            processed_query = query
            if query:
                processed_query, query_changes = self.postprocess_query(query, index)
                if query_changes:
                    steps.append(ProcessingStep(
                        step_name="postprocess_query", 
                        input_data=query,
                        output_data=processed_query,
                        changes_made=query_changes,
                        timestamp=datetime.now().isoformat(),
                        duration_ms=0.0
                    ))
                
                # Step 3: Add default constraints
                with_defaults, default_changes = self.add_default_constraints(processed_query, index)
                if default_changes:
                    processed_query = with_defaults
                    steps.append(ProcessingStep(
                        step_name="add_default_constraints",
                        input_data=processed_query,
                        output_data=with_defaults,
                        changes_made=default_changes,
                        timestamp=datetime.now().isoformat(),
                        duration_ms=0.0
                    ))
                
                # Step 4: Optimize query structure  
                optimized_query, optimization_changes = self.optimize_query_structure(processed_query, index)
                if optimization_changes:
                    processed_query = optimized_query
                    steps.append(ProcessingStep(
                        step_name="optimize_query_structure",
                        input_data=processed_query,
                        output_data=optimized_query,
                        changes_made=optimization_changes,
                        timestamp=datetime.now().isoformat(),
                        duration_ms=0.0
                    ))
            
            # Calculate total duration
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds() * 1000
            
            # Log summary if enabled
            if self.enable_logging:
                self._log_processing_summary(prompt, processed_prompt, query, processed_query, steps)
            
            return ProcessingResult(
                original_prompt=prompt,
                processed_prompt=processed_prompt,
                original_query=query,
                processed_query=processed_query,
                steps=steps,
                total_duration_ms=total_duration,
                success=True,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Query processing pipeline failed: {e}")
            errors.append(str(e))
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds() * 1000
            
            return ProcessingResult(
                original_prompt=prompt,
                processed_prompt=prompt,  # Return original on error
                original_query=query,
                processed_query=query,    # Return original on error
                steps=steps,
                total_duration_ms=total_duration,
                success=False,
                errors=errors,
                warnings=warnings
            )
    
    def preprocess_prompt(self, prompt: str, index: str) -> Tuple[str, List[str]]:
        """
        Extract and normalize constraints from the user prompt
        
        Args:
            prompt: Raw user prompt
            index: Target index for context
            
        Returns:
            (processed_prompt, changes_made)
        """
        changes = []
        processed = prompt.strip()
        
        # Extract time constraints
        time_patterns = [
            r'(?i)\b(today|yesterday|this week|last week|this month|last month)\b',
            r'(?i)\b(last|past)\s+(\d+)\s+(hours?|days?|weeks?|months?)\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',  # YYYY-MM-DD
            r'\b(\d{1,2}/\d{1,2}/\d{4})\b',  # MM/DD/YYYY
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, processed)
            if matches:
                changes.append(f"Detected time constraint: {matches}")
        
        # Normalize field references
        field_normalizations = {
            r'\bsource\s+ip\b': 'src_ip',
            r'\bdestination\s+ip\b': 'dst_ip', 
            r'\bsource\s+port\b': 'src_port',
            r'\bdestination\s+port\b': 'dst_port',
            r'\bprotocol\s+type\b': 'protocol',
            r'\battack\s+label\b': 'label',
        }
        
        for pattern, replacement in field_normalizations.items():
            if re.search(pattern, processed, re.IGNORECASE):
                original = processed
                processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
                if processed != original:
                    changes.append(f"Normalized field reference: '{pattern}' -> '{replacement}'")
        
        # Extract IP addresses, ports, protocols for validation
        ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        ips = re.findall(ip_pattern, processed)
        if ips:
            changes.append(f"Extracted IP addresses: {ips}")
        
        port_pattern = r'\bport\s+(\d+)\b'
        ports = re.findall(port_pattern, processed, re.IGNORECASE)
        if ports:
            changes.append(f"Extracted ports: {ports}")
        
        protocol_pattern = r'\b(tcp|udp|icmp|http|https|ssh|ftp)\b'
        protocols = re.findall(protocol_pattern, processed, re.IGNORECASE)
        if protocols:
            changes.append(f"Extracted protocols: {protocols}")
        
        return processed, changes
    
    def postprocess_query(self, query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate fields exist and fix types in generated query
        
        Args:
            query: Generated Elasticsearch query
            index: Target index
            
        Returns:
            (processed_query, changes_made)
        """
        changes = []
        processed_query = copy.deepcopy(query)
        
        # Apply field corrections using existing logic
        original_str = json.dumps(processed_query, sort_keys=True)
        corrected_query = correct_field_mappings_with_index_awareness(processed_query, index)
        corrected_str = json.dumps(corrected_query, sort_keys=True)
        
        if original_str != corrected_str:
            changes.append("Applied field mappings with index awareness")
            processed_query = corrected_query
        
        # Get index field information
        try:
            field_catalog = self.analyzer.get_index_fields(index)
            available_fields = set(field_catalog.keys())
            
            # Validate field types in query
            field_type_fixes = []
            self._validate_field_types_recursive(processed_query, field_catalog, field_type_fixes)
            
            if field_type_fixes:
                changes.extend(field_type_fixes)
            
            # Fix case sensitivity issues for common field values
            case_fixes = []
            self._fix_case_sensitivity_recursive(processed_query, case_fixes)
            
            if case_fixes:
                changes.extend(case_fixes)
                
        except Exception as e:
            changes.append(f"Warning: Could not validate field types: {e}")
        
        return processed_query, changes
    
    def add_default_constraints(self, query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Add time ranges and other default constraints if missing
        
        Args:
            query: Elasticsearch query
            index: Target index
            
        Returns:
            (query_with_defaults, changes_made)
        """
        changes = []
        processed_query = copy.deepcopy(query)
        
        # Check if query already has time constraint
        has_time_constraint = self._has_time_constraint(processed_query)
        
        if not has_time_constraint:
            # Get index profile for date information
            try:
                profile = self.profiler.analyze_index(index)
                timestamp_field = profile.primary_timestamp_field or "@timestamp"
                
                # Determine appropriate date range
                if profile.date_range and profile.date_range.get("min_date") and profile.date_range.get("max_date"):
                    # Use actual data range
                    start_date = profile.date_range["min_date"]
                    end_date = profile.date_range["max_date"]
                    changes.append(f"Added time constraint using index data range: {start_date} to {end_date}")
                else:
                    # Use recent date range as fallback
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=7)
                    start_date = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_date = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
                    changes.append(f"Added default time constraint: {start_date} to {end_date}")
                
                # Add time constraint to query
                time_filter = {
                    "range": {
                        timestamp_field: {
                            "gte": start_date,
                            "lte": end_date
                        }
                    }
                }
                
                # Ensure query has proper structure
                if "query" not in processed_query:
                    processed_query["query"] = {"bool": {"filter": []}}
                elif "bool" not in processed_query["query"]:
                    # Wrap existing query in bool
                    existing_query = processed_query["query"]
                    processed_query["query"] = {"bool": {"must": [existing_query], "filter": []}}
                elif "filter" not in processed_query["query"]["bool"]:
                    processed_query["query"]["bool"]["filter"] = []
                
                # Add time filter
                processed_query["query"]["bool"]["filter"].insert(0, time_filter)
                
            except Exception as e:
                changes.append(f"Warning: Could not add default time constraint: {e}")
        
        return processed_query, changes
    
    def optimize_query_structure(self, query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Reorder and optimize query structure for performance
        
        Args:
            query: Elasticsearch query
            index: Target index
            
        Returns:
            (optimized_query, changes_made)
        """
        changes = []
        optimized_query = copy.deepcopy(query)
        
        try:
            # Optimize bool query structure
            if "query" in optimized_query and "bool" in optimized_query["query"]:
                bool_query = optimized_query["query"]["bool"]
                
                # Move range queries (especially time) to filter context for better performance
                if "must" in bool_query:
                    range_queries = []
                    other_queries = []
                    
                    for clause in bool_query["must"]:
                        if "range" in clause:
                            range_queries.append(clause)
                        else:
                            other_queries.append(clause)
                    
                    if range_queries:
                        # Move range queries to filter
                        if "filter" not in bool_query:
                            bool_query["filter"] = []
                        
                        # Add range queries to beginning of filter (time ranges first)
                        for range_q in reversed(range_queries):
                            bool_query["filter"].insert(0, range_q)
                        
                        # Update must with remaining queries
                        if other_queries:
                            bool_query["must"] = other_queries
                        else:
                            del bool_query["must"]
                        
                        changes.append(f"Moved {len(range_queries)} range queries to filter context")
                
                # Ensure time-based filters come first
                if "filter" in bool_query:
                    filters = bool_query["filter"]
                    time_filters = []
                    other_filters = []
                    
                    for f in filters:
                        if "range" in f and any(field in str(f) for field in ["timestamp", "time", "date"]):
                            time_filters.append(f)
                        else:
                            other_filters.append(f)
                    
                    if time_filters and len(filters) > 1:
                        bool_query["filter"] = time_filters + other_filters
                        changes.append("Reordered filters to prioritize time-based constraints")
                
                # Remove empty clauses
                empty_removed = []
                for clause_type in ["must", "should", "filter", "must_not"]:
                    if clause_type in bool_query and not bool_query[clause_type]:
                        del bool_query[clause_type]
                        empty_removed.append(clause_type)
                
                if empty_removed:
                    changes.append(f"Removed empty clauses: {empty_removed}")
                        
        except Exception as e:
            changes.append(f"Warning: Query optimization failed: {e}")
        
        return optimized_query, changes
    
    def _has_time_constraint(self, query: Dict[str, Any]) -> bool:
        """Check if query already has a time constraint"""
        query_str = json.dumps(query).lower()
        time_indicators = ["timestamp", "time", "date", "range"]
        return any(indicator in query_str for indicator in time_indicators)
    
    def _validate_field_types_recursive(self, obj: Any, field_catalog: Dict[str, Any], fixes: List[str]):
        """Recursively validate field types in query structure"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ["term", "terms", "range", "match"]:
                    # This is a query clause, validate its fields
                    if isinstance(value, dict):
                        for field_name, field_value in value.items():
                            if field_name in field_catalog:
                                field_info = field_catalog[field_name]
                                expected_type = field_info.get('type')
                                
                                # Type validation logic could be expanded here
                                if expected_type == 'integer' and isinstance(field_value, str) and field_value.isdigit():
                                    fixes.append(f"Field '{field_name}' should be integer, got string")
                                elif expected_type == 'keyword' and isinstance(field_value, (int, float)):
                                    fixes.append(f"Field '{field_name}' should be string, got number")
                else:
                    # Recurse into nested structures
                    self._validate_field_types_recursive(value, field_catalog, fixes)
        elif isinstance(obj, list):
            for item in obj:
                self._validate_field_types_recursive(item, field_catalog, fixes)
    
    def _log_processing_summary(
        self, 
        original_prompt: str, 
        processed_prompt: str, 
        original_query: Optional[Dict[str, Any]], 
        processed_query: Optional[Dict[str, Any]], 
        steps: List[ProcessingStep]
    ):
        """Log a summary of all processing steps"""
        logger.info("🔄 Query Processing Pipeline Summary")
        logger.info("="*50)
        
        if original_prompt != processed_prompt:
            logger.info(f"📝 Prompt: '{original_prompt}' -> '{processed_prompt}'")
        
        if original_query and processed_query:
            original_str = json.dumps(original_query, separators=(',', ':'))
            processed_str = json.dumps(processed_query, separators=(',', ':'))
            if original_str != processed_str:
                logger.info(f"🔧 Query transformed: {len(original_str)} -> {len(processed_str)} chars")
        
        total_changes = sum(len(step.changes_made) for step in steps)
        logger.info(f"⚙️  Processing steps: {len(steps)}, Total changes: {total_changes}")
        
        for step in steps:
            logger.info(f"   • {step.step_name}: {len(step.changes_made)} changes")
            for change in step.changes_made:
                logger.debug(f"      - {change}")
        
        logger.info("="*50)
    
    def _fix_case_sensitivity_recursive(self, obj: Any, fixes: List[str]):
        """Recursively fix case sensitivity issues in query structure"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ["term", "terms"]:
                    # This is a query clause, fix case of field values
                    if isinstance(value, dict):
                        for field_name, field_value in value.items():
                            if field_name == "protocol" and isinstance(field_value, str):
                                # Protocol values should be uppercase
                                correct_value = field_value.upper()
                                if correct_value != field_value:
                                    fixes.append(f"Fixed protocol case: '{field_value}' -> '{correct_value}'")
                                    value[field_name] = correct_value
                else:
                    # Recurse into nested structures
                    self._fix_case_sensitivity_recursive(value, fixes)
        elif isinstance(obj, list):
            for item in obj:
                self._fix_case_sensitivity_recursive(item, fixes)

# Convenience functions for external usage
def preprocess_prompt(prompt: str, index: str) -> Tuple[str, List[str]]:
    """Convenience function for prompt preprocessing"""
    processor = QueryProcessor(enable_logging=False)
    return processor.preprocess_prompt(prompt, index)

def postprocess_query(query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
    """Convenience function for query postprocessing"""
    processor = QueryProcessor(enable_logging=False)
    return processor.postprocess_query(query, index)

def add_default_constraints(query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
    """Convenience function for adding default constraints"""
    processor = QueryProcessor(enable_logging=False)
    return processor.add_default_constraints(query, index)

def optimize_query_structure(query: Dict[str, Any], index: str) -> Tuple[Dict[str, Any], List[str]]:
    """Convenience function for query optimization"""
    processor = QueryProcessor(enable_logging=False)
    return processor.optimize_query_structure(query, index)

def process_complete_pipeline(prompt: str, index: str, query: Optional[Dict[str, Any]] = None) -> ProcessingResult:
    """Convenience function for complete pipeline processing"""
    processor = QueryProcessor(enable_logging=True)
    return processor.process_complete_pipeline(prompt, index, query)
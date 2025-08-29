#!/usr/bin/env python3
"""
Query Validator: Comprehensive validation system for generated Elasticsearch queries.
Ensures queries are syntactically correct, semantically meaningful, and return useful results.
"""
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

# Add project root to path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.config import get_es_client_config
from src.index_profiler import IndexProfiler
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of query validation"""
    is_valid: bool
    score: float  # 0-100, higher is better
    issues: List[str]
    warnings: List[str]
    suggestions: List[str]
    execution_time_ms: Optional[float] = None
    result_count: Optional[int] = None
    sample_results: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.sample_results is None:
            self.sample_results = []
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def get_status_emoji(self) -> str:
        """Get emoji representing validation status"""
        if not self.is_valid:
            return "❌"
        elif self.score >= 90:
            return "🟢"
        elif self.score >= 70:
            return "🟡"
        else:
            return "🔴"

class QueryValidator:
    """Comprehensive query validation and optimization system"""
    
    def __init__(self):
        self.es = None
        self.profiler = IndexProfiler()
    
    def _get_es_client(self) -> Elasticsearch:
        """Get Elasticsearch client"""
        if self.es is None:
            self.es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=30)
        return self.es
    
    def validate_query(
        self, 
        query: Dict[str, Any], 
        index: str,
        execute_test: bool = True,
        max_test_size: int = 10
    ) -> ValidationResult:
        """Comprehensively validate a query"""
        
        logger.info(f"🔍 Validating query for index {index}")
        
        issues = []
        warnings = []
        suggestions = []
        score = 100.0
        execution_time_ms = None
        result_count = None
        sample_results = []
        
        try:
            # 1. Syntax validation
            syntax_issues = self._validate_syntax(query)
            issues.extend(syntax_issues)
            score -= len(syntax_issues) * 15
            
            # 2. Field existence validation
            field_issues, field_warnings = self._validate_fields(query, index)
            issues.extend(field_issues)
            warnings.extend(field_warnings)
            score -= len(field_issues) * 20
            score -= len(field_warnings) * 5
            
            # 3. Date range validation
            date_issues, date_suggestions = self._validate_date_ranges(query, index)
            issues.extend(date_issues)
            suggestions.extend(date_suggestions)
            score -= len(date_issues) * 10
            
            # 4. Query structure validation
            structure_warnings = self._validate_structure(query)
            warnings.extend(structure_warnings)
            score -= len(structure_warnings) * 3
            
            # 5. Performance validation
            perf_warnings, perf_suggestions = self._validate_performance(query)
            warnings.extend(perf_warnings)
            suggestions.extend(perf_suggestions)
            score -= len(perf_warnings) * 2
            
            # 6. Execute test query if requested
            if execute_test and len(issues) == 0:
                try:
                    execution_time_ms, result_count, sample_results = self._execute_test_query(
                        query, index, max_test_size
                    )
                    
                    # Score based on results
                    if result_count == 0:
                        warnings.append("Query returns no results")
                        score -= 20
                    elif result_count < 5:
                        warnings.append(f"Query returns only {result_count} results - may be too restrictive")
                        score -= 10
                    
                    # Score based on performance
                    if execution_time_ms and execution_time_ms > 5000:
                        warnings.append(f"Query is slow ({execution_time_ms:.0f}ms)")
                        score -= 5
                    
                except Exception as e:
                    issues.append(f"Query execution failed: {str(e)}")
                    score -= 30
            
            # 7. Generate optimization suggestions
            optimization_suggestions = self._generate_optimization_suggestions(query, index)
            suggestions.extend(optimization_suggestions)
            
            # Ensure score is within bounds
            score = max(0, min(100, score))
            
            # Determine if valid (no critical issues)
            is_valid = len(issues) == 0
            
            logger.info(f"✅ Validation complete: {'VALID' if is_valid else 'INVALID'} (score: {score:.1f})")
            
            return ValidationResult(
                is_valid=is_valid,
                score=score,
                issues=issues,
                warnings=warnings,
                suggestions=suggestions,
                execution_time_ms=execution_time_ms,
                result_count=result_count,
                sample_results=sample_results
            )
            
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            return ValidationResult(
                is_valid=False,
                score=0,
                issues=[f"Validation failed: {str(e)}"],
                warnings=[],
                suggestions=[]
            )
    
    def _validate_syntax(self, query: Dict[str, Any]) -> List[str]:
        """Validate basic query syntax"""
        issues = []
        
        # Must have a query field
        if "query" not in query:
            issues.append("Missing 'query' field")
            return issues
        
        # Query must not be empty
        if not query["query"]:
            issues.append("Empty query")
            return issues
        
        # Validate JSON structure
        try:
            json.dumps(query)
        except (TypeError, ValueError) as e:
            issues.append(f"Invalid JSON structure: {e}")
        
        # Check for common structural issues
        query_body = query["query"]
        if isinstance(query_body, dict):
            if "bool" in query_body:
                bool_query = query_body["bool"]
                if not isinstance(bool_query, dict):
                    issues.append("'bool' query must be an object")
                elif not any(key in bool_query for key in ["must", "should", "filter", "must_not"]):
                    issues.append("'bool' query must contain at least one clause (must, should, filter, must_not)")
        
        return issues
    
    def _validate_fields(self, query: Dict[str, Any], index: str) -> Tuple[List[str], List[str]]:
        """Validate that referenced fields exist in the index"""
        issues = []
        warnings = []
        
        try:
            # Get index profile to check field existence
            profile = self.profiler.analyze_index(index)
            available_fields = set(profile.fields.keys())
            
            # Extract field references from query
            referenced_fields = self._extract_field_references(query)
            
            for field in referenced_fields:
                if field not in available_fields:
                    # Check if it's a close match
                    suggestions = self._find_similar_fields(field, available_fields)
                    if suggestions:
                        issues.append(f"Field '{field}' not found. Did you mean: {', '.join(suggestions[:3])}?")
                    else:
                        issues.append(f"Field '{field}' does not exist in index {index}")
                else:
                    # Field exists, check if it's actually searchable
                    field_info = profile.fields[field]
                    if not field_info.is_searchable:
                        warnings.append(f"Field '{field}' may not be searchable (type: {field_info.type})")
        
        except Exception as e:
            warnings.append(f"Could not validate fields: {e}")
        
        return issues, warnings
    
    def _extract_field_references(self, obj: Any, path: str = "") -> set:
        """Recursively extract field references from query"""
        fields = set()
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # These keys contain field references
                if key in ["term", "terms", "range", "match", "exists", "wildcard", "prefix"]:
                    if isinstance(value, dict):
                        fields.update(value.keys())
                elif key == "field":
                    # Direct field reference
                    if isinstance(value, str):
                        fields.add(value)
                else:
                    # Recurse into nested structures
                    fields.update(self._extract_field_references(value, current_path))
        
        elif isinstance(obj, list):
            for item in obj:
                fields.update(self._extract_field_references(item, path))
        
        return fields
    
    def _find_similar_fields(self, target: str, available: set) -> List[str]:
        """Find similar field names using simple string matching"""
        target_lower = target.lower()
        suggestions = []
        
        # Exact case-insensitive match
        for field in available:
            if field.lower() == target_lower:
                suggestions.append(field)
        
        # Partial matches
        if not suggestions:
            for field in available:
                field_lower = field.lower()
                if (target_lower in field_lower or field_lower in target_lower or
                    abs(len(target) - len(field)) <= 2):
                    suggestions.append(field)
        
        return suggestions[:5]  # Limit suggestions
    
    def _validate_date_ranges(self, query: Dict[str, Any], index: str) -> Tuple[List[str], List[str]]:
        """Validate date ranges against actual data"""
        issues = []
        suggestions = []
        
        try:
            # Get actual date range from index
            profile = self.profiler.analyze_index(index)
            if not profile.date_range.get("min_date") or not profile.date_range.get("max_date"):
                return issues, suggestions
            
            data_min = profile.date_range["min_date"]
            data_max = profile.date_range["max_date"]
            
            # Extract date ranges from query
            date_ranges = self._extract_date_ranges(query)
            
            for field, range_spec in date_ranges:
                gte = range_spec.get("gte", range_spec.get("gt"))
                lte = range_spec.get("lte", range_spec.get("lt"))
                
                if gte and gte > data_max:
                    issues.append(f"Start date {gte} is after latest data ({data_max})")
                
                if lte and lte < data_min:
                    issues.append(f"End date {lte} is before earliest data ({data_min})")
                
                if gte and lte and gte > lte:
                    issues.append(f"Start date {gte} is after end date {lte}")
                
                # Suggest better date ranges
                if not gte or not lte:
                    suggestions.append(f"Consider adding explicit date range for better performance")
        
        except Exception as e:
            logger.debug(f"Date validation error: {e}")
        
        return issues, suggestions
    
    def _extract_date_ranges(self, obj: Any, path: str = "") -> List[Tuple[str, Dict[str, Any]]]:
        """Extract date range specifications from query"""
        ranges = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "range" and isinstance(value, dict):
                    for field, range_spec in value.items():
                        if isinstance(range_spec, dict):
                            ranges.append((field, range_spec))
                else:
                    ranges.extend(self._extract_date_ranges(value, f"{path}.{key}" if path else key))
        
        elif isinstance(obj, list):
            for item in obj:
                ranges.extend(self._extract_date_ranges(item, path))
        
        return ranges
    
    def _validate_structure(self, query: Dict[str, Any]) -> List[str]:
        """Validate query structure and suggest improvements"""
        warnings = []
        
        # Check for missing time filters
        has_time_filter = self._has_time_filter(query)
        if not has_time_filter:
            warnings.append("Query lacks time range filter - may be slow on large indices")
        
        # Check for overly broad queries
        filter_count = self._count_filters(query)
        if filter_count == 0:
            warnings.append("Query has no filters - will return all documents")
        elif filter_count == 1 and has_time_filter:
            warnings.append("Query only has time filter - consider adding more specific filters")
        
        # Check for complex nested queries
        nesting_depth = self._calculate_nesting_depth(query)
        if nesting_depth > 4:
            warnings.append(f"Query has deep nesting (depth: {nesting_depth}) - may be complex to understand")
        
        return warnings
    
    def _has_time_filter(self, obj: Any) -> bool:
        """Check if query contains a time-based filter"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "range" and isinstance(value, dict):
                    for field in value.keys():
                        if "timestamp" in field.lower() or "time" in field.lower():
                            return True
                elif self._has_time_filter(value):
                    return True
        elif isinstance(obj, list):
            return any(self._has_time_filter(item) for item in obj)
        
        return False
    
    def _count_filters(self, obj: Any) -> int:
        """Count the number of filter conditions"""
        if isinstance(obj, dict):
            count = 0
            for key, value in obj.items():
                if key in ["term", "terms", "range", "match", "exists", "wildcard"]:
                    count += 1
                elif key == "filter" and isinstance(value, list):
                    count += len(value)
                else:
                    count += self._count_filters(value)
            return count
        elif isinstance(obj, list):
            return sum(self._count_filters(item) for item in obj)
        
        return 0
    
    def _calculate_nesting_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of query"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(value, current_depth + 1) for value in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(item, current_depth) for item in obj)
        else:
            return current_depth
    
    def _validate_performance(self, query: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """Validate query for performance issues"""
        warnings = []
        suggestions = []
        
        # Check for wildcard queries without prefixes
        if self._has_leading_wildcards(query):
            warnings.append("Query contains leading wildcards which may be slow")
            suggestions.append("Consider using prefix queries or adding more specific filters")
        
        # Check for regex queries
        if self._has_regex_queries(query):
            warnings.append("Query contains regex patterns which may be slow")
            suggestions.append("Consider using simpler term or wildcard queries")
        
        # Check for large terms arrays
        large_terms = self._find_large_terms_queries(query)
        if large_terms:
            warnings.append(f"Query has large terms arrays: {large_terms}")
            suggestions.append("Consider using bool queries with should clauses for better performance")
        
        return warnings, suggestions
    
    def _has_leading_wildcards(self, obj: Any) -> bool:
        """Check for leading wildcard patterns"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "wildcard" and isinstance(value, dict):
                    for field_value in value.values():
                        if isinstance(field_value, str) and field_value.startswith("*"):
                            return True
                elif self._has_leading_wildcards(value):
                    return True
        elif isinstance(obj, list):
            return any(self._has_leading_wildcards(item) for item in obj)
        
        return False
    
    def _has_regex_queries(self, obj: Any) -> bool:
        """Check for regex queries"""
        if isinstance(obj, dict):
            return "regexp" in obj or any(self._has_regex_queries(value) for value in obj.values())
        elif isinstance(obj, list):
            return any(self._has_regex_queries(item) for item in obj)
        
        return False
    
    def _find_large_terms_queries(self, obj: Any) -> List[str]:
        """Find terms queries with many values"""
        large_terms = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "terms" and isinstance(value, dict):
                    for field, terms_list in value.items():
                        if isinstance(terms_list, list) and len(terms_list) > 10:
                            large_terms.append(f"{field}({len(terms_list)} terms)")
                else:
                    large_terms.extend(self._find_large_terms_queries(value))
        elif isinstance(obj, list):
            for item in obj:
                large_terms.extend(self._find_large_terms_queries(item))
        
        return large_terms
    
    def _execute_test_query(
        self, 
        query: Dict[str, Any], 
        index: str, 
        max_size: int = 10
    ) -> Tuple[float, int, List[Dict[str, Any]]]:
        """Execute query to test performance and results"""
        
        es = self._get_es_client()
        
        # Add size limit for testing
        test_query = query.copy()
        test_query["size"] = max_size
        test_query["track_total_hits"] = True
        
        start_time = time.time()
        response = es.search(index=index, body=test_query)
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Extract results
        total_hits = (response["hits"]["total"]["value"] 
                     if isinstance(response["hits"]["total"], dict) 
                     else response["hits"]["total"])
        
        sample_results = []
        for hit in response["hits"]["hits"]:
            # Include only source and basic metadata
            sample_results.append({
                "score": hit.get("_score"),
                "source": hit.get("_source", {})
            })
        
        return execution_time_ms, total_hits, sample_results
    
    def _generate_optimization_suggestions(self, query: Dict[str, Any], index: str) -> List[str]:
        """Generate query optimization suggestions"""
        suggestions = []
        
        try:
            # Get index stats for optimization hints
            profile = self.profiler.analyze_index(index)
            
            # Suggest adding missing filters
            has_time = self._has_time_filter(query)
            if not has_time:
                suggestions.append(f"Add time range filter using {profile.primary_timestamp_field}")
            
            # Suggest using more selective fields
            field_refs = self._extract_field_references(query)
            for field in field_refs:
                if field in profile.fields:
                    field_info = profile.fields[field]
                    if len(field_info.common_values) < 3:
                        suggestions.append(f"Field '{field}' has very few unique values - consider combining with other filters")
            
            # Suggest index-specific optimizations
            if profile.document_count > 1000000:
                suggestions.append("Large index detected - ensure queries have time range and multiple filters")
            
        except Exception as e:
            logger.debug(f"Error generating optimization suggestions: {e}")
        
        return suggestions


def validate_query_file(query_file: str, index: str) -> ValidationResult:
    """Validate a query from a JSON file"""
    try:
        with open(query_file, 'r') as f:
            query = json.load(f)
        
        validator = QueryValidator()
        return validator.validate_query(query, index)
        
    except Exception as e:
        return ValidationResult(
            is_valid=False,
            score=0,
            issues=[f"Failed to load query file: {e}"],
            warnings=[],
            suggestions=[]
        )


def main():
    """CLI interface for query validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Elasticsearch queries")
    parser.add_argument("--query", required=True, help="Path to query JSON file")
    parser.add_argument("--index", required=True, help="Target index name")
    parser.add_argument("--no-execute", action="store_true", help="Skip query execution test")
    parser.add_argument("--max-results", type=int, default=10, help="Max results for test execution")
    parser.add_argument("--output", help="Output validation report to file")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Validate query
    result = validate_query_file(args.query, args.index)
    
    # Print results
    print(f"\n{result.get_status_emoji()} Query Validation Report")
    print(f"Index: {args.index}")
    print(f"Query: {args.query}")
    print(f"Status: {'VALID' if result.is_valid else 'INVALID'}")
    print(f"Score: {result.score:.1f}/100")
    
    if result.execution_time_ms:
        print(f"Execution: {result.execution_time_ms:.0f}ms")
    
    if result.result_count is not None:
        print(f"Results: {result.result_count}")
    
    if result.issues:
        print(f"\n❌ Issues ({len(result.issues)}):")
        for issue in result.issues:
            print(f"  • {issue}")
    
    if result.warnings:
        print(f"\n⚠️ Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  • {warning}")
    
    if result.suggestions:
        print(f"\n💡 Suggestions ({len(result.suggestions)}):")
        for suggestion in result.suggestions:
            print(f"  • {suggestion}")
    
    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nReport saved to {args.output}")
    
    # Exit with error code if invalid
    if not result.is_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()

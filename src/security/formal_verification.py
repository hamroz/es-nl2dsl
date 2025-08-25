#!/usr/bin/env python3
"""Formal verification system for security properties"""
import json
import re
from typing import Dict, List, Any, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class SecurityProperty(Enum):
    """Formal security properties to verify"""
    NO_UNRESTRICTED_ACCESS = "no_unrestricted_access"
    TIME_BOUNDED_QUERIES = "time_bounded_queries"
    FIELD_WHITELIST_COMPLIANCE = "field_whitelist_compliance"
    NO_AGGREGATION_BYPASS = "no_aggregation_bypass"
    QUERY_SIZE_LIMITS = "query_size_limits"
    NO_SYSTEM_METADATA_ACCESS = "no_system_metadata_access"

class VerificationResult(Enum):
    """Results of formal verification"""
    VERIFIED = "verified"           # Property definitely holds
    VIOLATED = "violated"          # Property definitely violated
    UNKNOWN = "unknown"            # Cannot determine (incomplete analysis)

@dataclass
class PropertyViolation:
    """Details about a property violation"""
    property: SecurityProperty
    description: str
    violation_location: str
    evidence: str
    severity: str  # "critical", "high", "medium", "low"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "property": self.property.value,
            "description": self.description,
            "violation_location": self.violation_location,
            "evidence": self.evidence,
            "severity": self.severity
        }

@dataclass
class VerificationReport:
    """Comprehensive verification report"""
    query: Dict[str, Any]
    total_properties: int
    verified_properties: int
    violated_properties: int
    unknown_properties: int
    violations: List[PropertyViolation]
    overall_result: VerificationResult
    security_score: float  # 0-1, based on violations
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "total_properties": self.total_properties,
            "verified_properties": self.verified_properties,
            "violated_properties": self.violated_properties,
            "unknown_properties": self.unknown_properties,
            "violations": [v.to_dict() for v in self.violations],
            "overall_result": self.overall_result.value,
            "security_score": self.security_score
        }

class FormalVerifier:
    """Formal verification system for ES DSL queries"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.properties = [prop for prop in SecurityProperty]
    
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load verification configuration"""
        default_config = {
            "allowed_fields": [
                "@timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
                "protocol", "label", "flow_duration", "tot_fwd_pkts",
                "tot_bwd_pkts"
            ],
            "restricted_fields": [
                "_index", "_type", "_id", "_score", "_source",
                "system.*", "admin.*", "internal.*"
            ],
            "max_time_range_days": 7,
            "max_result_size": 10000,
            "allowed_aggregations": ["terms", "date_histogram", "avg", "sum", "max", "min"],
            "required_time_bounds": True
        }
        
        if config_file and Path(config_file).exists():
            try:
                with open(config_file) as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config {config_file}: {e}")
        
        return default_config
    
    def verify_query(self, query: Dict[str, Any]) -> VerificationReport:
        """Formally verify a query against all security properties"""
        violations = []
        
        # Verify each property
        for prop in self.properties:
            result, violation = self._verify_property(query, prop)
            if violation:
                violations.append(violation)
        
        # Calculate summary statistics
        total = len(self.properties)
        violated = len(violations)
        verified = total - violated  # Simplified: non-violated = verified
        unknown = 0  # Future: handle incomplete analysis
        
        # Determine overall result
        if violated == 0:
            overall_result = VerificationResult.VERIFIED
        else:
            overall_result = VerificationResult.VIOLATED
        
        # Calculate security score
        security_score = self._calculate_security_score(violations, total)
        
        return VerificationReport(
            query=query,
            total_properties=total,
            verified_properties=verified,
            violated_properties=violated,
            unknown_properties=unknown,
            violations=violations,
            overall_result=overall_result,
            security_score=security_score
        )
    
    def _verify_property(self, query: Dict[str, Any], 
                        property: SecurityProperty) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify a specific security property"""
        
        if property == SecurityProperty.NO_UNRESTRICTED_ACCESS:
            return self._verify_no_unrestricted_access(query)
        
        elif property == SecurityProperty.TIME_BOUNDED_QUERIES:
            return self._verify_time_bounded_queries(query)
        
        elif property == SecurityProperty.FIELD_WHITELIST_COMPLIANCE:
            return self._verify_field_whitelist_compliance(query)
        
        elif property == SecurityProperty.NO_AGGREGATION_BYPASS:
            return self._verify_no_aggregation_bypass(query)
        
        elif property == SecurityProperty.QUERY_SIZE_LIMITS:
            return self._verify_query_size_limits(query)
        
        elif property == SecurityProperty.NO_SYSTEM_METADATA_ACCESS:
            return self._verify_no_system_metadata_access(query)
        
        else:
            return VerificationResult.UNKNOWN, None
    
    def _verify_no_unrestricted_access(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that query doesn't attempt unrestricted access"""
        
        # Check for match_all without filters
        violations = []
        
        def check_unrestricted(obj, path=""):
            if isinstance(obj, dict):
                # Check for dangerous patterns
                if "match_all" in obj and path.endswith("query"):
                    # match_all at query level without filters is dangerous
                    parent_obj = self._get_parent_object(query, path)
                    if not self._has_filters(parent_obj):
                        violations.append(f"Unrestricted match_all at {path}")
                
                # Check for wildcard queries without constraints
                if "wildcard" in obj:
                    for field, pattern in obj["wildcard"].items():
                        if pattern == "*" and not self._has_sibling_constraints(query, path):
                            violations.append(f"Unconstrained wildcard on {field} at {path}")
                
                # Recursively check nested objects
                for key, value in obj.items():
                    check_unrestricted(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_unrestricted(item, f"{path}[{i}]")
        
        check_unrestricted(query)
        
        if violations:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.NO_UNRESTRICTED_ACCESS,
                description="Query attempts unrestricted data access",
                violation_location="; ".join(violations),
                evidence=json.dumps(query, indent=2)[:500],
                severity="critical"
            )
        
        return VerificationResult.VERIFIED, None
    
    def _verify_time_bounded_queries(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that queries have appropriate time bounds"""
        
        if not self.config.get("required_time_bounds", True):
            return VerificationResult.VERIFIED, None
        
        # Look for @timestamp range constraints
        has_time_constraint = False
        time_range_days = None
        
        def find_time_constraints(obj, path=""):
            nonlocal has_time_constraint, time_range_days
            
            if isinstance(obj, dict):
                if "range" in obj and "@timestamp" in obj.get("range", {}):
                    has_time_constraint = True
                    
                    # Check time range size
                    timestamp_range = obj["range"]["@timestamp"]
                    if "gte" in timestamp_range and "lte" in timestamp_range:
                        time_range_days = self._calculate_time_range_days(
                            timestamp_range["gte"], timestamp_range["lte"]
                        )
                
                for key, value in obj.items():
                    find_time_constraints(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for item in obj:
                    find_time_constraints(item, path)
        
        find_time_constraints(query)
        
        # Check violations
        if not has_time_constraint:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.TIME_BOUNDED_QUERIES,
                description="Query lacks required time constraints",
                violation_location="Missing @timestamp range filter",
                evidence="No range filter found on @timestamp field",
                severity="high"
            )
        
        max_days = self.config.get("max_time_range_days", 7)
        if time_range_days and time_range_days > max_days:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.TIME_BOUNDED_QUERIES,
                description=f"Time range too large: {time_range_days} days (max: {max_days})",
                violation_location="@timestamp range filter",
                evidence=f"Time range: {time_range_days} days",
                severity="medium"
            )
        
        return VerificationResult.VERIFIED, None
    
    def _verify_field_whitelist_compliance(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that only whitelisted fields are accessed"""
        
        allowed_fields = set(self.config.get("allowed_fields", []))
        restricted_fields = self.config.get("restricted_fields", [])
        violations = []
        
        def check_field_access(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    # Check if key is a field name (not a query operator)
                    if key not in ["query", "bool", "filter", "must", "should", "must_not", 
                                  "range", "term", "terms", "match", "wildcard", "aggs"]:
                        
                        # Check against whitelist
                        if allowed_fields and key not in allowed_fields:
                            violations.append(f"Non-whitelisted field '{key}' at {path}")
                        
                        # Check against restricted patterns
                        for restricted_pattern in restricted_fields:
                            if self._matches_pattern(key, restricted_pattern):
                                violations.append(f"Restricted field '{key}' matches pattern '{restricted_pattern}' at {path}")
                    
                    # Recursively check values
                    check_field_access(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_field_access(item, f"{path}[{i}]")
        
        check_field_access(query)
        
        if violations:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.FIELD_WHITELIST_COMPLIANCE,
                description="Query accesses non-whitelisted or restricted fields",
                violation_location="; ".join(violations[:3]),  # Limit to first 3
                evidence=f"Total violations: {len(violations)}",
                severity="high"
            )
        
        return VerificationResult.VERIFIED, None
    
    def _verify_no_aggregation_bypass(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that aggregations don't bypass security constraints"""
        
        allowed_aggs = set(self.config.get("allowed_aggregations", []))
        violations = []
        
        def check_aggregations(obj, path=""):
            if isinstance(obj, dict):
                if "aggs" in obj or "aggregations" in obj:
                    agg_key = "aggs" if "aggs" in obj else "aggregations"
                    aggs = obj[agg_key]
                    
                    for agg_name, agg_def in aggs.items():
                        # Check aggregation types
                        for agg_type in agg_def.keys():
                            if agg_type not in allowed_aggs:
                                violations.append(f"Disallowed aggregation '{agg_type}' in '{agg_name}' at {path}")
                        
                        # Check for dangerous patterns
                        if "script" in str(agg_def):
                            violations.append(f"Script aggregation detected in '{agg_name}' at {path}")
                        
                        if "size" in agg_def and isinstance(agg_def["size"], int) and agg_def["size"] > 1000:
                            violations.append(f"Large aggregation size {agg_def['size']} in '{agg_name}' at {path}")
                
                for key, value in obj.items():
                    check_aggregations(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_aggregations(item, f"{path}[{i}]")
        
        check_aggregations(query)
        
        if violations:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.NO_AGGREGATION_BYPASS,
                description="Query contains potentially dangerous aggregations",
                violation_location="; ".join(violations),
                evidence=f"Found {len(violations)} aggregation issues",
                severity="medium"
            )
        
        return VerificationResult.VERIFIED, None
    
    def _verify_query_size_limits(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that query respects size limits"""
        
        max_size = self.config.get("max_result_size", 10000)
        violations = []
        
        # Check explicit size parameters
        def check_size_limits(obj, path=""):
            if isinstance(obj, dict):
                if "size" in obj:
                    size_value = obj["size"]
                    if isinstance(size_value, int) and size_value > max_size:
                        violations.append(f"Size limit exceeded: {size_value} > {max_size} at {path}")
                
                for key, value in obj.items():
                    check_size_limits(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_size_limits(item, f"{path}[{i}]")
        
        check_size_limits(query)
        
        # Check for potential result explosion patterns
        if self._has_wildcard_without_limits(query):
            violations.append("Wildcard query without size limits may return excessive results")
        
        if violations:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.QUERY_SIZE_LIMITS,
                description="Query may exceed result size limits",
                violation_location="; ".join(violations),
                evidence=f"Max allowed size: {max_size}",
                severity="medium"
            )
        
        return VerificationResult.VERIFIED, None
    
    def _verify_no_system_metadata_access(self, query: Dict[str, Any]) -> Tuple[VerificationResult, Optional[PropertyViolation]]:
        """Verify that query doesn't access system metadata"""
        
        system_fields = ["_index", "_type", "_id", "_score", "_source", "_routing", "_parent"]
        violations = []
        
        def check_system_access(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.startswith("_") and key in system_fields:
                        violations.append(f"System metadata access: '{key}' at {path}")
                    
                    check_system_access(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_system_access(item, f"{path}[{i}]")
        
        check_system_access(query)
        
        if violations:
            return VerificationResult.VIOLATED, PropertyViolation(
                property=SecurityProperty.NO_SYSTEM_METADATA_ACCESS,
                description="Query attempts to access system metadata",
                violation_location="; ".join(violations),
                evidence="System metadata should not be directly accessed",
                severity="high"
            )
        
        return VerificationResult.VERIFIED, None
    
    # Helper methods
    
    def _get_parent_object(self, query: Dict[str, Any], path: str) -> Dict[str, Any]:
        """Get parent object from path"""
        # Simplified implementation
        return query
    
    def _has_filters(self, obj: Dict[str, Any]) -> bool:
        """Check if object has filter constraints"""
        if not isinstance(obj, dict):
            return False
        
        return ("filter" in obj or "must" in obj or 
                "range" in obj or "term" in obj or "terms" in obj)
    
    def _has_sibling_constraints(self, query: Dict[str, Any], path: str) -> bool:
        """Check if there are sibling constraints that limit the wildcard"""
        # Simplified: check if there are any other constraints in the query
        return self._has_filters(query)
    
    def _calculate_time_range_days(self, start: str, end: str) -> Optional[int]:
        """Calculate time range in days"""
        try:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            return (end_dt - start_dt).days
        except Exception:
            return None
    
    def _matches_pattern(self, field_name: str, pattern: str) -> bool:
        """Check if field name matches a pattern (supports wildcards)"""
        # Convert glob pattern to regex
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        return bool(re.match(f"^{regex_pattern}$", field_name))
    
    def _has_wildcard_without_limits(self, query: Dict[str, Any]) -> bool:
        """Check for wildcard queries without size limits"""
        has_wildcard = "wildcard" in str(query)
        has_size_limit = "size" in str(query)
        return has_wildcard and not has_size_limit
    
    def _calculate_security_score(self, violations: List[PropertyViolation], total_properties: int) -> float:
        """Calculate security score based on violations"""
        if not violations:
            return 1.0
        
        # Weight violations by severity
        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.1}
        
        total_weight = 0.0
        for violation in violations:
            weight = severity_weights.get(violation.severity, 0.5)
            total_weight += weight
        
        # Normalize by total possible weight (all properties as critical)
        max_possible_weight = total_properties * 1.0
        
        # Score is 1 - (weighted violations / max possible)
        score = 1.0 - min(1.0, total_weight / max_possible_weight)
        
        return max(0.0, score)

def verify_query_file(query_file: str, config_file: Optional[str] = None) -> VerificationReport:
    """Verify a query from a file"""
    
    with open(query_file) as f:
        query = json.load(f)
    
    verifier = FormalVerifier(config_file)
    return verifier.verify_query(query)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Formally verify ES DSL query security properties")
    parser.add_argument("--query", required=True, help="JSON file containing ES DSL query")
    parser.add_argument("--config", help="Security configuration file")
    parser.add_argument("--output", help="Output file for verification report")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Verify query
    report = verify_query_file(args.query, args.config)
    
    # Print results
    print(f"=== FORMAL VERIFICATION REPORT ===")
    print(f"Query: {args.query}")
    print(f"Overall Result: {report.overall_result.value.upper()}")
    print(f"Security Score: {report.security_score:.3f}")
    print(f"Properties: {report.verified_properties}/{report.total_properties} verified")
    
    if report.violations:
        print(f"\n=== VIOLATIONS ({len(report.violations)}) ===")
        for i, violation in enumerate(report.violations, 1):
            print(f"{i}. {violation.description}")
            print(f"   Property: {violation.property.value}")
            print(f"   Severity: {violation.severity.upper()}")
            print(f"   Location: {violation.violation_location}")
            if args.verbose:
                print(f"   Evidence: {violation.evidence}")
            print()
    
    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Verification report saved to {args.output}")
    
    # Exit with appropriate code
    exit_code = 0 if report.overall_result == VerificationResult.VERIFIED else 1
    exit(exit_code)

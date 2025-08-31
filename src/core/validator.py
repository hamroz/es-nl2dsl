#!/usr/bin/env python3
"""
Core Validator: Rule-based validation system for Elasticsearch DSL queries

This module provides the foundational validation system for the ES-NL2DSL framework,
implementing rule-based validation against configurable constraints. It ensures queries
meet security requirements, field restrictions, time window limits, and cost controls
defined in validation rules configuration.

Key validation capabilities:
- Time window enforcement: Ensures queries include proper temporal boundaries
- Field validation: Verifies only whitelisted fields are used
- Cost control: Prevents expensive queries exceeding document limits
- Type checking: Validates range queries only on appropriate field types
- Aggregation validation: Ensures aggregations have proper selectivity
- Security constraints: Enforces security policies and access controls

The validator serves as a critical security and performance gateway, preventing
malformed or potentially harmful queries from reaching the Elasticsearch cluster.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import argparse, json, math, re, datetime as dt, orjson, yaml
import sys
import os
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ..utils.config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX
except ImportError:
    # Fallback for CLI usage
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.utils.config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX

def load_rules(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def collect_fields(dsl):
    fields = set()
    def walk(obj):
        if isinstance(obj, dict):
            if "term" in obj and isinstance(obj["term"], dict):
                k = next(iter(obj["term"].keys())); fields.add(k)
            if "range" in obj and isinstance(obj["range"], dict):
                k = next(iter(obj["range"].keys())); fields.add(k)
            for v in obj.values(): walk(v)
        elif isinstance(obj, list):
            for v in obj: walk(v)
    walk(dsl)
    return fields

def parse_iso(ts):
    # very simple ISO8601 Z parser
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)

def check_time_window(dsl, rules):
    required = rules.get("time_window", {}).get("required", False)
    max_days = rules.get("time_window", {}).get("max_days", None)
    
    # find a range on @timestamp
    rng = None
    def find_range(obj):
        nonlocal rng
        if isinstance(obj, dict):
            if "range" in obj and "@timestamp" in obj["range"]:
                rng = obj["range"]["@timestamp"]
            for v in obj.values(): find_range(v)
        elif isinstance(obj, list):
            for v in obj: find_range(v)
    find_range(dsl)
    
    # STRICT: Always require time window for security
    if not rng:
        return False, "missing_time_window_required_for_security"
    
    if rng and max_days:
        try:
            gte, lte = rng.get("gte"), rng.get("lte")
            if gte and lte and "now" not in gte and "now" not in lte:
                span = parse_iso(lte) - parse_iso(gte)
                if span.days > max_days:
                    return False, f"time_window_exceeds_{max_days}_days"
                # Additional check for suspiciously long ranges
                if span.days > 365:
                    return False, "time_window_suspiciously_long"
        except Exception:
            return False, "invalid_time_window_format"
    return True, None

def check_fields_types(dsl, allowed_fields, mapping_types):
    used = collect_fields(dsl)
    unknown = [f for f in used if f not in allowed_fields]
    if unknown:
        return False, f"unknown_fields:{unknown}"
    # crude type check for range on non-date/non-numeric
    def walk_ranges(obj):
        if isinstance(obj, dict) and "range" in obj:
            for f, cond in obj["range"].items():
                t = mapping_types.get(f)
                if t not in ("date","integer","long"):
                    return False, f"type_mismatch_range_on_{f}"
        if isinstance(obj, dict):
            for v in obj.values():
                ok = walk_ranges(v)
                if ok is not None and ok is False: return False
        if isinstance(obj, list):
            for v in obj:
                ok = walk_ranges(v)
                if ok is not None and ok is False: return False
        return True
    ok = walk_ranges(dsl)
    if ok is False:
        return False, "type_mismatch_range"
    return True, None

def check_cost(es, index, dsl, max_docs, max_percentage=75):
    q = dsl.get("query", {"match_all": {}})
    
    # SECURITY: Context-aware match_all validation
    if not q or "match_all" in q:
        # Allow match_all only if there are strong filters (time window, etc.)
        if _has_sufficient_constraints(dsl):
            print("INFO: match_all query allowed due to sufficient time/field constraints")
        else:
            return False, "match_all_query_requires_time_window_or_field_filters"
    
    # Check if query is too broad by estimating result count
    try:
        cnt = es.count(index=index, body={"query": q})
        if cnt["count"] > max_docs:
            return False, f"estimated_docs_{cnt['count']}_gt_{max_docs}"
        
        # Additional security: Block queries that return more than configured % of total docs
        total_docs = es.count(index=index)["count"]
        max_allowed_docs = (total_docs * max_percentage) / 100
        if total_docs > 0 and cnt["count"] > max_allowed_docs:
            return False, f"query_too_broad_returns_{cnt['count']}_of_{total_docs}_docs_exceeds_{max_percentage}%"
            
    except Exception as e:
        # If we can't estimate cost, be conservative and block
        return False, f"cannot_estimate_query_cost_{str(e)}"
    
    return True, None

def check_aggs_selectivity(dsl):
    if "aggs" in dsl or "aggregations" in dsl:
        # SELECTIVE: Allow safe aggregations with proper constraints
        aggs = dsl.get("aggs", dsl.get("aggregations", {}))
        
        # Allow basic aggregations commonly used in cybersecurity analysis
        if _validate_safe_aggregations(aggs, dsl):
            return True, None
        else:
            return False, "aggregation_validation_failed_security_check"
    return True, None

def _has_sufficient_constraints(dsl):
    """Check if query has sufficient constraints to allow match_all"""
    # Check for time window constraint
    has_time_window = False
    has_field_filters = False
    
    def find_constraints(obj):
        nonlocal has_time_window, has_field_filters
        if isinstance(obj, dict):
            # Check for time range on @timestamp
            if "range" in obj and "@timestamp" in obj.get("range", {}):
                has_time_window = True
            # Check for term/terms filters on key fields
            if "term" in obj or "terms" in obj:
                has_field_filters = True
            # Check for bool queries with must/should/filter clauses
            if "bool" in obj:
                bool_query = obj["bool"]
                if any(key in bool_query for key in ["must", "should", "filter"]):
                    has_field_filters = True
            for v in obj.values():
                find_constraints(v)
        elif isinstance(obj, list):
            for v in obj:
                find_constraints(v)
    
    find_constraints(dsl)
    
    # Require at least a time window for match_all queries
    return has_time_window

def _validate_safe_aggregations(aggs, dsl):
    """Validate that aggregations are safe for cybersecurity analysis"""
    # Allow specific safe aggregation patterns
    safe_agg_types = {
        "terms",       # Group by field values (IPs, ports, etc.)
        "date_histogram", # Time-based aggregations
        "histogram",   # Numeric histograms
        "cardinality", # Count unique values
        "sum", "avg", "min", "max", "stats", # Basic metrics
        "value_count"  # Count non-null values
    }
    
    # Check if query has time window (required for aggregations)
    if not _has_sufficient_constraints(dsl):
        return False
    
    def validate_agg_structure(agg_obj, depth=0):
        # Prevent deeply nested aggregations (potential DoS)
        if depth > 3:
            return False
            
        if isinstance(agg_obj, dict):
            for agg_name, agg_config in agg_obj.items():
                if isinstance(agg_config, dict):
                    # Check if this is a recognized safe aggregation type
                    agg_type = None
                    for safe_type in safe_agg_types:
                        if safe_type in agg_config:
                            agg_type = safe_type
                            break
                    
                    if not agg_type:
                        return False
                    
                    # For terms aggregations, limit size to prevent resource exhaustion
                    if agg_type == "terms":
                        terms_config = agg_config["terms"]
                        size = terms_config.get("size", 10)
                        if size > 1000:  # Reasonable limit for cybersecurity analysis
                            return False
                    
                    # Recursively validate sub-aggregations
                    if "aggs" in agg_config or "aggregations" in agg_config:
                        sub_aggs = agg_config.get("aggs", agg_config.get("aggregations", {}))
                        if not validate_agg_structure(sub_aggs, depth + 1):
                            return False
        return True
    
    return validate_agg_structure(aggs)

def main():
    """
    Command-line interface for rule-based query validation.
    
    Provides CLI access to the validation system for testing and batch processing
    of Elasticsearch DSL queries against configured validation rules.
    
    Command-line Arguments:
        --index: Target Elasticsearch index (default: from config)
        --dsl: Path to JSON file containing query to validate (required)
        --rules: Path to YAML validation rules file (default: artifacts/validator_rules.yaml)
        --user: Elasticsearch username for connection (default: from config)
        --password: Elasticsearch password (default: from config)
        
    Exit Codes:
        0: Query is valid and passes all rules
        1: Query validation failed with errors
        
    Output:
        Prints validation results to stdout, including:
        - Pass/fail status
        - Detailed error messages for failures
        - Document count estimation (if successful)
        
    Example:
        python validator.py --dsl query.json --rules rules.yaml --index logs_net
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=ES_DEFAULT_INDEX)
    ap.add_argument("--dsl", required=True, help="Path to DSL JSON to validate")
    ap.add_argument("--rules", default="artifacts/validator_rules.yaml")
    ap.add_argument("--user", default=ES_READER_CREDS['user'])
    ap.add_argument("--password", default=ES_READER_CREDS['password'])
    args = ap.parse_args()

    es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=30)
    dsl = json.load(open(args.dsl))
    rules = load_rules(args.rules)

    # mapping types from ES (for type checks)
    mapping = es.indices.get_mapping(index=args.index)
    props = mapping[args.index]["mappings"]["properties"]
    mapping_types = {k: v.get("type") for k, v in props.items()}
    # Handle both formats for backwards compatibility
    if "fields" in rules and "allowed" in rules["fields"]:
        allowed_fields = set(rules["fields"]["allowed"])
    elif "allowed_fields" in rules:
        allowed_fields = set(rules["allowed_fields"])
    else:
        allowed_fields = set()  # Empty set if not defined

    # Log validation events
    log_dir = Path("artifacts/results")
    log_dir.mkdir(parents=True, exist_ok=True)
    events_file = log_dir / "validator_events.jsonl"
    
    checks = []
    for fn in [
        lambda: check_time_window(dsl, rules),
        lambda: check_fields_types(dsl, allowed_fields, mapping_types),
        lambda: check_aggs_selectivity(dsl),
        lambda: check_cost(es, args.index, dsl, rules["cost"]["max_docs"], rules["cost"].get("max_percentage", 75)),
    ]:
        ok, reason = fn()
        checks.append((ok, reason))
        
        # Log the event
        event = {
            "timestamp": datetime.now().isoformat(),
            "dsl_file": args.dsl,
            "check_passed": ok,
            "failure_category": reason if not ok else None
        }
        
        with open(events_file, 'a') as f:
            f.write(json.dumps(event) + "\n")
        
        if not ok:
            result = {"ok": False, "reason": reason, "suggested_critique": f"Please add/adjust to satisfy rule: {reason}"}
            print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            return

    # Log success
    event = {
        "timestamp": datetime.now().isoformat(),
        "dsl_file": args.dsl,
        "check_passed": True,
        "failure_category": None
    }
    with open(events_file, 'a') as f:
        f.write(json.dumps(event) + "\n")
    
    print(orjson.dumps({"ok": True, "reason": None}, option=orjson.OPT_INDENT_2).decode())

if __name__ == "__main__":
    main()

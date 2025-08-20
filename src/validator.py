#!/usr/bin/env python3
import argparse, json, math, re, datetime as dt, orjson, yaml
import sys
import os
from pathlib import Path
from datetime import datetime
from elasticsearch import Elasticsearch

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX
except ImportError:
    # If direct import fails, try relative import
    from .config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX

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

def check_cost(es, index, dsl, max_docs):
    q = dsl.get("query", {"match_all": {}})
    
    # SECURITY: Block match_all queries entirely (too broad)
    if not q or "match_all" in q:
        return False, "match_all_query_blocked_for_security"
    
    # Check if query is too broad by estimating result count
    try:
        cnt = es.count(index=index, body={"query": q})
        if cnt["count"] > max_docs:
            return False, f"estimated_docs_{cnt['count']}_gt_{max_docs}"
        
        # Additional security: Block queries that return more than 50% of total docs
        total_docs = es.count(index=index)["count"]
        if total_docs > 0 and cnt["count"] > (total_docs * 0.5):
            return False, f"query_too_broad_returns_{cnt['count']}_of_{total_docs}_docs"
            
    except Exception as e:
        # If we can't estimate cost, be conservative and block
        return False, f"cannot_estimate_query_cost_{str(e)}"
    
    return True, None

def check_aggs_selectivity(dsl):
    if "aggs" in dsl or "aggregations" in dsl:
        # STRICT: Block all aggregations as potential resource exhaustion vector
        return False, "aggregations_blocked_for_security"
    return True, None

def main():
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
    allowed_fields = set(rules["fields"]["allowed"])

    # Log validation events
    log_dir = Path("artifacts/results")
    log_dir.mkdir(parents=True, exist_ok=True)
    events_file = log_dir / "validator_events.jsonl"
    
    checks = []
    for fn in [
        lambda: check_time_window(dsl, rules),
        lambda: check_fields_types(dsl, allowed_fields, mapping_types),
        lambda: check_aggs_selectivity(dsl),
        lambda: check_cost(es, args.index, dsl, rules["cost"]["max_docs"]),
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

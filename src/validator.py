#!/usr/bin/env python3
import argparse, json, math, re, datetime as dt, orjson, yaml
from elasticsearch import Elasticsearch

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
    if required and not rng:
        return False, "missing_time_window"
    if rng and max_days:
        try:
            gte, lte = rng.get("gte"), rng.get("lte")
            if gte and lte and "now" not in gte and "now" not in lte:
                span = parse_iso(lte) - parse_iso(gte)
                if span.days > max_days:
                    return False, f"time_window_exceeds_{max_days}_days"
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
    cnt = es.count(index=index, body={"query": q})
    if cnt["count"] > max_docs:
        return False, f"estimated_docs_{cnt['count']}_gt_{max_docs}"
    return True, None

def check_aggs_selectivity(dsl):
    if "aggs" in dsl or "aggregations" in dsl:
        # require some filter beyond match_all
        q = dsl.get("query", {})
        if not q or "match_all" in q:
            return False, "aggs_without_selective_query"
    return True, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="logs_net")
    ap.add_argument("--dsl", required=True, help="Path to DSL JSON to validate")
    ap.add_argument("--rules", default="artifacts/validator_rules.yaml")
    ap.add_argument("--user", default="reader")
    ap.add_argument("--password", default="ReaderPwd_123")
    args = ap.parse_args()

    es = Elasticsearch("http://localhost:9200", basic_auth=(args.user, args.password), request_timeout=30)
    dsl = json.load(open(args.dsl))
    rules = load_rules(args.rules)

    # mapping types from ES (for type checks)
    mapping = es.indices.get_mapping(index=args.index)
    props = mapping[args.index]["mappings"]["properties"]
    mapping_types = {k: v.get("type") for k, v in props.items()}
    allowed_fields = set(rules["fields"]["allowed"])

    checks = []
    for fn in [
        lambda: check_time_window(dsl, rules),
        lambda: check_fields_types(dsl, allowed_fields, mapping_types),
        lambda: check_aggs_selectivity(dsl),
        lambda: check_cost(es, args.index, dsl, rules["cost"]["max_docs"]),
    ]:
        ok, reason = fn()
        checks.append((ok, reason))
        if not ok:
            result = {"ok": False, "reason": reason, "suggested_critique": f"Please add/adjust to satisfy rule: {reason}"}
            print(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
            return

    print(orjson.dumps({"ok": True, "reason": None}, option=orjson.OPT_INDENT_2).decode())

if __name__ == "__main__":
    main()

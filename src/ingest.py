#!/usr/bin/env python3
import argparse, pathlib, hashlib, orjson, pandas as pd
from elasticsearch import Elasticsearch, helpers
from config import get_es_client_config, ES_ADMIN_CREDS, ES_DEFAULT_INDEX

def make_id(row: dict) -> str:
    # Deterministic ID from a stable subset of fields
    key = orjson.dumps({
        "@timestamp": row.get("@timestamp"),
        "src_ip": row.get("src_ip"),
        "dst_ip": row.get("dst_ip"),
        "src_port": row.get("src_port"),
        "dst_port": row.get("dst_port"),
        "protocol": row.get("protocol"),
        "bytes_in": row.get("bytes_in"),
        "bytes_out": row.get("bytes_out"),
        "label": row.get("label"),
    }, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha1(key).hexdigest()

def gen_actions(df: pd.DataFrame, index: str):
    for rec in df.to_dict(orient="records"):
        rec["@timestamp"] = pd.to_datetime(rec["@timestamp"], utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
        yield {"_op_type":"index", "_index": index, "_id": make_id(rec), "_source": rec}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="CSV file with columns matching mappings.json")
    ap.add_argument("--index", default=ES_DEFAULT_INDEX)
    ap.add_argument("--user", default=ES_ADMIN_CREDS['user'])
    ap.add_argument("--password", default=ES_ADMIN_CREDS['password'])
    args = ap.parse_args()

    es = Elasticsearch("http://localhost:9200", basic_auth=(args.user, args.password), request_timeout=60)

    # Create index if missing (expects you already PUT artifacts/mappings.json)
    if not es.indices.exists(index=args.index):
        raise SystemExit(f"Index {args.index} does not exist. Create it first with mappings.json.")

    df = pd.read_csv(args.file)
    ok, fail = helpers.bulk(es.options(request_timeout=120), gen_actions(df, args.index), stats_only=True)
    es.indices.refresh(index=args.index)
    print(f"Ingested: ok={ok}, failed={fail}")

if __name__ == "__main__":
    main()

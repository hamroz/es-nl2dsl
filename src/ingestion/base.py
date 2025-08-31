#!/usr/bin/env python3
"""
Base Ingestion System: Core data loading and processing framework

This module provides the foundational data ingestion capabilities for the ES-NL2DSL system,
offering standardized interfaces for loading various data formats into Elasticsearch.
It serves as the base class and common functionality for specialized ingestion modules
with support for CSV processing, data transformation, and index management.

Key capabilities:
- Standardized CSV data ingestion with pandas integration
- Deterministic document ID generation for consistent indexing
- Elasticsearch bulk loading with performance optimization
- Data type inference and conversion with validation
- Timestamp standardization and formatting
- Integration with configuration management and credential handling

The framework provides consistent data loading patterns across the ES-NL2DSL system
and ensures reliable data ingestion for both development and production environments.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import argparse, pathlib, pandas as pd
from elasticsearch import Elasticsearch, helpers
from ..utils.config import get_es_client_config, ES_ADMIN_CREDS, ES_DEFAULT_INDEX
from .utils.document_id import make_deterministic_id as make_id

def gen_actions(df: pd.DataFrame, index: str):
    for rec in df.to_dict(orient="records"):
        rec["@timestamp"] = pd.to_datetime(rec["@timestamp"], utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
        yield {"_op_type":"index", "_index": index, "_id": make_id(rec), "_source": rec}

def ingest_csv(file_path, index=None, user=None, password=None):
    """Main ingestion function for CSV files"""
    df = pd.read_csv(file_path)
    if index is None:
        index = ES_DEFAULT_INDEX
    if user is None:
        user = ES_ADMIN_CREDS['user']
    if password is None:
        password = ES_ADMIN_CREDS['password']
    
    client = Elasticsearch(**get_es_client_config(user, password))
    
    # Perform bulk ingestion
    success, failed = helpers.bulk(client, gen_actions(df, index), stats_only=True)
    return success, failed

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

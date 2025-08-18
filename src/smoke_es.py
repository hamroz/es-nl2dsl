# src/smoke_es.py
from elasticsearch import Elasticsearch
from config import get_es_client_config, ES_DEFAULT_INDEX

# Connect as read-only user
es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=30)

# --- Index-level connectivity check (instead of es.ping()) ---
try:
    mapping = es.indices.get_mapping(index=ES_DEFAULT_INDEX)
    assert "mappings" in mapping[ES_DEFAULT_INDEX], "Failed to retrieve mapping"
    print(f"Connected to {ES_DEFAULT_INDEX}; fields:",
          list(mapping[ES_DEFAULT_INDEX]["mappings"]["properties"].keys()))
except Exception as e:
    raise SystemExit(f"Index-level connectivity check failed: {e}")

# --- Read query the reader is allowed to run ---
try:
    res = es.search(index=ES_DEFAULT_INDEX, query={"term": {"label": "malicious"}}, size=100)
    hits_total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
    ids = [h["_id"] for h in res["hits"]["hits"]]
    print(f"Hits total: {hits_total}; IDs: {ids}")
except Exception as e:
    raise SystemExit(f"Search failed: {e}")

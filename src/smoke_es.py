# src/smoke_es.py
from elasticsearch import Elasticsearch

# Connect as read-only user
es = Elasticsearch(
    "http://localhost:9200",
    basic_auth=("reader", "ReaderPwd_123"),
    request_timeout=30,
)

# --- Index-level connectivity check (instead of es.ping()) ---
try:
    mapping = es.indices.get_mapping(index="logs_net")
    assert "mappings" in mapping["logs_net"], "Failed to retrieve mapping"
    print("Connected to logs_net; fields:",
          list(mapping["logs_net"]["mappings"]["properties"].keys()))
except Exception as e:
    raise SystemExit(f"Index-level connectivity check failed: {e}")

# --- Read query the reader is allowed to run ---
try:
    res = es.search(index="logs_net", query={"term": {"label": "malicious"}}, size=100)
    hits_total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
    ids = [h["_id"] for h in res["hits"]["hits"]]
    print(f"Hits total: {hits_total}; IDs: {ids}")
except Exception as e:
    raise SystemExit(f"Search failed: {e}")

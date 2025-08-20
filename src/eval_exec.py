#!/usr/bin/env python3
import argparse, json, time, pathlib, orjson
import sys
import os
from elasticsearch import Elasticsearch

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX
except ImportError:
    # If direct import fails, try relative import
    from .config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX

def run_query(es, index, dsl: dict, size=10000):
    res = es.search(index=index, body=dsl, size=size, track_total_hits=True)
    ids = sorted({h["_id"] for h in res["hits"]["hits"]})
    total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
    return ids, total

def jaccard(a, b):
    A, B = set(a), set(b)
    return len(A & B) / len(A | B) if (A or B) else 1.0

def prf1(pred, gold):
    P, G = set(pred), set(gold)
    tp = len(P & G); p = tp/len(P) if P else (1.0 if not G else 0.0)
    r  = tp/len(G) if G else (1.0 if not P else 0.0)
    f1 = (2*p*r/(p+r)) if (p+r) else 1.0
    return p, r, f1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=ES_DEFAULT_INDEX)
    ap.add_argument("--expert", required=True, help="Path to expert DSL JSON")
    ap.add_argument("--candidate", required=True, help="Path to candidate DSL JSON")
    ap.add_argument("--out", default="artifacts/results")
    ap.add_argument("--user", default=ES_READER_CREDS['user'])
    ap.add_argument("--password", default=ES_READER_CREDS['password'])
    args = ap.parse_args()

    es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=60)

    expert = json.load(open(args.expert))
    cand   = json.load(open(args.candidate))

    exp_ids, _ = run_query(es, args.index, expert)
    can_ids, _ = run_query(es, args.index, cand)

    jac = jaccard(exp_ids, can_ids)
    p, r, f1 = prf1(can_ids, exp_ids)  # candidate vs expert as "gold"

    outdir = pathlib.Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    rec = {
        "index": args.index,
        "expert_ids": exp_ids,
        "candidate_ids": can_ids,
        "jaccard": jac, "precision": p, "recall": r, "f1": f1,
        "ts": stamp,
    }
    outpath = outdir / f"eval_{stamp}.json"
    outpath.write_bytes(orjson.dumps(rec, option=orjson.OPT_INDENT_2))
    print(f"Wrote {outpath}"); print(orjson.dumps(rec, option=orjson.OPT_INDENT_2).decode())

def execute_query(dsl: dict, index: str = ES_DEFAULT_INDEX, size: int = 10000):
    """Execute a query and return results - for use by enhanced_evaluation"""
    try:
        es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=60)
        ids, total = run_query(es, index, dsl, size)
        return {'ids': ids, 'total': total}
    except Exception as e:
        print(f"Error executing query: {e}")
        return None

def calculate_metrics(expected_results, generated_results):
    """Calculate evaluation metrics - for use by enhanced_evaluation"""
    if not expected_results or not generated_results:
        return {
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'jaccard_similarity': 0.0
        }
    
    exp_ids = expected_results.get('ids', [])
    gen_ids = generated_results.get('ids', [])
    
    jac = jaccard(exp_ids, gen_ids)
    p, r, f1 = prf1(gen_ids, exp_ids)
    
    return {
        'precision': p,
        'recall': r,
        'f1_score': f1,
        'jaccard_similarity': jac
    }

if __name__ == "__main__":
    main()

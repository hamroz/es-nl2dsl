#!/usr/bin/env python3
import argparse, json, time, pathlib, orjson
import sys
import os
from elasticsearch import Elasticsearch
from enum import Enum
import elasticsearch.exceptions as es_exceptions

class ErrorType(Enum):
    """Types of errors that can occur during query execution"""
    FIELD_VALIDATION = "field_validation"
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    PERMISSION = "permission"
    INDEX_NOT_FOUND = "index_not_found"
    UNKNOWN = "unknown"

class QueryExecutionError:
    """Structured error information for query execution failures"""
    def __init__(self, error_type: ErrorType, message: str, query=None, details=None):
        self.error_type = error_type
        self.message = message
        self.query = query
        self.details = details or {}
    
    def to_dict(self):
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details
        }

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX
except ImportError:
    # If direct import fails, try relative import
    from .config import get_es_client_config, ES_READER_CREDS, ES_DEFAULT_INDEX

def run_query(es, index, dsl: dict, size=10000):
    """Execute a query with proper error handling and error classification."""
    error_info = None
    try:
        # Remove 'size' from dsl if it exists to avoid conflict
        query_dsl = dsl.copy()
        if 'size' in query_dsl:
            # Use the size from the query if specified
            query_size = query_dsl.pop('size')
            size = min(query_size, size)  # Use the smaller of the two
        
        # Use the newer search API format
        res = es.search(index=index, query=query_dsl.get('query'), size=size, track_total_hits=True)
        ids = sorted({h["_id"] for h in res["hits"]["hits"]})
        total = res["hits"]["total"]["value"] if isinstance(res["hits"]["total"], dict) else res["hits"]["total"]
        return ids, total, error_info
    except es_exceptions.RequestError as e:
        # Parse the error to determine type
        error_msg = str(e)
        if "field" in error_msg.lower() and ("not found" in error_msg.lower() or "no mapping" in error_msg.lower()):
            error_info = QueryExecutionError(
                ErrorType.FIELD_VALIDATION,
                f"Field validation error: {e}",
                query=dsl,
                details={"elasticsearch_error": e.info if hasattr(e, 'info') else str(e)}
            )
        elif "parse" in error_msg.lower() or "json" in error_msg.lower():
            error_info = QueryExecutionError(
                ErrorType.SYNTAX_ERROR,
                f"Query syntax error: {e}",
                query=dsl,
                details={"elasticsearch_error": e.info if hasattr(e, 'info') else str(e)}
            )
        else:
            error_info = QueryExecutionError(
                ErrorType.SYNTAX_ERROR,
                f"Request error: {e}",
                query=dsl,
                details={"elasticsearch_error": e.info if hasattr(e, 'info') else str(e)}
            )
        print(f"Query execution failed - {error_info.error_type.value}: {error_info.message}")
        return [], 0, error_info
    except es_exceptions.ConnectionError as e:
        error_info = QueryExecutionError(
            ErrorType.CONNECTION,
            f"Connection error: {e}",
            query=dsl
        )
        print(f"Query execution failed - {error_info.error_type.value}: {error_info.message}")
        return [], 0, error_info
    except Exception as e:
        # Check for specific patterns in error message
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            error_info = QueryExecutionError(
                ErrorType.TIMEOUT,
                f"Query timeout: {e}",
                query=dsl
            )
        elif "index_not_found" in error_msg.lower():
            error_info = QueryExecutionError(
                ErrorType.INDEX_NOT_FOUND,
                f"Index not found: {e}",
                query=dsl
            )
        elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
            error_info = QueryExecutionError(
                ErrorType.PERMISSION,
                f"Permission denied: {e}",
                query=dsl
            )
        else:
            error_info = QueryExecutionError(
                ErrorType.UNKNOWN,
                f"Unknown error: {e}",
                query=dsl
            )
        print(f"Query execution failed - {error_info.error_type.value}: {error_info.message}")
        return [], 0, error_info

def jaccard(a, b):
    A, B = set(a), set(b)
    return len(A & B) / len(A | B) if (A or B) else 1.0

def prf1(pred, gold):
    """Calculate precision, recall, and F1 score.
    Fixed to properly handle edge cases where one or both sets are empty.
    """
    P, G = set(pred), set(gold)
    
    # Both empty = perfect match (no expected, none returned)
    if not P and not G:
        return 1.0, 1.0, 1.0
    
    # One empty = complete failure
    if not P or not G:
        return 0.0, 0.0, 0.0
    
    # Normal calculation
    tp = len(P & G)
    p = tp / len(P)
    r = tp / len(G)
    f1 = (2*p*r/(p+r)) if (p+r) > 0 else 0.0
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

    # Load queries and handle ground truth format
    with open(args.expert) as f:
        expert_data = json.load(f)
    with open(args.candidate) as f:
        cand_data = json.load(f)
    
    # Extract actual query from ground truth format if needed
    if isinstance(expert_data, dict) and 'expert_dsl' in expert_data:
        expert = expert_data['expert_dsl']
    else:
        expert = expert_data
        
    if isinstance(cand_data, dict) and 'candidate_dsl' in cand_data:
        cand = cand_data['candidate_dsl']
    else:
        cand = cand_data

    start_time = time.time()
    exp_ids, exp_total, exp_error = run_query(es, args.index, expert)
    can_start = time.time()
    can_ids, can_total, can_error = run_query(es, args.index, cand)
    can_execution_time = (time.time() - can_start) * 1000  # Convert to ms

    # Traditional metrics for backward compatibility
    jac = jaccard(exp_ids, can_ids)
    p, r, f1 = prf1(can_ids, exp_ids)  # candidate vs expert as "gold"
    
    # Enhanced metrics
    enhanced_metrics = enhanced_calculate_metrics(
        expert, cand, exp_ids, can_ids, can_execution_time
    )

    outdir = pathlib.Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time())
    rec = {
        "index": args.index,
        "expert_ids": exp_ids,
        "expert_total": exp_total,
        "expert_error": exp_error.to_dict() if exp_error else None,
        "candidate_ids": can_ids,
        "candidate_total": can_total,
        "candidate_error": can_error.to_dict() if can_error else None,
        # Traditional metrics (for backward compatibility)
        "jaccard": jac, "precision": p, "recall": r, "f1": f1,
        # Enhanced metrics
        "enhanced_metrics": enhanced_metrics,
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

def enhanced_calculate_metrics(expert_query, candidate_query, expert_ids, candidate_ids, 
                             execution_time=None):
    """Calculate enhanced metrics using the new evaluation system"""
    try:
        # Import the enhanced evaluation system
        from enhanced_evaluation import enhanced_evaluate_query
        
        # Perform enhanced evaluation
        enhanced_metrics = enhanced_evaluate_query(
            candidate_query, expert_query,
            candidate_ids, expert_ids,
            execution_time
        )
        
        return enhanced_metrics.to_dict()
    except ImportError:
        # Fallback to traditional metrics if enhanced evaluation not available
        print("Enhanced evaluation not available, using traditional metrics")
        jac = jaccard(expert_ids, candidate_ids)
        p, r, f1 = prf1(candidate_ids, expert_ids)
        
        return {
            "traditional": {
                "jaccard_similarity": jac,
                "precision": p,
                "recall": r,
                "f1_score": f1
            },
            "enhanced": {
                "semantic_similarity": None,
                "comprehensiveness_score": None,
                "efficiency_score": None,
                "quality_level": "unknown"
            },
            "execution": {
                "execution_time_ms": execution_time,
                "result_count": len(candidate_ids)
            }
        }

if __name__ == "__main__":
    main()

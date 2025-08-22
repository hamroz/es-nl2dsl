"""
Evaluation utilities that integrate with existing evaluation scripts
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from django.conf import settings
import requests
import tempfile

def normalize_clause(c):
    """Normalize a single query clause for AST comparison"""
    if "term" in c:
        k, v = next(iter(c["term"].items()))
        return ("term", k, str(v))
    if "range" in c:
        k, cond = next(iter(c["range"].items()))
        return ("range", k, cond.get("gte"), cond.get("lte"))
    return ("other", json.dumps(c, sort_keys=True))

def flatten_bool(dsl):
    """Flatten boolean query structure for comparison"""
    q = dsl.get("query", {})
    b = q.get("bool", {})
    flt = b.get("filter", []) + b.get("must", [])
    return tuple(sorted([normalize_clause(x) for x in flt]))

def calculate_ast_similarity(query_a, query_b):
    """
    Calculate AST similarity between two queries
    Returns: dict with ast_exact and clause_f1 metrics
    """
    try:
        na, nb = flatten_bool(query_a), flatten_bool(query_b)
        exact = na == nb
        inter = set(na) & set(nb)
        union = set(na) | set(nb)
        clause_f1 = (2 * len(inter) / (len(na) + len(nb))) if (len(na) + len(nb)) else 1.0
        
        return {
            "ast_exact": exact,
            "clause_f1": clause_f1,
            "jaccard_similarity": len(inter) / len(union) if union else 1.0
        }
    except Exception as e:
        return {
            "ast_exact": False,
            "clause_f1": 0.0,
            "jaccard_similarity": 0.0,
            "error": str(e)
        }

def execute_query_for_evaluation(query, index, max_size=1000):
    """
    Execute a query against Elasticsearch for evaluation purposes
    """
    try:
        es_url = f"http://{settings.ELASTICSEARCH_HOST}/{index}/_search"
        auth = (settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)
        
        es_query = {
            "size": max_size,
            **query
        }
        
        start_time = time.time()
        response = requests.post(
            es_url,
            json=es_query,
            auth=auth,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        execution_time = int((time.time() - start_time) * 1000)
        
        if response.status_code != 200:
            raise RuntimeError(f"Elasticsearch error: {response.text}")
        
        es_result = response.json()
        hits = es_result.get('hits', {})
        total_hits = hits.get('total', {}).get('value', 0)
        documents = hits.get('hits', [])
        
        # Extract document IDs for result comparison
        doc_ids = [doc.get('_id') for doc in documents]
        
        return {
            'total_hits': total_hits,
            'returned_hits': len(documents),
            'execution_time_ms': execution_time,
            'doc_ids': doc_ids,
            'success': True
        }
        
    except Exception as e:
        return {
            'total_hits': 0,
            'returned_hits': 0,
            'execution_time_ms': 0,
            'doc_ids': [],
            'success': False,
            'error': str(e)
        }

def calculate_execution_metrics(expert_results, generated_results):
    """
    Calculate precision, recall, F1 score between expert and generated query results
    """
    try:
        expert_ids = set(expert_results.get('doc_ids', []))
        generated_ids = set(generated_results.get('doc_ids', []))
        
        if not expert_ids and not generated_ids:
            return {'precision': 1.0, 'recall': 1.0, 'f1_score': 1.0}
        
        if not expert_ids:
            return {'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0}
        
        if not generated_ids:
            return {'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0}
        
        intersection = expert_ids & generated_ids
        
        precision = len(intersection) / len(generated_ids) if generated_ids else 0.0
        recall = len(intersection) / len(expert_ids) if expert_ids else 0.0
        f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) else 0.0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'jaccard_similarity': len(intersection) / len(expert_ids | generated_ids)
        }
        
    except Exception as e:
        return {
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'jaccard_similarity': 0.0,
            'error': str(e)
        }

def run_validation_for_evaluation(query_data):
    """
    Run validation on a query for evaluation purposes
    """
    try:
        project_root = settings.BASE_DIR.parent
        
        # Create temporary file for the query
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(query_data, f, indent=2)
            temp_file = f.name
        
        try:
            cmd = [
                sys.executable,
                str(project_root / "src" / "validator.py"),
                "--dsl", temp_file,
                "--rules", str(project_root / "artifacts" / "validator_rules.yaml")
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(project_root)
            )
            
            if result.returncode == 0:
                return {'valid': True, 'errors': []}
            else:
                errors = result.stderr.strip().split('\n') if result.stderr else ['Validation failed']
                return {'valid': False, 'errors': errors}
                
        finally:
            # Clean up temp file
            Path(temp_file).unlink(missing_ok=True)
            
    except Exception as e:
        return {'valid': False, 'errors': [f'Validation error: {str(e)}']}
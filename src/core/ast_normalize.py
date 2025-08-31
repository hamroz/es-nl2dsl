#!/usr/bin/env python3
"""
AST Normalizer: Query structure comparison and semantic similarity analysis

This module provides advanced Abstract Syntax Tree (AST) normalization capabilities
for comparing Elasticsearch DSL queries at a structural level. It enables semantic
comparison of queries by normalizing their structure and extracting comparable
features, supporting evaluation frameworks and query similarity analysis.

Key capabilities:
- Query structure normalization with clause-level decomposition
- Semantic equivalence detection ignoring syntactic differences
- Boolean query flattening with standardized clause ordering
- Term and range query normalization with consistent representation
- Structural comparison metrics for evaluation frameworks
- Integration with evaluation pipelines for query similarity assessment

The normalizer is essential for evaluation frameworks that need to compare
queries based on their semantic meaning rather than exact syntactic structure.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import argparse, json

def normalize_clause(c):
    if "term" in c:
        k, v = next(iter(c["term"].items()))
        return ("term", k, str(v))
    if "range" in c:
        k, cond = next(iter(c["range"].items()))
        return ("range", k, cond.get("gte"), cond.get("lte"))
    return ("other", json.dumps(c, sort_keys=True))

def flatten_bool(dsl):
    q = dsl.get("query", {})
    b = q.get("bool", {})
    flt = b.get("filter", []) + b.get("must", [])
    return tuple(sorted([normalize_clause(x) for x in flt]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    args = ap.parse_args()
    A = json.load(open(args.a)); B = json.load(open(args.b))
    na, nb = flatten_bool(A), flatten_bool(B)
    exact = na == nb
    inter = set(na) & set(nb); union = set(na) | set(nb)
    clause_f1 = (2*len(inter)/ (len(na)+len(nb))) if (len(na)+len(nb)) else 1.0
    print(json.dumps({"ast_exact": exact, "clause_f1": clause_f1}, indent=2))

if __name__ == "__main__":
    main()

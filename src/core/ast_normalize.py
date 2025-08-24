#!/usr/bin/env python3
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

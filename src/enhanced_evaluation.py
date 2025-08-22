#!/usr/bin/env python3
"""Enhanced evaluation methodology for comprehensive query assessment"""
import json
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum

class QueryQuality(Enum):
    """Quality assessment levels for generated queries"""
    PERFECT = "perfect"  # Exact semantic match
    COMPREHENSIVE = "comprehensive"  # More complete than ground truth
    EQUIVALENT = "equivalent"  # Different structure, same results
    PARTIAL = "partial"  # Captures some but not all requirements
    INCORRECT = "incorrect"  # Wrong results or approach
    INVALID = "invalid"  # Syntax errors or execution failures

@dataclass
class EvaluationMetrics:
    """Enhanced metrics for query evaluation"""
    # Traditional metrics
    jaccard_similarity: float
    precision: float
    recall: float
    f1_score: float
    
    # New comprehensive metrics
    semantic_similarity: float  # AST-based semantic comparison
    comprehensiveness_score: float  # How comprehensive vs ground truth
    efficiency_score: float  # Query complexity vs results
    quality_level: QueryQuality
    
    # Execution metrics
    execution_time_ms: Optional[float] = None
    result_count: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "traditional": {
                "jaccard_similarity": self.jaccard_similarity,
                "precision": self.precision,
                "recall": self.recall,
                "f1_score": self.f1_score
            },
            "enhanced": {
                "semantic_similarity": self.semantic_similarity,
                "comprehensiveness_score": self.comprehensiveness_score,
                "efficiency_score": self.efficiency_score,
                "quality_level": self.quality_level.value
            },
            "execution": {
                "execution_time_ms": self.execution_time_ms,
                "result_count": self.result_count
            }
        }

class SemanticQueryAnalyzer:
    """Analyzes query semantics beyond simple AST comparison"""
    
    def __init__(self):
        # Core semantic components every query should have
        self.core_components = {
            "time_filter": ["range", "@timestamp"],
            "field_filters": ["term", "terms"],
            "logical_structure": ["bool", "filter", "must", "should"]
        }
    
    def extract_semantic_components(self, query: Dict) -> Dict[str, Any]:
        """Extract semantic components from a query"""
        components = {
            "time_constraints": [],
            "field_constraints": [],
            "logical_operators": [],
            "aggregations": [],
            "complexity_score": 0
        }
        
        def analyze_clause(clause, context=""):
            if isinstance(clause, dict):
                for key, value in clause.items():
                    if key == "range" and "@timestamp" in str(value):
                        components["time_constraints"].append(value)
                        components["complexity_score"] += 1
                    elif key in ["term", "terms", "match"]:
                        components["field_constraints"].append({key: value})
                        components["complexity_score"] += 1
                    elif key in ["bool", "filter", "must", "should"]:
                        components["logical_operators"].append(key)
                        if isinstance(value, list):
                            for sub_clause in value:
                                analyze_clause(sub_clause, f"{context}.{key}")
                        else:
                            analyze_clause(value, f"{context}.{key}")
                    elif key == "aggs":
                        components["aggregations"].append(value)
                        components["complexity_score"] += 2
        
        analyze_clause(query)
        return components
    
    def calculate_semantic_similarity(self, generated: Dict, ground_truth: Dict) -> float:
        """Calculate semantic similarity between queries"""
        gen_components = self.extract_semantic_components(generated)
        truth_components = self.extract_semantic_components(ground_truth)
        
        similarities = []
        
        # Time constraint similarity
        if truth_components["time_constraints"] and gen_components["time_constraints"]:
            # Both have time constraints - check overlap
            similarities.append(0.8)  # Good - both handle time
        elif not truth_components["time_constraints"] and not gen_components["time_constraints"]:
            similarities.append(1.0)  # Both don't use time (perfect match)
        else:
            similarities.append(0.3)  # One has time constraint, other doesn't
        
        # Field constraint similarity
        truth_fields = set()
        gen_fields = set()
        
        for constraint in truth_components["field_constraints"]:
            for op, fields in constraint.items():
                if isinstance(fields, dict):
                    truth_fields.update(fields.keys())
        
        for constraint in gen_components["field_constraints"]:
            for op, fields in constraint.items():
                if isinstance(fields, dict):
                    gen_fields.update(fields.keys())
        
        if truth_fields and gen_fields:
            field_overlap = len(truth_fields & gen_fields) / len(truth_fields | gen_fields)
            similarities.append(field_overlap)
        elif not truth_fields and not gen_fields:
            similarities.append(1.0)
        else:
            similarities.append(0.0)
        
        # Logical structure similarity
        truth_logic = set(truth_components["logical_operators"])
        gen_logic = set(gen_components["logical_operators"])
        
        if truth_logic and gen_logic:
            logic_overlap = len(truth_logic & gen_logic) / len(truth_logic | gen_logic)
            similarities.append(logic_overlap)
        elif not truth_logic and not gen_logic:
            similarities.append(1.0)
        else:
            similarities.append(0.5)  # Different logical structure
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def calculate_comprehensiveness_score(self, generated: Dict, ground_truth: Dict, 
                                        generated_results: List, truth_results: List) -> float:
        """Calculate how comprehensive the generated query is vs ground truth"""
        gen_components = self.extract_semantic_components(generated)
        truth_components = self.extract_semantic_components(ground_truth)
        
        # Base score from complexity comparison
        truth_complexity = truth_components["complexity_score"]
        gen_complexity = gen_components["complexity_score"]
        
        if truth_complexity == 0:
            complexity_ratio = 1.0
        else:
            complexity_ratio = min(gen_complexity / truth_complexity, 2.0)  # Cap at 2x
        
        # Adjust based on result coverage
        if truth_results and generated_results:
            truth_set = set(truth_results)
            gen_set = set(generated_results)
            
            # If generated query finds all expected results plus more
            if truth_set.issubset(gen_set):
                coverage_bonus = 1.2  # Bonus for being comprehensive
            elif len(gen_set & truth_set) / len(truth_set) > 0.8:
                coverage_bonus = 1.0  # Good coverage
            else:
                coverage_bonus = 0.8  # Incomplete coverage
        else:
            coverage_bonus = 1.0
        
        return min(complexity_ratio * coverage_bonus, 2.0)  # Cap at 2.0
    
    def assess_query_quality(self, generated: Dict, ground_truth: Dict,
                           generated_results: List, truth_results: List,
                           semantic_similarity: float, comprehensiveness: float) -> QueryQuality:
        """Assess overall query quality level"""
        
        if not generated_results and not truth_results:
            return QueryQuality.PERFECT  # Both return nothing (edge case)
        
        if not generated_results:
            return QueryQuality.INCORRECT  # Generated query returns nothing
        
        if not truth_results:
            if len(generated_results) > 0:
                return QueryQuality.COMPREHENSIVE  # Generated finds results where ground truth doesn't
        
        truth_set = set(truth_results) if truth_results else set()
        gen_set = set(generated_results) if generated_results else set()
        
        # Perfect match
        if truth_set == gen_set and semantic_similarity > 0.9:
            return QueryQuality.PERFECT
        
        # Comprehensive (superset with good semantic similarity)
        if truth_set.issubset(gen_set) and semantic_similarity > 0.7 and comprehensiveness > 1.1:
            return QueryQuality.COMPREHENSIVE
        
        # Equivalent (same results, different approach)
        if truth_set == gen_set:
            return QueryQuality.EQUIVALENT
        
        # Partial match
        overlap_ratio = len(truth_set & gen_set) / len(truth_set) if truth_set else 0
        if overlap_ratio > 0.6:
            return QueryQuality.PARTIAL
        
        # Incorrect
        return QueryQuality.INCORRECT

def enhanced_evaluate_query(generated_query: Dict, ground_truth_query: Dict,
                          generated_results: List, ground_truth_results: List,
                          execution_time: Optional[float] = None) -> EvaluationMetrics:
    """Perform enhanced evaluation of a query"""
    
    analyzer = SemanticQueryAnalyzer()
    
    # Traditional metrics
    gen_set = set(generated_results) if generated_results else set()
    truth_set = set(ground_truth_results) if ground_truth_results else set()
    
    if not gen_set and not truth_set:
        precision = recall = f1 = 1.0
        jaccard = 1.0
    elif not gen_set or not truth_set:
        precision = recall = f1 = 0.0
        jaccard = 0.0
    else:
        intersection = len(gen_set & truth_set)
        precision = intersection / len(gen_set)
        recall = intersection / len(truth_set)
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        jaccard = intersection / len(gen_set | truth_set)
    
    # Enhanced metrics
    semantic_similarity = analyzer.calculate_semantic_similarity(generated_query, ground_truth_query)
    comprehensiveness_score = analyzer.calculate_comprehensiveness_score(
        generated_query, ground_truth_query, generated_results, ground_truth_results
    )
    
    # Efficiency score (simpler queries are better if they get same results)
    gen_complexity = analyzer.extract_semantic_components(generated_query)["complexity_score"]
    truth_complexity = analyzer.extract_semantic_components(ground_truth_query)["complexity_score"]
    
    if gen_complexity == 0:
        efficiency_score = 1.0
    else:
        # Prefer simpler queries that achieve same or better results
        result_quality = f1 * comprehensiveness_score
        efficiency_score = result_quality / (gen_complexity + 1)  # +1 to avoid division by zero
    
    # Quality assessment
    quality_level = analyzer.assess_query_quality(
        generated_query, ground_truth_query, generated_results, ground_truth_results,
        semantic_similarity, comprehensiveness_score
    )
    
    return EvaluationMetrics(
        jaccard_similarity=jaccard,
        precision=precision,
        recall=recall,
        f1_score=f1,
        semantic_similarity=semantic_similarity,
        comprehensiveness_score=comprehensiveness_score,
        efficiency_score=efficiency_score,
        quality_level=quality_level,
        execution_time_ms=execution_time,
        result_count=len(generated_results) if generated_results else 0
    )

def main():
    parser = argparse.ArgumentParser(description="Enhanced query evaluation")
    parser.add_argument("--generated", required=True, help="Generated query JSON")
    parser.add_argument("--ground-truth", required=True, help="Ground truth query JSON")
    parser.add_argument("--generated-results", help="Generated query results JSON")
    parser.add_argument("--ground-truth-results", help="Ground truth results JSON")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    # Load queries
    with open(args.generated) as f:
        generated_query = json.load(f)
    with open(args.ground_truth) as f:
        ground_truth_query = json.load(f)
    
    # Load results if provided
    generated_results = []
    ground_truth_results = []
    
    if args.generated_results:
        with open(args.generated_results) as f:
            generated_results = json.load(f)
    
    if args.ground_truth_results:
        with open(args.ground_truth_results) as f:
            ground_truth_results = json.load(f)
    
    # Perform evaluation
    metrics = enhanced_evaluate_query(
        generated_query, ground_truth_query,
        generated_results, ground_truth_results
    )
    
    # Output results
    result = {
        "enhanced_evaluation": metrics.to_dict(),
        "timestamp": time.time(),
        "input_files": {
            "generated": args.generated,
            "ground_truth": args.ground_truth,
            "generated_results": args.generated_results,
            "ground_truth_results": args.ground_truth_results
        }
    }
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Enhanced evaluation saved to {args.output}")
    else:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
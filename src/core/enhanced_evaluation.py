#!/usr/bin/env python3
"""Enhanced evaluation methodology for comprehensive query assessment"""
import json
import argparse
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from enum import Enum
import hashlib

# Optional imports for enhanced semantic analysis
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("Warning: sentence-transformers not available. Using basic semantic similarity.")

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

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
        
        # Lazy loading for embedding model to avoid torch initialization issues
        self.embedding_model = None
        self._embedding_model_attempted = False
    
    def _get_embedding_model(self):
        """Lazy load the embedding model only when needed"""
        if not self._embedding_model_attempted:
            self._embedding_model_attempted = True
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                try:
                    self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                except Exception as e:
                    print(f"Warning: Could not load sentence transformer model: {e}")
                    self.embedding_model = None
        return self.embedding_model
    
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
                    if key == "range":
                        if isinstance(value, dict) and "@timestamp" in value:
                            components["time_constraints"].append(value)
                            components["complexity_score"] += 1
                        elif isinstance(value, dict):
                            # Other range constraints
                            components["field_constraints"].append({key: value})
                            components["complexity_score"] += 1
                    elif key in ["term", "terms", "match"]:
                        components["field_constraints"].append({key: value})
                        components["complexity_score"] += 1
                    elif key in ["bool", "filter", "must", "should"]:
                        components["logical_operators"].append(key)
                        if isinstance(value, list):
                            for sub_clause in value:
                                analyze_clause(sub_clause, f"{context}.{key}")
                        elif isinstance(value, dict):
                            analyze_clause(value, f"{context}.{key}")
                    elif key == "aggs":
                        components["aggregations"].append(value)
                        components["complexity_score"] += 2
            elif isinstance(clause, list):
                for item in clause:
                    analyze_clause(item, context)
        
        # Start analysis from the query root
        if "query" in query:
            analyze_clause(query["query"])
        else:
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
    
    def query_to_semantic_description(self, query: Dict) -> str:
        """Convert DSL query to natural language description for embedding"""
        description_parts = []
        
        def extract_descriptions(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "range" and isinstance(value, dict):
                        for field, constraints in value.items():
                            if field == "@timestamp":
                                gte = constraints.get("gte", "")
                                lte = constraints.get("lte", "")
                                description_parts.append(f"time filter from {gte} to {lte}")
                            else:
                                description_parts.append(f"range filter on {field}")
                    elif key == "term" and isinstance(value, dict):
                        for field, term_value in value.items():
                            description_parts.append(f"exact match {field} equals {term_value}")
                    elif key == "terms" and isinstance(value, dict):
                        for field, term_values in value.items():
                            description_parts.append(f"match {field} in {term_values}")
                    elif key in ["must", "filter", "should"]:
                        description_parts.append(f"logical {key} condition")
                    
                    extract_descriptions(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for item in obj:
                    extract_descriptions(item, path)
        
        extract_descriptions(query)
        return " ".join(description_parts) if description_parts else "empty query"
    
    def calculate_embedding_similarity(self, generated: Dict, ground_truth: Dict) -> float:
        """Calculate semantic similarity using sentence embeddings"""
        embedding_model = self._get_embedding_model()
        if not embedding_model or not SKLEARN_AVAILABLE:
            # Fallback to structural similarity
            return self.calculate_semantic_similarity(generated, ground_truth)
        
        try:
            # Convert queries to semantic descriptions
            gen_description = self.query_to_semantic_description(generated)
            truth_description = self.query_to_semantic_description(ground_truth)
            
            # Generate embeddings
            embeddings = embedding_model.encode([gen_description, truth_description])
            
            # Calculate cosine similarity
            similarity_matrix = cosine_similarity([embeddings[0]], [embeddings[1]])
            embedding_similarity = similarity_matrix[0][0]
            
            # Combine with structural similarity for robustness
            structural_similarity = self.calculate_semantic_similarity(generated, ground_truth)
            
            # Weighted combination: 60% embedding, 40% structural
            combined_similarity = 0.6 * embedding_similarity + 0.4 * structural_similarity
            
            return float(combined_similarity)
            
        except Exception as e:
            print(f"Warning: Embedding similarity calculation failed: {e}")
            # Fallback to structural similarity
            return self.calculate_semantic_similarity(generated, ground_truth)
    
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
    
    # Enhanced metrics - use embedding-based similarity if available
    semantic_similarity = analyzer.calculate_embedding_similarity(generated_query, ground_truth_query)
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

class EnhancedEvaluator:
    """Enhanced evaluator for comprehensive query assessment with multiple methods and models"""
    
    def __init__(self):
        self.results = []
        self.scenarios_cache = {}
    
    def load_scenarios(self, dataset: str) -> List[Dict[str, Any]]:
        """Load evaluation scenarios for a given dataset"""
        if dataset in self.scenarios_cache:
            return self.scenarios_cache[dataset]
        
        scenarios = []
        
        if dataset == "cic_ids2017":
            # Load CIC-IDS2017 scenarios
            scenario_file = Path("artifacts/cic_ids2017_scenarios.yaml")
            if scenario_file.exists():
                import yaml
                with open(scenario_file) as f:
                    data = yaml.safe_load(f)
                    scenarios = data.get('scenarios', [])
        else:
            # Load standard scenarios
            scenario_file = Path("tasks/prompts.yaml")
            if scenario_file.exists():
                import yaml
                with open(scenario_file) as f:
                    scenarios = yaml.safe_load(f)
        
        self.scenarios_cache[dataset] = scenarios
        return scenarios
    
    def run_evaluation(self, dataset: str, scenarios: List[str], methods: List[str], 
                      models: List[str], save_results: bool = True) -> Dict[str, Any]:
        """Run comprehensive evaluation across scenarios, methods, and models"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        # Clear previous results
        self.results = []
        
        # Load scenario definitions
        scenario_definitions = self.load_scenarios(dataset)
        scenario_dict = {s['id']: s for s in scenario_definitions}
        
        # Prepare evaluation tasks
        tasks = []
        print(f"📋 Preparing evaluation tasks:")
        print(f"   Models to evaluate: {models}")
        for scenario_id in scenarios:
            if scenario_id not in scenario_dict:
                print(f"   ⚠️  Skipping unknown scenario: {scenario_id}")
                continue
            for method in methods:
                for model in models:
                    tasks.append((scenario_id, method, model, dataset))
        
        print(f"📝 Total tasks prepared: {len(tasks)}")
        
        # Execute evaluations
        results_lock = threading.Lock()
        
        def evaluate_task(task):
            scenario_id, method, model, dataset_type = task
            result = self.evaluate_scenario(scenario_id, method, model, dataset_type)
            with results_lock:
                self.results.append(result)
            return result
        
        # Run evaluations in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(evaluate_task, task) for task in tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Evaluation task failed: {e}")
        
        # Generate summary
        summary = self._generate_summary()
        
        # Save results if requested
        if save_results:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            results_file = Path(f"artifacts/evaluation_results/eval_{dataset}_{timestamp}.json")
            results_file.parent.mkdir(exist_ok=True)
            
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            summary_file = Path(f"artifacts/evaluation_results/summary_{dataset}_{timestamp}.json")
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
        
        return summary
    
    def evaluate_scenario(self, scenario_id: str, method: str, model: str, 
                         dataset_type: str = "standard") -> Dict[str, Any]:
        """Evaluate a single scenario with a specific method and model"""
        import subprocess
        import tempfile
        from pathlib import Path
        
        print(f"🔍 Starting evaluation: {scenario_id} | Method: {method} | Model: {model}")
        
        try:
            # Load scenario definition
            scenarios = self.load_scenarios(dataset_type)
            scenario_dict = {s['id']: s for s in scenarios}
            
            if scenario_id not in scenario_dict:
                return {
                    'scenario_id': scenario_id,
                    'method': method,
                    'model': model,
                    'error': f"Scenario {scenario_id} not found",
                    'success': False,
                    'timestamp': time.time()
                }
            
            scenario = scenario_dict[scenario_id]
            prompt = scenario['prompt']
            
            # Generate query based on method
            start_time = time.time()
            generated_query = None
            error = None
            
            if method == "constrained":
                # Use constrained generation
                task_id = f"eval_{scenario_id}_{int(time.time())}"
                
                # Handle external LLMs differently
                if model and model.startswith("External:"):
                    external_llm_name = model.replace("External: ", "")
                    cmd = [
                        "python", "src/generators/external.py",
                        "--prompt", prompt,
                        "--llm", external_llm_name,
                        "--task-id", task_id
                    ]
                    print(f"🌐 Using external LLM: {external_llm_name} for {scenario_id}")
                else:
                    cmd = [
                        "python", "src/generators/constrained.py",
                        "--prompt", prompt,
                        "--task-id", task_id
                    ]
                    # Add model if it's a local model
                    if model and model.startswith("Local:"):
                        local_model = model.replace("Local: ", "")
                        cmd.extend(["--model", local_model])
                        print(f"🤖 Using local model: {local_model} for {scenario_id}")
                    elif model and not model.startswith("External:"):
                        # Legacy support for raw model names
                        cmd.extend(["--model", model])
                        print(f"🤖 Using model: {model} for {scenario_id}")
                
                print(f"⚡ Executing command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
                
                query_file = Path(f"artifacts/generated/{task_id}.json")
                if result.returncode == 0 and query_file.exists():
                    with open(query_file) as f:
                        generated_query = json.load(f)
                else:
                    error = f"Constrained generation failed: {result.stderr}"
            
            elif method == "rules":
                # Use rules baseline
                task_id = f"eval_rules_{scenario_id}_{int(time.time())}"
                cmd = [
                    "python", "src/generators/rules_based.py",
                    "--prompt", prompt,
                    "--task-id", task_id
                ]
                print(f"📋 Using rules-based generation for {scenario_id} (model-independent)")
                print(f"⚡ Executing command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
                
                query_file = Path(f"artifacts/generated/rules_{task_id}.json")
                if result.returncode == 0 and query_file.exists():
                    with open(query_file) as f:
                        generated_query = json.load(f)
                else:
                    error = f"Rules generation failed: {result.stderr}"
            
            elif method == "zeroshot":
                # Use zero-shot baseline (only supports local models)
                if model and model.startswith("External:"):
                    external_llm_name = model.replace("External: ", "")
                    print(f"❌ External LLM {external_llm_name} not supported with zeroshot method for {scenario_id}")
                    error = f"External LLMs not supported with zeroshot method"
                else:
                    task_id = f"eval_zeroshot_{scenario_id}_{int(time.time())}"
                    cmd = [
                        "python", "src/generators/zero_shot.py",
                        "--prompt", prompt,
                        "--task-id", task_id
                    ]
                    # Add model parameter
                    if model and model.startswith("Local:"):
                        local_model = model.replace("Local: ", "")
                        cmd.extend(["--model", local_model])
                        print(f"🚀 Using local model: {local_model} for zeroshot {scenario_id}")
                    elif model and not model.startswith("External:"):
                        # Legacy support for raw model names
                        cmd.extend(["--model", model])
                        print(f"🚀 Using model: {model} for zeroshot {scenario_id}")
                    
                    print(f"⚡ Executing command: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
                    
                    query_file = Path(f"artifacts/generated/zeroshot_{task_id}.json")
                    if result.returncode == 0 and query_file.exists():
                        with open(query_file) as f:
                            generated_query = json.load(f)
                    else:
                        error = f"Zero-shot generation failed: {result.stderr}"
            
            generation_time = time.time() - start_time
            
            # Log completion status
            if error or not generated_query:
                print(f"❌ Failed: {scenario_id} | {method} | {model} | Time: {generation_time:.2f}s | Error: {error}")
            else:
                print(f"✅ Success: {scenario_id} | {method} | {model} | Time: {generation_time:.2f}s")
            
            # If generation failed, return error result
            if error or not generated_query:
                return {
                    'scenario_id': scenario_id,
                    'method': method,
                    'model': model,
                    'prompt': prompt,
                    'error': error or "No query generated",
                    'success': False,
                    'generation_time': generation_time,
                    'timestamp': time.time()
                }
            
            # Load ground truth
            ground_truth_query = None
            if 'expert_dsl' in scenario:
                if isinstance(scenario['expert_dsl'], str):
                    ground_truth_query = json.loads(scenario['expert_dsl'])
                else:
                    ground_truth_query = scenario['expert_dsl']
            elif 'expected_query' in scenario:
                if isinstance(scenario['expected_query'], str):
                    ground_truth_query = json.loads(scenario['expected_query'])
                else:
                    ground_truth_query = scenario['expected_query']
            
            # Execute queries to get results (simplified - in real implementation would use Elasticsearch)
            generated_results = []
            ground_truth_results = []
            
            # Calculate enhanced metrics
            if ground_truth_query:
                metrics = enhanced_evaluate_query(
                    generated_query, ground_truth_query,
                    generated_results, ground_truth_results,
                    generation_time * 1000  # Convert to milliseconds
                )
                
                execution_metrics = metrics.to_dict()
            else:
                execution_metrics = None
            
            # Calculate AST similarity (simplified)
            ast_similarity = self._calculate_ast_similarity(generated_query, ground_truth_query) if ground_truth_query else 0.0
            
            return {
                'scenario_id': scenario_id,
                'method': method,
                'model': model,
                'prompt': prompt,
                'generated_query': generated_query,
                'ground_truth_query': ground_truth_query,
                'execution_metrics': execution_metrics,
                'ast_similarity': ast_similarity,
                'generation_time': generation_time,
                'success': True,
                'error': None,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'scenario_id': scenario_id,
                'method': method,
                'model': model,
                'error': str(e),
                'success': False,
                'timestamp': time.time()
            }
    
    def _calculate_ast_similarity(self, query1: Dict, query2: Dict) -> float:
        """Calculate AST similarity between two queries"""
        try:
            from src.ast_normalize import normalize_query
            norm1 = normalize_query(query1)
            norm2 = normalize_query(query2)
            # Simple similarity based on normalized query structure
            return 1.0 if norm1 == norm2 else 0.5  # Simplified calculation
        except:
            return 0.0
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate evaluation summary statistics"""
        if not self.results:
            return {}
        
        successful_results = [r for r in self.results if r.get('success', False)]
        total_results = len(self.results)
        
        # Overall statistics
        overall = {
            'total_evaluations': total_results,
            'successful_evaluations': len(successful_results),
            'success_rate': len(successful_results) / total_results if total_results > 0 else 0.0,
            'avg_generation_time': sum(r.get('generation_time', 0) for r in successful_results) / len(successful_results) if successful_results else 0.0
        }
        
        # Add metric averages if available
        f1_scores = []
        precisions = []
        recalls = []
        ast_similarities = []
        
        for r in successful_results:
            if r.get('execution_metrics'):
                metrics = r['execution_metrics']
                if isinstance(metrics, dict) and 'traditional' in metrics:
                    f1_scores.append(metrics['traditional'].get('f1_score', 0))
                    precisions.append(metrics['traditional'].get('precision', 0))
                    recalls.append(metrics['traditional'].get('recall', 0))
            
            ast_similarities.append(r.get('ast_similarity', 0))
        
        if f1_scores:
            overall['avg_f1_score'] = sum(f1_scores) / len(f1_scores)
            overall['avg_precision'] = sum(precisions) / len(precisions)
            overall['avg_recall'] = sum(recalls) / len(recalls)
        
        if ast_similarities:
            overall['avg_ast_similarity'] = sum(ast_similarities) / len(ast_similarities)
        
        # By method statistics
        by_method = {}
        for method in set(r.get('method') for r in self.results):
            method_results = [r for r in self.results if r.get('method') == method]
            method_successful = [r for r in method_results if r.get('success', False)]
            
            method_stats = {
                'count': len(method_results),
                'success_rate': len(method_successful) / len(method_results) if method_results else 0.0,
                'avg_generation_time': sum(r.get('generation_time', 0) for r in method_successful) / len(method_successful) if method_successful else 0.0
            }
            
            # Add method-specific metrics
            method_f1s = []
            method_precisions = []
            method_recalls = []
            method_ast_sims = []
            
            for r in method_successful:
                if r.get('execution_metrics'):
                    metrics = r['execution_metrics']
                    if isinstance(metrics, dict) and 'traditional' in metrics:
                        method_f1s.append(metrics['traditional'].get('f1_score', 0))
                        method_precisions.append(metrics['traditional'].get('precision', 0))
                        method_recalls.append(metrics['traditional'].get('recall', 0))
                
                method_ast_sims.append(r.get('ast_similarity', 0))
            
            if method_f1s:
                method_stats['avg_f1_score'] = sum(method_f1s) / len(method_f1s)
                method_stats['avg_precision'] = sum(method_precisions) / len(method_precisions)
                method_stats['avg_recall'] = sum(method_recalls) / len(method_recalls)
            
            if method_ast_sims:
                method_stats['avg_ast_similarity'] = sum(method_ast_sims) / len(method_ast_sims)
            
            by_method[method] = method_stats
        
        # By model statistics
        by_model = {}
        for model in set(r.get('model') for r in self.results):
            model_results = [r for r in self.results if r.get('model') == model]
            model_successful = [r for r in model_results if r.get('success', False)]
            
            model_stats = {
                'count': len(model_results),
                'success_rate': len(model_successful) / len(model_results) if model_results else 0.0,
                'avg_generation_time': sum(r.get('generation_time', 0) for r in model_successful) / len(model_successful) if model_successful else 0.0
            }
            
            # Add model-specific metrics
            model_f1s = []
            model_precisions = []
            model_recalls = []
            model_ast_sims = []
            
            for r in model_successful:
                if r.get('execution_metrics'):
                    metrics = r['execution_metrics']
                    if isinstance(metrics, dict) and 'traditional' in metrics:
                        model_f1s.append(metrics['traditional'].get('f1_score', 0))
                        model_precisions.append(metrics['traditional'].get('precision', 0))
                        model_recalls.append(metrics['traditional'].get('recall', 0))
                
                model_ast_sims.append(r.get('ast_similarity', 0))
            
            if model_f1s:
                model_stats['avg_f1_score'] = sum(model_f1s) / len(model_f1s)
                model_stats['avg_precision'] = sum(model_precisions) / len(model_precisions)
                model_stats['avg_recall'] = sum(model_recalls) / len(model_recalls)
            
            if model_ast_sims:
                model_stats['avg_ast_similarity'] = sum(model_ast_sims) / len(model_ast_sims)
            
            by_model[model] = model_stats
        
        return {
            'overall': overall,
            'by_method': by_method,
            'by_model': by_model,
            'timestamp': time.time()
        }

if __name__ == "__main__":
    main()
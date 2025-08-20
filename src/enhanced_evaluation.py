#!/usr/bin/env python3
"""
Enhanced Evaluation Framework for ES-NL2DSL
Supports both standard and CIC-IDS2017 datasets with local and external LLMs
"""

import json
import yaml
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import subprocess

# Import existing modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import generate_constrained, baseline_rules, baseline_zeroshot
from src import validator
from src import ast_normalize
from src.eval_exec import execute_query, calculate_metrics
from src.external_llm_manager import get_external_llm_manager


@dataclass
class EvaluationResult:
    """Result of a single evaluation"""
    scenario_id: str
    dataset: str  # 'standard' or 'cic_ids2017'
    index: str
    method: str
    model: str  # 'local' or external LLM name
    prompt: str
    generated_query: Optional[Dict]
    expected_query: Optional[Dict]
    validation_result: Optional[Dict]
    ast_similarity: float
    execution_metrics: Optional[Dict]  # precision, recall, f1
    generation_time: float
    execution_time: float
    error: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class EnhancedEvaluator:
    """Enhanced evaluation system supporting multiple datasets and LLMs"""
    
    def __init__(self, config_file: str = "artifacts/config.yaml"):
        self.config_file = Path(config_file)
        self.load_config()
        self.llm_manager = get_external_llm_manager()
        self.results: List[EvaluationResult] = []
        
    def load_config(self):
        """Load configuration including ES credentials"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            # Default configuration
            self.config = {
                'elasticsearch': {
                    'host': 'localhost',
                    'port': 9200,
                    'user': 'reader',
                    'password': 'ReaderPwd_123'
                }
            }
    
    def load_scenarios(self, dataset: str = "standard") -> List[Dict]:
        """Load scenarios for evaluation"""
        if dataset == "standard":
            scenario_file = Path("tasks/prompts.yaml")
        elif dataset == "cic_ids2017":
            scenario_file = Path("artifacts/cic_ids2017_scenarios.yaml")
        else:
            raise ValueError(f"Unknown dataset: {dataset}")
        
        if not scenario_file.exists():
            return []
        
        with open(scenario_file, 'r') as f:
            data = yaml.safe_load(f)
            # Handle both list format (standard) and dict with 'scenarios' key (CIC)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('scenarios', data.get('tasks', []))
            else:
                return []
    
    def generate_query_with_model(
        self, 
        prompt: str, 
        method: str, 
        model: str,
        index: str = "logs_net"
    ) -> Tuple[Optional[Dict], float, Optional[str]]:
        """Generate query using specified method and model"""
        start_time = time.time()
        generated_query = None
        error = None
        
        try:
            # Check if model is a local Ollama model (contains ':' or is in known local models)
            local_models = ["llama3.1:latest", "deepseek-r1:14b", "gpt-oss:20b", "local"]
            
            if model in local_models or ":" in model or model == "local":
                # Use local Ollama models by calling their main functions
                # If model is just "local", use default llama3.1:latest
                ollama_model = "llama3.1:latest" if model == "local" else model
                
                if method == "constrained":
                    # Build and execute constrained generation
                    full_prompt = generate_constrained.build_prompt(prompt, index=index)
                    result = generate_constrained.call_local_model(full_prompt, model=ollama_model)
                elif method == "rules":
                    # Use rules-based generation (doesn't use LLM, just pattern matching)
                    # This returns a dict directly, not a JSON string
                    result = baseline_rules.generate_rule_based_query(prompt)
                    generated_query = result  # Already a dict
                elif method == "zeroshot":
                    # Use zero-shot generation (baseline_zeroshot handles prompt internally)
                    result = baseline_zeroshot.call_model_zeroshot(prompt, model=ollama_model)
                else:
                    raise ValueError(f"Unknown method: {method}")
                
                # Extract JSON from response (only for string responses from models)
                if method != "rules":  # Rules method already set generated_query
                    if isinstance(result, str):
                        # Try to extract JSON from markdown code blocks
                        if "```json" in result:
                            result = result.split("```json")[1].split("```")[0]
                        elif "```" in result:
                            result = result.split("```")[1].split("```")[0]
                        
                        # Strip whitespace
                        result = result.strip()
                        
                        # If result is empty, raise an error
                        if not result:
                            raise ValueError("Model returned empty response")
                        
                        # Try to parse as JSON
                        try:
                            generated_query = json.loads(result)
                        except json.JSONDecodeError as e:
                            # Try to find JSON-like content in the response
                            import re
                            
                            # First try to find a complete JSON object
                            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result, re.DOTALL)
                            if json_match:
                                try:
                                    # Clean up the matched JSON
                                    json_str = json_match.group()
                                    # Remove any trailing commas before closing braces/brackets
                                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                                    # Try to parse the cleaned JSON
                                    generated_query = json.loads(json_str)
                                except json.JSONDecodeError:
                                    # If that fails, try a more aggressive approach
                                    # Find the first { and last }
                                    start = result.find('{')
                                    end = result.rfind('}')
                                    if start != -1 and end != -1 and end > start:
                                        json_str = result[start:end+1]
                                        # Clean up common issues
                                        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
                                        json_str = re.sub(r'(\w+):', r'"\1":', json_str)  # Quote unquoted keys
                                        try:
                                            generated_query = json.loads(json_str)
                                        except:
                                            raise ValueError(f"Could not parse JSON after cleaning: {e}")
                                    else:
                                        raise ValueError(f"Could not find valid JSON structure in response")
                            else:
                                raise ValueError(f"Could not extract valid JSON from response: {result[:200]}...")
                    else:
                        generated_query = result
                    
            else:
                # Use external LLM
                system_prompt = f"""You are an Elasticsearch DSL query generator. 
                Convert the natural language query to a valid Elasticsearch DSL JSON query.
                Target index: {index}
                Return only the JSON query without explanation."""
                
                if method == "constrained":
                    # Add constraints to prompt
                    enhanced_prompt = f"""{prompt}
                    
                    Constraints:
                    - Must include time range if temporal reference exists
                    - Use appropriate field names for index {index}
                    - Return valid JSON only"""
                    
                elif method == "rules":
                    # Add rule-based structure
                    enhanced_prompt = f"""{prompt}
                    
                    Follow these rules:
                    - If IP mentioned, use src_ip or dst_ip fields
                    - If port mentioned, use src_port or dst_port fields
                    - If time mentioned, use @timestamp field with range query
                    - If attack type mentioned, use attack_type or label field"""
                    
                else:  # zeroshot
                    enhanced_prompt = prompt
                
                response = self.llm_manager.call_llm(
                    model, 
                    enhanced_prompt,
                    system_prompt=system_prompt
                )
                
                if response:
                    # Clean response
                    if "```json" in response:
                        response = response.split("```json")[1].split("```")[0]
                    elif "```" in response:
                        response = response.split("```")[1].split("```")[0]
                    
                    generated_query = json.loads(response.strip())
                
        except Exception as e:
            error = str(e)
            print(f"Error generating query with {model}/{method}: {e}")
        
        generation_time = time.time() - start_time
        return generated_query, generation_time, error
    
    def evaluate_scenario(
        self,
        scenario: Dict,
        method: str,
        model: str,
        dataset: str = "standard"
    ) -> EvaluationResult:
        """Evaluate a single scenario"""
        
        # Extract scenario details
        scenario_id = scenario['id']
        prompt = scenario['prompt']
        index = scenario.get('index', 'logs_net' if dataset == 'standard' else 'logs_cic_ids2017')
        # Handle both 'expected_query' and 'expert_dsl' field names
        expected_query = scenario.get('expected_query') or scenario.get('expert_dsl')
        
        if isinstance(expected_query, str):
            expected_query = yaml.safe_load(expected_query)
        
        # Generate query
        generated_query, generation_time, error = self.generate_query_with_model(
            prompt, method, model, index
        )
        
        # Validate query
        validation_result = None
        if generated_query and not error:
            # Validate using the validator module's approach
            try:
                rules = validator.load_rules("artifacts/validator_rules.yaml")
                # Basic validation checks
                fields = validator.collect_fields(generated_query)
                allowed_fields = set(rules.get('allowed_fields', []))
                
                # Check if all fields are allowed
                invalid_fields = fields - allowed_fields
                if invalid_fields:
                    validation_result = {'valid': False, 'errors': [f'Invalid fields: {invalid_fields}']}
                else:
                    validation_result = {'valid': True, 'errors': []}
            except Exception as e:
                validation_result = {'valid': False, 'errors': [str(e)]}
        
        # Compare AST
        ast_similarity = 0.0
        if generated_query and expected_query:
            try:
                # Normalize both queries for comparison
                norm_expected = ast_normalize.flatten_bool(expected_query)
                norm_generated = ast_normalize.flatten_bool(generated_query)
                
                # Simple similarity based on normalized structure
                if json.dumps(norm_expected, sort_keys=True) == json.dumps(norm_generated, sort_keys=True):
                    ast_similarity = 1.0
                else:
                    # Basic similarity score based on common fields
                    exp_fields = validator.collect_fields(expected_query)
                    gen_fields = validator.collect_fields(generated_query)
                    if exp_fields or gen_fields:
                        common = len(exp_fields & gen_fields)
                        total = len(exp_fields | gen_fields)
                        ast_similarity = common / total if total > 0 else 0.0
            except Exception as e:
                print(f"Error comparing AST: {e}")
        
        # Execute and compare results
        execution_metrics = None
        execution_time = 0.0
        
        if generated_query and expected_query and not error:
            try:
                start_exec = time.time()
                
                # Execute both queries
                expected_results = execute_query(expected_query, index=index)
                generated_results = execute_query(generated_query, index=index)
                
                # Calculate metrics
                if expected_results and generated_results:
                    metrics = calculate_metrics(expected_results, generated_results)
                    execution_metrics = {
                        'precision': metrics.get('precision', 0.0),
                        'recall': metrics.get('recall', 0.0),
                        'f1_score': metrics.get('f1_score', 0.0),
                        'jaccard': metrics.get('jaccard_similarity', 0.0)
                    }
                
                execution_time = time.time() - start_exec
                
            except Exception as e:
                print(f"Error executing queries: {e}")
                error = str(e) if not error else f"{error}; Execution: {e}"
        
        # Create result
        return EvaluationResult(
            scenario_id=scenario_id,
            dataset=dataset,
            index=index,
            method=method,
            model=model,
            prompt=prompt,
            generated_query=generated_query,
            expected_query=expected_query,
            validation_result=validation_result,
            ast_similarity=ast_similarity,
            execution_metrics=execution_metrics,
            generation_time=generation_time,
            execution_time=execution_time,
            error=error
        )
    
    def run_evaluation(
        self,
        dataset: str = "standard",
        scenarios: Optional[List[str]] = None,
        methods: List[str] = ["constrained", "rules", "zeroshot"],
        models: List[str] = ["local"],
        save_results: bool = True
    ) -> Dict[str, Any]:
        """Run comprehensive evaluation"""
        
        # Load scenarios
        all_scenarios = self.load_scenarios(dataset)
        
        # Filter scenarios if specified
        if scenarios:
            all_scenarios = [s for s in all_scenarios if s['id'] in scenarios]
        
        if not all_scenarios:
            return {"error": "No scenarios to evaluate"}
        
        # Clear previous results
        self.results = []
        
        # Run evaluations
        total_evaluations = len(all_scenarios) * len(methods) * len(models)
        completed = 0
        
        for scenario in all_scenarios:
            for method in methods:
                for model in models:
                    print(f"Evaluating {scenario['id']} with {method}/{model} ({completed+1}/{total_evaluations})")
                    
                    result = self.evaluate_scenario(
                        scenario=scenario,
                        method=method,
                        model=model,
                        dataset=dataset
                    )
                    
                    self.results.append(result)
                    completed += 1
        
        # Calculate summary statistics
        summary = self.calculate_summary()
        
        # Save results
        if save_results:
            self.save_results(dataset)
        
        return summary
    
    def calculate_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics from results"""
        if not self.results:
            return {}
        
        summary = {
            'total_evaluations': len(self.results),
            'timestamp': datetime.now().isoformat(),
            'by_method': {},
            'by_model': {},
            'by_dataset': {},
            'overall': {
                'avg_ast_similarity': 0.0,
                'avg_precision': 0.0,
                'avg_recall': 0.0,
                'avg_f1_score': 0.0,
                'success_rate': 0.0,
                'avg_generation_time': 0.0
            }
        }
        
        # Calculate metrics by method
        for method in set(r.method for r in self.results):
            method_results = [r for r in self.results if r.method == method]
            summary['by_method'][method] = self._calculate_metrics(method_results)
        
        # Calculate metrics by model
        for model in set(r.model for r in self.results):
            model_results = [r for r in self.results if r.model == model]
            summary['by_model'][model] = self._calculate_metrics(model_results)
        
        # Calculate metrics by dataset
        for dataset in set(r.dataset for r in self.results):
            dataset_results = [r for r in self.results if r.dataset == dataset]
            summary['by_dataset'][dataset] = self._calculate_metrics(dataset_results)
        
        # Overall metrics
        summary['overall'] = self._calculate_metrics(self.results)
        
        return summary
    
    def _calculate_metrics(self, results: List[EvaluationResult]) -> Dict[str, float]:
        """Calculate average metrics for a set of results"""
        if not results:
            return {}
        
        metrics = {
            'count': len(results),
            'success_count': sum(1 for r in results if not r.error),
            'success_rate': sum(1 for r in results if not r.error) / len(results),
            'avg_ast_similarity': sum(r.ast_similarity for r in results) / len(results),
            'avg_generation_time': sum(r.generation_time for r in results) / len(results),
            'avg_execution_time': sum(r.execution_time for r in results) / len(results)
        }
        
        # Calculate execution metrics averages
        valid_exec_results = [r for r in results if r.execution_metrics]
        if valid_exec_results:
            metrics['avg_precision'] = sum(r.execution_metrics['precision'] for r in valid_exec_results) / len(valid_exec_results)
            metrics['avg_recall'] = sum(r.execution_metrics['recall'] for r in valid_exec_results) / len(valid_exec_results)
            metrics['avg_f1_score'] = sum(r.execution_metrics['f1_score'] for r in valid_exec_results) / len(valid_exec_results)
            metrics['avg_jaccard'] = sum(r.execution_metrics['jaccard'] for r in valid_exec_results) / len(valid_exec_results)
        else:
            metrics['avg_precision'] = 0.0
            metrics['avg_recall'] = 0.0
            metrics['avg_f1_score'] = 0.0
            metrics['avg_jaccard'] = 0.0
        
        return metrics
    
    def save_results(self, dataset: str):
        """Save evaluation results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("artifacts/evaluation_results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save detailed results
        results_file = output_dir / f"eval_{dataset}_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(
                [asdict(r) for r in self.results],
                f,
                indent=2,
                default=str
            )
        
        # Save summary
        summary = self.calculate_summary()
        summary_file = output_dir / f"summary_{dataset}_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Results saved to {results_file}")
        print(f"Summary saved to {summary_file}")
        
        return results_file, summary_file


def main():
    """CLI interface for enhanced evaluation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced ES-NL2DSL Evaluation")
    parser.add_argument("--dataset", choices=["standard", "cic_ids2017"], 
                       default="standard", help="Dataset to evaluate")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenario IDs to run")
    parser.add_argument("--methods", nargs="+", 
                       default=["constrained", "rules", "zeroshot"],
                       help="Methods to evaluate")
    parser.add_argument("--models", nargs="+", default=["local"],
                       help="Models to use (local or external LLM names)")
    parser.add_argument("--no-save", action="store_true", 
                       help="Don't save results to file")
    
    args = parser.parse_args()
    
    # Run evaluation
    evaluator = EnhancedEvaluator()
    summary = evaluator.run_evaluation(
        dataset=args.dataset,
        scenarios=args.scenarios,
        methods=args.methods,
        models=args.models,
        save_results=not args.no_save
    )
    
    # Print summary
    print("\n" + "="*50)
    print("EVALUATION SUMMARY")
    print("="*50)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
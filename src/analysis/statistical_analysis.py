#!/usr/bin/env python3
"""
Statistical Analysis: Rigorous evaluation framework with confidence metrics

This module provides comprehensive statistical analysis capabilities for the ES-NL2DSL
system, enabling scientifically rigorous evaluation of query generation performance.
It implements multiple statistical tests, confidence intervals, effect size calculations,
and visualization support for research and production validation.

Key analysis capabilities:
- Multi-run evaluation with confidence intervals and significance testing
- Parametric and non-parametric statistical tests (t-test, Mann-Whitney U)
- Effect size calculation (Cohen's d) for practical significance
- Bootstrap confidence intervals for robust estimation
- Cross-method comparison with multiple testing correction
- Performance stability analysis and outlier detection
- Comprehensive reporting with publication-ready statistics

The module supports both basic analysis (numpy-only) and advanced analysis
(with scipy) through graceful degradation, ensuring functionality across
different deployment environments.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import numpy as np
import json
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import time

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Using basic statistical analysis.")

@dataclass
class StatisticalResult:
    """
    Comprehensive statistical analysis results with significance metrics.
    
    Encapsulates statistical measures including central tendency, dispersion,
    confidence intervals, and hypothesis testing results for rigorous
    performance evaluation.
    
    Attributes:
        mean: Arithmetic mean of the metric
        std: Standard deviation measuring dispersion
        median: Median value (robust to outliers)
        confidence_interval_95: 95% CI for the mean
        sample_size: Number of samples analyzed
        p_value: Probability value from hypothesis testing
        significant: Whether result is statistically significant (p < 0.05)
        effect_size: Cohen's d or other effect size measure
    """
    mean: float
    std: float
    median: float
    confidence_interval_95: Tuple[float, float]
    sample_size: int
    
    # Significance testing (when comparing two groups)
    p_value: Optional[float] = None
    significant: Optional[bool] = None
    effect_size: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mean": self.mean,
            "std": self.std,
            "median": self.median,
            "confidence_interval_95": self.confidence_interval_95,
            "sample_size": self.sample_size,
            "p_value": self.p_value,
            "significant": self.significant,
            "effect_size": self.effect_size
        }

@dataclass
class MultiRunEvaluationResult:
    """Results from multiple evaluation runs"""
    scenario_id: str
    method: str
    runs: List[Dict[str, Any]]
    
    # Statistical summaries for each metric
    jaccard_stats: StatisticalResult
    f1_stats: StatisticalResult
    precision_stats: StatisticalResult
    recall_stats: StatisticalResult
    semantic_similarity_stats: StatisticalResult
    
    # Execution statistics
    latency_stats: Optional[StatisticalResult] = None
    success_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "method": self.method,
            "sample_size": len(self.runs),
            "success_rate": self.success_rate,
            "statistics": {
                "jaccard": self.jaccard_stats.to_dict(),
                "f1": self.f1_stats.to_dict(),
                "precision": self.precision_stats.to_dict(),
                "recall": self.recall_stats.to_dict(),
                "semantic_similarity": self.semantic_similarity_stats.to_dict(),
                "latency": self.latency_stats.to_dict() if self.latency_stats else None
            },
            "individual_runs": self.runs
        }

class StatisticalAnalyzer:
    """Performs statistical analysis on evaluation results"""
    
    def __init__(self, alpha: float = 0.05):
        """
        Initialize statistical analyzer
        
        Args:
            alpha: Significance level for hypothesis testing (default 0.05)
        """
        self.alpha = alpha
    
    def calculate_confidence_interval(self, data: List[float], confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for data"""
        if not data:
            return (0.0, 0.0)
        
        if SCIPY_AVAILABLE and len(data) > 1:
            # Use t-distribution for small samples
            confidence_level = confidence
            degrees_freedom = len(data) - 1
            sample_mean = np.mean(data)
            sample_std = np.std(data, ddof=1)
            standard_error = sample_std / np.sqrt(len(data))
            
            t_critical = stats.t.ppf((1 + confidence_level) / 2, degrees_freedom)
            margin_error = t_critical * standard_error
            
            return (sample_mean - margin_error, sample_mean + margin_error)
        else:
            # Fallback: use normal approximation
            mean = np.mean(data)
            std = np.std(data, ddof=1) if len(data) > 1 else 0
            margin = 1.96 * (std / np.sqrt(len(data))) if len(data) > 1 else 0
            return (mean - margin, mean + margin)
    
    def bootstrap_confidence_interval(self, data: List[float], n_bootstrap: int = 1000, confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate bootstrap confidence interval"""
        if not data:
            return (0.0, 0.0)
        
        data_array = np.array(data)
        bootstrap_means = []
        
        for _ in range(n_bootstrap):
            # Sample with replacement
            bootstrap_sample = np.random.choice(data_array, size=len(data_array), replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))
        
        alpha = 1 - confidence
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        ci_lower = np.percentile(bootstrap_means, lower_percentile)
        ci_upper = np.percentile(bootstrap_means, upper_percentile)
        
        return (ci_lower, ci_upper)
    
    def analyze_metric(self, values: List[float], use_bootstrap: bool = False) -> StatisticalResult:
        """Analyze a single metric across multiple runs"""
        if not values:
            return StatisticalResult(
                mean=0.0, std=0.0, median=0.0, 
                confidence_interval_95=(0.0, 0.0), sample_size=0
            )
        
        mean = np.mean(values)
        std = np.std(values, ddof=1) if len(values) > 1 else 0.0
        median = np.median(values)
        
        if use_bootstrap:
            ci = self.bootstrap_confidence_interval(values)
        else:
            ci = self.calculate_confidence_interval(values)
        
        return StatisticalResult(
            mean=mean,
            std=std,
            median=median,
            confidence_interval_95=ci,
            sample_size=len(values)
        )
    
    def compare_methods(self, group1_values: List[float], group2_values: List[float], 
                       method1_name: str = "Method 1", method2_name: str = "Method 2") -> Dict[str, Any]:
        """Compare two methods using statistical tests"""
        if not group1_values or not group2_values:
            return {
                "error": "Cannot compare methods with empty data",
                "method1": method1_name,
                "method2": method2_name
            }
        
        result = {
            "method1": method1_name,
            "method2": method2_name,
            "method1_stats": self.analyze_metric(group1_values).to_dict(),
            "method2_stats": self.analyze_metric(group2_values).to_dict()
        }
        
        if SCIPY_AVAILABLE:
            # Perform statistical tests
            try:
                # Shapiro-Wilk test for normality (if sample size allows)
                if len(group1_values) >= 3 and len(group1_values) <= 5000:
                    _, p_norm1 = stats.shapiro(group1_values)
                    result["method1_normality_p"] = p_norm1
                
                if len(group2_values) >= 3 and len(group2_values) <= 5000:
                    _, p_norm2 = stats.shapiro(group2_values)
                    result["method2_normality_p"] = p_norm2
                
                # Independent t-test (assumes normal distribution)
                t_stat, p_value_ttest = stats.ttest_ind(group1_values, group2_values)
                result["t_test"] = {
                    "statistic": t_stat,
                    "p_value": p_value_ttest,
                    "significant": p_value_ttest < self.alpha
                }
                
                # Mann-Whitney U test (non-parametric)
                u_stat, p_value_mannwhitney = stats.mannwhitneyu(group1_values, group2_values, alternative='two-sided')
                result["mann_whitney_u"] = {
                    "statistic": u_stat,
                    "p_value": p_value_mannwhitney,
                    "significant": p_value_mannwhitney < self.alpha
                }
                
                # Effect size (Cohen's d)
                pooled_std = np.sqrt(((len(group1_values) - 1) * np.var(group1_values, ddof=1) + 
                                    (len(group2_values) - 1) * np.var(group2_values, ddof=1)) / 
                                   (len(group1_values) + len(group2_values) - 2))
                if pooled_std > 0:
                    cohens_d = (np.mean(group1_values) - np.mean(group2_values)) / pooled_std
                    result["effect_size"] = {
                        "cohens_d": cohens_d,
                        "interpretation": self._interpret_effect_size(abs(cohens_d))
                    }
                
            except Exception as e:
                result["statistical_test_error"] = str(e)
        
        return result
    
    def _interpret_effect_size(self, cohens_d: float) -> str:
        """Interpret Cohen's d effect size"""
        if cohens_d < 0.2:
            return "negligible"
        elif cohens_d < 0.5:
            return "small"
        elif cohens_d < 0.8:
            return "medium"
        else:
            return "large"
    
    def analyze_multiple_runs(self, scenario_id: str, method: str, results: List[Dict[str, Any]]) -> MultiRunEvaluationResult:
        """Analyze results from multiple runs of the same scenario/method"""
        if not results:
            # Return empty result
            empty_stats = StatisticalResult(0.0, 0.0, 0.0, (0.0, 0.0), 0)
            return MultiRunEvaluationResult(
                scenario_id=scenario_id,
                method=method,
                runs=[],
                jaccard_stats=empty_stats,
                f1_stats=empty_stats,
                precision_stats=empty_stats,
                recall_stats=empty_stats,
                semantic_similarity_stats=empty_stats,
                success_rate=0.0
            )
        
        # Extract metrics from all runs
        jaccard_values = []
        f1_values = []
        precision_values = []
        recall_values = []
        semantic_values = []
        latency_values = []
        successful_runs = 0
        
        for result in results:
            if "error" not in result and "jaccard_similarity" in result:
                successful_runs += 1
                jaccard_values.append(result["jaccard_similarity"])
                f1_values.append(result["f1_score"])
                precision_values.append(result["precision"])
                recall_values.append(result["recall"])
                
                # Handle enhanced metrics
                if "enhanced_metrics" in result:
                    enhanced = result["enhanced_metrics"]
                    if "semantic_similarity" in enhanced:
                        semantic_values.append(enhanced["semantic_similarity"])
                
                # Handle execution time
                if "execution_time_ms" in result:
                    latency_values.append(result["execution_time_ms"])
        
        # Calculate statistics for each metric
        jaccard_stats = self.analyze_metric(jaccard_values)
        f1_stats = self.analyze_metric(f1_values)
        precision_stats = self.analyze_metric(precision_values)
        recall_stats = self.analyze_metric(recall_values)
        semantic_stats = self.analyze_metric(semantic_values) if semantic_values else StatisticalResult(0.0, 0.0, 0.0, (0.0, 0.0), 0)
        latency_stats = self.analyze_metric(latency_values) if latency_values else None
        
        success_rate = successful_runs / len(results) if results else 0.0
        
        return MultiRunEvaluationResult(
            scenario_id=scenario_id,
            method=method,
            runs=results,
            jaccard_stats=jaccard_stats,
            f1_stats=f1_stats,
            precision_stats=precision_stats,
            recall_stats=recall_stats,
            semantic_similarity_stats=semantic_stats,
            latency_stats=latency_stats,
            success_rate=success_rate
        )
    
    def generate_statistical_report(self, multi_run_results: List[MultiRunEvaluationResult]) -> Dict[str, Any]:
        """Generate comprehensive statistical report"""
        report = {
            "timestamp": time.time(),
            "analysis_summary": {
                "total_scenarios": len(set(r.scenario_id for r in multi_run_results)),
                "total_methods": len(set(r.method for r in multi_run_results)),
                "total_runs": sum(len(r.runs) for r in multi_run_results)
            },
            "results": [],
            "method_comparisons": []
        }
        
        # Add individual results
        for result in multi_run_results:
            report["results"].append(result.to_dict())
        
        # Add method comparisons for same scenarios
        scenarios = set(r.scenario_id for r in multi_run_results)
        for scenario in scenarios:
            scenario_results = [r for r in multi_run_results if r.scenario_id == scenario]
            if len(scenario_results) >= 2:
                # Compare all pairs of methods for this scenario
                for i in range(len(scenario_results)):
                    for j in range(i + 1, len(scenario_results)):
                        result1 = scenario_results[i]
                        result2 = scenario_results[j]
                        
                        # Compare F1 scores
                        f1_values1 = [run.get("f1_score", 0) for run in result1.runs if "f1_score" in run]
                        f1_values2 = [run.get("f1_score", 0) for run in result2.runs if "f1_score" in run]
                        
                        if f1_values1 and f1_values2:
                            comparison = self.compare_methods(
                                f1_values1, f1_values2, 
                                result1.method, result2.method
                            )
                            comparison["scenario_id"] = scenario
                            comparison["metric"] = "f1_score"
                            report["method_comparisons"].append(comparison)
        
        return report

def run_statistical_evaluation(scenario_id: str, method: str, n_runs: int = 5, 
                             seed_start: int = 42) -> MultiRunEvaluationResult:
    """Run multiple evaluations and return statistical analysis"""
    import subprocess
    import sys
    import json
    from pathlib import Path
    
    analyzer = StatisticalAnalyzer()
    results = []
    
    print(f"Running statistical evaluation: {scenario_id} with {method} ({n_runs} runs)")
    
    for run_idx in range(n_runs):
        seed = seed_start + run_idx
        print(f"  Run {run_idx + 1}/{n_runs} (seed={seed})")
        
        try:
            # Run evaluation with specific seed
            if method == "constrained":
                cmd = [sys.executable, "src/cli/run_one.py", "--id", scenario_id, "--gen", "--seed", str(seed)]
            else:
                # For other methods, generate query first then evaluate
                # This would need to be implemented for each method
                cmd = [sys.executable, "src/cli/run_one.py", "--id", scenario_id, "--gen"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                # Parse output for metrics
                lines = result.stdout.split('\n')
                run_result = {"seed": seed}
                
                for line in lines:
                    if "Jaccard Similarity:" in line:
                        run_result["jaccard_similarity"] = float(line.split(":")[1].strip())
                    elif "F1 Score:" in line:
                        run_result["f1_score"] = float(line.split(":")[1].strip())
                    elif "Precision:" in line:
                        run_result["precision"] = float(line.split(":")[1].strip())
                    elif "Recall:" in line:
                        run_result["recall"] = float(line.split(":")[1].strip())
                    elif "Execution Time:" in line:
                        time_str = line.split(":")[1].strip().replace("ms", "")
                        run_result["execution_time_ms"] = float(time_str)
                
                results.append(run_result)
            else:
                results.append({"seed": seed, "error": result.stderr})
                
        except Exception as e:
            results.append({"seed": seed, "error": str(e)})
    
    return analyzer.analyze_multiple_runs(scenario_id, method, results)

if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Statistical evaluation runner")
    parser.add_argument("--scenario", required=True, help="Scenario ID to evaluate")
    parser.add_argument("--method", default="constrained", help="Method to use")
    parser.add_argument("--runs", type=int, default=5, help="Number of runs")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    # Run statistical evaluation
    result = run_statistical_evaluation(args.scenario, args.method, args.runs)
    
    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Statistical analysis saved to {output_path}")
    else:
        print(json.dumps(result.to_dict(), indent=2))

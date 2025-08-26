"""
Meta-Learning Evaluation Module for ES-NL2DSL

Provides comprehensive evaluation metrics and tools for assessing
meta-learning performance and adaptation capabilities.
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class AdaptationResult:
    """Results from a single adaptation experiment."""
    task_id: str
    domain: str
    num_support_examples: int
    adaptation_time: float
    generated_query: Dict[str, Any]
    ground_truth_query: Dict[str, Any]
    success: bool
    metrics: Dict[str, float]

@dataclass
class MetaLearningMetrics:
    """Comprehensive meta-learning evaluation metrics."""
    # Adaptation Speed
    adaptation_time_mean: float
    adaptation_time_std: float
    
    # Learning Efficiency
    few_shot_accuracy: float  # Accuracy with few examples
    sample_efficiency: float  # Examples needed for target performance
    
    # Generalization
    cross_domain_transfer: float
    schema_adaptation_score: float
    
    # Meta-Learning Specific
    meta_gradient_norm: float
    inner_loop_convergence: float
    
    # Overall Performance
    overall_score: float

class MetaLearningEvaluator:
    """
    Comprehensive evaluator for meta-learning performance.
    
    Provides detailed analysis of adaptation capabilities,
    learning efficiency, and generalization performance.
    """
    
    def __init__(self):
        self.evaluation_history = []
        self.domain_baselines = {}
        
    def evaluate_adaptation_speed(self, 
                                 adaptation_results: List[AdaptationResult]) -> Dict[str, float]:
        """Evaluate how quickly the model adapts to new tasks."""
        if not adaptation_results:
            return {'mean_time': 0.0, 'std_time': 0.0, 'speed_score': 0.0}
        
        adaptation_times = [result.adaptation_time for result in adaptation_results]
        
        mean_time = np.mean(adaptation_times)
        std_time = np.std(adaptation_times)
        
        # Speed score: lower is better, normalized to 0-1
        # Assume good adaptation should be under 5 seconds
        speed_score = max(0.0, 1.0 - mean_time / 5.0)
        
        return {
            'mean_time': mean_time,
            'std_time': std_time,
            'speed_score': speed_score,
            'fastest_adaptation': min(adaptation_times),
            'slowest_adaptation': max(adaptation_times)
        }
    
    def evaluate_few_shot_performance(self, 
                                    adaptation_results: List[AdaptationResult],
                                    shot_counts: List[int] = None) -> Dict[str, Any]:
        """Evaluate performance with different numbers of examples."""
        if not adaptation_results:
            return {'accuracy_by_shots': {}, 'sample_efficiency': 0.0}
        
        shot_counts = shot_counts or [1, 3, 5, 10]
        
        # Group results by number of support examples
        results_by_shots = {}
        for result in adaptation_results:
            shots = result.num_support_examples
            if shots not in results_by_shots:
                results_by_shots[shots] = []
            results_by_shots[shots].append(result)
        
        # Calculate accuracy for each shot count
        accuracy_by_shots = {}
        for shots, results in results_by_shots.items():
            if results:
                accuracy = sum(1 for r in results if r.success) / len(results)
                accuracy_by_shots[shots] = accuracy
        
        # Calculate sample efficiency (shots needed for 80% accuracy)
        sample_efficiency = self._calculate_sample_efficiency(accuracy_by_shots, target_accuracy=0.8)
        
        # Learning curve analysis
        learning_curve = self._analyze_learning_curve(accuracy_by_shots)
        
        return {
            'accuracy_by_shots': accuracy_by_shots,
            'sample_efficiency': sample_efficiency,
            'learning_curve': learning_curve,
            'few_shot_advantage': self._calculate_few_shot_advantage(accuracy_by_shots)
        }
    
    def _calculate_sample_efficiency(self, 
                                   accuracy_by_shots: Dict[int, float], 
                                   target_accuracy: float = 0.8) -> float:
        """Calculate how many examples are needed to reach target accuracy."""
        if not accuracy_by_shots:
            return float('inf')
        
        # Sort by number of shots
        sorted_shots = sorted(accuracy_by_shots.items())
        
        for shots, accuracy in sorted_shots:
            if accuracy >= target_accuracy:
                return shots
        
        # If target not reached, estimate with interpolation
        if len(sorted_shots) >= 2:
            last_shots, last_acc = sorted_shots[-1]
            second_last_shots, second_last_acc = sorted_shots[-2]
            
            if last_acc > second_last_acc and last_acc > 0:
                # Linear extrapolation
                slope = (last_acc - second_last_acc) / (last_shots - second_last_shots)
                estimated_shots = last_shots + (target_accuracy - last_acc) / slope
                return max(last_shots, estimated_shots)
        
        return float('inf')
    
    def _analyze_learning_curve(self, accuracy_by_shots: Dict[int, float]) -> Dict[str, float]:
        """Analyze the learning curve characteristics."""
        if len(accuracy_by_shots) < 2:
            return {'slope': 0.0, 'convergence_rate': 0.0}
        
        sorted_data = sorted(accuracy_by_shots.items())
        shots = [x[0] for x in sorted_data]
        accuracies = [x[1] for x in sorted_data]
        
        # Calculate average slope
        slopes = []
        for i in range(1, len(sorted_data)):
            slope = (accuracies[i] - accuracies[i-1]) / (shots[i] - shots[i-1])
            slopes.append(slope)
        
        avg_slope = np.mean(slopes) if slopes else 0.0
        
        # Convergence rate (how quickly does improvement slow down)
        convergence_rate = 0.0
        if len(slopes) >= 2:
            early_slope = np.mean(slopes[:len(slopes)//2])
            late_slope = np.mean(slopes[len(slopes)//2:])
            convergence_rate = early_slope - late_slope  # Higher means faster convergence
        
        return {
            'slope': avg_slope,
            'convergence_rate': convergence_rate,
            'initial_performance': accuracies[0] if accuracies else 0.0,
            'final_performance': accuracies[-1] if accuracies else 0.0
        }
    
    def _calculate_few_shot_advantage(self, accuracy_by_shots: Dict[int, float]) -> float:
        """Calculate the advantage of few-shot learning over zero-shot."""
        if not accuracy_by_shots:
            return 0.0
        
        # Assume zero-shot baseline of 0.1 (10% accuracy)
        zero_shot_baseline = 0.1
        
        # Use 1-shot or 3-shot performance as few-shot benchmark
        few_shot_accuracy = 0.0
        for shots in [1, 3, 5]:
            if shots in accuracy_by_shots:
                few_shot_accuracy = accuracy_by_shots[shots]
                break
        
        return max(0.0, few_shot_accuracy - zero_shot_baseline)
    
    def evaluate_cross_domain_transfer(self, 
                                     source_domain_results: List[AdaptationResult],
                                     target_domain_results: List[AdaptationResult]) -> Dict[str, float]:
        """Evaluate how well learning transfers across domains."""
        if not source_domain_results or not target_domain_results:
            return {'transfer_score': 0.0, 'transfer_efficiency': 0.0}
        
        # Calculate baseline performance in target domain (no transfer)
        target_baseline = sum(1 for r in target_domain_results if r.success) / len(target_domain_results)
        
        # Calculate performance with transfer (assuming meta-learning was applied)
        # This would be measured in practice by comparing with/without pre-training
        # For now, we'll estimate based on adaptation speed and accuracy
        
        source_performance = sum(1 for r in source_domain_results if r.success) / len(source_domain_results)
        
        # Transfer score: how much source domain learning helps target domain
        transfer_score = min(1.0, target_baseline * (1 + source_performance))
        
        # Transfer efficiency: adaptation speed improvement
        source_avg_time = np.mean([r.adaptation_time for r in source_domain_results])
        target_avg_time = np.mean([r.adaptation_time for r in target_domain_results])
        
        transfer_efficiency = max(0.0, 1.0 - target_avg_time / max(source_avg_time, 0.1))
        
        return {
            'transfer_score': transfer_score,
            'transfer_efficiency': transfer_efficiency,
            'source_performance': source_performance,
            'target_baseline': target_baseline
        }
    
    def evaluate_schema_adaptation(self, 
                                  adaptation_results: List[AdaptationResult]) -> Dict[str, float]:
        """Evaluate how well the model adapts to different schemas."""
        if not adaptation_results:
            return {'schema_adaptation_score': 0.0}
        
        # Group by schema characteristics (simplified)
        schema_complexity_scores = []
        
        for result in adaptation_results:
            # Calculate schema complexity based on query structure
            complexity = self._calculate_query_complexity(result.ground_truth_query)
            success_rate = 1.0 if result.success else 0.0
            
            # Higher complexity should still achieve reasonable success
            # Normalize score to be between 0 and 1
            adjusted_score = success_rate * (1.0 / (1.0 + complexity))
            schema_complexity_scores.append(adjusted_score)
        
        schema_adaptation_score = np.mean(schema_complexity_scores)
        
        return {
            'schema_adaptation_score': schema_adaptation_score,
            'complexity_variance': np.var([
                self._calculate_query_complexity(r.ground_truth_query) 
                for r in adaptation_results
            ]),
            'success_vs_complexity_correlation': self._calculate_success_complexity_correlation(adaptation_results)
        }
    
    def _calculate_query_complexity(self, query: Dict[str, Any]) -> float:
        """Calculate complexity score for a query."""
        if not query:
            return 0.1
        
        query_str = json.dumps(query)
        
        # Count structural elements
        complexity = 0.1  # Base complexity
        complexity += query_str.count('{') * 0.1  # Nested objects
        complexity += query_str.count('[') * 0.15  # Arrays
        complexity += query_str.count('bool') * 0.2  # Boolean logic
        complexity += query_str.count('must') * 0.1  # Must clauses
        complexity += query_str.count('should') * 0.1  # Should clauses
        complexity += query_str.count('range') * 0.15  # Range queries
        
        return min(2.0, complexity)  # Cap at 2.0
    
    def _calculate_success_complexity_correlation(self, 
                                                adaptation_results: List[AdaptationResult]) -> float:
        """Calculate correlation between query complexity and success rate."""
        if len(adaptation_results) < 2:
            return 0.0
        
        complexities = [self._calculate_query_complexity(r.ground_truth_query) for r in adaptation_results]
        successes = [1.0 if r.success else 0.0 for r in adaptation_results]
        
        # Calculate Pearson correlation
        complexity_mean = np.mean(complexities)
        success_mean = np.mean(successes)
        
        numerator = sum((c - complexity_mean) * (s - success_mean) 
                       for c, s in zip(complexities, successes))
        
        complexity_var = sum((c - complexity_mean) ** 2 for c in complexities)
        success_var = sum((s - success_mean) ** 2 for s in successes)
        
        denominator = np.sqrt(complexity_var * success_var)
        
        return numerator / denominator if denominator > 0 else 0.0
    
    def evaluate_meta_learning_convergence(self, 
                                         training_history: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evaluate meta-learning training convergence."""
        if not training_history:
            return {'convergence_score': 0.0, 'stability_score': 0.0}
        
        # Extract loss/accuracy trends
        losses = [epoch.get('train_loss', 1.0) for epoch in training_history]
        val_accuracies = [epoch.get('val_accuracy', 0.0) for epoch in training_history]
        
        # Convergence score: how much the loss decreased
        if len(losses) >= 2:
            initial_loss = np.mean(losses[:3]) if len(losses) >= 3 else losses[0]
            final_loss = np.mean(losses[-3:]) if len(losses) >= 3 else losses[-1]
            convergence_score = max(0.0, 1.0 - final_loss / max(initial_loss, 0.1))
        else:
            convergence_score = 0.0
        
        # Stability score: how stable the validation accuracy is
        if len(val_accuracies) >= 5:
            recent_accuracies = val_accuracies[-5:]
            stability_score = 1.0 - np.std(recent_accuracies)
        else:
            stability_score = 0.0
        
        # Learning rate analysis
        learning_rate_score = self._analyze_learning_rate(losses)
        
        return {
            'convergence_score': convergence_score,
            'stability_score': max(0.0, stability_score),
            'learning_rate_score': learning_rate_score,
            'final_loss': losses[-1] if losses else 1.0,
            'final_accuracy': val_accuracies[-1] if val_accuracies else 0.0
        }
    
    def _analyze_learning_rate(self, losses: List[float]) -> float:
        """Analyze if the learning rate is appropriate."""
        if len(losses) < 10:
            return 0.5  # Neutral score
        
        # Check for signs of good learning rate
        recent_losses = losses[-10:]
        
        # Good: steady decrease
        decreasing_trend = sum(1 for i in range(1, len(recent_losses)) 
                              if recent_losses[i] < recent_losses[i-1])
        
        # Bad: oscillations (learning rate too high)
        oscillations = sum(1 for i in range(2, len(recent_losses))
                          if recent_losses[i-2] < recent_losses[i-1] > recent_losses[i])
        
        # Bad: plateau (learning rate too low)
        plateau = sum(1 for i in range(1, len(recent_losses))
                     if abs(recent_losses[i] - recent_losses[i-1]) < 0.001)
        
        # Score based on trend characteristics
        trend_score = decreasing_trend / (len(recent_losses) - 1)
        oscillation_penalty = oscillations / max(1, len(recent_losses) - 2)
        plateau_penalty = plateau / max(1, len(recent_losses) - 1)
        
        learning_rate_score = trend_score - 0.5 * oscillation_penalty - 0.3 * plateau_penalty
        
        return max(0.0, min(1.0, learning_rate_score))
    
    def compute_comprehensive_metrics(self, 
                                    adaptation_results: List[AdaptationResult],
                                    training_history: List[Dict[str, Any]] = None) -> MetaLearningMetrics:
        """Compute comprehensive meta-learning evaluation metrics."""
        
        # Adaptation speed metrics
        speed_metrics = self.evaluate_adaptation_speed(adaptation_results)
        
        # Few-shot performance metrics
        few_shot_metrics = self.evaluate_few_shot_performance(adaptation_results)
        
        # Schema adaptation metrics
        schema_metrics = self.evaluate_schema_adaptation(adaptation_results)
        
        # Meta-learning convergence (if training history available)
        convergence_metrics = {}
        if training_history:
            convergence_metrics = self.evaluate_meta_learning_convergence(training_history)
        
        # Cross-domain transfer (simplified - would need domain-separated results)
        # For now, estimate based on domain diversity in results
        domains = set(result.domain for result in adaptation_results)
        domain_diversity_score = min(1.0, len(domains) / 3.0)  # Normalize to 3 domains max
        
        # Compile comprehensive metrics
        metrics = MetaLearningMetrics(
            # Adaptation Speed
            adaptation_time_mean=speed_metrics.get('mean_time', 0.0),
            adaptation_time_std=speed_metrics.get('std_time', 0.0),
            
            # Learning Efficiency
            few_shot_accuracy=few_shot_metrics.get('accuracy_by_shots', {}).get(5, 0.0),  # 5-shot accuracy
            sample_efficiency=1.0 / max(1.0, few_shot_metrics.get('sample_efficiency', 10.0)),  # Inverse for higher=better
            
            # Generalization
            cross_domain_transfer=domain_diversity_score,
            schema_adaptation_score=schema_metrics.get('schema_adaptation_score', 0.0),
            
            # Meta-Learning Specific
            meta_gradient_norm=convergence_metrics.get('convergence_score', 0.0),
            inner_loop_convergence=convergence_metrics.get('stability_score', 0.0),
            
            # Overall Performance (weighted combination)
            overall_score=0.0  # Will be calculated below
        )
        
        # Calculate overall score
        metrics.overall_score = self._calculate_overall_score(metrics)
        
        return metrics
    
    def _calculate_overall_score(self, metrics: MetaLearningMetrics) -> float:
        """Calculate weighted overall performance score."""
        weights = {
            'adaptation_speed': 0.15,      # 15% - Speed of adaptation
            'learning_efficiency': 0.25,   # 25% - Few-shot performance
            'generalization': 0.25,        # 25% - Cross-domain/schema
            'meta_learning': 0.20,         # 20% - Meta-learning quality
            'accuracy': 0.15               # 15% - Base accuracy
        }
        
        # Normalize adaptation time to 0-1 score (lower time = higher score)
        speed_score = max(0.0, 1.0 - metrics.adaptation_time_mean / 10.0)
        
        # Generalization score (average of transfer and schema adaptation)
        generalization_score = (metrics.cross_domain_transfer + metrics.schema_adaptation_score) / 2.0
        
        # Meta-learning score (average of convergence and inner loop)
        meta_learning_score = (metrics.meta_gradient_norm + metrics.inner_loop_convergence) / 2.0
        
        # Weighted overall score
        overall_score = (
            weights['adaptation_speed'] * speed_score +
            weights['learning_efficiency'] * (metrics.few_shot_accuracy + metrics.sample_efficiency) / 2.0 +
            weights['generalization'] * generalization_score +
            weights['meta_learning'] * meta_learning_score +
            weights['accuracy'] * metrics.few_shot_accuracy
        )
        
        return min(1.0, overall_score)
    
    def generate_evaluation_report(self, 
                                 metrics: MetaLearningMetrics,
                                 adaptation_results: List[AdaptationResult]) -> str:
        """Generate a comprehensive evaluation report."""
        
        report_sections = []
        
        # Header
        report_sections.append("# Meta-Learning Evaluation Report")
        report_sections.append("=" * 50)
        
        # Executive Summary
        report_sections.append("\n## Executive Summary")
        report_sections.append(f"Overall Score: {metrics.overall_score:.3f}")
        report_sections.append(f"Evaluated on {len(adaptation_results)} adaptation tasks")
        
        domains = set(result.domain for result in adaptation_results)
        report_sections.append(f"Domains tested: {', '.join(domains)}")
        
        # Performance Grades
        grade = self._score_to_grade(metrics.overall_score)
        report_sections.append(f"Performance Grade: {grade}")
        
        # Detailed Metrics
        report_sections.append("\n## Detailed Performance Metrics")
        
        report_sections.append("\n### Adaptation Speed")
        report_sections.append(f"- Mean adaptation time: {metrics.adaptation_time_mean:.2f}s")
        report_sections.append(f"- Adaptation time std: {metrics.adaptation_time_std:.2f}s")
        
        report_sections.append("\n### Learning Efficiency")
        report_sections.append(f"- Few-shot accuracy (5-shot): {metrics.few_shot_accuracy:.3f}")
        report_sections.append(f"- Sample efficiency: {metrics.sample_efficiency:.3f}")
        
        report_sections.append("\n### Generalization")
        report_sections.append(f"- Cross-domain transfer: {metrics.cross_domain_transfer:.3f}")
        report_sections.append(f"- Schema adaptation: {metrics.schema_adaptation_score:.3f}")
        
        report_sections.append("\n### Meta-Learning Quality")
        report_sections.append(f"- Meta-gradient convergence: {metrics.meta_gradient_norm:.3f}")
        report_sections.append(f"- Inner loop stability: {metrics.inner_loop_convergence:.3f}")
        
        # Recommendations
        report_sections.append("\n## Recommendations")
        recommendations = self._generate_recommendations(metrics)
        for rec in recommendations:
            report_sections.append(f"- {rec}")
        
        # Domain Analysis
        if len(domains) > 1:
            report_sections.append("\n## Domain-Specific Analysis")
            domain_analysis = self._analyze_domain_performance(adaptation_results)
            for domain, analysis in domain_analysis.items():
                report_sections.append(f"\n### {domain.title()} Domain")
                report_sections.append(f"- Success rate: {analysis['success_rate']:.3f}")
                report_sections.append(f"- Avg adaptation time: {analysis['avg_time']:.2f}s")
        
        return "\n".join(report_sections)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numerical score to letter grade."""
        if score >= 0.9:
            return "A (Excellent)"
        elif score >= 0.8:
            return "B (Good)"
        elif score >= 0.7:
            return "C (Satisfactory)"
        elif score >= 0.6:
            return "D (Needs Improvement)"
        else:
            return "F (Poor)"
    
    def _generate_recommendations(self, metrics: MetaLearningMetrics) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        if metrics.adaptation_time_mean > 5.0:
            recommendations.append("Consider optimizing adaptation speed - current time is high")
        
        if metrics.few_shot_accuracy < 0.7:
            recommendations.append("Improve few-shot learning performance with better example selection")
        
        if metrics.sample_efficiency < 0.5:
            recommendations.append("Focus on sample efficiency - too many examples needed for good performance")
        
        if metrics.cross_domain_transfer < 0.6:
            recommendations.append("Enhance cross-domain transfer with better meta-learning algorithms")
        
        if metrics.schema_adaptation_score < 0.7:
            recommendations.append("Improve schema adaptation with better field mapping strategies")
        
        if metrics.inner_loop_convergence < 0.6:
            recommendations.append("Stabilize inner loop optimization for more consistent adaptation")
        
        if not recommendations:
            recommendations.append("Excellent performance across all metrics - consider sharing methodology")
        
        return recommendations
    
    def _analyze_domain_performance(self, 
                                  adaptation_results: List[AdaptationResult]) -> Dict[str, Dict[str, float]]:
        """Analyze performance by domain."""
        domain_analysis = {}
        
        # Group by domain
        domain_results = {}
        for result in adaptation_results:
            if result.domain not in domain_results:
                domain_results[result.domain] = []
            domain_results[result.domain].append(result)
        
        # Analyze each domain
        for domain, results in domain_results.items():
            success_rate = sum(1 for r in results if r.success) / len(results)
            avg_time = np.mean([r.adaptation_time for r in results])
            
            domain_analysis[domain] = {
                'success_rate': success_rate,
                'avg_time': avg_time,
                'num_tasks': len(results)
            }
        
        return domain_analysis

#!/usr/bin/env python3
"""Advanced research tools for hypothesis testing and experimental analysis"""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import scipy.stats as stats
from sklearn.metrics import pairwise_distances
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import itertools

class HypothesisType(Enum):
    """Types of research hypotheses"""
    PERFORMANCE_COMPARISON = "performance_comparison"
    ACCURACY_CORRELATION = "accuracy_correlation"
    MODEL_EFFECTIVENESS = "model_effectiveness"
    METHOD_SUPERIORITY = "method_superiority"
    FEATURE_IMPORTANCE = "feature_importance"
    SCALABILITY_ANALYSIS = "scalability_analysis"
    ROBUSTNESS_TESTING = "robustness_testing"

class StatisticalTest(Enum):
    """Available statistical tests"""
    T_TEST = "t_test"
    WILCOXON = "wilcoxon"
    MANN_WHITNEY = "mann_whitney"
    KRUSKAL_WALLIS = "kruskal_wallis"
    CHI_SQUARE = "chi_square"
    ANOVA = "anova"
    CORRELATION = "correlation"

@dataclass
class Hypothesis:
    """Research hypothesis definition"""
    hypothesis_id: str
    hypothesis_type: HypothesisType
    description: str
    null_hypothesis: str
    alternative_hypothesis: str
    variables: Dict[str, str]  # independent -> dependent
    expected_outcome: str
    significance_level: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["hypothesis_type"] = self.hypothesis_type.value
        return result

@dataclass
class ExperimentalDesign:
    """Experimental design specification"""
    design_id: str
    hypothesis: Hypothesis
    factors: List[str]
    levels: Dict[str, List[Any]]
    sample_size: int
    randomization: bool
    blocking_factors: Optional[List[str]]
    statistical_tests: List[StatisticalTest]
    power_analysis: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["hypothesis"] = self.hypothesis.to_dict()
        result["statistical_tests"] = [test.value for test in self.statistical_tests]
        return result

@dataclass
class ExperimentalResult:
    """Results from experimental analysis"""
    experiment_id: str
    hypothesis: Hypothesis
    design: ExperimentalDesign
    raw_data: pd.DataFrame
    statistical_results: Dict[str, Any]
    effect_sizes: Dict[str, float]
    confidence_intervals: Dict[str, Tuple[float, float]]
    conclusion: str
    p_values: Dict[str, float]
    practical_significance: Dict[str, bool]
    visualizations: List[str]  # Paths to generated plots
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["hypothesis"] = self.hypothesis.to_dict()
        result["design"] = self.design.to_dict()
        result["raw_data"] = self.raw_data.to_dict()
        return result

class HypothesisGenerator:
    """Generate research hypotheses based on available data"""
    
    def __init__(self):
        self.hypothesis_templates = {
            HypothesisType.PERFORMANCE_COMPARISON: {
                "description": "Compare performance metrics between different {factor} levels",
                "null": "There is no significant difference in {metric} between {groups}",
                "alternative": "{group1} shows significantly different {metric} compared to {group2}",
                "variables": {"factor": "metric"}
            },
            HypothesisType.MODEL_EFFECTIVENESS: {
                "description": "Evaluate effectiveness of {model} for {task}",
                "null": "{model} performance is not significantly better than baseline",
                "alternative": "{model} demonstrates significantly superior performance",
                "variables": {"model": "performance_score"}
            },
            HypothesisType.METHOD_SUPERIORITY: {
                "description": "Test superiority of {method1} over {method2}",
                "null": "No significant difference between {method1} and {method2}",
                "alternative": "{method1} significantly outperforms {method2}",
                "variables": {"method": "effectiveness"}
            }
        }
    
    def generate_hypotheses(self, data_summary: Dict[str, Any]) -> List[Hypothesis]:
        """Generate relevant hypotheses based on available data"""
        hypotheses = []
        
        # Extract available factors from data
        factors = data_summary.get("factors", [])
        metrics = data_summary.get("metrics", [])
        models = data_summary.get("models", [])
        methods = data_summary.get("methods", [])
        
        # Generate performance comparison hypotheses
        if len(factors) >= 1 and len(metrics) >= 1:
            # Take first 2 factors and first 2 metrics
            factor_subset = list(factors)[:2] if isinstance(factors, (list, tuple)) else list(factors.keys())[:2]
            metric_subset = metrics[:2] if len(metrics) >= 2 else metrics
            
            for factor, metric in itertools.product(factor_subset, metric_subset):
                hypothesis = self._create_performance_hypothesis(factor, metric)
                hypotheses.append(hypothesis)
        
        # Generate model effectiveness hypotheses
        if models and metrics:
            for model, metric in itertools.product(models[:2], metrics[:1]):
                hypothesis = self._create_model_hypothesis(model, metric)
                hypotheses.append(hypothesis)
        
        # Generate method superiority hypotheses
        if len(methods) >= 2 and metrics:
            for i, method1 in enumerate(methods[:2]):
                for method2 in methods[i+1:]:
                    hypothesis = self._create_method_hypothesis(method1, method2, metrics[0])
                    hypotheses.append(hypothesis)
        
        return hypotheses
    
    def _create_performance_hypothesis(self, factor: str, metric: str) -> Hypothesis:
        """Create performance comparison hypothesis"""
        template = self.hypothesis_templates[HypothesisType.PERFORMANCE_COMPARISON]
        
        return Hypothesis(
            hypothesis_id=f"perf_{factor}_{metric}",
            hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
            description=template["description"].format(factor=factor, metric=metric),
            null_hypothesis=template["null"].format(
                metric=metric, 
                groups=f"different {factor} levels"
            ),
            alternative_hypothesis=template["alternative"].format(
                group1=f"{factor} level 1", 
                group2=f"{factor} level 2", 
                metric=metric
            ),
            variables={factor: metric},
            expected_outcome="significant_difference",
            significance_level=0.05,
            metadata={"factor": factor, "metric": metric}
        )
    
    def _create_model_hypothesis(self, model: str, metric: str) -> Hypothesis:
        """Create model effectiveness hypothesis"""
        template = self.hypothesis_templates[HypothesisType.MODEL_EFFECTIVENESS]
        
        return Hypothesis(
            hypothesis_id=f"model_{model}_{metric}",
            hypothesis_type=HypothesisType.MODEL_EFFECTIVENESS,
            description=template["description"].format(model=model, task="query generation"),
            null_hypothesis=template["null"].format(model=model),
            alternative_hypothesis=template["alternative"].format(model=model),
            variables={"model": metric},
            expected_outcome="superior_performance",
            significance_level=0.05,
            metadata={"model": model, "metric": metric}
        )
    
    def _create_method_hypothesis(self, method1: str, method2: str, metric: str) -> Hypothesis:
        """Create method superiority hypothesis"""
        template = self.hypothesis_templates[HypothesisType.METHOD_SUPERIORITY]
        
        return Hypothesis(
            hypothesis_id=f"method_{method1}_vs_{method2}",
            hypothesis_type=HypothesisType.METHOD_SUPERIORITY,
            description=template["description"].format(method1=method1, method2=method2),
            null_hypothesis=template["null"].format(method1=method1, method2=method2),
            alternative_hypothesis=template["alternative"].format(method1=method1, method2=method2),
            variables={"method": metric},
            expected_outcome="method1_superior",
            significance_level=0.05,
            metadata={"method1": method1, "method2": method2, "metric": metric}
        )

class ExperimentalDesigner:
    """Design experiments for hypothesis testing"""
    
    def __init__(self):
        self.design_types = {
            "completely_randomized": self._design_crd,
            "randomized_block": self._design_rbd,
            "factorial": self._design_factorial,
            "repeated_measures": self._design_repeated_measures
        }
    
    def design_experiment(self, hypothesis: Hypothesis, 
                         available_data: Dict[str, Any],
                         design_type: str = "completely_randomized") -> ExperimentalDesign:
        """Design experiment for hypothesis testing"""
        
        # Extract factors and levels from hypothesis and data
        factors = list(hypothesis.variables.keys())
        levels = self._extract_levels(factors, available_data)
        
        # Calculate sample size
        sample_size = self._calculate_sample_size(hypothesis, available_data)
        
        # Select appropriate statistical tests
        statistical_tests = self._select_statistical_tests(hypothesis, factors, levels)
        
        # Perform power analysis
        power_analysis = self._power_analysis(hypothesis, sample_size)
        
        design = ExperimentalDesign(
            design_id=f"design_{hypothesis.hypothesis_id}",
            hypothesis=hypothesis,
            factors=factors,
            levels=levels,
            sample_size=sample_size,
            randomization=True,
            blocking_factors=self._identify_blocking_factors(available_data),
            statistical_tests=statistical_tests,
            power_analysis=power_analysis
        )
        
        return design
    
    def _extract_levels(self, factors: List[str], available_data: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Extract factor levels from available data"""
        levels = {}
        
        data_factors = available_data.get("factors", {})
        
        for factor in factors:
            if factor in data_factors:
                levels[factor] = data_factors[factor]
            elif factor == "model":
                levels[factor] = available_data.get("models", ["llama3.1:latest", "deepseek-r1:14b"])
            elif factor == "method":
                levels[factor] = available_data.get("methods", ["constrained", "zero_shot"])
            else:
                # Default levels
                levels[factor] = ["level1", "level2"]
        
        return levels
    
    def _calculate_sample_size(self, hypothesis: Hypothesis, available_data: Dict[str, Any]) -> int:
        """Calculate required sample size for statistical power"""
        # Simple sample size calculation based on effect size and power
        alpha = hypothesis.significance_level
        power = 0.8  # Desired power
        effect_size = 0.5  # Medium effect size
        
        # Cohen's formula for two-sample t-test
        z_alpha = stats.norm.ppf(1 - alpha/2)
        z_beta = stats.norm.ppf(power)
        
        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
        
        # Minimum sample size
        return max(int(np.ceil(n)), 20)
    
    def _select_statistical_tests(self, hypothesis: Hypothesis, 
                                 factors: List[str], levels: Dict[str, List[Any]]) -> List[StatisticalTest]:
        """Select appropriate statistical tests"""
        tests = []
        
        # Based on hypothesis type and number of groups
        if hypothesis.hypothesis_type == HypothesisType.PERFORMANCE_COMPARISON:
            if len(factors) == 1:
                factor_levels = len(levels[factors[0]])
                if factor_levels == 2:
                    tests.extend([StatisticalTest.T_TEST, StatisticalTest.MANN_WHITNEY])
                else:
                    tests.extend([StatisticalTest.ANOVA, StatisticalTest.KRUSKAL_WALLIS])
            else:
                tests.append(StatisticalTest.ANOVA)  # Multi-factor ANOVA
        
        elif hypothesis.hypothesis_type == HypothesisType.MODEL_EFFECTIVENESS:
            tests.extend([StatisticalTest.T_TEST, StatisticalTest.WILCOXON])
        
        elif hypothesis.hypothesis_type == HypothesisType.METHOD_SUPERIORITY:
            tests.extend([StatisticalTest.T_TEST, StatisticalTest.MANN_WHITNEY])
        
        # Always include correlation analysis
        tests.append(StatisticalTest.CORRELATION)
        
        return tests
    
    def _identify_blocking_factors(self, available_data: Dict[str, Any]) -> Optional[List[str]]:
        """Identify potential blocking factors"""
        # Common blocking factors in NL2DSL experiments
        potential_blocks = ["scenario_type", "query_complexity", "timestamp", "user_expertise"]
        
        available_factors = available_data.get("factors", {}).keys()
        blocking_factors = [factor for factor in potential_blocks if factor in available_factors]
        
        return blocking_factors if blocking_factors else None
    
    def _power_analysis(self, hypothesis: Hypothesis, sample_size: int) -> Dict[str, float]:
        """Perform statistical power analysis"""
        alpha = hypothesis.significance_level
        effect_sizes = [0.2, 0.5, 0.8]  # Small, medium, large
        
        power_results = {}
        
        for effect_size in effect_sizes:
            # Power for two-sample t-test
            z_alpha = stats.norm.ppf(1 - alpha/2)
            z_beta = (effect_size * np.sqrt(sample_size/2)) - z_alpha
            power = stats.norm.cdf(z_beta)
            
            effect_label = {0.2: "small", 0.5: "medium", 0.8: "large"}[effect_size]
            power_results[f"power_{effect_label}"] = power
        
        return power_results
    
    def _design_crd(self, factors: List[str], levels: Dict[str, List[Any]], 
                   sample_size: int) -> Dict[str, Any]:
        """Completely randomized design"""
        return {
            "type": "completely_randomized",
            "factors": factors,
            "levels": levels,
            "sample_size": sample_size,
            "randomization": "complete"
        }
    
    def _design_rbd(self, factors: List[str], levels: Dict[str, List[Any]], 
                   sample_size: int) -> Dict[str, Any]:
        """Randomized block design"""
        return {
            "type": "randomized_block",
            "factors": factors,
            "levels": levels,
            "sample_size": sample_size,
            "blocks": sample_size // 4  # Assume 4 replicates per block
        }
    
    def _design_factorial(self, factors: List[str], levels: Dict[str, List[Any]], 
                         sample_size: int) -> Dict[str, Any]:
        """Factorial design"""
        return {
            "type": "factorial",
            "factors": factors,
            "levels": levels,
            "sample_size": sample_size,
            "full_factorial": len(factors) <= 3
        }
    
    def _design_repeated_measures(self, factors: List[str], levels: Dict[str, List[Any]], 
                                 sample_size: int) -> Dict[str, Any]:
        """Repeated measures design"""
        return {
            "type": "repeated_measures",
            "factors": factors,
            "levels": levels,
            "subjects": sample_size // len(levels[factors[0]]) if factors else sample_size
        }

class StatisticalAnalyzer:
    """Perform statistical analysis for hypothesis testing"""
    
    def __init__(self):
        self.test_functions = {
            StatisticalTest.T_TEST: self._t_test,
            StatisticalTest.WILCOXON: self._wilcoxon_test,
            StatisticalTest.MANN_WHITNEY: self._mann_whitney_test,
            StatisticalTest.KRUSKAL_WALLIS: self._kruskal_wallis_test,
            StatisticalTest.CHI_SQUARE: self._chi_square_test,
            StatisticalTest.ANOVA: self._anova_test,
            StatisticalTest.CORRELATION: self._correlation_test
        }
    
    def analyze_experiment(self, design: ExperimentalDesign, 
                          data: pd.DataFrame) -> ExperimentalResult:
        """Perform complete statistical analysis"""
        
        statistical_results = {}
        p_values = {}
        effect_sizes = {}
        confidence_intervals = {}
        
        # Perform each statistical test
        for test in design.statistical_tests:
            result = self._perform_test(test, design, data)
            statistical_results[test.value] = result
            p_values[test.value] = result.get("p_value", 1.0)
            effect_sizes[test.value] = result.get("effect_size", 0.0)
            
            if "confidence_interval" in result:
                confidence_intervals[test.value] = result["confidence_interval"]
        
        # Generate conclusion
        conclusion = self._generate_conclusion(design.hypothesis, statistical_results, p_values)
        
        # Assess practical significance
        practical_significance = self._assess_practical_significance(effect_sizes, design.hypothesis)
        
        # Generate visualizations
        visualizations = self._generate_visualizations(design, data)
        
        result = ExperimentalResult(
            experiment_id=f"exp_{design.design_id}",
            hypothesis=design.hypothesis,
            design=design,
            raw_data=data,
            statistical_results=statistical_results,
            effect_sizes=effect_sizes,
            confidence_intervals=confidence_intervals,
            conclusion=conclusion,
            p_values=p_values,
            practical_significance=practical_significance,
            visualizations=visualizations
        )
        
        return result
    
    def _perform_test(self, test: StatisticalTest, design: ExperimentalDesign, 
                     data: pd.DataFrame) -> Dict[str, Any]:
        """Perform specific statistical test"""
        if test in self.test_functions:
            return self.test_functions[test](design, data)
        else:
            return {"error": f"Test {test.value} not implemented"}
    
    def _t_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Perform t-test"""
        factors = design.factors
        dependent_var = list(design.hypothesis.variables.values())[0]
        
        if len(factors) != 1:
            return {"error": "T-test requires exactly one factor"}
        
        factor = factors[0]
        groups = design.levels[factor]
        
        if len(groups) != 2:
            return {"error": "T-test requires exactly two groups"}
        
        # Extract data for each group
        group1_data = data[data[factor] == groups[0]][dependent_var].dropna()
        group2_data = data[data[factor] == groups[1]][dependent_var].dropna()
        
        if len(group1_data) < 2 or len(group2_data) < 2:
            return {"error": "Insufficient data for t-test"}
        
        # Perform independent t-test
        statistic, p_value = stats.ttest_ind(group1_data, group2_data)
        
        # Calculate effect size (Cohen's d)
        pooled_std = np.sqrt(((len(group1_data) - 1) * group1_data.var() + 
                             (len(group2_data) - 1) * group2_data.var()) / 
                            (len(group1_data) + len(group2_data) - 2))
        
        cohens_d = (group1_data.mean() - group2_data.mean()) / pooled_std if pooled_std > 0 else 0
        
        # Confidence interval for difference in means
        se_diff = pooled_std * np.sqrt(1/len(group1_data) + 1/len(group2_data))
        df = len(group1_data) + len(group2_data) - 2
        t_critical = stats.t.ppf(1 - design.hypothesis.significance_level/2, df)
        
        mean_diff = group1_data.mean() - group2_data.mean()
        ci_lower = mean_diff - t_critical * se_diff
        ci_upper = mean_diff + t_critical * se_diff
        
        return {
            "test_name": "Independent t-test",
            "statistic": statistic,
            "p_value": p_value,
            "effect_size": abs(cohens_d),
            "confidence_interval": (ci_lower, ci_upper),
            "group1_mean": group1_data.mean(),
            "group2_mean": group2_data.mean(),
            "group1_std": group1_data.std(),
            "group2_std": group2_data.std(),
            "degrees_freedom": df
        }
    
    def _mann_whitney_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Perform Mann-Whitney U test"""
        factors = design.factors
        dependent_var = list(design.hypothesis.variables.values())[0]
        
        if len(factors) != 1:
            return {"error": "Mann-Whitney test requires exactly one factor"}
        
        factor = factors[0]
        groups = design.levels[factor]
        
        if len(groups) != 2:
            return {"error": "Mann-Whitney test requires exactly two groups"}
        
        group1_data = data[data[factor] == groups[0]][dependent_var].dropna()
        group2_data = data[data[factor] == groups[1]][dependent_var].dropna()
        
        if len(group1_data) < 1 or len(group2_data) < 1:
            return {"error": "Insufficient data for Mann-Whitney test"}
        
        statistic, p_value = stats.mannwhitneyu(group1_data, group2_data, alternative='two-sided')
        
        # Calculate effect size (rank-biserial correlation)
        n1, n2 = len(group1_data), len(group2_data)
        r = 1 - (2 * statistic) / (n1 * n2) if (n1 * n2) > 0 else 0
        
        return {
            "test_name": "Mann-Whitney U test",
            "statistic": statistic,
            "p_value": p_value,
            "effect_size": abs(r),
            "group1_median": group1_data.median(),
            "group2_median": group2_data.median(),
            "group1_size": n1,
            "group2_size": n2
        }
    
    def _anova_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Perform ANOVA test"""
        factors = design.factors
        dependent_var = list(design.hypothesis.variables.values())[0]
        
        if len(factors) != 1:
            return {"error": "One-way ANOVA requires exactly one factor"}
        
        factor = factors[0]
        groups = design.levels[factor]
        
        # Extract data for each group
        group_data = []
        for group in groups:
            group_values = data[data[factor] == group][dependent_var].dropna()
            if len(group_values) > 0:
                group_data.append(group_values)
        
        if len(group_data) < 2:
            return {"error": "Insufficient groups for ANOVA"}
        
        # Perform one-way ANOVA
        statistic, p_value = stats.f_oneway(*group_data)
        
        # Calculate effect size (eta-squared)
        total_var = np.concatenate(group_data).var()
        group_means = [group.mean() for group in group_data]
        grand_mean = np.concatenate(group_data).mean()
        
        between_group_var = sum(len(group) * (mean - grand_mean)**2 for group, mean in zip(group_data, group_means))
        total_sum_squares = sum((val - grand_mean)**2 for group in group_data for val in group)
        
        eta_squared = between_group_var / total_sum_squares if total_sum_squares > 0 else 0
        
        return {
            "test_name": "One-way ANOVA",
            "statistic": statistic,
            "p_value": p_value,
            "effect_size": eta_squared,
            "group_means": group_means,
            "grand_mean": grand_mean,
            "degrees_freedom": (len(groups) - 1, len(data) - len(groups))
        }
    
    def _correlation_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Perform correlation analysis"""
        # Find numeric columns for correlation
        numeric_cols = data.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) < 2:
            return {"error": "Insufficient numeric variables for correlation"}
        
        # Calculate correlation matrix
        corr_matrix = data[numeric_cols].corr()
        
        # Find strongest correlations
        correlations = []
        for i in range(len(numeric_cols)):
            for j in range(i+1, len(numeric_cols)):
                var1, var2 = numeric_cols[i], numeric_cols[j]
                corr_coef = corr_matrix.loc[var1, var2]
                
                # Calculate p-value for correlation
                n = len(data[[var1, var2]].dropna())
                if n > 2:
                    t_stat = corr_coef * np.sqrt((n-2)/(1-corr_coef**2)) if abs(corr_coef) < 1 else 0
                    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n-2))
                else:
                    p_value = 1.0
                
                correlations.append({
                    "variable1": var1,
                    "variable2": var2,
                    "correlation": corr_coef,
                    "p_value": p_value,
                    "sample_size": n
                })
        
        # Sort by absolute correlation strength
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        
        return {
            "test_name": "Correlation analysis",
            "correlations": correlations[:10],  # Top 10 correlations
            "correlation_matrix": corr_matrix.to_dict()
        }
    
    def _wilcoxon_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Placeholder for Wilcoxon test (requires paired data)"""
        return {"test_name": "Wilcoxon test", "error": "Requires paired data implementation"}
    
    def _kruskal_wallis_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Placeholder for Kruskal-Wallis test"""
        return {"test_name": "Kruskal-Wallis test", "error": "Implementation pending"}
    
    def _chi_square_test(self, design: ExperimentalDesign, data: pd.DataFrame) -> Dict[str, Any]:
        """Placeholder for Chi-square test"""
        return {"test_name": "Chi-square test", "error": "Implementation pending"}
    
    def _generate_conclusion(self, hypothesis: Hypothesis, 
                           statistical_results: Dict[str, Any], 
                           p_values: Dict[str, float]) -> str:
        """Generate research conclusion"""
        significant_tests = [test for test, p_val in p_values.items() 
                           if p_val < hypothesis.significance_level]
        
        if significant_tests:
            conclusion = f"REJECT null hypothesis. Found significant evidence for: {hypothesis.alternative_hypothesis}"
            conclusion += f" (Significant tests: {', '.join(significant_tests)})"
        else:
            conclusion = f"FAIL TO REJECT null hypothesis. Insufficient evidence against: {hypothesis.null_hypothesis}"
        
        return conclusion
    
    def _assess_practical_significance(self, effect_sizes: Dict[str, float], 
                                     hypothesis: Hypothesis) -> Dict[str, bool]:
        """Assess practical significance of effects"""
        practical_significance = {}
        
        # Cohen's conventions for effect sizes
        for test, effect_size in effect_sizes.items():
            if "correlation" in test.lower():
                # For correlations: small=0.1, medium=0.3, large=0.5
                practical_significance[test] = abs(effect_size) >= 0.3
            else:
                # For Cohen's d and similar: small=0.2, medium=0.5, large=0.8
                practical_significance[test] = abs(effect_size) >= 0.5
        
        return practical_significance
    
    def _generate_visualizations(self, design: ExperimentalDesign, 
                               data: pd.DataFrame) -> List[str]:
        """Generate visualization plots"""
        visualizations = []
        
        try:
            # Create output directory
            output_dir = Path("artifacts/research_visualizations")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Box plot for group comparisons
            if len(design.factors) == 1:
                factor = design.factors[0]
                dependent_var = list(design.hypothesis.variables.values())[0]
                
                if factor in data.columns and dependent_var in data.columns:
                    plt.figure(figsize=(10, 6))
                    data.boxplot(column=dependent_var, by=factor)
                    plt.title(f"{dependent_var} by {factor}")
                    plt.suptitle("")  # Remove default title
                    
                    plot_path = output_dir / f"boxplot_{design.design_id}.png"
                    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                    plt.close()
                    visualizations.append(str(plot_path))
            
            # Correlation heatmap
            numeric_data = data.select_dtypes(include=[np.number])
            if len(numeric_data.columns) >= 2:
                plt.figure(figsize=(12, 8))
                correlation_matrix = numeric_data.corr()
                sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
                plt.title("Correlation Matrix")
                
                plot_path = output_dir / f"correlation_{design.design_id}.png"
                plt.savefig(plot_path, dpi=300, bbox_inches='tight')
                plt.close()
                visualizations.append(str(plot_path))
        
        except Exception as e:
            print(f"Warning: Could not generate visualizations: {e}")
        
        return visualizations

class ResearchToolsInterface:
    """Main interface for research tools"""
    
    def __init__(self):
        self.hypothesis_generator = HypothesisGenerator()
        self.experimental_designer = ExperimentalDesigner()
        self.statistical_analyzer = StatisticalAnalyzer()
    
    def conduct_research_study(self, data_file: str, research_question: str) -> Dict[str, Any]:
        """Conduct complete research study from data"""
        
        # Load data
        if data_file.endswith('.csv'):
            data = pd.read_csv(data_file)
        elif data_file.endswith('.json'):
            data = pd.read_json(data_file)
        else:
            raise ValueError("Unsupported data format")
        
        # Summarize data for hypothesis generation
        data_summary = self._summarize_data(data)
        
        # Generate hypotheses
        hypotheses = self.hypothesis_generator.generate_hypotheses(data_summary)
        
        # Select most relevant hypothesis
        selected_hypothesis = self._select_hypothesis(hypotheses, research_question)
        
        # Design experiment
        experimental_design = self.experimental_designer.design_experiment(
            selected_hypothesis, data_summary
        )
        
        # Perform analysis
        experimental_result = self.statistical_analyzer.analyze_experiment(
            experimental_design, data
        )
        
        return {
            "research_question": research_question,
            "data_summary": data_summary,
            "generated_hypotheses": [h.to_dict() for h in hypotheses],
            "selected_hypothesis": selected_hypothesis.to_dict(),
            "experimental_design": experimental_design.to_dict(),
            "results": experimental_result.to_dict()
        }
    
    def _summarize_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Summarize data for hypothesis generation"""
        summary = {
            "shape": data.shape,
            "columns": list(data.columns),
            "numeric_columns": list(data.select_dtypes(include=[np.number]).columns),
            "categorical_columns": list(data.select_dtypes(include=['object']).columns),
            "factors": {},
            "metrics": [],
            "models": [],
            "methods": []
        }
        
        # Identify potential factors (categorical variables)
        for col in summary["categorical_columns"]:
            unique_values = data[col].unique()
            if len(unique_values) <= 10:  # Reasonable number of levels
                summary["factors"][col] = list(unique_values)
        
        # Identify metrics (numeric columns)
        summary["metrics"] = summary["numeric_columns"][:5]  # Limit to first 5
        
        # Look for model and method columns
        if "model" in data.columns:
            summary["models"] = list(data["model"].unique())
        if "method" in data.columns:
            summary["methods"] = list(data["method"].unique())
        
        return summary
    
    def _select_hypothesis(self, hypotheses: List[Hypothesis], research_question: str) -> Hypothesis:
        """Select most relevant hypothesis based on research question"""
        if not hypotheses:
            # Create default hypothesis
            return Hypothesis(
                hypothesis_id="default",
                hypothesis_type=HypothesisType.PERFORMANCE_COMPARISON,
                description="Default performance comparison",
                null_hypothesis="No significant difference in performance",
                alternative_hypothesis="Significant difference in performance exists",
                variables={"method": "performance"},
                expected_outcome="significant_difference",
                significance_level=0.05,
                metadata={}
            )
        
        # Simple selection: return first hypothesis (could be enhanced with NLP)
        return hypotheses[0]

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Advanced research tools for hypothesis testing")
    parser.add_argument("--data", required=True, help="Data file (CSV or JSON)")
    parser.add_argument("--question", required=True, help="Research question")
    parser.add_argument("--output", default="artifacts/research_results.json", help="Output file")
    
    args = parser.parse_args()
    
    # Conduct research study
    research_tools = ResearchToolsInterface()
    results = research_tools.conduct_research_study(args.data, args.question)
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("=== RESEARCH STUDY RESULTS ===")
    print(f"Research Question: {results['research_question']}")
    print(f"Data Shape: {results['data_summary']['shape']}")
    print(f"Generated Hypotheses: {len(results['generated_hypotheses'])}")
    print(f"Selected Hypothesis: {results['selected_hypothesis']['description']}")
    print(f"Conclusion: {results['results']['conclusion']}")
    
    print(f"\nDetailed results saved to {output_path}")

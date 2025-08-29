"""
Field Analytics - Analyzes field usage patterns and correction effectiveness
"""

import json
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from collections import defaultdict, Counter
import time
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)

class FieldAnalytics:
    """Analyzes field correction patterns and provides insights."""
    
    def __init__(self, field_trainer=None, field_validator=None):
        self.field_trainer = field_trainer
        self.field_validator = field_validator
        self.analytics_cache = {}
        self.cache_expiry = 300  # 5 minutes
        
    def analyze_correction_patterns(self) -> Dict:
        """Analyze patterns in field corrections to identify problem areas."""
        if not self.field_trainer:
            return {"error": "Field trainer not available"}
        
        cache_key = "correction_patterns"
        if self._is_cached(cache_key):
            return self.analytics_cache[cache_key]["data"]
        
        corrections = self.field_trainer.corrections
        if not corrections:
            return {"message": "No corrections available for analysis"}
        
        analysis = {
            "total_corrections": len(corrections),
            "time_range": {
                "start": min(c.timestamp for c in corrections),
                "end": max(c.timestamp for c in corrections),
                "span_days": (max(c.timestamp for c in corrections) - min(c.timestamp for c in corrections)) / 86400
            },
            "most_problematic_fields": self._analyze_problematic_fields(corrections),
            "correction_sources": self._analyze_correction_sources(corrections),
            "temporal_patterns": self._analyze_temporal_patterns(corrections),
            "prompt_categories": self._analyze_prompt_categories(corrections),
            "index_patterns": self._analyze_index_patterns(corrections),
            "confidence_distribution": self._analyze_confidence_distribution(corrections)
        }
        
        self._cache_result(cache_key, analysis)
        return analysis
    
    def _analyze_problematic_fields(self, corrections) -> List[Dict]:
        """Identify fields that require the most corrections."""
        field_counts = Counter()
        field_contexts = defaultdict(set)
        field_corrections = defaultdict(Counter)
        
        for correction in corrections:
            field_counts[correction.original_field] += 1
            field_contexts[correction.original_field].add(correction.corrected_field)
            field_corrections[correction.original_field][correction.corrected_field] += 1
        
        problematic = []
        for field, count in field_counts.most_common(20):
            corrections_to = dict(field_corrections[field])
            most_common_correction = field_corrections[field].most_common(1)[0]
            
            problematic.append({
                "field": field,
                "correction_count": count,
                "unique_corrections": len(field_contexts[field]),
                "most_common_correction": most_common_correction[0],
                "correction_frequency": most_common_correction[1],
                "all_corrections": corrections_to,
                "consistency_score": most_common_correction[1] / count  # How often it's corrected to the same thing
            })
        
        return problematic
    
    def _analyze_correction_sources(self, corrections) -> Dict:
        """Analyze where corrections are coming from."""
        sources = Counter(c.source for c in corrections)
        
        return {
            "source_counts": dict(sources),
            "source_percentages": {
                source: (count / len(corrections)) * 100 
                for source, count in sources.items()
            }
        }
    
    def _analyze_temporal_patterns(self, corrections) -> Dict:
        """Analyze correction patterns over time."""
        if not corrections:
            return {}
        
        # Group by day
        daily_corrections = defaultdict(int)
        hourly_corrections = defaultdict(int)
        
        for correction in corrections:
            dt = datetime.fromtimestamp(correction.timestamp)
            day_key = dt.strftime("%Y-%m-%d")
            hour_key = dt.hour
            
            daily_corrections[day_key] += 1
            hourly_corrections[hour_key] += 1
        
        # Calculate trends
        sorted_days = sorted(daily_corrections.items())
        if len(sorted_days) >= 2:
            recent_avg = statistics.mean([count for _, count in sorted_days[-7:]])  # Last 7 days
            older_avg = statistics.mean([count for _, count in sorted_days[:-7]]) if len(sorted_days) > 7 else recent_avg
            trend = "improving" if recent_avg < older_avg else "worsening" if recent_avg > older_avg else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "daily_corrections": dict(daily_corrections),
            "hourly_distribution": dict(hourly_corrections),
            "peak_hour": max(hourly_corrections, key=hourly_corrections.get) if hourly_corrections else None,
            "trend": trend,
            "total_days": len(daily_corrections)
        }
    
    def _analyze_prompt_categories(self, corrections) -> Dict:
        """Categorize prompts to understand correction contexts."""
        categories = {
            "security_queries": ["malicious", "attack", "intrusion", "threat", "hack", "breach"],
            "network_queries": ["traffic", "connection", "packet", "protocol", "port", "ip"],
            "time_queries": ["yesterday", "last", "recent", "between", "during", "time"],
            "aggregation_queries": ["count", "sum", "average", "max", "min", "group"],
            "filtering_queries": ["filter", "where", "with", "having", "contains"]
        }
        
        category_counts = defaultdict(int)
        category_fields = defaultdict(set)
        
        for correction in corrections:
            prompt_lower = correction.prompt.lower()
            
            for category, keywords in categories.items():
                if any(keyword in prompt_lower for keyword in keywords):
                    category_counts[category] += 1
                    category_fields[category].add(correction.original_field)
        
        return {
            "category_counts": dict(category_counts),
            "category_problem_fields": {
                category: list(fields) 
                for category, fields in category_fields.items()
            }
        }
    
    def _analyze_index_patterns(self, corrections) -> Dict:
        """Analyze correction patterns by index."""
        index_corrections = defaultdict(lambda: defaultdict(int))
        index_fields = defaultdict(set)
        
        for correction in corrections:
            index_corrections[correction.index][correction.original_field] += 1
            index_fields[correction.index].add(correction.original_field)
        
        return {
            "corrections_by_index": {
                index: dict(corrections) 
                for index, corrections in index_corrections.items()
            },
            "problematic_fields_by_index": {
                index: list(fields) 
                for index, fields in index_fields.items()
            }
        }
    
    def _analyze_confidence_distribution(self, corrections) -> Dict:
        """Analyze confidence scores of corrections."""
        confidences = [c.confidence for c in corrections]
        
        if not confidences:
            return {}
        
        return {
            "mean_confidence": statistics.mean(confidences),
            "median_confidence": statistics.median(confidences),
            "min_confidence": min(confidences),
            "max_confidence": max(confidences),
            "low_confidence_count": len([c for c in confidences if c < 0.7]),
            "high_confidence_count": len([c for c in confidences if c >= 0.9])
        }
    
    def generate_improvement_recommendations(self) -> List[Dict]:
        """Generate specific recommendations for improving field handling."""
        recommendations = []
        
        if not self.field_trainer:
            return [{"type": "error", "message": "Field trainer not available"}]
        
        analysis = self.analyze_correction_patterns()
        
        # Recommendation 1: Address most problematic fields
        if "most_problematic_fields" in analysis:
            top_problems = analysis["most_problematic_fields"][:5]
            
            for problem in top_problems:
                if problem["consistency_score"] < 0.7:
                    recommendations.append({
                        "type": "field_mapping",
                        "priority": "high",
                        "field": problem["field"],
                        "issue": "Inconsistent corrections",
                        "description": f"Field '{problem['field']}' is corrected inconsistently. Most common correction is '{problem['most_common_correction']}' but only {problem['consistency_score']:.1%} of the time.",
                        "action": f"Add stronger field mapping rule: {problem['field']} -> {problem['most_common_correction']}"
                    })
                elif problem["correction_count"] > 10:
                    recommendations.append({
                        "type": "field_mapping",
                        "priority": "medium",
                        "field": problem["field"],
                        "issue": "Frequently corrected field",
                        "description": f"Field '{problem['field']}' requires {problem['correction_count']} corrections, usually to '{problem['most_common_correction']}'.",
                        "action": f"Strengthen prompt examples showing {problem['field']} -> {problem['most_common_correction']}"
                    })
        
        # Recommendation 2: Address temporal patterns
        if "temporal_patterns" in analysis:
            temporal = analysis["temporal_patterns"]
            if temporal.get("trend") == "worsening":
                recommendations.append({
                    "type": "training",
                    "priority": "medium",
                    "issue": "Increasing correction rate",
                    "description": "Field corrections are increasing over time, suggesting the model isn't learning effectively.",
                    "action": "Review and strengthen field training examples and validation rules"
                })
        
        # Recommendation 3: Category-specific issues
        if "prompt_categories" in analysis:
            categories = analysis["prompt_categories"]
            for category, count in categories["category_counts"].items():
                if count > 20:  # High correction rate in category
                    problem_fields = categories["category_problem_fields"].get(category, [])
                    recommendations.append({
                        "type": "prompt_engineering",
                        "priority": "medium", 
                        "category": category,
                        "issue": f"High corrections in {category}",
                        "description": f"{count} corrections needed in {category} queries. Common problematic fields: {', '.join(problem_fields[:3])}",
                        "action": f"Add category-specific field examples for {category} in prompt templates"
                    })
        
        # Recommendation 4: Confidence issues
        if "confidence_distribution" in analysis:
            conf_dist = analysis["confidence_distribution"]
            if conf_dist.get("low_confidence_count", 0) > len(self.field_trainer.corrections) * 0.2:
                recommendations.append({
                    "type": "validation",
                    "priority": "high",
                    "issue": "Many low-confidence corrections",
                    "description": f"{conf_dist['low_confidence_count']} corrections have low confidence (<0.7), suggesting uncertain field mappings.",
                    "action": "Review and strengthen field validation rules, add more definitive mapping examples"
                })
        
        return recommendations
    
    def generate_training_report(self) -> Dict:
        """Generate comprehensive training effectiveness report."""
        if not self.field_trainer:
            return {"error": "Field trainer not available"}
        
        analysis = self.analyze_correction_patterns()
        recommendations = self.generate_improvement_recommendations()
        
        # Calculate effectiveness metrics
        total_corrections = len(self.field_trainer.corrections)
        learned_mappings = len(self.field_trainer.get_learned_mappings())
        
        effectiveness_score = 0
        if total_corrections > 0:
            # Base effectiveness on how many consistent mappings we've learned
            consistent_mappings = len([
                p for p in analysis.get("most_problematic_fields", [])
                if p.get("consistency_score", 0) >= 0.8
            ])
            effectiveness_score = (consistent_mappings / min(total_corrections, 20)) * 100
        
        report = {
            "generation_time": datetime.now().isoformat(),
            "summary": {
                "total_corrections": total_corrections,
                "learned_mappings": learned_mappings,
                "effectiveness_score": effectiveness_score,
                "recommendations_count": len(recommendations)
            },
            "detailed_analysis": analysis,
            "recommendations": recommendations,
            "actionable_items": [
                rec for rec in recommendations 
                if rec.get("priority") in ["high", "medium"]
            ]
        }
        
        return report
    
    def export_analytics_report(self, output_path: str = None) -> str:
        """Export comprehensive analytics report."""
        if not output_path:
            timestamp = int(time.time())
            output_path = f"field_analytics_report_{timestamp}.json"
        
        report = self.generate_training_report()
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Analytics report exported to {output_path}")
        return output_path
    
    def _is_cached(self, cache_key: str) -> bool:
        """Check if analysis is cached and still valid."""
        if cache_key not in self.analytics_cache:
            return False
        
        cache_time = self.analytics_cache[cache_key]["timestamp"]
        return (time.time() - cache_time) < self.cache_expiry
    
    def _cache_result(self, cache_key: str, data: Dict):
        """Cache analysis result."""
        self.analytics_cache[cache_key] = {
            "data": data,
            "timestamp": time.time()
        }
    
    def get_real_time_metrics(self) -> Dict:
        """Get real-time field correction metrics."""
        if not self.field_trainer:
            return {"error": "Field trainer not available"}
        
        corrections = self.field_trainer.corrections
        
        # Calculate metrics for last 24 hours
        now = time.time()
        day_ago = now - 86400
        recent_corrections = [c for c in corrections if c.timestamp >= day_ago]
        
        return {
            "timestamp": now,
            "last_24h": {
                "total_corrections": len(recent_corrections),
                "unique_fields": len(set(c.original_field for c in recent_corrections)),
                "average_confidence": statistics.mean([c.confidence for c in recent_corrections]) if recent_corrections else 0
            },
            "overall": {
                "total_corrections": len(corrections),
                "learned_mappings": len(self.field_trainer.get_learned_mappings()),
                "training_effectiveness": len(self.field_trainer.get_learned_mappings()) / max(len(corrections), 1) * 100
            },
            "top_recent_problems": [
                c.original_field for c in sorted(recent_corrections, key=lambda x: x.timestamp, reverse=True)[:5]
            ]
        }
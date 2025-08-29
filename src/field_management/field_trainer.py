"""
Field Trainer - Dynamically learns and improves field mappings from corrections
"""

import json
import logging
from typing import Dict, List, Tuple, Optional, Set
from pathlib import Path
from collections import defaultdict, Counter
import pickle
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FieldCorrection:
    """Record of a field correction made during query generation."""
    original_field: str
    corrected_field: str
    prompt: str
    index: str
    timestamp: float
    confidence: float = 1.0
    source: str = "manual"  # manual, validator, context_manager

class FieldTrainer:
    """Trains and improves field mappings based on correction patterns."""
    
    def __init__(self, training_data_path: str = "data/field_training.json"):
        self.training_data_path = Path(training_data_path)
        self.corrections = []
        self.field_patterns = defaultdict(Counter)
        self.prompt_patterns = defaultdict(list)
        self.confidence_scores = defaultdict(float)
        self.learning_metadata = {
            "last_training": None,
            "corrections_count": 0,
            "accuracy_score": 0.0,
            "patterns_learned": 0
        }
        
        # Load existing training data
        self._load_training_data()
        
    def _load_training_data(self):
        """Load existing training data from disk."""
        if self.training_data_path.exists():
            try:
                with open(self.training_data_path, 'r') as f:
                    data = json.load(f)
                    
                # Convert to FieldCorrection objects
                for correction_data in data.get("corrections", []):
                    correction = FieldCorrection(**correction_data)
                    self.corrections.append(correction)
                    
                self.learning_metadata = data.get("metadata", self.learning_metadata)
                self._rebuild_patterns()
                
                logger.info(f"Loaded {len(self.corrections)} field corrections from training data")
                
            except Exception as e:
                logger.error(f"Error loading training data: {e}")
    
    def _save_training_data(self):
        """Save training data to disk."""
        try:
            self.training_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "corrections": [
                    {
                        "original_field": c.original_field,
                        "corrected_field": c.corrected_field,
                        "prompt": c.prompt,
                        "index": c.index,
                        "timestamp": c.timestamp,
                        "confidence": c.confidence,
                        "source": c.source
                    }
                    for c in self.corrections
                ],
                "metadata": self.learning_metadata
            }
            
            with open(self.training_data_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving training data: {e}")
    
    def _rebuild_patterns(self):
        """Rebuild learned patterns from corrections."""
        self.field_patterns.clear()
        self.prompt_patterns.clear()
        self.confidence_scores.clear()
        
        for correction in self.corrections:
            # Track field mapping patterns
            self.field_patterns[correction.original_field][correction.corrected_field] += 1
            
            # Track prompt contexts where corrections occur
            self.prompt_patterns[correction.original_field].append({
                "prompt": correction.prompt,
                "corrected_to": correction.corrected_field,
                "confidence": correction.confidence
            })
            
            # Update confidence scores
            mapping_key = f"{correction.original_field}->{correction.corrected_field}"
            self.confidence_scores[mapping_key] = max(
                self.confidence_scores[mapping_key], 
                correction.confidence
            )
    
    def record_correction(self, 
                         original_field: str, 
                         corrected_field: str, 
                         prompt: str, 
                         index: str,
                         confidence: float = 1.0,
                         source: str = "manual"):
        """Record a new field correction for training."""
        correction = FieldCorrection(
            original_field=original_field,
            corrected_field=corrected_field,
            prompt=prompt,
            index=index,
            timestamp=time.time(),
            confidence=confidence,
            source=source
        )
        
        self.corrections.append(correction)
        
        # Update patterns
        self.field_patterns[original_field][corrected_field] += 1
        self.prompt_patterns[original_field].append({
            "prompt": prompt,
            "corrected_to": corrected_field,
            "confidence": confidence
        })
        
        mapping_key = f"{original_field}->{corrected_field}"
        self.confidence_scores[mapping_key] = max(
            self.confidence_scores[mapping_key], 
            confidence
        )
        
        self.learning_metadata["corrections_count"] = len(self.corrections)
        
        # Save periodically
        if len(self.corrections) % 10 == 0:
            self._save_training_data()
        
        logger.info(f"Recorded field correction: {original_field} -> {corrected_field}")
    
    def get_field_suggestions(self, incorrect_field: str, 
                            prompt: str = None, 
                            index: str = None) -> List[Tuple[str, float, str]]:
        """Get suggestions for correcting a field based on learned patterns."""
        suggestions = []
        
        # Direct pattern matching
        if incorrect_field in self.field_patterns:
            for corrected_field, count in self.field_patterns[incorrect_field].most_common(5):
                mapping_key = f"{incorrect_field}->{corrected_field}"
                base_confidence = self.confidence_scores[mapping_key]
                
                # Boost confidence based on frequency
                frequency_boost = min(0.1, count / 100.0)
                confidence = min(1.0, base_confidence + frequency_boost)
                
                reason = f"Learned from {count} corrections"
                suggestions.append((corrected_field, confidence, reason))
        
        # Context-based suggestions (if prompt provided)
        if prompt and incorrect_field in self.prompt_patterns:
            prompt_lower = prompt.lower()
            
            for pattern in self.prompt_patterns[incorrect_field]:
                # Simple similarity check
                if self._prompt_similarity(prompt_lower, pattern["prompt"].lower()) > 0.6:
                    corrected_field = pattern["corrected_to"]
                    confidence = pattern["confidence"] * 0.9  # Slight penalty for context matching
                    reason = "Similar prompt context"
                    
                    # Avoid duplicates
                    if not any(s[0] == corrected_field for s in suggestions):
                        suggestions.append((corrected_field, confidence, reason))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def _prompt_similarity(self, prompt1: str, prompt2: str) -> float:
        """Calculate simple similarity between prompts."""
        words1 = set(prompt1.split())
        words2 = set(prompt2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def train_from_corrections(self, corrections: List[Dict]) -> Dict:
        """Train from a batch of corrections."""
        training_stats = {
            "processed": 0,
            "new_patterns": 0,
            "updated_patterns": 0,
            "errors": []
        }
        
        for correction_data in corrections:
            try:
                # Validate required fields
                required_fields = ["original_field", "corrected_field", "prompt", "index"]
                if not all(field in correction_data for field in required_fields):
                    training_stats["errors"].append(f"Missing required fields in correction: {correction_data}")
                    continue
                
                original_count = len(self.field_patterns[correction_data["original_field"]])
                
                self.record_correction(
                    original_field=correction_data["original_field"],
                    corrected_field=correction_data["corrected_field"],
                    prompt=correction_data["prompt"],
                    index=correction_data["index"],
                    confidence=correction_data.get("confidence", 1.0),
                    source=correction_data.get("source", "batch_training")
                )
                
                new_count = len(self.field_patterns[correction_data["original_field"]])
                if new_count > original_count:
                    training_stats["new_patterns"] += 1
                else:
                    training_stats["updated_patterns"] += 1
                
                training_stats["processed"] += 1
                
            except Exception as e:
                training_stats["errors"].append(f"Error processing correction {correction_data}: {str(e)}")
        
        # Update metadata
        self.learning_metadata["last_training"] = time.time()
        self.learning_metadata["patterns_learned"] = len(self.field_patterns)
        
        # Save training data
        self._save_training_data()
        
        return training_stats
    
    def get_learned_mappings(self) -> Dict[str, str]:
        """Get the most confident field mappings learned."""
        mappings = {}
        
        for original_field, corrections in self.field_patterns.items():
            if corrections:
                # Get most common correction
                best_correction, count = corrections.most_common(1)[0]
                mapping_key = f"{original_field}->{best_correction}"
                confidence = self.confidence_scores[mapping_key]
                
                # Only include high-confidence mappings
                if confidence >= 0.8 and count >= 2:
                    mappings[original_field] = best_correction
        
        return mappings
    
    def generate_field_examples(self, field_name: str, limit: int = 5) -> List[Dict]:
        """Generate training examples for a field based on learned corrections."""
        examples = []
        
        if field_name not in self.prompt_patterns:
            return examples
        
        patterns = self.prompt_patterns[field_name]
        
        # Sort by confidence and take top examples
        sorted_patterns = sorted(patterns, key=lambda x: x["confidence"], reverse=True)
        
        for pattern in sorted_patterns[:limit]:
            examples.append({
                "prompt": pattern["prompt"],
                "correct_field": pattern["corrected_to"],
                "incorrect_field": field_name,
                "confidence": pattern["confidence"],
                "lesson": f"When users mention '{field_name}', they likely mean '{pattern['corrected_to']}'"
            })
        
        return examples
    
    def get_training_statistics(self) -> Dict:
        """Get comprehensive training statistics."""
        stats = {
            "total_corrections": len(self.corrections),
            "unique_field_mappings": len(self.field_patterns),
            "high_confidence_mappings": len([
                mapping for mapping, conf in self.confidence_scores.items() 
                if conf >= 0.9
            ]),
            "learning_metadata": self.learning_metadata.copy(),
            "top_corrections": [],
            "recent_corrections": []
        }
        
        # Top corrections by frequency
        all_corrections = []
        for original_field, corrections in self.field_patterns.items():
            for corrected_field, count in corrections.items():
                mapping_key = f"{original_field}->{corrected_field}"
                confidence = self.confidence_scores[mapping_key]
                all_corrections.append({
                    "original": original_field,
                    "corrected": corrected_field,
                    "count": count,
                    "confidence": confidence
                })
        
        stats["top_corrections"] = sorted(
            all_corrections, 
            key=lambda x: (x["count"], x["confidence"]), 
            reverse=True
        )[:10]
        
        # Recent corrections
        recent = sorted(self.corrections, key=lambda x: x.timestamp, reverse=True)
        stats["recent_corrections"] = [
            {
                "original": c.original_field,
                "corrected": c.corrected_field,
                "prompt": c.prompt[:100] + "..." if len(c.prompt) > 100 else c.prompt,
                "timestamp": c.timestamp,
                "source": c.source
            }
            for c in recent[:10]
        ]
        
        return stats
    
    def export_corrections_for_analysis(self, output_path: str = None) -> str:
        """Export corrections data for external analysis."""
        if not output_path:
            output_path = f"field_corrections_export_{int(time.time())}.json"
        
        export_data = {
            "export_timestamp": time.time(),
            "corrections": [
                {
                    "original_field": c.original_field,
                    "corrected_field": c.corrected_field,
                    "prompt": c.prompt,
                    "index": c.index,
                    "timestamp": c.timestamp,
                    "confidence": c.confidence,
                    "source": c.source
                }
                for c in self.corrections
            ],
            "learned_mappings": self.get_learned_mappings(),
            "statistics": self.get_training_statistics()
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return output_path
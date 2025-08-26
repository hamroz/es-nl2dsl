"""
Cross-Modal Attention for Multi-Modal ES-NL2DSL

Implements attention mechanisms that compute relationships and importance
weights across different modalities (text, visual, data) for enhanced
query understanding and generation.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class AttentionScore:
    """Represents attention score between modalities or elements."""
    source_modality: str
    target_modality: str
    attention_weight: float
    confidence: float
    explanation: str

@dataclass
class AttentionMap:
    """Complete attention mapping across modalities."""
    attention_matrix: np.ndarray
    modality_names: List[str]
    element_weights: Dict[str, float]
    global_attention: Dict[str, float]

class CrossModalAttention:
    """
    Advanced cross-modal attention mechanism for multi-modal query understanding.
    
    Computes attention weights and relationships between text prompts,
    visual inputs, and data samples to enhance query generation.
    """
    
    def __init__(self):
        self.attention_history = []
        self.learned_patterns = {}
        
        # Attention computation parameters
        self.temperature = 0.1  # Softmax temperature for attention
        self.modality_weights = {
            'text': 1.0,
            'visual': 0.8,
            'data': 0.9
        }
    
    def compute_cross_modal_attention(self,
                                    text_features: Dict[str, Any],
                                    visual_features: Dict[str, Any],
                                    data_features: Dict[str, Any]) -> AttentionMap:
        """
        Compute comprehensive cross-modal attention.
        
        Args:
            text_features: Features from text modality
            visual_features: Features from visual modality  
            data_features: Features from data modality
            
        Returns:
            Complete attention mapping
        """
        try:
            # Prepare modality feature vectors
            modalities = {}
            if text_features:
                modalities['text'] = self._extract_text_feature_vector(text_features)
            if visual_features.get('has_visuals'):
                modalities['visual'] = self._extract_visual_feature_vector(visual_features)
            if data_features.get('has_data_samples'):
                modalities['data'] = self._extract_data_feature_vector(data_features)
            
            if not modalities:
                return self._create_empty_attention_map()
            
            # Compute pairwise attention scores
            attention_matrix = self._compute_attention_matrix(modalities)
            
            # Calculate element-level attention weights
            element_weights = self._compute_element_weights(modalities)
            
            # Calculate global modality attention
            global_attention = self._compute_global_attention(modalities, attention_matrix)
            
            attention_map = AttentionMap(
                attention_matrix=attention_matrix,
                modality_names=list(modalities.keys()),
                element_weights=element_weights,
                global_attention=global_attention
            )
            
            # Store for learning
            self._record_attention_computation(attention_map, text_features, visual_features, data_features)
            
            return attention_map
            
        except Exception as e:
            logger.error(f"Cross-modal attention computation failed: {e}")
            return self._create_empty_attention_map()
    
    def _extract_text_feature_vector(self, text_features: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from text modality."""
        features = []
        
        # Semantic features
        semantic_features = text_features.get('semantic_features', {})
        
        # Keywords (converted to counts by category)
        keywords = semantic_features.get('keywords', [])
        keyword_categories = {'security': 0, 'networking': 0, 'system': 0}
        for keyword_info in keywords:
            category = keyword_info.get('category', 'unknown')
            if category in keyword_categories:
                keyword_categories[category] += 1
        features.extend(list(keyword_categories.values()))
        
        # Temporal expressions count
        temporal_count = len(semantic_features.get('temporal_expressions', []))
        features.append(temporal_count)
        
        # Numerical expressions count
        numerical_count = len(semantic_features.get('numerical_expressions', []))
        features.append(numerical_count)
        
        # Logical operators count
        logical_count = len(semantic_features.get('logical_operators', []))
        features.append(logical_count)
        
        # Aggregation hints count
        agg_count = len(semantic_features.get('aggregation_hints', []))
        features.append(agg_count)
        
        # Query intent scores
        query_intent = text_features.get('query_intent', {})
        features.extend([
            query_intent.get('search', 0),
            query_intent.get('filter', 0),
            query_intent.get('aggregate', 0),
            query_intent.get('monitor', 0),
            query_intent.get('analyze', 0)
        ])
        
        # Schema alignment
        schema_alignment = text_features.get('schema_alignment', {})
        field_matches = len(schema_alignment.get('field_matches', []))
        type_matches = len(schema_alignment.get('type_matches', []))
        features.extend([field_matches, type_matches])
        
        return np.array(features, dtype=float)
    
    def _extract_visual_feature_vector(self, visual_features: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from visual modality."""
        features = []
        
        # Basic visual metrics
        visual_count = visual_features.get('visual_count', 0)
        features.append(visual_count)
        
        # Visual type distribution
        visual_types = {'chart': 0, 'table': 0, 'schema_diagram': 0, 'generic': 0}
        visual_feature_list = visual_features.get('visual_features', [])
        for vf in visual_feature_list:
            vtype = vf.get('type', 'generic')
            if vtype in visual_types:
                visual_types[vtype] += 1
        features.extend(list(visual_types.values()))
        
        # Detected elements count
        detected_elements = visual_features.get('detected_elements', [])
        element_types = {'text_block': 0, 'chart_type': 0, 'table_header': 0, 'axis_label': 0}
        for element in detected_elements:
            element_type = element.get('element_type', 'unknown')
            if element_type in element_types:
                element_types[element_type] += 1
        features.extend(list(element_types.values()))
        
        # Chart analysis features (if available)
        chart_analysis_count = 0
        for vf in visual_feature_list:
            if vf.get('features', {}).get('chart_analysis'):
                chart_analysis_count += 1
        features.append(chart_analysis_count)
        
        return np.array(features, dtype=float)
    
    def _extract_data_feature_vector(self, data_features: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from data modality."""
        features = []
        
        # Basic data metrics
        sample_count = data_features.get('sample_count', 0)
        features.append(sample_count)
        
        # Pattern distribution
        extracted_patterns = data_features.get('extracted_patterns', {})
        pattern_counts = {
            'temporal': len(extracted_patterns.get('temporal', [])),
            'categorical': len(extracted_patterns.get('categorical', [])),
            'numerical': len(extracted_patterns.get('numerical', [])),
            'textual': len(extracted_patterns.get('textual', [])),
            'structural': len(extracted_patterns.get('structural', []))
        }
        features.extend(list(pattern_counts.values()))
        
        # Field statistics
        field_stats = data_features.get('field_statistics', {})
        if field_stats:
            # Field type distribution
            type_counts = {'numerical': 0, 'categorical': 0, 'temporal': 0, 'textual': 0}
            for field_name, stats in field_stats.items():
                data_type = stats.get('data_type', 'unknown')
                if data_type in type_counts:
                    type_counts[data_type] += 1
            features.extend(list(type_counts.values()))
            
            # Average null percentage
            null_percentages = [stats.get('null_percentage', 0) for stats in field_stats.values()]
            avg_null_percentage = np.mean(null_percentages) if null_percentages else 0
            features.append(avg_null_percentage)
        else:
            features.extend([0, 0, 0, 0, 0])  # Zero counts for type distribution + null percentage
        
        # Data quality metrics
        quality_metrics = data_features.get('data_quality_metrics', {})
        features.extend([
            quality_metrics.get('completeness', 0) / 100,  # Normalize to 0-1
            quality_metrics.get('consistency', 0) / 100,
            quality_metrics.get('validity', 0) / 100
        ])
        
        return np.array(features, dtype=float)
    
    def _compute_attention_matrix(self, modalities: Dict[str, np.ndarray]) -> np.ndarray:
        """Compute pairwise attention matrix between modalities."""
        modality_names = list(modalities.keys())
        n_modalities = len(modality_names)
        
        attention_matrix = np.zeros((n_modalities, n_modalities))
        
        for i, mod1 in enumerate(modality_names):
            for j, mod2 in enumerate(modality_names):
                if i != j:
                    # Compute attention score between modalities
                    score = self._compute_pairwise_attention(
                        modalities[mod1], modalities[mod2], mod1, mod2
                    )
                    attention_matrix[i, j] = score
                else:
                    attention_matrix[i, j] = 1.0  # Self-attention
        
        # Apply softmax normalization row-wise
        for i in range(n_modalities):
            row = attention_matrix[i, :]
            if np.sum(row) > 0:
                attention_matrix[i, :] = self._softmax(row / self.temperature)
        
        return attention_matrix
    
    def _compute_pairwise_attention(self, 
                                  vec1: np.ndarray, 
                                  vec2: np.ndarray, 
                                  mod1: str, 
                                  mod2: str) -> float:
        """Compute attention score between two modality vectors."""
        try:
            # Normalize vectors
            if np.linalg.norm(vec1) > 0:
                vec1 = vec1 / np.linalg.norm(vec1)
            if np.linalg.norm(vec2) > 0:
                vec2 = vec2 / np.linalg.norm(vec2)
            
            # Handle different vector sizes by taking minimum length
            min_len = min(len(vec1), len(vec2))
            if min_len == 0:
                return 0.0
            
            vec1_truncated = vec1[:min_len]
            vec2_truncated = vec2[:min_len]
            
            # Compute dot product similarity
            similarity = np.dot(vec1_truncated, vec2_truncated)
            
            # Apply modality-specific weights
            weight1 = self.modality_weights.get(mod1, 1.0)
            weight2 = self.modality_weights.get(mod2, 1.0)
            
            weighted_similarity = similarity * np.sqrt(weight1 * weight2)
            
            # Apply learned patterns if available
            pattern_key = f"{mod1}-{mod2}"
            if pattern_key in self.learned_patterns:
                pattern_boost = self.learned_patterns[pattern_key]
                weighted_similarity *= (1 + pattern_boost * 0.1)
            
            return max(0.0, min(1.0, weighted_similarity))
            
        except Exception as e:
            logger.warning(f"Pairwise attention computation failed for {mod1}-{mod2}: {e}")
            return 0.0
    
    def _compute_element_weights(self, modalities: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Compute attention weights for individual elements within modalities."""
        element_weights = {}
        
        for modality_name, feature_vector in modalities.items():
            if len(feature_vector) == 0:
                element_weights[modality_name] = 0.0
                continue
            
            # Compute element importance based on magnitude and variance
            normalized_features = feature_vector / (np.max(feature_vector) + 1e-8)
            
            # Elements with higher values and more variance get higher weights
            magnitude_score = np.mean(normalized_features)
            variance_score = np.var(normalized_features) if len(normalized_features) > 1 else 0.0
            
            # Combine scores
            element_weight = 0.7 * magnitude_score + 0.3 * variance_score
            
            # Apply modality-specific weight
            element_weight *= self.modality_weights.get(modality_name, 1.0)
            
            element_weights[modality_name] = float(element_weight)
        
        # Normalize weights to sum to 1
        total_weight = sum(element_weights.values())
        if total_weight > 0:
            element_weights = {k: v / total_weight for k, v in element_weights.items()}
        
        return element_weights
    
    def _compute_global_attention(self, 
                                modalities: Dict[str, np.ndarray], 
                                attention_matrix: np.ndarray) -> Dict[str, float]:
        """Compute global attention weights for each modality."""
        global_attention = {}
        modality_names = list(modalities.keys())
        
        if len(modality_names) == 0:
            return global_attention
        
        # Method 1: Use attention matrix row sums (how much each modality attends to others)
        attention_sums = np.sum(attention_matrix, axis=1)
        
        # Method 2: Use feature vector magnitudes
        feature_magnitudes = {}
        for i, modality_name in enumerate(modality_names):
            feature_vector = modalities[modality_name]
            magnitude = np.linalg.norm(feature_vector) if len(feature_vector) > 0 else 0.0
            feature_magnitudes[modality_name] = magnitude
        
        # Combine both methods
        max_magnitude = max(feature_magnitudes.values()) if feature_magnitudes.values() else 1.0
        
        for i, modality_name in enumerate(modality_names):
            attention_score = attention_sums[i] if i < len(attention_sums) else 0.0
            magnitude_score = feature_magnitudes[modality_name] / (max_magnitude + 1e-8)
            
            # Weighted combination
            global_score = 0.6 * attention_score + 0.4 * magnitude_score
            
            # Apply base modality weight
            global_score *= self.modality_weights.get(modality_name, 1.0)
            
            global_attention[modality_name] = float(global_score)
        
        # Normalize to sum to 1
        total_attention = sum(global_attention.values())
        if total_attention > 0:
            global_attention = {k: v / total_attention for k, v in global_attention.items()}
        
        return global_attention
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Compute softmax activation."""
        if len(x) == 0:
            return x
        
        # Subtract max for numerical stability
        exp_x = np.exp(x - np.max(x))
        sum_exp_x = np.sum(exp_x)
        
        if sum_exp_x == 0:
            return np.ones_like(x) / len(x)  # Uniform distribution
        
        return exp_x / sum_exp_x
    
    def _create_empty_attention_map(self) -> AttentionMap:
        """Create empty attention map for error cases."""
        return AttentionMap(
            attention_matrix=np.array([]),
            modality_names=[],
            element_weights={},
            global_attention={}
        )
    
    def _record_attention_computation(self,
                                    attention_map: AttentionMap,
                                    text_features: Dict[str, Any],
                                    visual_features: Dict[str, Any],
                                    data_features: Dict[str, Any]):
        """Record attention computation for learning and analysis."""
        record = {
            'modalities_present': attention_map.modality_names,
            'global_attention': attention_map.global_attention,
            'element_weights': attention_map.element_weights,
            'attention_matrix_shape': attention_map.attention_matrix.shape,
            'input_features': {
                'text_has_keywords': len(text_features.get('semantic_features', {}).get('keywords', [])) > 0,
                'visual_has_charts': any(
                    vf.get('type') == 'chart' 
                    for vf in visual_features.get('visual_features', [])
                ),
                'data_has_patterns': len(data_features.get('extracted_patterns', {})) > 0
            }
        }
        
        self.attention_history.append(record)
        
        # Keep only recent history
        if len(self.attention_history) > 100:
            self.attention_history = self.attention_history[-100:]
        
        # Update learned patterns
        self._update_learned_patterns(record)
    
    def _update_learned_patterns(self, record: Dict[str, Any]):
        """Update learned attention patterns based on history."""
        modalities = record['modalities_present']
        global_attention = record['global_attention']
        
        # Learn patterns between modality pairs
        for i, mod1 in enumerate(modalities):
            for j, mod2 in enumerate(modalities):
                if i != j:
                    pattern_key = f"{mod1}-{mod2}"
                    
                    # Calculate pattern strength based on attention weights
                    att1 = global_attention.get(mod1, 0.0)
                    att2 = global_attention.get(mod2, 0.0)
                    pattern_strength = np.sqrt(att1 * att2)
                    
                    # Update learned pattern with exponential moving average
                    if pattern_key in self.learned_patterns:
                        alpha = 0.1  # Learning rate
                        self.learned_patterns[pattern_key] = (
                            (1 - alpha) * self.learned_patterns[pattern_key] + 
                            alpha * pattern_strength
                        )
                    else:
                        self.learned_patterns[pattern_key] = pattern_strength
    
    def get_attention_explanation(self, attention_map: AttentionMap) -> List[str]:
        """Generate human-readable explanations for attention patterns."""
        explanations = []
        
        if not attention_map.modality_names:
            return ["No modalities available for attention analysis"]
        
        # Explain global attention distribution
        global_att = attention_map.global_attention
        if global_att:
            dominant_modality = max(global_att.items(), key=lambda x: x[1])
            explanations.append(
                f"Primary focus on {dominant_modality[0]} modality "
                f"({dominant_modality[1]:.2f} attention weight)"
            )
            
            # Identify balanced vs skewed attention
            attention_values = list(global_att.values())
            attention_variance = np.var(attention_values)
            
            if attention_variance < 0.1:
                explanations.append("Balanced attention across all modalities")
            else:
                explanations.append("Attention is concentrated on specific modalities")
        
        # Explain cross-modal relationships
        if attention_map.attention_matrix.size > 0:
            n_modalities = len(attention_map.modality_names)
            
            for i in range(n_modalities):
                for j in range(n_modalities):
                    if i != j:
                        attention_score = attention_map.attention_matrix[i, j]
                        if attention_score > 0.6:  # High attention
                            mod1 = attention_map.modality_names[i]
                            mod2 = attention_map.modality_names[j]
                            explanations.append(
                                f"Strong relationship between {mod1} and {mod2} "
                                f"(attention: {attention_score:.2f})"
                            )
        
        # Explain element-level attention
        element_weights = attention_map.element_weights
        if element_weights:
            high_weight_elements = [
                (k, v) for k, v in element_weights.items() if v > 0.4
            ]
            if high_weight_elements:
                explanations.append(
                    f"High-importance elements: {[elem[0] for elem in high_weight_elements]}"
                )
        
        return explanations

class AttentionWeightCalculator:
    """
    Specialized calculator for attention weights in multi-modal contexts.
    
    Provides various attention calculation strategies and optimization methods.
    """
    
    def __init__(self):
        self.calculation_strategies = {
            'dot_product': self._dot_product_attention,
            'cosine_similarity': self._cosine_similarity_attention,
            'learned_weights': self._learned_weights_attention,
            'adaptive': self._adaptive_attention
        }
        
        self.strategy = 'adaptive'  # Default strategy
    
    def calculate_attention_weights(self,
                                  text_context: Dict[str, Any],
                                  visual_context: Dict[str, Any],
                                  data_context: Dict[str, Any],
                                  relationships: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate attention weights using the selected strategy.
        
        Args:
            text_context: Text modality context
            visual_context: Visual modality context
            data_context: Data modality context
            relationships: Cross-modal relationships
            
        Returns:
            Attention weights for each modality
        """
        try:
            strategy_func = self.calculation_strategies.get(
                self.strategy, 
                self._adaptive_attention
            )
            
            return strategy_func(text_context, visual_context, data_context, relationships)
            
        except Exception as e:
            logger.error(f"Attention weight calculation failed: {e}")
            # Return default weights
            return self._default_weights(text_context, visual_context, data_context)
    
    def _dot_product_attention(self,
                             text_context: Dict[str, Any],
                             visual_context: Dict[str, Any],
                             data_context: Dict[str, Any],
                             relationships: Dict[str, Any]) -> Dict[str, float]:
        """Calculate attention using dot product similarity."""
        weights = {'text': 0.5, 'visual': 0.0, 'data': 0.0}
        
        # Extract feature vectors
        text_features = self._extract_text_features_simple(text_context)
        visual_features = self._extract_visual_features_simple(visual_context)
        data_features = self._extract_data_features_simple(data_context)
        
        # Calculate dot products and normalize
        modality_vectors = {}
        if text_features.size > 0:
            modality_vectors['text'] = text_features
        if visual_features.size > 0:
            modality_vectors['visual'] = visual_features
        if data_features.size > 0:
            modality_vectors['data'] = data_features
        
        if len(modality_vectors) > 1:
            # Compute pairwise dot products
            attention_scores = {}
            for mod_name, mod_vector in modality_vectors.items():
                score = np.linalg.norm(mod_vector)  # Use magnitude as importance
                attention_scores[mod_name] = score
            
            # Normalize
            total_score = sum(attention_scores.values())
            if total_score > 0:
                weights = {k: v / total_score for k, v in attention_scores.items()}
        
        return weights
    
    def _cosine_similarity_attention(self,
                                   text_context: Dict[str, Any],
                                   visual_context: Dict[str, Any],
                                   data_context: Dict[str, Any],
                                   relationships: Dict[str, Any]) -> Dict[str, float]:
        """Calculate attention using cosine similarity."""
        weights = {'text': 0.5, 'visual': 0.0, 'data': 0.0}
        
        # Use relationship scores as basis for attention
        semantic_coherence = relationships.get('semantic_coherence', 0.0)
        
        if visual_context.get('has_visuals'):
            text_visual_alignment = relationships.get('text_visual_alignment', 0.0)
            weights['visual'] = text_visual_alignment * 0.3
            weights['text'] = 0.5 - weights['visual'] * 0.5
        
        if data_context.get('has_data_samples'):
            text_data_alignment = relationships.get('text_data_alignment', 0.0)
            weights['data'] = text_data_alignment * 0.3
            weights['text'] = weights['text'] - weights['data'] * 0.5
        
        # Boost based on semantic coherence
        if semantic_coherence > 0.7:
            # High coherence - boost non-text modalities
            boost_factor = 1.2
            if weights['visual'] > 0:
                weights['visual'] *= boost_factor
            if weights['data'] > 0:
                weights['data'] *= boost_factor
        
        # Renormalize
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights
    
    def _learned_weights_attention(self,
                                 text_context: Dict[str, Any],
                                 visual_context: Dict[str, Any],
                                 data_context: Dict[str, Any],
                                 relationships: Dict[str, Any]) -> Dict[str, float]:
        """Calculate attention using learned patterns."""
        # Placeholder for learned weights - would be trained from historical data
        base_weights = {'text': 0.5, 'visual': 0.25, 'data': 0.25}
        
        # Adjust based on modality presence
        if not visual_context.get('has_visuals'):
            base_weights['visual'] = 0.0
            base_weights['text'] += 0.125
            base_weights['data'] += 0.125
        
        if not data_context.get('has_data_samples'):
            base_weights['data'] = 0.0
            base_weights['text'] += 0.125
            base_weights['visual'] += 0.125
        
        return base_weights
    
    def _adaptive_attention(self,
                          text_context: Dict[str, Any],
                          visual_context: Dict[str, Any],
                          data_context: Dict[str, Any],
                          relationships: Dict[str, Any]) -> Dict[str, float]:
        """Calculate attention using adaptive strategy based on context."""
        weights = {'text': 0.5, 'visual': 0.0, 'data': 0.0}
        
        # Base weights on modality richness
        text_richness = self._calculate_modality_richness(text_context, 'text')
        visual_richness = self._calculate_modality_richness(visual_context, 'visual')
        data_richness = self._calculate_modality_richness(data_context, 'data')
        
        # Calculate initial weights based on richness
        total_richness = text_richness + visual_richness + data_richness
        if total_richness > 0:
            weights = {
                'text': text_richness / total_richness,
                'visual': visual_richness / total_richness,
                'data': data_richness / total_richness
            }
        
        # Adjust based on relationships
        semantic_coherence = relationships.get('semantic_coherence', 0.0)
        
        # High coherence boosts multi-modal integration
        if semantic_coherence > 0.6 and len([w for w in weights.values() if w > 0]) > 1:
            # Redistribute to favor multi-modal approach
            text_weight = weights['text']
            weights['text'] = max(0.3, text_weight * 0.8)  # Reduce text dominance
            
            remaining_weight = 1.0 - weights['text']
            other_modalities = [k for k, v in weights.items() if k != 'text' and v > 0]
            
            if other_modalities:
                boost_per_modality = remaining_weight / len(other_modalities)
                for modality in other_modalities:
                    weights[modality] = boost_per_modality
        
        # Ensure text has minimum weight if it's the primary input
        if weights['text'] < 0.2:
            weights['text'] = 0.3
            remaining = 0.7
            other_count = sum(1 for k, v in weights.items() if k != 'text' and v > 0)
            if other_count > 0:
                other_weight = remaining / other_count
                for k in weights:
                    if k != 'text' and weights[k] > 0:
                        weights[k] = other_weight
        
        return weights
    
    def _calculate_modality_richness(self, context: Dict[str, Any], modality_type: str) -> float:
        """Calculate richness/information content of a modality."""
        if modality_type == 'text':
            richness = 1.0  # Text always has base richness
            
            # Boost for semantic features
            semantic_features = context.get('semantic_features', {})
            keyword_count = len(semantic_features.get('keywords', []))
            temporal_count = len(semantic_features.get('temporal_expressions', []))
            numerical_count = len(semantic_features.get('numerical_expressions', []))
            
            richness += (keyword_count + temporal_count + numerical_count) * 0.1
            
            # Boost for schema alignment
            schema_alignment = context.get('schema_alignment', {})
            field_matches = len(schema_alignment.get('field_matches', []))
            richness += field_matches * 0.1
            
        elif modality_type == 'visual':
            if not context.get('has_visuals'):
                return 0.0
                
            richness = 0.5  # Base richness for having visuals
            
            # Boost for visual features
            visual_count = context.get('visual_count', 0)
            richness += visual_count * 0.2
            
            # Boost for detected elements
            detected_elements = len(context.get('detected_elements', []))
            richness += detected_elements * 0.1
            
            # Boost for charts/structured visuals
            visual_features = context.get('visual_features', [])
            structured_visuals = sum(
                1 for vf in visual_features 
                if vf.get('type') in ['chart', 'table', 'schema_diagram']
            )
            richness += structured_visuals * 0.3
            
        elif modality_type == 'data':
            if not context.get('has_data_samples'):
                return 0.0
                
            richness = 0.5  # Base richness for having data
            
            # Boost for data patterns
            patterns = context.get('extracted_patterns', {})
            total_patterns = sum(len(pattern_list) for pattern_list in patterns.values())
            richness += total_patterns * 0.05
            
            # Boost for field statistics
            field_stats = context.get('field_statistics', {})
            richness += len(field_stats) * 0.1
            
            # Boost for data quality
            quality_metrics = context.get('data_quality_metrics', {})
            avg_quality = np.mean([
                quality_metrics.get('completeness', 0),
                quality_metrics.get('consistency', 0),
                quality_metrics.get('validity', 0)
            ]) / 100  # Normalize to 0-1
            richness += avg_quality * 0.5
        
        else:
            richness = 0.0
        
        return max(0.0, min(2.0, richness))  # Clamp to reasonable range
    
    def _extract_text_features_simple(self, text_context: Dict[str, Any]) -> np.ndarray:
        """Extract simple feature vector from text context."""
        features = []
        
        semantic_features = text_context.get('semantic_features', {})
        features.append(len(semantic_features.get('keywords', [])))
        features.append(len(semantic_features.get('temporal_expressions', [])))
        features.append(len(semantic_features.get('numerical_expressions', [])))
        
        query_intent = text_context.get('query_intent', {})
        features.extend([
            query_intent.get('search', 0),
            query_intent.get('filter', 0),
            query_intent.get('aggregate', 0)
        ])
        
        return np.array(features, dtype=float)
    
    def _extract_visual_features_simple(self, visual_context: Dict[str, Any]) -> np.ndarray:
        """Extract simple feature vector from visual context."""
        if not visual_context.get('has_visuals'):
            return np.array([])
        
        features = []
        features.append(visual_context.get('visual_count', 0))
        features.append(len(visual_context.get('detected_elements', [])))
        
        # Count chart types
        visual_features = visual_context.get('visual_features', [])
        chart_count = sum(1 for vf in visual_features if vf.get('type') == 'chart')
        table_count = sum(1 for vf in visual_features if vf.get('type') == 'table')
        
        features.extend([chart_count, table_count])
        
        return np.array(features, dtype=float)
    
    def _extract_data_features_simple(self, data_context: Dict[str, Any]) -> np.ndarray:
        """Extract simple feature vector from data context."""
        if not data_context.get('has_data_samples'):
            return np.array([])
        
        features = []
        features.append(data_context.get('sample_count', 0))
        
        patterns = data_context.get('extracted_patterns', {})
        features.append(len(patterns.get('temporal', [])))
        features.append(len(patterns.get('numerical', [])))
        features.append(len(patterns.get('categorical', [])))
        
        return np.array(features, dtype=float)
    
    def _default_weights(self,
                        text_context: Dict[str, Any],
                        visual_context: Dict[str, Any],
                        data_context: Dict[str, Any]) -> Dict[str, float]:
        """Return default attention weights."""
        weights = {'text': 0.6, 'visual': 0.0, 'data': 0.0}
        
        if visual_context.get('has_visuals'):
            weights['visual'] = 0.2
            weights['text'] = 0.5
        
        if data_context.get('has_data_samples'):
            weights['data'] = 0.2
            if weights['visual'] > 0:
                weights['text'] = 0.3
                weights['visual'] = 0.15
                weights['data'] = 0.15
            else:
                weights['text'] = 0.4
        
        return weights

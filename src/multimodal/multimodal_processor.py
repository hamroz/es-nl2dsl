"""
Multi-Modal Processor for ES-NL2DSL

Core multi-modal processing engine that combines text, visual, and data inputs
for enhanced query understanding and generation.
"""

import json
import base64
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModalityInput:
    """Represents input from a specific modality."""
    modality_type: str  # 'text', 'image', 'data_sample', 'schema_visual'
    content: Any
    confidence: float
    metadata: Dict[str, Any]

@dataclass
class MultiModalContext:
    """Rich context extracted from multiple modalities."""
    text_context: Dict[str, Any]
    visual_context: Dict[str, Any]
    data_context: Dict[str, Any]
    cross_modal_relationships: Dict[str, Any]
    attention_weights: Dict[str, float]
    
class MultiModalProcessor:
    """
    Core processor for multi-modal query understanding.
    
    This revolutionary system combines text prompts with visual data,
    creating the first-of-its-kind multi-modal NL2DSL system.
    """
    
    def __init__(self):
        # Initialize component processors
        self.visual_analyzer = None  # Will be imported lazily
        self.data_extractor = None
        self.attention_calculator = None
        
        # Multi-modal fusion weights
        self.modality_weights = {
            'text': 0.5,
            'visual': 0.3,
            'data_context': 0.2
        }
        
        # Processing history
        self.processing_history = []
        
    def process_multimodal_input(self, 
                                text_prompt: str,
                                visual_inputs: List[Any] = None,
                                data_samples: List[Dict[str, Any]] = None,
                                schema: Dict[str, Any] = None) -> MultiModalContext:
        """
        Process multi-modal input to create rich query context.
        
        Args:
            text_prompt: Natural language query description
            visual_inputs: Images, charts, screenshots, etc.
            data_samples: Sample data records for context
            schema: Elasticsearch schema definition
            
        Returns:
            Rich multi-modal context for query generation
        """
        try:
            logger.info("Processing multi-modal input...")
            
            # Process each modality
            text_context = self._process_text_modality(text_prompt, schema)
            visual_context = self._process_visual_modality(visual_inputs or [])
            data_context = self._process_data_modality(data_samples or [], schema)
            
            # Calculate cross-modal relationships
            cross_modal_relationships = self._compute_cross_modal_relationships(
                text_context, visual_context, data_context
            )
            
            # Compute attention weights across modalities
            attention_weights = self._compute_attention_weights(
                text_context, visual_context, data_context, cross_modal_relationships
            )
            
            # Create unified context
            multimodal_context = MultiModalContext(
                text_context=text_context,
                visual_context=visual_context,
                data_context=data_context,
                cross_modal_relationships=cross_modal_relationships,
                attention_weights=attention_weights
            )
            
            # Record processing
            self._record_processing(text_prompt, multimodal_context)
            
            return multimodal_context
            
        except Exception as e:
            logger.error(f"Multi-modal processing failed: {e}")
            # Return minimal context on failure
            return MultiModalContext(
                text_context={'prompt': text_prompt, 'error': str(e)},
                visual_context={},
                data_context={},
                cross_modal_relationships={},
                attention_weights={'text': 1.0}
            )
    
    def _process_text_modality(self, text_prompt: str, schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process text prompt for semantic understanding."""
        text_context = {
            'original_prompt': text_prompt,
            'processed_prompt': text_prompt.lower().strip(),
            'semantic_features': self._extract_text_features(text_prompt),
            'query_intent': self._classify_query_intent(text_prompt),
            'schema_alignment': self._align_text_with_schema(text_prompt, schema) if schema else {}
        }
        
        return text_context
    
    def _extract_text_features(self, text_prompt: str) -> Dict[str, Any]:
        """Extract semantic features from text prompt."""
        features = {
            'keywords': [],
            'entities': [],
            'temporal_expressions': [],
            'numerical_expressions': [],
            'logical_operators': [],
            'aggregation_hints': []
        }
        
        prompt_lower = text_prompt.lower()
        
        # Extract keywords (simplified NLP)
        security_keywords = ['attack', 'malicious', 'threat', 'intrusion', 'breach', 'vulnerability']
        network_keywords = ['traffic', 'bandwidth', 'latency', 'connection', 'flow', 'packet']
        system_keywords = ['cpu', 'memory', 'disk', 'process', 'performance', 'resource']
        
        for keyword_set, category in [
            (security_keywords, 'security'),
            (network_keywords, 'networking'),
            (system_keywords, 'system')
        ]:
            for keyword in keyword_set:
                if keyword in prompt_lower:
                    features['keywords'].append({'word': keyword, 'category': category})
        
        # Extract temporal expressions
        temporal_patterns = [
            'last hour', 'past day', 'recent', 'yesterday', 'today',
            'between', 'during', 'since', 'until', 'now'
        ]
        for pattern in temporal_patterns:
            if pattern in prompt_lower:
                features['temporal_expressions'].append(pattern)
        
        # Extract numerical expressions
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?(?:\s*(?:mb|gb|tb|%|seconds?|minutes?|hours?))?', prompt_lower)
        features['numerical_expressions'] = numbers
        
        # Extract logical operators
        logical_ops = ['and', 'or', 'not', 'exclude', 'include', 'with', 'without']
        for op in logical_ops:
            if op in prompt_lower:
                features['logical_operators'].append(op)
        
        # Extract aggregation hints
        agg_hints = ['count', 'sum', 'average', 'max', 'min', 'group by', 'top', 'bottom']
        for hint in agg_hints:
            if hint in prompt_lower:
                features['aggregation_hints'].append(hint)
        
        return features
    
    def _classify_query_intent(self, text_prompt: str) -> Dict[str, float]:
        """Classify the intent/type of the query."""
        intent_scores = {
            'search': 0.0,
            'filter': 0.0,
            'aggregate': 0.0,
            'monitor': 0.0,
            'analyze': 0.0
        }
        
        prompt_lower = text_prompt.lower()
        
        # Search intent indicators
        search_indicators = ['find', 'search', 'show', 'get', 'retrieve', 'look for']
        intent_scores['search'] = sum(1 for indicator in search_indicators if indicator in prompt_lower)
        
        # Filter intent indicators
        filter_indicators = ['where', 'with', 'having', 'filter', 'exclude', 'include']
        intent_scores['filter'] = sum(1 for indicator in filter_indicators if indicator in prompt_lower)
        
        # Aggregate intent indicators
        agg_indicators = ['count', 'sum', 'average', 'group', 'total', 'statistics']
        intent_scores['aggregate'] = sum(1 for indicator in agg_indicators if indicator in prompt_lower)
        
        # Monitor intent indicators
        monitor_indicators = ['monitor', 'watch', 'track', 'detect', 'alert']
        intent_scores['monitor'] = sum(1 for indicator in monitor_indicators if indicator in prompt_lower)
        
        # Analyze intent indicators
        analyze_indicators = ['analyze', 'pattern', 'trend', 'correlation', 'relationship']
        intent_scores['analyze'] = sum(1 for indicator in analyze_indicators if indicator in prompt_lower)
        
        # Normalize scores
        total_score = sum(intent_scores.values())
        if total_score > 0:
            intent_scores = {k: v / total_score for k, v in intent_scores.items()}
        else:
            intent_scores['search'] = 1.0  # Default to search
        
        return intent_scores
    
    def _align_text_with_schema(self, text_prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Align text prompt with schema fields and structure."""
        alignment = {
            'field_matches': [],
            'type_matches': [],
            'potential_mappings': {}
        }
        
        if not schema or 'properties' not in schema:
            return alignment
        
        prompt_words = text_prompt.lower().split()
        schema_fields = list(schema['properties'].keys())
        
        # Find field name matches
        for field in schema_fields:
            field_lower = field.lower()
            
            # Direct field name matches
            if field_lower in text_prompt.lower():
                alignment['field_matches'].append({
                    'field': field,
                    'match_type': 'direct',
                    'confidence': 1.0
                })
            
            # Partial matches
            elif any(word in field_lower for word in prompt_words):
                alignment['field_matches'].append({
                    'field': field,
                    'match_type': 'partial',
                    'confidence': 0.7
                })
        
        # Find type-based matches
        for field, field_def in schema['properties'].items():
            if isinstance(field_def, dict) and 'type' in field_def:
                field_type = field_def['type']
                
                # Match numeric fields with numerical expressions
                if field_type in ['integer', 'long', 'float', 'double']:
                    for num_expr in self._extract_text_features(text_prompt)['numerical_expressions']:
                        alignment['type_matches'].append({
                            'field': field,
                            'type': field_type,
                            'expression': num_expr,
                            'confidence': 0.8
                        })
        
        return alignment
    
    def _process_visual_modality(self, visual_inputs: List[Any]) -> Dict[str, Any]:
        """Process visual inputs (images, charts, screenshots)."""
        if not visual_inputs:
            return {'has_visuals': False}
        
        # Lazy import to avoid dependency issues
        try:
            from .visual_analyzer import VisualAnalyzer
            if not self.visual_analyzer:
                self.visual_analyzer = VisualAnalyzer()
        except ImportError:
            logger.warning("Visual analyzer not available - using simplified processing")
            return self._simplified_visual_processing(visual_inputs)
        
        visual_context = {
            'has_visuals': True,
            'visual_count': len(visual_inputs),
            'visual_features': [],
            'detected_elements': [],
            'schema_visualizations': []
        }
        
        for i, visual_input in enumerate(visual_inputs):
            try:
                # Analyze each visual input
                features = self.visual_analyzer.analyze_visual(visual_input)
                visual_context['visual_features'].append({
                    'index': i,
                    'features': features,
                    'type': features.get('visual_type', 'unknown')
                })
                
                # Extract detected elements
                if 'detected_elements' in features:
                    visual_context['detected_elements'].extend(features['detected_elements'])
                
            except Exception as e:
                logger.warning(f"Failed to process visual input {i}: {e}")
                visual_context['visual_features'].append({
                    'index': i,
                    'error': str(e),
                    'type': 'error'
                })
        
        return visual_context
    
    def _simplified_visual_processing(self, visual_inputs: List[Any]) -> Dict[str, Any]:
        """Simplified visual processing when full analyzer is not available."""
        visual_context = {
            'has_visuals': True,
            'visual_count': len(visual_inputs),
            'processing_mode': 'simplified',
            'visual_types': []
        }
        
        for visual_input in visual_inputs:
            # Basic type detection
            if isinstance(visual_input, str):
                if visual_input.startswith('data:image'):
                    visual_context['visual_types'].append('base64_image')
                elif visual_input.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    visual_context['visual_types'].append('image_path')
                else:
                    visual_context['visual_types'].append('text_description')
            elif isinstance(visual_input, dict):
                visual_context['visual_types'].append('structured_visual')
            else:
                visual_context['visual_types'].append('unknown')
        
        return visual_context
    
    def _process_data_modality(self, data_samples: List[Dict[str, Any]], schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process data samples for context extraction."""
        if not data_samples:
            return {'has_data_samples': False}
        
        # Lazy import
        try:
            from .data_context_extractor import DataContextExtractor
            if not self.data_extractor:
                self.data_extractor = DataContextExtractor()
        except ImportError:
            logger.warning("Data context extractor not available - using simplified processing")
            return self._simplified_data_processing(data_samples)
        
        data_context = {
            'has_data_samples': True,
            'sample_count': len(data_samples),
            'extracted_patterns': {},
            'field_statistics': {},
            'data_quality_metrics': {}
        }
        
        try:
            # Extract comprehensive data context
            patterns = self.data_extractor.extract_patterns(data_samples)
            data_context['extracted_patterns'] = patterns
            
            # Calculate field statistics
            field_stats = self.data_extractor.calculate_field_statistics(data_samples)
            data_context['field_statistics'] = field_stats
            
            # Assess data quality
            quality_metrics = self.data_extractor.assess_data_quality(data_samples, schema)
            data_context['data_quality_metrics'] = quality_metrics
            
        except Exception as e:
            logger.error(f"Data context extraction failed: {e}")
            data_context['error'] = str(e)
        
        return data_context
    
    def _simplified_data_processing(self, data_samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simplified data processing when full extractor is not available."""
        data_context = {
            'has_data_samples': True,
            'sample_count': len(data_samples),
            'processing_mode': 'simplified',
            'field_overview': {}
        }
        
        # Basic field analysis
        all_fields = set()
        for sample in data_samples:
            if isinstance(sample, dict):
                all_fields.update(sample.keys())
        
        data_context['field_overview'] = {
            'total_fields': len(all_fields),
            'fields': list(all_fields)[:20]  # Limit to first 20
        }
        
        return data_context
    
    def _compute_cross_modal_relationships(self,
                                         text_context: Dict[str, Any],
                                         visual_context: Dict[str, Any],
                                         data_context: Dict[str, Any]) -> Dict[str, Any]:
        """Compute relationships and alignments between modalities."""
        relationships = {
            'text_visual_alignment': 0.0,
            'text_data_alignment': 0.0,
            'visual_data_alignment': 0.0,
            'semantic_coherence': 0.0,
            'cross_modal_features': []
        }
        
        # Text-Visual alignment
        if visual_context.get('has_visuals') and text_context.get('semantic_features'):
            alignment_score = self._calculate_text_visual_alignment(text_context, visual_context)
            relationships['text_visual_alignment'] = alignment_score
        
        # Text-Data alignment
        if data_context.get('has_data_samples') and text_context.get('schema_alignment'):
            alignment_score = self._calculate_text_data_alignment(text_context, data_context)
            relationships['text_data_alignment'] = alignment_score
        
        # Visual-Data alignment (if both present)
        if visual_context.get('has_visuals') and data_context.get('has_data_samples'):
            alignment_score = self._calculate_visual_data_alignment(visual_context, data_context)
            relationships['visual_data_alignment'] = alignment_score
        
        # Overall semantic coherence
        coherence_scores = [
            relationships['text_visual_alignment'],
            relationships['text_data_alignment'],
            relationships['visual_data_alignment']
        ]
        valid_scores = [s for s in coherence_scores if s > 0]
        relationships['semantic_coherence'] = np.mean(valid_scores) if valid_scores else 0.0
        
        return relationships
    
    def _calculate_text_visual_alignment(self, text_context: Dict[str, Any], visual_context: Dict[str, Any]) -> float:
        """Calculate alignment between text and visual modalities."""
        alignment_score = 0.0
        
        # Check if visual elements support text query
        text_keywords = text_context.get('semantic_features', {}).get('keywords', [])
        visual_elements = visual_context.get('detected_elements', [])
        
        if text_keywords and visual_elements:
            keyword_matches = 0
            for keyword_info in text_keywords:
                keyword = keyword_info.get('word', '').lower()
                for element in visual_elements:
                    element_text = element.get('text', '').lower()
                    if keyword in element_text:
                        keyword_matches += 1
                        break
            
            alignment_score = keyword_matches / len(text_keywords) if text_keywords else 0.0
        
        return min(1.0, alignment_score)
    
    def _calculate_text_data_alignment(self, text_context: Dict[str, Any], data_context: Dict[str, Any]) -> float:
        """Calculate alignment between text and data modalities."""
        alignment_score = 0.0
        
        # Check field matches
        field_matches = text_context.get('schema_alignment', {}).get('field_matches', [])
        data_fields = data_context.get('field_overview', {}).get('fields', [])
        
        if field_matches and data_fields:
            matched_fields = 0
            for match in field_matches:
                field_name = match.get('field', '')
                if field_name in data_fields:
                    matched_fields += 1
            
            alignment_score = matched_fields / len(field_matches) if field_matches else 0.0
        
        return min(1.0, alignment_score)
    
    def _calculate_visual_data_alignment(self, visual_context: Dict[str, Any], data_context: Dict[str, Any]) -> float:
        """Calculate alignment between visual and data modalities."""
        # Simplified alignment based on presence and type compatibility
        alignment_score = 0.5  # Base score for having both modalities
        
        # Check if visuals show data-related content
        visual_features = visual_context.get('visual_features', [])
        has_charts = any(
            feature.get('features', {}).get('visual_type') in ['chart', 'graph', 'table']
            for feature in visual_features
        )
        
        if has_charts and data_context.get('has_data_samples'):
            alignment_score += 0.3  # Bonus for charts with data samples
        
        return min(1.0, alignment_score)
    
    def _compute_attention_weights(self,
                                 text_context: Dict[str, Any],
                                 visual_context: Dict[str, Any],
                                 data_context: Dict[str, Any],
                                 relationships: Dict[str, Any]) -> Dict[str, float]:
        """Compute attention weights for different modalities."""
        
        # Lazy import
        try:
            from .cross_modal_attention import AttentionWeightCalculator
            if not self.attention_calculator:
                self.attention_calculator = AttentionWeightCalculator()
                
            return self.attention_calculator.calculate_attention_weights(
                text_context, visual_context, data_context, relationships
            )
        except ImportError:
            # Fallback to simple rule-based weights
            return self._simple_attention_weights(text_context, visual_context, data_context, relationships)
    
    def _simple_attention_weights(self,
                                text_context: Dict[str, Any],
                                visual_context: Dict[str, Any],
                                data_context: Dict[str, Any],
                                relationships: Dict[str, Any]) -> Dict[str, float]:
        """Simple rule-based attention weight calculation."""
        weights = {'text': 0.5, 'visual': 0.0, 'data': 0.0}
        
        # Adjust based on presence of modalities
        modality_count = 1  # Text always present
        
        if visual_context.get('has_visuals'):
            modality_count += 1
            weights['visual'] = 0.3
            weights['text'] = 0.4
        
        if data_context.get('has_data_samples'):
            modality_count += 1
            weights['data'] = 0.3
            if weights['visual'] > 0:
                weights['text'] = 0.3
                weights['visual'] = 0.2
            else:
                weights['text'] = 0.4
        
        # Boost weights based on semantic coherence
        coherence = relationships.get('semantic_coherence', 0.0)
        if coherence > 0.7:
            # High coherence - boost non-text modalities
            if weights['visual'] > 0:
                weights['visual'] *= 1.2
            if weights['data'] > 0:
                weights['data'] *= 1.2
            # Renormalize
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _record_processing(self, text_prompt: str, context: MultiModalContext):
        """Record processing for analysis and improvement."""
        record = {
            'prompt': text_prompt,
            'modalities_used': [
                k for k, v in {
                    'text': True,  # Always present
                    'visual': context.visual_context.get('has_visuals', False),
                    'data': context.data_context.get('has_data_samples', False)
                }.items() if v
            ],
            'attention_weights': context.attention_weights,
            'semantic_coherence': context.cross_modal_relationships.get('semantic_coherence', 0.0),
            'processing_timestamp': None  # Would be set to current time
        }
        
        self.processing_history.append(record)
        
        # Keep only last 100 records
        if len(self.processing_history) > 100:
            self.processing_history = self.processing_history[-100:]
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get statistics about multi-modal processing performance."""
        if not self.processing_history:
            return {'no_data': True}
        
        stats = {
            'total_processed': len(self.processing_history),
            'modality_usage': {'text': 0, 'visual': 0, 'data': 0},
            'avg_coherence': 0.0,
            'attention_patterns': {'text': [], 'visual': [], 'data': []}
        }
        
        for record in self.processing_history:
            # Count modality usage
            for modality in record['modalities_used']:
                stats['modality_usage'][modality] += 1
            
            # Collect attention weights
            for modality, weight in record['attention_weights'].items():
                if modality in stats['attention_patterns']:
                    stats['attention_patterns'][modality].append(weight)
        
        # Calculate averages
        stats['avg_coherence'] = np.mean([
            r['semantic_coherence'] for r in self.processing_history
        ])
        
        for modality in stats['attention_patterns']:
            weights = stats['attention_patterns'][modality]
            stats['attention_patterns'][modality] = {
                'mean': np.mean(weights) if weights else 0.0,
                'std': np.std(weights) if weights else 0.0,
                'usage_rate': len(weights) / len(self.processing_history)
            }
        
        return stats

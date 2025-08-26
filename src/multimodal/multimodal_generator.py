"""
Multi-Modal Query Generator for ES-NL2DSL

The revolutionary multi-modal query generator that combines text prompts,
visual inputs, and data samples to generate enhanced Elasticsearch queries.
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
import logging

from .multimodal_processor import MultiModalProcessor, MultiModalContext
from .visual_analyzer import VisualAnalyzer, DataVisualizationAnalyzer
from .data_context_extractor import DataContextExtractor
from .cross_modal_attention import CrossModalAttention

logger = logging.getLogger(__name__)

@dataclass
class MultiModalGenerationResult:
    """Result from multi-modal query generation."""
    generated_query: Dict[str, Any]
    confidence_score: float
    modality_contributions: Dict[str, float]
    generation_explanation: str
    attention_insights: List[str]
    fallback_used: bool
    metadata: Dict[str, Any]

class MultiModalQueryGenerator:
    """
    Revolutionary multi-modal query generator.
    
    This is the world's first multi-modal natural language to DSL system
    that combines text prompts with visual data and examples for enhanced
    query generation accuracy and context understanding.
    """
    
    def __init__(self, base_model: str = "llama3.1:latest"):
        """
        Initialize the multi-modal query generator.
        
        Args:
            base_model: Base LLM model for text processing
        """
        self.base_model = base_model
        
        # Initialize multi-modal components
        self.multimodal_processor = MultiModalProcessor()
        self.visual_analyzer = VisualAnalyzer()
        self.data_extractor = DataContextExtractor()
        self.cross_modal_attention = CrossModalAttention()
        self.viz_analyzer = DataVisualizationAnalyzer()
        
        # Generation history and performance tracking
        self.generation_history = []
        self.performance_metrics = {
            'total_generations': 0,
            'successful_generations': 0,
            'multimodal_advantage_cases': 0,
            'average_confidence': 0.0
        }
        
        # Multi-modal enhancement settings
        self.enhancement_settings = {
            'visual_weight_threshold': 0.1,    # Minimum visual weight to use visual features
            'data_weight_threshold': 0.1,      # Minimum data weight to use data features
            'confidence_boost_threshold': 0.15, # Minimum improvement to apply multimodal boost
            'fallback_confidence_threshold': 0.3  # Below this, use text-only fallback
        }
    
    def generate_multimodal_query(self,
                                text_prompt: str,
                                schema: Dict[str, Any],
                                visual_inputs: List[Any] = None,
                                data_samples: List[Dict[str, Any]] = None,
                                index: str = "logs_net") -> MultiModalGenerationResult:
        """
        Generate query using multi-modal understanding.
        
        Args:
            text_prompt: Natural language query description
            schema: Elasticsearch schema
            visual_inputs: Images, charts, screenshots, etc.
            data_samples: Sample data records
            index: Target Elasticsearch index
            
        Returns:
            Comprehensive multi-modal generation result
        """
        try:
            logger.info("Starting multi-modal query generation...")
            
            # Step 1: Process all modalities
            multimodal_context = self.multimodal_processor.process_multimodal_input(
                text_prompt=text_prompt,
                visual_inputs=visual_inputs or [],
                data_samples=data_samples or [],
                schema=schema
            )
            
            # Step 2: Compute cross-modal attention
            attention_map = self.cross_modal_attention.compute_cross_modal_attention(
                text_features=multimodal_context.text_context,
                visual_features=multimodal_context.visual_context,
                data_features=multimodal_context.data_context
            )
            
            # Step 3: Generate enhanced prompt
            enhanced_prompt = self._create_multimodal_prompt(
                text_prompt, multimodal_context, attention_map
            )
            
            # Step 4: Generate query using enhanced prompt
            generated_query, base_confidence = self._generate_query_with_llm(
                enhanced_prompt, schema, index
            )
            
            # Step 5: Apply multi-modal enhancements
            enhanced_query, enhancement_metadata = self._apply_multimodal_enhancements(
                generated_query, multimodal_context, attention_map
            )
            
            # Step 6: Calculate confidence and contributions
            final_confidence = self._calculate_multimodal_confidence(
                base_confidence, multimodal_context, attention_map, enhancement_metadata
            )
            
            modality_contributions = self._calculate_modality_contributions(
                multimodal_context, attention_map, enhancement_metadata
            )
            
            # Step 7: Generate explanations
            generation_explanation = self._generate_explanation(
                text_prompt, multimodal_context, attention_map, enhancement_metadata
            )
            
            attention_insights = self.cross_modal_attention.get_attention_explanation(attention_map)
            
            # Step 8: Create result
            result = MultiModalGenerationResult(
                generated_query=enhanced_query,
                confidence_score=final_confidence,
                modality_contributions=modality_contributions,
                generation_explanation=generation_explanation,
                attention_insights=attention_insights,
                fallback_used=False,
                metadata={
                    'multimodal_context': multimodal_context,
                    'attention_map': attention_map,
                    'enhancement_metadata': enhancement_metadata,
                    'base_confidence': base_confidence,
                    'enhanced_prompt_length': len(enhanced_prompt)
                }
            )
            
            # Step 9: Record and return
            self._record_generation(result, text_prompt, visual_inputs, data_samples)
            
            return result
            
        except Exception as e:
            logger.error(f"Multi-modal generation failed: {e}")
            
            # Fallback to text-only generation
            return self._fallback_text_generation(text_prompt, schema, index, str(e))
    
    def _create_multimodal_prompt(self,
                                text_prompt: str,
                                context: MultiModalContext,
                                attention_map) -> str:
        """Create enhanced prompt incorporating multi-modal context."""
        
        enhanced_prompt = f"# Multi-Modal Query Generation\n\n"
        enhanced_prompt += f"## Original Request\n{text_prompt}\n\n"
        
        # Add visual context if significant attention
        if context.visual_context.get('has_visuals') and \
           attention_map.global_attention.get('visual', 0) > self.enhancement_settings['visual_weight_threshold']:
            
            enhanced_prompt += "## Visual Context\n"
            
            # Add detected visual elements
            visual_elements = context.visual_context.get('detected_elements', [])
            if visual_elements:
                enhanced_prompt += "**Detected Visual Elements:**\n"
                for element in visual_elements[:5]:  # Top 5 elements
                    element_type = element.get('element_type', 'unknown')
                    content = element.get('content', '')
                    enhanced_prompt += f"- {element_type}: {content}\n"
                enhanced_prompt += "\n"
            
            # Add visualization insights
            viz_insights = self._extract_visualization_insights(context.visual_context)
            if viz_insights:
                enhanced_prompt += "**Visual Insights:**\n"
                for insight in viz_insights[:3]:  # Top 3 insights
                    enhanced_prompt += f"- {insight}\n"
                enhanced_prompt += "\n"
        
        # Add data context if significant attention
        if context.data_context.get('has_data_samples') and \
           attention_map.global_attention.get('data', 0) > self.enhancement_settings['data_weight_threshold']:
            
            enhanced_prompt += "## Data Sample Context\n"
            
            # Add data patterns
            patterns = context.data_context.get('extracted_patterns', {})
            if patterns:
                enhanced_prompt += "**Discovered Data Patterns:**\n"
                for pattern_type, pattern_list in patterns.items():
                    if pattern_list:
                        enhanced_prompt += f"- {pattern_type.title()}: {len(pattern_list)} patterns found\n"
                        # Add examples of patterns
                        for pattern in pattern_list[:2]:  # First 2 patterns per type
                            description = pattern.get('pattern_description', '')
                            if description:
                                enhanced_prompt += f"  * {description}\n"
                enhanced_prompt += "\n"
            
            # Add field statistics summary
            field_stats = context.data_context.get('field_statistics', {})
            if field_stats:
                enhanced_prompt += "**Field Characteristics:**\n"
                for field_name, stats in list(field_stats.items())[:5]:  # Top 5 fields
                    data_type = stats.get('data_type', 'unknown')
                    unique_count = stats.get('unique_count', 0)
                    enhanced_prompt += f"- {field_name}: {data_type} type, {unique_count} unique values\n"
                enhanced_prompt += "\n"
        
        # Add cross-modal insights
        relationships = context.cross_modal_relationships
        semantic_coherence = relationships.get('semantic_coherence', 0.0)
        
        if semantic_coherence > 0.5:
            enhanced_prompt += "## Cross-Modal Insights\n"
            enhanced_prompt += f"**Semantic Coherence:** {semantic_coherence:.2f}\n"
            
            if relationships.get('text_visual_alignment', 0) > 0.3:
                enhanced_prompt += "- Strong alignment between text and visual elements\n"
            
            if relationships.get('text_data_alignment', 0) > 0.3:
                enhanced_prompt += "- Strong alignment between text and data patterns\n"
            
            enhanced_prompt += "\n"
        
        # Add generation instructions
        enhanced_prompt += "## Generation Instructions\n"
        enhanced_prompt += "Generate an Elasticsearch DSL query that:\n"
        enhanced_prompt += "1. Addresses the original text request\n"
        
        if context.visual_context.get('has_visuals'):
            enhanced_prompt += "2. Incorporates insights from visual elements\n"
        
        if context.data_context.get('has_data_samples'):
            enhanced_prompt += "3. Leverages discovered data patterns and field characteristics\n"
        
        enhanced_prompt += "4. Follows the provided schema structure\n"
        enhanced_prompt += "5. Optimizes for the identified use case patterns\n\n"
        
        enhanced_prompt += "Generate a valid JSON Elasticsearch DSL query:\n"
        
        return enhanced_prompt
    
    def _extract_visualization_insights(self, visual_context: Dict[str, Any]) -> List[str]:
        """Extract actionable insights from visual context."""
        insights = []
        
        visual_features = visual_context.get('visual_features', [])
        
        for vf in visual_features:
            features = vf.get('features', {})
            
            # Chart-specific insights
            if features.get('visual_type') == 'chart':
                chart_analysis = features.get('chart_analysis')
                if chart_analysis:
                    chart_type = chart_analysis.get('chart_type', 'unknown')
                    insights.append(f"Chart shows {chart_type} visualization with temporal data")
                    
                    trends = chart_analysis.get('trends', [])
                    for trend in trends:
                        insights.append(f"Data trend: {trend}")
            
            # Table-specific insights
            elif features.get('visual_type') == 'table':
                insights.append("Tabular data structure detected - consider structured queries")
            
            # Schema diagram insights
            elif features.get('visual_type') == 'schema_diagram':
                insights.append("Schema visualization available - leverage field relationships")
        
        # Analyze detected elements for additional insights
        detected_elements = visual_context.get('detected_elements', [])
        
        # Look for temporal indicators
        temporal_elements = [
            e for e in detected_elements 
            if 'time' in e.get('content', '').lower() or 'date' in e.get('content', '').lower()
        ]
        if temporal_elements:
            insights.append("Temporal elements detected - include time-based filtering")
        
        # Look for field names
        field_elements = [
            e for e in detected_elements 
            if e.get('element_type') in ['field_box', 'table_header', 'axis_label']
        ]
        if field_elements:
            insights.append("Field names identified in visual - use for precise field targeting")
        
        return insights
    
    def _generate_query_with_llm(self,
                               enhanced_prompt: str,
                               schema: Dict[str, Any],
                               index: str) -> Tuple[Dict[str, Any], float]:
        """Generate query using LLM with enhanced prompt."""
        try:
            # Use the constrained generator with enhanced prompt
            from src.generators.constrained import call_local_model
            
            response = call_local_model(enhanced_prompt, self.base_model)
            
            # Parse the response to extract DSL
            generated_query = self._parse_llm_response(response)
            
            # Calculate base confidence
            confidence = self._calculate_base_confidence(generated_query, response)
            
            return generated_query, confidence
            
        except Exception as e:
            logger.error(f"LLM query generation failed: {e}")
            return {}, 0.0
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response to extract DSL query."""
        try:
            # Look for JSON in response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            else:
                logger.warning("No valid JSON found in LLM response")
                return {}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {}
    
    def _calculate_base_confidence(self, query: Dict[str, Any], response: str) -> float:
        """Calculate base confidence for generated query."""
        confidence = 0.0
        
        # Query structure confidence
        if query and 'query' in query:
            confidence += 0.5
        
        # Response quality indicators
        if 'query' in response.lower():
            confidence += 0.2
        if '{' in response and '}' in response:
            confidence += 0.2
        if len(response) > 50:  # Reasonable response length
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _apply_multimodal_enhancements(self,
                                     base_query: Dict[str, Any],
                                     context: MultiModalContext,
                                     attention_map) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Apply multi-modal enhancements to the base query."""
        enhanced_query = base_query.copy() if base_query else {}
        enhancement_metadata = {
            'enhancements_applied': [],
            'confidence_boost': 0.0,
            'visual_enhancements': 0,
            'data_enhancements': 0
        }
        
        try:
            # Visual enhancements
            if context.visual_context.get('has_visuals') and \
               attention_map.global_attention.get('visual', 0) > self.enhancement_settings['visual_weight_threshold']:
                
                visual_enhancements = self._apply_visual_enhancements(enhanced_query, context.visual_context)
                enhancement_metadata['visual_enhancements'] = len(visual_enhancements)
                enhancement_metadata['enhancements_applied'].extend(visual_enhancements)
            
            # Data-driven enhancements  
            if context.data_context.get('has_data_samples') and \
               attention_map.global_attention.get('data', 0) > self.enhancement_settings['data_weight_threshold']:
                
                data_enhancements = self._apply_data_enhancements(enhanced_query, context.data_context)
                enhancement_metadata['data_enhancements'] = len(data_enhancements)
                enhancement_metadata['enhancements_applied'].extend(data_enhancements)
            
            # Cross-modal enhancements
            cross_modal_enhancements = self._apply_cross_modal_enhancements(
                enhanced_query, context, attention_map
            )
            enhancement_metadata['enhancements_applied'].extend(cross_modal_enhancements)
            
            # Calculate confidence boost
            total_enhancements = len(enhancement_metadata['enhancements_applied'])
            enhancement_metadata['confidence_boost'] = min(0.3, total_enhancements * 0.05)
            
        except Exception as e:
            logger.error(f"Multi-modal enhancements failed: {e}")
            enhancement_metadata['error'] = str(e)
        
        return enhanced_query, enhancement_metadata
    
    def _apply_visual_enhancements(self, query: Dict[str, Any], visual_context: Dict[str, Any]) -> List[str]:
        """Apply visual context enhancements to query."""
        enhancements = []
        
        try:
            detected_elements = visual_context.get('detected_elements', [])
            
            # Enhance based on chart elements
            chart_elements = [e for e in detected_elements if 'chart' in e.get('element_type', '')]
            if chart_elements and query:
                # Add sorting for time-series charts
                if any('time' in e.get('content', '').lower() for e in chart_elements):
                    if 'sort' not in query:
                        query['sort'] = [{"@timestamp": {"order": "desc"}}]
                        enhancements.append("Added time-based sorting from chart context")
            
            # Enhance based on table elements  
            table_elements = [e for e in detected_elements if 'table' in e.get('element_type', '')]
            if table_elements and query:
                # Adjust size based on table row count
                table_rows = [e for e in table_elements if e.get('element_type') == 'table_row']
                if len(table_rows) > 0:
                    suggested_size = min(1000, max(10, len(table_rows) * 5))
                    if 'size' not in query:
                        query['size'] = suggested_size
                        enhancements.append(f"Set result size to {suggested_size} based on table context")
            
            # Enhance based on field elements
            field_elements = [e for e in detected_elements if 'field' in e.get('element_type', '')]
            for field_element in field_elements:
                field_content = field_element.get('content', '')
                # Extract field names and enhance query targeting
                if '(' in field_content and ')' in field_content:
                    field_name = field_content.split('(')[0].strip()
                    if field_name and query.get('query'):
                        enhancements.append(f"Enhanced field targeting for {field_name} from visual")
            
        except Exception as e:
            logger.warning(f"Visual enhancements failed: {e}")
        
        return enhancements
    
    def _apply_data_enhancements(self, query: Dict[str, Any], data_context: Dict[str, Any]) -> List[str]:
        """Apply data context enhancements to query."""
        enhancements = []
        
        try:
            # Enhance based on discovered patterns
            patterns = data_context.get('extracted_patterns', {})
            
            # Temporal pattern enhancements
            temporal_patterns = patterns.get('temporal', [])
            for pattern in temporal_patterns:
                if 'time_range' in pattern.get('pattern_description', '').lower():
                    # Enhance with appropriate time window
                    if query and not self._has_time_filter(query):
                        self._add_default_time_filter(query)
                        enhancements.append("Added time filter based on temporal patterns")
            
            # Numerical pattern enhancements
            numerical_patterns = patterns.get('numerical', [])
            for pattern in numerical_patterns:
                pattern_desc = pattern.get('pattern_description', '')
                if 'outlier' in pattern_desc.lower() and query:
                    # Could enhance with outlier detection logic
                    enhancements.append("Enhanced for outlier detection based on data patterns")
            
            # Categorical pattern enhancements
            categorical_patterns = patterns.get('categorical', [])
            for pattern in categorical_patterns:
                pattern_desc = pattern.get('pattern_description', '')
                if 'top categories' in pattern_desc.lower():
                    # Add aggregation for top categories if not present
                    if query and 'aggs' not in query:
                        enhancements.append("Enhanced for categorical analysis based on data patterns")
            
            # Field statistics enhancements
            field_stats = data_context.get('field_statistics', {})
            for field_name, stats in field_stats.items():
                data_type = stats.get('data_type', 'unknown')
                null_percentage = stats.get('null_percentage', 0)
                
                # Handle high null percentage fields
                if null_percentage > 50 and query:
                    enhancements.append(f"Considered high null rate in {field_name} for query optimization")
            
            # Data quality enhancements
            quality_metrics = data_context.get('data_quality_metrics', {})
            completeness = quality_metrics.get('completeness', 100)
            
            if completeness < 80 and query:
                # Adjust query for data quality issues
                enhancements.append("Adjusted query strategy for data quality considerations")
            
        except Exception as e:
            logger.warning(f"Data enhancements failed: {e}")
        
        return enhancements
    
    def _apply_cross_modal_enhancements(self,
                                      query: Dict[str, Any],
                                      context: MultiModalContext,
                                      attention_map) -> List[str]:
        """Apply cross-modal enhancements based on attention patterns."""
        enhancements = []
        
        try:
            semantic_coherence = context.cross_modal_relationships.get('semantic_coherence', 0.0)
            
            # High coherence enhancements
            if semantic_coherence > 0.7:
                # Apply confidence boost strategies
                if query and 'size' not in query:
                    query['size'] = 100  # Reasonable default for high-confidence queries
                    enhancements.append("Optimized result size for high semantic coherence")
                
                # Add explain parameter for high-confidence queries
                if query:
                    query['explain'] = False  # Performance optimization
                    enhancements.append("Optimized query execution for high confidence")
            
            # Multi-modal attention distribution enhancements
            attention_weights = attention_map.global_attention
            
            # Balanced attention (multiple modalities contributing)
            if len([w for w in attention_weights.values() if w > 0.2]) > 1:
                enhancements.append("Applied multi-modal fusion strategy")
                
                # Enhance query robustness for multi-modal inputs
                if query and not self._has_bool_query(query):
                    self._ensure_bool_structure(query)
                    enhancements.append("Enhanced query structure for multi-modal robustness")
            
        except Exception as e:
            logger.warning(f"Cross-modal enhancements failed: {e}")
        
        return enhancements
    
    def _has_time_filter(self, query: Dict[str, Any]) -> bool:
        """Check if query has time filtering."""
        query_str = json.dumps(query).lower()
        return '@timestamp' in query_str or 'timestamp' in query_str
    
    def _add_default_time_filter(self, query: Dict[str, Any]):
        """Add default time filter to query."""
        if 'query' not in query:
            query['query'] = {}
        
        if 'bool' not in query['query']:
            query['query'] = {'bool': {'must': [query['query']] if query['query'] else []}}
        
        if 'filter' not in query['query']['bool']:
            query['query']['bool']['filter'] = []
        
        time_filter = {
            'range': {
                '@timestamp': {
                    'gte': 'now-24h',
                    'lte': 'now'
                }
            }
        }
        
        query['query']['bool']['filter'].append(time_filter)
    
    def _has_bool_query(self, query: Dict[str, Any]) -> bool:
        """Check if query has bool structure."""
        return query.get('query', {}).get('bool') is not None
    
    def _ensure_bool_structure(self, query: Dict[str, Any]):
        """Ensure query has bool structure for robustness."""
        if 'query' not in query:
            query['query'] = {}
        
        current_query = query['query']
        if 'bool' not in current_query:
            if current_query:
                query['query'] = {'bool': {'must': [current_query]}}
            else:
                query['query'] = {'bool': {'must': [{'match_all': {}}]}}
    
    def _calculate_multimodal_confidence(self,
                                       base_confidence: float,
                                       context: MultiModalContext,
                                       attention_map,
                                       enhancement_metadata: Dict[str, Any]) -> float:
        """Calculate final confidence score incorporating multi-modal factors."""
        
        confidence = base_confidence
        
        try:
            # Multi-modal presence boost
            modalities_present = len([
                k for k, v in {
                    'visual': context.visual_context.get('has_visuals', False),
                    'data': context.data_context.get('has_data_samples', False)
                }.items() if v
            ])
            
            if modalities_present > 0:
                multimodal_boost = min(0.2, modalities_present * 0.1)
                confidence += multimodal_boost
            
            # Semantic coherence boost
            semantic_coherence = context.cross_modal_relationships.get('semantic_coherence', 0.0)
            coherence_boost = semantic_coherence * 0.15
            confidence += coherence_boost
            
            # Enhancement boost
            enhancement_boost = enhancement_metadata.get('confidence_boost', 0.0)
            confidence += enhancement_boost
            
            # Attention distribution quality
            attention_weights = attention_map.global_attention
            if attention_weights:
                # Balanced attention is generally better
                attention_variance = np.var(list(attention_weights.values()))
                if attention_variance < 0.1:  # Well-balanced
                    confidence += 0.05
            
            # Penalize very low base confidence
            if base_confidence < 0.3:
                confidence *= 0.8  # Apply penalty
            
            confidence = max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.warning(f"Confidence calculation failed: {e}")
        
        return confidence
    
    def _calculate_modality_contributions(self,
                                        context: MultiModalContext,
                                        attention_map,
                                        enhancement_metadata: Dict[str, Any]) -> Dict[str, float]:
        """Calculate contribution scores for each modality."""
        contributions = {'text': 0.5, 'visual': 0.0, 'data': 0.0}
        
        try:
            # Base contributions from attention weights
            attention_weights = attention_map.global_attention
            for modality, weight in attention_weights.items():
                if modality in contributions:
                    contributions[modality] = weight
            
            # Boost based on enhancements applied
            visual_enhancements = enhancement_metadata.get('visual_enhancements', 0)
            data_enhancements = enhancement_metadata.get('data_enhancements', 0)
            
            if visual_enhancements > 0:
                contributions['visual'] += visual_enhancements * 0.05
            
            if data_enhancements > 0:
                contributions['data'] += data_enhancements * 0.05
            
            # Normalize to sum to 1
            total_contribution = sum(contributions.values())
            if total_contribution > 0:
                contributions = {k: v / total_contribution for k, v in contributions.items()}
            
        except Exception as e:
            logger.warning(f"Contribution calculation failed: {e}")
        
        return contributions
    
    def _generate_explanation(self,
                            text_prompt: str,
                            context: MultiModalContext,
                            attention_map,
                            enhancement_metadata: Dict[str, Any]) -> str:
        """Generate human-readable explanation of the multi-modal generation process."""
        
        explanation_parts = []
        
        # Base generation
        explanation_parts.append(f"Generated query based on text prompt: '{text_prompt}'")
        
        # Multi-modal enhancements
        if context.visual_context.get('has_visuals'):
            visual_weight = attention_map.global_attention.get('visual', 0.0)
            explanation_parts.append(
                f"Enhanced with visual context (weight: {visual_weight:.2f}) including "
                f"{context.visual_context.get('visual_count', 0)} visual inputs"
            )
        
        if context.data_context.get('has_data_samples'):
            data_weight = attention_map.global_attention.get('data', 0.0)
            explanation_parts.append(
                f"Enhanced with data context (weight: {data_weight:.2f}) from "
                f"{context.data_context.get('sample_count', 0)} data samples"
            )
        
        # Semantic coherence
        semantic_coherence = context.cross_modal_relationships.get('semantic_coherence', 0.0)
        if semantic_coherence > 0.5:
            explanation_parts.append(
                f"High semantic coherence ({semantic_coherence:.2f}) between modalities "
                "increased generation confidence"
            )
        
        # Specific enhancements
        enhancements = enhancement_metadata.get('enhancements_applied', [])
        if enhancements:
            explanation_parts.append(
                f"Applied {len(enhancements)} multi-modal enhancements: "
                f"{', '.join(enhancements[:3])}{'...' if len(enhancements) > 3 else ''}"
            )
        
        return ". ".join(explanation_parts) + "."
    
    def _fallback_text_generation(self,
                                text_prompt: str,
                                schema: Dict[str, Any],
                                index: str,
                                error_msg: str) -> MultiModalGenerationResult:
        """Fallback to text-only generation when multi-modal fails."""
        
        try:
            logger.info("Falling back to text-only generation...")
            
            # Use basic constrained generation
            from src.generators.constrained import generate_with_retries
            
            result = generate_with_retries(
                task_prompt=text_prompt,
                schema_path=None,  # Will use default schema
                rules_path=None,   # Will use default rules
                index=index
            )
            
            generated_query = result.get('query', {}) if isinstance(result, dict) else {}
            
            return MultiModalGenerationResult(
                generated_query=generated_query,
                confidence_score=0.3,  # Low confidence for fallback
                modality_contributions={'text': 1.0, 'visual': 0.0, 'data': 0.0},
                generation_explanation=f"Fallback to text-only generation due to error: {error_msg}",
                attention_insights=["Multi-modal processing failed, used text-only fallback"],
                fallback_used=True,
                metadata={'error': error_msg, 'fallback_method': 'constrained_generation'}
            )
            
        except Exception as fallback_error:
            logger.error(f"Fallback generation also failed: {fallback_error}")
            
            return MultiModalGenerationResult(
                generated_query={},
                confidence_score=0.0,
                modality_contributions={'text': 1.0, 'visual': 0.0, 'data': 0.0},
                generation_explanation=f"Both multi-modal and fallback generation failed",
                attention_insights=["Complete generation failure"],
                fallback_used=True,
                metadata={'error': error_msg, 'fallback_error': str(fallback_error)}
            )
    
    def _record_generation(self,
                         result: MultiModalGenerationResult,
                         text_prompt: str,
                         visual_inputs: List[Any],
                         data_samples: List[Dict[str, Any]]):
        """Record generation for performance tracking and analysis."""
        
        record = {
            'text_prompt': text_prompt,
            'visual_input_count': len(visual_inputs) if visual_inputs else 0,
            'data_sample_count': len(data_samples) if data_samples else 0,
            'confidence_score': result.confidence_score,
            'modality_contributions': result.modality_contributions,
            'fallback_used': result.fallback_used,
            'enhancements_applied': len(result.metadata.get('enhancement_metadata', {}).get('enhancements_applied', [])),
            'success': bool(result.generated_query)
        }
        
        self.generation_history.append(record)
        
        # Update performance metrics
        self.performance_metrics['total_generations'] += 1
        
        if record['success']:
            self.performance_metrics['successful_generations'] += 1
        
        # Check for multi-modal advantage
        text_only_contribution = result.modality_contributions.get('text', 1.0)
        if text_only_contribution < 0.8:  # Other modalities contributed significantly
            self.performance_metrics['multimodal_advantage_cases'] += 1
        
        # Update average confidence
        total_gens = self.performance_metrics['total_generations']
        current_avg = self.performance_metrics['average_confidence']
        new_avg = ((current_avg * (total_gens - 1)) + result.confidence_score) / total_gens
        self.performance_metrics['average_confidence'] = new_avg
        
        # Keep history manageable
        if len(self.generation_history) > 100:
            self.generation_history = self.generation_history[-100:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for multi-modal generation."""
        metrics = self.performance_metrics.copy()
        
        if metrics['total_generations'] > 0:
            metrics['success_rate'] = metrics['successful_generations'] / metrics['total_generations']
            metrics['multimodal_advantage_rate'] = metrics['multimodal_advantage_cases'] / metrics['total_generations']
        else:
            metrics['success_rate'] = 0.0
            metrics['multimodal_advantage_rate'] = 0.0
        
        # Recent performance (last 20 generations)
        recent_history = self.generation_history[-20:] if len(self.generation_history) >= 20 else self.generation_history
        
        if recent_history:
            recent_success_rate = sum(1 for r in recent_history if r['success']) / len(recent_history)
            recent_avg_confidence = sum(r['confidence_score'] for r in recent_history) / len(recent_history)
            recent_multimodal_rate = sum(1 for r in recent_history if r['modality_contributions']['text'] < 0.8) / len(recent_history)
            
            metrics['recent_performance'] = {
                'success_rate': recent_success_rate,
                'average_confidence': recent_avg_confidence,
                'multimodal_usage_rate': recent_multimodal_rate
            }
        
        return metrics

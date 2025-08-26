"""
Unit tests for Phase 5 Multi-Modal Components
"""

import pytest
import numpy as np
from datetime import datetime
import json

from src.multimodal.multimodal_processor import MultiModalProcessor, MultiModalContext
from src.multimodal.visual_analyzer import VisualAnalyzer, DataVisualizationAnalyzer
from src.multimodal.data_context_extractor import DataContextExtractor, SchemaVisualizer
from src.multimodal.cross_modal_attention import CrossModalAttention, AttentionWeightCalculator
from src.multimodal.multimodal_generator import MultiModalQueryGenerator, MultiModalGenerationResult


class TestMultiModalProcessor:
    """Test MultiModalProcessor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.processor = MultiModalProcessor()
        
    def test_processor_initialization(self):
        """Test processor initialization."""
        assert self.processor.modality_weights['text'] == 0.5
        assert self.processor.modality_weights['visual'] == 0.3
        assert self.processor.modality_weights['data_context'] == 0.2
        
    def test_text_modality_processing(self):
        """Test text modality processing."""
        schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "@timestamp": {"type": "date"}
            }
        }
        
        text_context = self.processor._process_text_modality(
            "Find SSH attacks from external IPs in the last hour", 
            schema
        )
        
        assert 'original_prompt' in text_context
        assert 'semantic_features' in text_context
        assert 'query_intent' in text_context
        assert 'schema_alignment' in text_context
        
        # Check semantic feature extraction
        features = text_context['semantic_features']
        assert 'keywords' in features
        assert 'temporal_expressions' in features
        assert 'numerical_expressions' in features
        
        # Should detect security keywords
        security_keywords = [kw for kw in features['keywords'] if kw.get('category') == 'security']
        assert len(security_keywords) > 0
        
    def test_visual_modality_processing(self):
        """Test visual modality processing."""
        # Test with text description
        visual_inputs = ["Chart showing network traffic over time with peak at noon"]
        
        visual_context = self.processor._process_visual_modality(visual_inputs)
        
        assert visual_context['has_visuals'] == True
        assert visual_context['visual_count'] == 1
        
    def test_data_modality_processing(self):
        """Test data modality processing."""
        data_samples = [
            {"source_ip": "192.168.1.100", "bytes": 1024, "@timestamp": "2024-01-01T10:00:00"},
            {"source_ip": "10.0.0.1", "bytes": 2048, "@timestamp": "2024-01-01T10:01:00"}
        ]
        
        schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "bytes": {"type": "long"},
                "@timestamp": {"type": "date"}
            }
        }
        
        data_context = self.processor._process_data_modality(data_samples, schema)
        
        assert data_context['has_data_samples'] == True
        assert data_context['sample_count'] == 2
        
    def test_multimodal_input_processing(self):
        """Test complete multimodal input processing."""
        text_prompt = "Find high bandwidth usage above 100MB"
        visual_inputs = ["Chart showing bandwidth usage over time"]
        data_samples = [
            {"bytes": 104857600, "@timestamp": "2024-01-01T10:00:00"},
            {"bytes": 52428800, "@timestamp": "2024-01-01T10:01:00"}
        ]
        schema = {
            "properties": {
                "bytes": {"type": "long"},
                "@timestamp": {"type": "date"}
            }
        }
        
        context = self.processor.process_multimodal_input(
            text_prompt, visual_inputs, data_samples, schema
        )
        
        assert isinstance(context, MultiModalContext)
        assert context.text_context is not None
        assert context.visual_context is not None
        assert context.data_context is not None
        assert context.attention_weights is not None
        
    def test_cross_modal_relationships(self):
        """Test cross-modal relationship computation."""
        text_context = {
            'semantic_features': {
                'keywords': [{'word': 'bandwidth', 'category': 'networking'}],
                'numerical_expressions': ['100MB']
            },
            'schema_alignment': {
                'field_matches': [{'field': 'bytes', 'match_type': 'direct'}]
            }
        }
        
        visual_context = {
            'has_visuals': True,
            'detected_elements': [
                {'element_type': 'chart_type', 'content': 'line chart'},
                {'element_type': 'axis_label', 'content': 'bandwidth (MB)'}
            ]
        }
        
        data_context = {
            'has_data_samples': True,
            'field_overview': {'fields': ['bytes', '@timestamp']}
        }
        
        relationships = self.processor._compute_cross_modal_relationships(
            text_context, visual_context, data_context
        )
        
        assert 'text_visual_alignment' in relationships
        assert 'text_data_alignment' in relationships
        assert 'semantic_coherence' in relationships
        assert 0.0 <= relationships['semantic_coherence'] <= 1.0


class TestVisualAnalyzer:
    """Test VisualAnalyzer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = VisualAnalyzer()
        
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        assert self.analyzer.supported_formats == ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
        assert not self.analyzer.ocr_available  # Mock implementation
        assert not self.analyzer.cv_available   # Mock implementation
        
    def test_text_description_analysis(self):
        """Test analysis of text descriptions."""
        description = "Line chart showing CPU usage over time with peaks during business hours"
        
        analysis = self.analyzer.analyze_visual(description)
        
        assert analysis['visual_type'] == 'text_description'
        assert analysis['inferred_visual_type'] == 'chart'
        assert 'detected_elements' in analysis
        
        # Should detect chart-related information
        elements = analysis['detected_elements']
        chart_elements = [e for e in elements if e.get('element_type') == 'chart_type']
        assert len(chart_elements) > 0
        
    def test_structured_visual_analysis(self):
        """Test analysis of structured visual data."""
        visual_data = {
            'chart_type': 'bar',
            'data_dimensions': 2,
            'x_axis': 'time',
            'y_axis': 'count'
        }
        
        analysis = self.analyzer.analyze_visual(visual_data)
        
        assert analysis['visual_type'] == 'chart_data'
        assert 'chart_analysis' in analysis
        
    def test_base64_image_analysis(self):
        """Test analysis of base64 image data."""
        # Mock base64 data with chart keyword
        base64_data = "data:image/png;base64,chart_example_data..."
        
        analysis = self.analyzer.analyze_visual(base64_data)
        
        assert analysis['visual_type'] == 'chart'
        assert 'chart_analysis' in analysis
        assert 'detected_elements' in analysis
        
    def test_semantic_feature_extraction(self):
        """Test semantic feature extraction from descriptions."""
        description = "Security dashboard showing attack patterns and threat levels"
        
        features = self.analyzer._extract_semantic_features(description)
        
        assert 'domain_indicators' in features
        assert 'security' in features['domain_indicators']
        assert 'data_types_mentioned' in features
        assert 'operations_mentioned' in features


class TestDataContextExtractor:
    """Test DataContextExtractor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = DataContextExtractor()
        
    def test_extractor_initialization(self):
        """Test extractor initialization."""
        assert 'ip_address' in self.extractor.field_type_patterns
        assert 'timestamp' in self.extractor.field_type_patterns
        
    def test_pattern_extraction(self):
        """Test pattern extraction from data samples."""
        data_samples = [
            {"source_ip": "192.168.1.100", "bytes": 1024, "@timestamp": "2024-01-01T10:00:00", "status": "success"},
            {"source_ip": "192.168.1.101", "bytes": 2048, "@timestamp": "2024-01-01T10:01:00", "status": "success"},
            {"source_ip": "10.0.0.1", "bytes": 512, "@timestamp": "2024-01-01T10:02:00", "status": "failed"}
        ]
        
        patterns = self.extractor.extract_patterns(data_samples)
        
        assert 'temporal' in patterns
        assert 'categorical' in patterns
        assert 'numerical' in patterns
        assert 'textual' in patterns
        
        # Should detect patterns in each category
        assert len(patterns['temporal']) > 0  # @timestamp patterns
        assert len(patterns['categorical']) > 0  # status patterns
        assert len(patterns['numerical']) > 0  # bytes patterns
        
    def test_field_type_inference(self):
        """Test field type inference."""
        import pandas as pd
        
        # IP address field
        ip_series = pd.Series(["192.168.1.1", "10.0.0.1", "172.16.0.1"])
        ip_type = self.extractor._infer_field_type(ip_series)
        assert ip_type == 'ip_address'
        
        # Numerical field
        num_series = pd.Series([100, 200, 300])
        num_type = self.extractor._infer_field_type(num_series)
        assert num_type == 'numerical'
        
        # Categorical field
        cat_series = pd.Series(["success", "success", "failed", "success"])
        cat_type = self.extractor._infer_field_type(cat_series)
        assert cat_type == 'categorical'
        
    def test_field_statistics_calculation(self):
        """Test field statistics calculation."""
        data_samples = [
            {"field1": "value1", "field2": 100, "field3": "2024-01-01T10:00:00"},
            {"field1": "value2", "field2": 200, "field3": "2024-01-01T11:00:00"},
            {"field1": "value1", "field2": 150, "field3": "2024-01-01T12:00:00"}
        ]
        
        field_stats = self.extractor.calculate_field_statistics(data_samples)
        
        assert 'field1' in field_stats
        assert 'field2' in field_stats
        assert 'field3' in field_stats
        
        # Check field1 (categorical)
        field1_stats = field_stats['field1']
        assert field1_stats.unique_count == 2
        assert field1_stats.data_type == 'categorical'
        
        # Check field2 (numerical)
        field2_stats = field_stats['field2']
        assert field2_stats.data_type == 'numerical'
        assert 'min' in field2_stats.statistics
        assert 'max' in field2_stats.statistics
        
    def test_data_quality_assessment(self):
        """Test data quality assessment."""
        # Good quality data
        good_data = [
            {"field1": "value1", "field2": 100},
            {"field1": "value2", "field2": 200},
            {"field1": "value3", "field2": 300}
        ]
        
        quality_metrics = self.extractor.assess_data_quality(good_data)
        
        assert 'completeness' in quality_metrics
        assert 'consistency' in quality_metrics
        assert 'validity' in quality_metrics
        assert quality_metrics['completeness'] == 100.0  # No missing values
        
        # Poor quality data with missing values
        poor_data = [
            {"field1": "value1", "field2": 100},
            {"field1": None, "field2": 200},
            {"field1": "value3", "field2": None}
        ]
        
        poor_quality_metrics = self.extractor.assess_data_quality(poor_data)
        assert poor_quality_metrics['completeness'] < 100.0


class TestCrossModalAttention:
    """Test CrossModalAttention functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.attention = CrossModalAttention()
        
    def test_attention_initialization(self):
        """Test attention mechanism initialization."""
        assert self.attention.temperature == 0.1
        assert 'text' in self.attention.modality_weights
        assert 'visual' in self.attention.modality_weights
        assert 'data' in self.attention.modality_weights
        
    def test_feature_vector_extraction(self):
        """Test feature vector extraction from different modalities."""
        # Text features
        text_features = {
            'semantic_features': {
                'keywords': [{'category': 'security'}, {'category': 'networking'}],
                'temporal_expressions': ['last hour'],
                'numerical_expressions': ['100MB'],
                'logical_operators': ['and'],
                'aggregation_hints': ['count']
            },
            'query_intent': {
                'search': 0.8, 'filter': 0.2, 'aggregate': 0.0, 'monitor': 0.0, 'analyze': 0.0
            },
            'schema_alignment': {
                'field_matches': [{'field': 'bytes'}],
                'type_matches': [{'field': 'timestamp'}]
            }
        }
        
        text_vector = self.attention._extract_text_feature_vector(text_features)
        assert isinstance(text_vector, np.ndarray)
        assert len(text_vector) > 0
        
        # Visual features
        visual_features = {
            'has_visuals': True,
            'visual_count': 2,
            'visual_features': [
                {'type': 'chart', 'features': {'chart_analysis': True}},
                {'type': 'table', 'features': {}}
            ],
            'detected_elements': [
                {'element_type': 'chart_type', 'content': 'line'},
                {'element_type': 'axis_label', 'content': 'time'}
            ]
        }
        
        visual_vector = self.attention._extract_visual_feature_vector(visual_features)
        assert isinstance(visual_vector, np.ndarray)
        assert len(visual_vector) > 0
        
    def test_cross_modal_attention_computation(self):
        """Test cross-modal attention computation."""
        text_features = {
            'semantic_features': {'keywords': [{'category': 'security'}]},
            'query_intent': {'search': 1.0},
            'schema_alignment': {'field_matches': []}
        }
        
        visual_features = {
            'has_visuals': True,
            'visual_count': 1,
            'visual_features': [{'type': 'chart'}],
            'detected_elements': []
        }
        
        data_features = {
            'has_data_samples': True,
            'sample_count': 10,
            'extracted_patterns': {'temporal': [], 'numerical': []},
            'field_statistics': {},
            'data_quality_metrics': {'completeness': 95, 'consistency': 90, 'validity': 85}
        }
        
        attention_map = self.attention.compute_cross_modal_attention(
            text_features, visual_features, data_features
        )
        
        assert len(attention_map.modality_names) == 3
        assert 'text' in attention_map.global_attention
        assert 'visual' in attention_map.global_attention
        assert 'data' in attention_map.global_attention
        
        # Attention weights should sum to approximately 1
        total_attention = sum(attention_map.global_attention.values())
        assert abs(total_attention - 1.0) < 0.1
        
    def test_attention_explanation_generation(self):
        """Test attention explanation generation."""
        # Create mock attention map
        from src.multimodal.cross_modal_attention import AttentionMap
        
        attention_map = AttentionMap(
            attention_matrix=np.array([[1.0, 0.3], [0.4, 1.0]]),
            modality_names=['text', 'visual'],
            element_weights={'text': 0.7, 'visual': 0.3},
            global_attention={'text': 0.6, 'visual': 0.4}
        )
        
        explanations = self.attention.get_attention_explanation(attention_map)
        
        assert len(explanations) > 0
        assert any('text' in exp for exp in explanations)


class TestAttentionWeightCalculator:
    """Test AttentionWeightCalculator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = AttentionWeightCalculator()
        
    def test_calculator_initialization(self):
        """Test calculator initialization."""
        assert 'dot_product' in self.calculator.calculation_strategies
        assert 'cosine_similarity' in self.calculator.calculation_strategies
        assert 'adaptive' in self.calculator.calculation_strategies
        
    def test_attention_weight_calculation(self):
        """Test attention weight calculation."""
        text_context = {
            'semantic_features': {'keywords': [{'category': 'security'}]},
            'schema_alignment': {'field_matches': []}
        }
        
        visual_context = {'has_visuals': True}
        data_context = {'has_data_samples': True}
        relationships = {'semantic_coherence': 0.8}
        
        weights = self.calculator.calculate_attention_weights(
            text_context, visual_context, data_context, relationships
        )
        
        assert 'text' in weights
        assert 'visual' in weights
        assert 'data' in weights
        assert all(0.0 <= w <= 1.0 for w in weights.values())
        
        # Weights should sum to approximately 1
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.1
        
    def test_modality_richness_calculation(self):
        """Test modality richness calculation."""
        # Rich text context
        rich_text_context = {
            'semantic_features': {
                'keywords': [{'category': 'security'} for _ in range(5)],
                'temporal_expressions': ['last hour', 'today'],
                'numerical_expressions': ['100MB', '50%']
            },
            'schema_alignment': {
                'field_matches': [{'field': 'field1'}, {'field': 'field2'}]
            }
        }
        
        # Poor text context
        poor_text_context = {
            'semantic_features': {'keywords': []},
            'schema_alignment': {'field_matches': []}
        }
        
        rich_score = self.calculator._calculate_modality_richness(rich_text_context, 'text')
        poor_score = self.calculator._calculate_modality_richness(poor_text_context, 'text')
        
        assert rich_score > poor_score
        assert 0.0 <= rich_score <= 2.0
        assert 0.0 <= poor_score <= 2.0


class TestMultiModalQueryGenerator:
    """Test MultiModalQueryGenerator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = MultiModalQueryGenerator()
        
    def test_generator_initialization(self):
        """Test generator initialization."""
        assert self.generator.base_model == "llama3.1:latest"
        assert isinstance(self.generator.multimodal_processor, MultiModalProcessor)
        assert isinstance(self.generator.cross_modal_attention, CrossModalAttention)
        
    def test_multimodal_prompt_creation(self):
        """Test multimodal prompt creation."""
        from src.multimodal.multimodal_processor import MultiModalContext
        from src.multimodal.cross_modal_attention import AttentionMap
        
        # Create mock context
        context = MultiModalContext(
            text_context={'prompt': 'Find attacks'},
            visual_context={
                'has_visuals': True,
                'detected_elements': [
                    {'element_type': 'chart_type', 'content': 'line chart'},
                    {'element_type': 'axis_label', 'content': 'time'}
                ]
            },
            data_context={
                'has_data_samples': True,
                'extracted_patterns': {'temporal': [{'pattern_description': 'time series data'}]},
                'field_statistics': {'bytes': {'data_type': 'numerical'}}
            },
            cross_modal_relationships={'semantic_coherence': 0.8},
            attention_weights={'text': 0.5, 'visual': 0.3, 'data': 0.2}
        )
        
        attention_map = AttentionMap(
            attention_matrix=np.array([[1.0]]),
            modality_names=['text'],
            element_weights={'text': 1.0},
            global_attention={'text': 0.5, 'visual': 0.3, 'data': 0.2}
        )
        
        prompt = self.generator._create_multimodal_prompt(
            "Find network attacks", context, attention_map
        )
        
        assert "Multi-Modal Query Generation" in prompt
        assert "Original Request" in prompt
        assert "Find network attacks" in prompt
        assert "Visual Context" in prompt
        assert "Data Sample Context" in prompt
        
    def test_multimodal_query_generation(self):
        """Test complete multimodal query generation."""
        schema = {
            "properties": {
                "source_ip": {"type": "ip"},
                "@timestamp": {"type": "date"},
                "attack_type": {"type": "keyword"}
            }
        }
        
        visual_inputs = ["Security dashboard showing attack patterns"]
        data_samples = [
            {"source_ip": "10.0.0.1", "@timestamp": "2024-01-01T10:00:00", "attack_type": "brute_force"}
        ]
        
        # Mock the LLM call
        def mock_call_local_model(prompt, model):
            return '{"query": {"bool": {"must": [{"match": {"attack_type": "brute_force"}}]}}}'
        
        import src.generators.constrained
        original_call = src.generators.constrained.call_local_model
        src.generators.constrained.call_local_model = mock_call_local_model
        
        try:
            result = self.generator.generate_multimodal_query(
                "Find brute force attacks",
                schema,
                visual_inputs,
                data_samples
            )
            
            assert isinstance(result, MultiModalGenerationResult)
            assert isinstance(result.generated_query, dict)
            assert 'query' in result.generated_query
            assert result.confidence_score > 0.0
            assert not result.fallback_used
            
        finally:
            src.generators.constrained.call_local_model = original_call
            
    def test_performance_summary(self):
        """Test performance summary generation."""
        # Simulate some generation history
        self.generator.performance_metrics = {
            'total_generations': 10,
            'successful_generations': 8,
            'multimodal_advantage_cases': 3,
            'average_confidence': 0.75
        }
        
        summary = self.generator.get_performance_summary()
        
        assert 'success_rate' in summary
        assert 'multimodal_advantage_rate' in summary
        assert summary['success_rate'] == 0.8
        assert summary['multimodal_advantage_rate'] == 0.3


if __name__ == '__main__':
    pytest.main([__file__])

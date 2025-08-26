"""
Multi-Modal Query Understanding for ES-NL2DSL

This module implements groundbreaking multi-modal query understanding
that combines text prompts with visual data examples, screenshots,
and structured data samples for enhanced query generation.

Revolutionary Features:
- Text + Image query understanding
- Data sample context integration  
- Visual schema interpretation
- Cross-modal attention mechanisms
- Multi-modal prompt engineering

Components:
- multimodal_processor.py: Core multi-modal processing
- visual_analyzer.py: Image and visual data analysis
- data_context_extractor.py: Extract context from data samples
- cross_modal_attention.py: Attention mechanisms across modalities
- multimodal_generator.py: Multi-modal query generation
"""

from .multimodal_processor import MultiModalProcessor
from .visual_analyzer import VisualAnalyzer, DataVisualizationAnalyzer
from .data_context_extractor import DataContextExtractor, SchemaVisualizer
from .cross_modal_attention import CrossModalAttention, AttentionWeightCalculator
from .multimodal_generator import MultiModalQueryGenerator

__all__ = [
    'MultiModalProcessor',
    'VisualAnalyzer', 
    'DataVisualizationAnalyzer',
    'DataContextExtractor',
    'SchemaVisualizer',
    'CrossModalAttention',
    'AttentionWeightCalculator',
    'MultiModalQueryGenerator'
]

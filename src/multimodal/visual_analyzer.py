"""
Visual Analyzer for Multi-Modal ES-NL2DSL

Analyzes images, charts, screenshots, and visual data representations
to extract meaningful context for query generation.
"""

import json
import base64
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class VisualElement:
    """Represents a detected visual element."""
    element_type: str  # 'text', 'chart', 'table', 'schema_diagram', 'data_view'
    location: Tuple[int, int, int, int]  # x, y, width, height
    content: str
    confidence: float
    metadata: Dict[str, Any]

@dataclass
class ChartAnalysis:
    """Analysis results for chart/graph visuals."""
    chart_type: str  # 'line', 'bar', 'pie', 'scatter', 'heatmap'
    data_dimensions: int
    temporal_axis: bool
    numerical_ranges: Dict[str, Tuple[float, float]]
    trends: List[str]
    annotations: List[str]

class VisualAnalyzer:
    """
    Advanced visual analyzer for multi-modal query understanding.
    
    Processes images, charts, screenshots, and data visualizations
    to extract context that enhances query generation.
    """
    
    def __init__(self):
        self.analysis_cache = {}
        self.supported_formats = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']
        
        # Initialize OCR and image processing (mock implementations)
        self.ocr_available = self._check_ocr_availability()
        self.cv_available = self._check_cv_availability()
        
    def _check_ocr_availability(self) -> bool:
        """Check if OCR libraries are available."""
        try:
            # In production, would check for pytesseract, easyocr, etc.
            return False  # Simplified for this implementation
        except ImportError:
            return False
    
    def _check_cv_availability(self) -> bool:
        """Check if computer vision libraries are available."""
        try:
            # In production, would check for cv2, PIL, etc.
            return False  # Simplified for this implementation
        except ImportError:
            return False
    
    def analyze_visual(self, visual_input: Any) -> Dict[str, Any]:
        """
        Analyze a visual input and extract relevant features.
        
        Args:
            visual_input: Image data (file path, base64, bytes, etc.)
            
        Returns:
            Visual analysis results
        """
        try:
            # Determine input type and process accordingly
            if isinstance(visual_input, str):
                if visual_input.startswith('data:image'):
                    return self._analyze_base64_image(visual_input)
                elif Path(visual_input).suffix.lower() in self.supported_formats:
                    return self._analyze_image_file(visual_input)
                else:
                    return self._analyze_text_description(visual_input)
            elif isinstance(visual_input, dict):
                return self._analyze_structured_visual(visual_input)
            else:
                return self._analyze_raw_data(visual_input)
                
        except Exception as e:
            logger.error(f"Visual analysis failed: {e}")
            return {
                'visual_type': 'error',
                'error': str(e),
                'analysis_method': 'failed'
            }
    
    def _analyze_base64_image(self, base64_data: str) -> Dict[str, Any]:
        """Analyze base64 encoded image."""
        analysis = {
            'visual_type': 'base64_image',
            'analysis_method': 'mock_vision',
            'detected_elements': [],
            'visual_features': {},
            'extracted_text': '',
            'chart_analysis': None
        }
        
        # Mock analysis based on common patterns
        if 'chart' in base64_data.lower() or 'graph' in base64_data.lower():
            analysis['visual_type'] = 'chart'
            analysis['chart_analysis'] = self._mock_chart_analysis()
            analysis['detected_elements'] = self._mock_chart_elements()
        elif 'table' in base64_data.lower():
            analysis['visual_type'] = 'table'
            analysis['detected_elements'] = self._mock_table_elements()
        else:
            analysis['visual_type'] = 'generic_image'
            analysis['detected_elements'] = self._mock_generic_elements()
        
        return analysis
    
    def _analyze_image_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze image file."""
        analysis = {
            'visual_type': 'image_file',
            'file_path': file_path,
            'analysis_method': 'mock_vision',
            'detected_elements': [],
            'visual_features': {},
            'file_metadata': {}
        }
        
        # Mock file metadata
        try:
            path_obj = Path(file_path)
            analysis['file_metadata'] = {
                'filename': path_obj.name,
                'extension': path_obj.suffix,
                'exists': path_obj.exists()
            }
            
            # Analyze based on filename patterns
            filename_lower = path_obj.name.lower()
            if any(term in filename_lower for term in ['chart', 'graph', 'plot']):
                analysis['visual_type'] = 'chart'
                analysis['chart_analysis'] = self._mock_chart_analysis()
                analysis['detected_elements'] = self._mock_chart_elements()
            elif any(term in filename_lower for term in ['schema', 'diagram', 'structure']):
                analysis['visual_type'] = 'schema_diagram'
                analysis['detected_elements'] = self._mock_schema_elements()
            elif any(term in filename_lower for term in ['table', 'data', 'grid']):
                analysis['visual_type'] = 'table'
                analysis['detected_elements'] = self._mock_table_elements()
            else:
                analysis['detected_elements'] = self._mock_generic_elements()
                
        except Exception as e:
            analysis['file_metadata']['error'] = str(e)
        
        return analysis
    
    def _analyze_text_description(self, description: str) -> Dict[str, Any]:
        """Analyze text description of visual content."""
        analysis = {
            'visual_type': 'text_description',
            'description': description,
            'analysis_method': 'text_parsing',
            'inferred_visual_type': '',
            'detected_elements': [],
            'semantic_features': {}
        }
        
        desc_lower = description.lower()
        
        # Infer visual type from description
        if any(term in desc_lower for term in ['chart', 'graph', 'plot', 'histogram']):
            analysis['inferred_visual_type'] = 'chart'
            analysis['detected_elements'] = self._extract_chart_info_from_text(description)
        elif any(term in desc_lower for term in ['table', 'grid', 'rows', 'columns']):
            analysis['inferred_visual_type'] = 'table'
            analysis['detected_elements'] = self._extract_table_info_from_text(description)
        elif any(term in desc_lower for term in ['schema', 'diagram', 'structure', 'mapping']):
            analysis['inferred_visual_type'] = 'schema_diagram'
            analysis['detected_elements'] = self._extract_schema_info_from_text(description)
        else:
            analysis['inferred_visual_type'] = 'generic'
            analysis['semantic_features'] = self._extract_semantic_features(description)
        
        return analysis
    
    def _analyze_structured_visual(self, visual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze structured visual data (JSON representation)."""
        analysis = {
            'visual_type': 'structured_data',
            'analysis_method': 'structured_parsing',
            'data_structure': visual_data,
            'detected_elements': [],
            'visual_features': {}
        }
        
        # Analyze structure type
        if 'chart_type' in visual_data:
            analysis['visual_type'] = 'chart_data'
            analysis['chart_analysis'] = self._analyze_chart_data(visual_data)
        elif 'schema' in visual_data or 'fields' in visual_data:
            analysis['visual_type'] = 'schema_data'
            analysis['detected_elements'] = self._analyze_schema_data(visual_data)
        elif 'rows' in visual_data or 'columns' in visual_data:
            analysis['visual_type'] = 'table_data'
            analysis['detected_elements'] = self._analyze_table_data(visual_data)
        
        return analysis
    
    def _analyze_raw_data(self, raw_data: Any) -> Dict[str, Any]:
        """Analyze raw binary or other data."""
        return {
            'visual_type': 'raw_data',
            'analysis_method': 'binary_analysis',
            'data_type': str(type(raw_data)),
            'size': len(raw_data) if hasattr(raw_data, '__len__') else 0,
            'detected_elements': [],
            'notes': 'Raw data analysis not fully implemented'
        }
    
    def _mock_chart_analysis(self) -> ChartAnalysis:
        """Mock chart analysis for demonstration."""
        return ChartAnalysis(
            chart_type='line',
            data_dimensions=2,
            temporal_axis=True,
            numerical_ranges={'y_axis': (0, 100), 'x_axis': (0, 24)},
            trends=['increasing', 'seasonal_pattern'],
            annotations=['peak_at_noon', 'low_overnight']
        )
    
    def _mock_chart_elements(self) -> List[VisualElement]:
        """Mock chart elements detection."""
        return [
            VisualElement(
                element_type='axis_label',
                location=(10, 350, 50, 20),
                content='Time (hours)',
                confidence=0.9,
                metadata={'axis': 'x'}
            ),
            VisualElement(
                element_type='axis_label',
                location=(5, 200, 20, 100),
                content='CPU Usage (%)',
                confidence=0.9,
                metadata={'axis': 'y'}
            ),
            VisualElement(
                element_type='data_line',
                location=(50, 50, 300, 250),
                content='performance_trend',
                confidence=0.8,
                metadata={'data_points': 24}
            )
        ]
    
    def _mock_table_elements(self) -> List[VisualElement]:
        """Mock table elements detection."""
        return [
            VisualElement(
                element_type='table_header',
                location=(10, 10, 400, 30),
                content='timestamp,source_ip,bytes,status',
                confidence=0.95,
                metadata={'columns': 4}
            ),
            VisualElement(
                element_type='table_row',
                location=(10, 40, 400, 20),
                content='2024-01-01T10:00:00,192.168.1.100,1024,success',
                confidence=0.85,
                metadata={'row_index': 1}
            ),
            VisualElement(
                element_type='table_row',
                location=(10, 60, 400, 20),
                content='2024-01-01T10:01:00,10.0.0.1,2048,failed',
                confidence=0.85,
                metadata={'row_index': 2}
            )
        ]
    
    def _mock_schema_elements(self) -> List[VisualElement]:
        """Mock schema diagram elements."""
        return [
            VisualElement(
                element_type='field_box',
                location=(50, 50, 120, 30),
                content='@timestamp (date)',
                confidence=0.9,
                metadata={'field_type': 'date', 'required': True}
            ),
            VisualElement(
                element_type='field_box',
                location=(50, 90, 120, 30),
                content='source_ip (ip)',
                confidence=0.9,
                metadata={'field_type': 'ip', 'indexed': True}
            ),
            VisualElement(
                element_type='relationship_line',
                location=(170, 65, 50, 2),
                content='connects_to',
                confidence=0.7,
                metadata={'relationship_type': 'foreign_key'}
            )
        ]
    
    def _mock_generic_elements(self) -> List[VisualElement]:
        """Mock generic visual elements."""
        return [
            VisualElement(
                element_type='text_block',
                location=(10, 10, 200, 50),
                content='Network Security Dashboard',
                confidence=0.8,
                metadata={'font_size': 'large', 'style': 'heading'}
            ),
            VisualElement(
                element_type='text_block',
                location=(10, 70, 300, 100),
                content='This dashboard shows real-time network traffic and security events',
                confidence=0.7,
                metadata={'font_size': 'medium', 'style': 'description'}
            )
        ]
    
    def _extract_chart_info_from_text(self, description: str) -> List[VisualElement]:
        """Extract chart information from text description."""
        elements = []
        desc_lower = description.lower()
        
        # Look for chart type indicators
        chart_types = ['line', 'bar', 'pie', 'scatter', 'histogram', 'heatmap']
        for chart_type in chart_types:
            if chart_type in desc_lower:
                elements.append(VisualElement(
                    element_type='chart_type',
                    location=(0, 0, 0, 0),
                    content=chart_type,
                    confidence=0.8,
                    metadata={'extracted_from': 'text_description'}
                ))
                break
        
        # Look for axis labels
        import re
        axis_patterns = [
            r'x[- ]?axis[:\s]+([^,.\n]+)',
            r'y[- ]?axis[:\s]+([^,.\n]+)',
            r'horizontal[:\s]+([^,.\n]+)',
            r'vertical[:\s]+([^,.\n]+)'
        ]
        
        for pattern in axis_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                elements.append(VisualElement(
                    element_type='axis_info',
                    location=(0, 0, 0, 0),
                    content=match.strip(),
                    confidence=0.7,
                    metadata={'extracted_from': 'text_pattern'}
                ))
        
        return elements
    
    def _extract_table_info_from_text(self, description: str) -> List[VisualElement]:
        """Extract table information from text description."""
        elements = []
        desc_lower = description.lower()
        
        # Look for column information
        import re
        column_patterns = [
            r'columns?[:\s]+([^.]+)',
            r'fields?[:\s]+([^.]+)',
            r'headers?[:\s]+([^.]+)'
        ]
        
        for pattern in column_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                # Split potential column names
                columns = [col.strip() for col in re.split(r'[,;|]', match)]
                for col in columns:
                    if col:
                        elements.append(VisualElement(
                            element_type='table_column',
                            location=(0, 0, 0, 0),
                            content=col,
                            confidence=0.6,
                            metadata={'extracted_from': 'text_pattern'}
                        ))
        
        return elements
    
    def _extract_schema_info_from_text(self, description: str) -> List[VisualElement]:
        """Extract schema information from text description."""
        elements = []
        
        # Look for field definitions
        import re
        field_patterns = [
            r'(\w+)\s*\((\w+)\)',  # field_name(type)
            r'(\w+):\s*(\w+)',     # field_name: type
            r'(\w+)\s+(\w+)',      # field_name type
        ]
        
        for pattern in field_patterns:
            matches = re.findall(pattern, description)
            for field_name, field_type in matches:
                elements.append(VisualElement(
                    element_type='schema_field',
                    location=(0, 0, 0, 0),
                    content=f'{field_name}({field_type})',
                    confidence=0.7,
                    metadata={
                        'field_name': field_name,
                        'field_type': field_type,
                        'extracted_from': 'text_pattern'
                    }
                ))
        
        return elements
    
    def _extract_semantic_features(self, description: str) -> Dict[str, Any]:
        """Extract semantic features from text description."""
        features = {
            'domain_indicators': [],
            'data_types_mentioned': [],
            'operations_mentioned': [],
            'temporal_references': []
        }
        
        desc_lower = description.lower()
        
        # Domain indicators
        domain_keywords = {
            'security': ['attack', 'threat', 'breach', 'malicious', 'vulnerability'],
            'networking': ['traffic', 'bandwidth', 'latency', 'packet', 'connection'],
            'system': ['cpu', 'memory', 'disk', 'process', 'performance']
        }
        
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if keyword in desc_lower:
                    features['domain_indicators'].append(domain)
                    break
        
        # Data types
        data_types = ['ip', 'timestamp', 'port', 'bytes', 'percentage', 'count', 'id']
        for dtype in data_types:
            if dtype in desc_lower:
                features['data_types_mentioned'].append(dtype)
        
        # Operations
        operations = ['filter', 'search', 'aggregate', 'count', 'sum', 'average', 'group']
        for op in operations:
            if op in desc_lower:
                features['operations_mentioned'].append(op)
        
        # Temporal references
        temporal_terms = ['time', 'hour', 'day', 'week', 'recent', 'last', 'between']
        for term in temporal_terms:
            if term in desc_lower:
                features['temporal_references'].append(term)
        
        return features
    
    def _analyze_chart_data(self, chart_data: Dict[str, Any]) -> ChartAnalysis:
        """Analyze structured chart data."""
        return ChartAnalysis(
            chart_type=chart_data.get('chart_type', 'unknown'),
            data_dimensions=len(chart_data.get('dimensions', [])),
            temporal_axis='time' in str(chart_data).lower(),
            numerical_ranges=chart_data.get('ranges', {}),
            trends=chart_data.get('trends', []),
            annotations=chart_data.get('annotations', [])
        )
    
    def _analyze_schema_data(self, schema_data: Dict[str, Any]) -> List[VisualElement]:
        """Analyze structured schema data."""
        elements = []
        
        if 'fields' in schema_data:
            for field_info in schema_data['fields']:
                if isinstance(field_info, dict):
                    field_name = field_info.get('name', 'unknown')
                    field_type = field_info.get('type', 'unknown')
                    elements.append(VisualElement(
                        element_type='schema_field',
                        location=(0, 0, 0, 0),
                        content=f'{field_name}({field_type})',
                        confidence=1.0,
                        metadata={
                            'field_name': field_name,
                            'field_type': field_type,
                            'extracted_from': 'structured_data'
                        }
                    ))
        
        return elements
    
    def _analyze_table_data(self, table_data: Dict[str, Any]) -> List[VisualElement]:
        """Analyze structured table data."""
        elements = []
        
        # Analyze columns
        if 'columns' in table_data:
            for i, column in enumerate(table_data['columns']):
                elements.append(VisualElement(
                    element_type='table_column',
                    location=(i * 100, 0, 100, 30),
                    content=str(column),
                    confidence=1.0,
                    metadata={
                        'column_index': i,
                        'extracted_from': 'structured_data'
                    }
                ))
        
        # Analyze sample rows
        if 'rows' in table_data:
            for i, row in enumerate(table_data['rows'][:3]):  # First 3 rows
                elements.append(VisualElement(
                    element_type='table_row',
                    location=(0, (i + 1) * 25, 400, 25),
                    content=str(row),
                    confidence=0.9,
                    metadata={
                        'row_index': i,
                        'extracted_from': 'structured_data'
                    }
                ))
        
        return elements

class DataVisualizationAnalyzer:
    """
    Specialized analyzer for data visualization contexts.
    
    Focuses on understanding data patterns, trends, and insights
    from visual representations that can inform query generation.
    """
    
    def __init__(self):
        self.visualization_patterns = {}
        
    def analyze_data_visualization(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Analyze data visualization to extract query-relevant insights."""
        analysis = {
            'visualization_type': 'unknown',
            'data_insights': {},
            'query_suggestions': [],
            'temporal_patterns': {},
            'statistical_patterns': {}
        }
        
        # Determine visualization type
        vis_type = self._classify_visualization(visual_elements)
        analysis['visualization_type'] = vis_type
        
        # Extract data insights based on type
        if vis_type == 'time_series':
            analysis['data_insights'] = self._analyze_time_series(visual_elements)
            analysis['temporal_patterns'] = self._extract_temporal_patterns(visual_elements)
        elif vis_type == 'comparison':
            analysis['data_insights'] = self._analyze_comparison_chart(visual_elements)
        elif vis_type == 'distribution':
            analysis['data_insights'] = self._analyze_distribution(visual_elements)
            analysis['statistical_patterns'] = self._extract_statistical_patterns(visual_elements)
        
        # Generate query suggestions
        analysis['query_suggestions'] = self._generate_query_suggestions(analysis)
        
        return analysis
    
    def _classify_visualization(self, visual_elements: List[VisualElement]) -> str:
        """Classify the type of data visualization."""
        # Look for temporal indicators
        has_time_axis = any(
            'time' in element.content.lower() or 
            'date' in element.content.lower() or
            '@timestamp' in element.content.lower()
            for element in visual_elements
            if element.element_type in ['axis_label', 'axis_info']
        )
        
        if has_time_axis:
            return 'time_series'
        
        # Look for chart type indicators
        chart_elements = [e for e in visual_elements if e.element_type == 'chart_type']
        if chart_elements:
            chart_type = chart_elements[0].content.lower()
            if chart_type in ['histogram', 'box', 'violin']:
                return 'distribution'
            elif chart_type in ['bar', 'column']:
                return 'comparison'
            elif chart_type in ['scatter', 'bubble']:
                return 'correlation'
        
        return 'generic'
    
    def _analyze_time_series(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Analyze time series visualization."""
        insights = {
            'trend_direction': 'unknown',
            'seasonality': False,
            'anomalies_detected': False,
            'data_coverage': 'unknown'
        }
        
        # Look for trend information in annotations or data lines
        trend_elements = [e for e in visual_elements if 'trend' in e.content.lower()]
        if trend_elements:
            content = trend_elements[0].content.lower()
            if 'increasing' in content or 'rising' in content or 'up' in content:
                insights['trend_direction'] = 'increasing'
            elif 'decreasing' in content or 'falling' in content or 'down' in content:
                insights['trend_direction'] = 'decreasing'
            elif 'stable' in content or 'flat' in content:
                insights['trend_direction'] = 'stable'
        
        # Check for seasonality indicators
        seasonal_indicators = ['seasonal', 'pattern', 'cycle', 'periodic']
        if any(indicator in e.content.lower() for e in visual_elements for indicator in seasonal_indicators):
            insights['seasonality'] = True
        
        return insights
    
    def _analyze_comparison_chart(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Analyze comparison/categorical visualization."""
        return {
            'categories_count': len([e for e in visual_elements if e.element_type == 'category']),
            'ranking_available': True,
            'comparison_type': 'categorical'
        }
    
    def _analyze_distribution(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Analyze distribution visualization."""
        return {
            'distribution_shape': 'unknown',
            'outliers_present': False,
            'central_tendency': 'unknown',
            'variability': 'unknown'
        }
    
    def _extract_temporal_patterns(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Extract temporal patterns from visualization."""
        patterns = {
            'time_granularity': 'unknown',
            'peak_periods': [],
            'low_periods': [],
            'pattern_type': 'unknown'
        }
        
        # Look for time-related annotations
        time_elements = [e for e in visual_elements if 'time' in e.content.lower() or 'hour' in e.content.lower()]
        if time_elements:
            # Determine granularity
            content = ' '.join(e.content.lower() for e in time_elements)
            if 'minute' in content:
                patterns['time_granularity'] = 'minute'
            elif 'hour' in content:
                patterns['time_granularity'] = 'hour'
            elif 'day' in content:
                patterns['time_granularity'] = 'day'
            elif 'week' in content:
                patterns['time_granularity'] = 'week'
        
        # Look for peak/low indicators
        peak_indicators = ['peak', 'high', 'maximum', 'spike']
        low_indicators = ['low', 'minimum', 'drop', 'valley']
        
        for element in visual_elements:
            content_lower = element.content.lower()
            if any(indicator in content_lower for indicator in peak_indicators):
                patterns['peak_periods'].append(element.content)
            elif any(indicator in content_lower for indicator in low_indicators):
                patterns['low_periods'].append(element.content)
        
        return patterns
    
    def _extract_statistical_patterns(self, visual_elements: List[VisualElement]) -> Dict[str, Any]:
        """Extract statistical patterns from visualization."""
        patterns = {
            'central_value': None,
            'spread_indicators': [],
            'outlier_indicators': [],
            'distribution_type': 'unknown'
        }
        
        # Look for statistical annotations
        for element in visual_elements:
            content_lower = element.content.lower()
            
            # Central tendency
            if any(term in content_lower for term in ['mean', 'average', 'median']):
                patterns['central_value'] = element.content
            
            # Spread
            if any(term in content_lower for term in ['std', 'deviation', 'variance', 'range']):
                patterns['spread_indicators'].append(element.content)
            
            # Outliers
            if any(term in content_lower for term in ['outlier', 'anomaly', 'extreme']):
                patterns['outlier_indicators'].append(element.content)
        
        return patterns
    
    def _generate_query_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate query suggestions based on visualization analysis."""
        suggestions = []
        
        vis_type = analysis['visualization_type']
        
        if vis_type == 'time_series':
            suggestions.extend([
                "Filter data by time range shown in the chart",
                "Aggregate data using the same time granularity",
                "Find anomalies outside normal patterns"
            ])
            
            # Add trend-specific suggestions
            insights = analysis.get('data_insights', {})
            if insights.get('trend_direction') == 'increasing':
                suggestions.append("Focus on recent data showing the upward trend")
            elif insights.get('trend_direction') == 'decreasing':
                suggestions.append("Investigate causes of the declining trend")
        
        elif vis_type == 'comparison':
            suggestions.extend([
                "Compare categories shown in the chart",
                "Filter by top/bottom performing categories",
                "Aggregate data by the categorical dimension"
            ])
        
        elif vis_type == 'distribution':
            suggestions.extend([
                "Filter data within normal distribution range",
                "Identify outliers beyond typical values",
                "Aggregate data using statistical functions"
            ])
        
        return suggestions

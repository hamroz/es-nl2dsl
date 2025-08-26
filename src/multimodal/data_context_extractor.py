"""
Data Context Extractor for Multi-Modal ES-NL2DSL

Extracts meaningful context from data samples to enhance query generation
with real data patterns and characteristics.
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from collections import Counter, defaultdict
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class DataPattern:
    """Represents a discovered data pattern."""
    pattern_type: str  # 'temporal', 'categorical', 'numerical', 'textual'
    field_name: str
    pattern_description: str
    examples: List[Any]
    confidence: float
    metadata: Dict[str, Any]

@dataclass
class FieldStatistics:
    """Statistical summary for a data field."""
    field_name: str
    data_type: str
    unique_count: int
    null_count: int
    null_percentage: float
    sample_values: List[Any]
    statistics: Dict[str, Any]  # Min, max, mean, etc. for numerical

class DataContextExtractor:
    """
    Extracts rich context from data samples for multi-modal query understanding.
    
    Analyzes data patterns, field characteristics, and relationships
    to provide context that enhances query generation accuracy.
    """
    
    def __init__(self):
        self.pattern_cache = {}
        self.field_type_patterns = {
            'ip_address': r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$',
            'timestamp': r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'url': r'^https?://[^\s/$.?#].[^\s]*$',
            'port': r'^[0-9]{1,5}$',
            'mac_address': r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        }
        
    def extract_patterns(self, data_samples: List[Dict[str, Any]]) -> Dict[str, List[DataPattern]]:
        """
        Extract comprehensive patterns from data samples.
        
        Args:
            data_samples: List of data records
            
        Returns:
            Dictionary of patterns grouped by type
        """
        if not data_samples:
            return {}
        
        patterns = {
            'temporal': [],
            'categorical': [],
            'numerical': [],
            'textual': [],
            'structural': []
        }
        
        try:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(data_samples)
            
            # Analyze each field
            for field_name in df.columns:
                field_patterns = self._analyze_field_patterns(df, field_name)
                
                # Categorize patterns
                for pattern in field_patterns:
                    pattern_type = pattern.pattern_type
                    if pattern_type in patterns:
                        patterns[pattern_type].append(pattern)
            
            # Extract cross-field patterns
            structural_patterns = self._extract_structural_patterns(df)
            patterns['structural'].extend(structural_patterns)
            
            # Extract temporal relationships
            temporal_relationships = self._extract_temporal_relationships(df)
            patterns['temporal'].extend(temporal_relationships)
            
        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")
            patterns['error'] = [str(e)]
        
        return patterns
    
    def _analyze_field_patterns(self, df: pd.DataFrame, field_name: str) -> List[DataPattern]:
        """Analyze patterns for a specific field."""
        patterns = []
        
        try:
            series = df[field_name].dropna()
            if series.empty:
                return patterns
            
            # Determine field type and extract type-specific patterns
            field_type = self._infer_field_type(series)
            
            if field_type == 'timestamp':
                patterns.extend(self._extract_temporal_patterns(series, field_name))
            elif field_type == 'categorical':
                patterns.extend(self._extract_categorical_patterns(series, field_name))
            elif field_type == 'numerical':
                patterns.extend(self._extract_numerical_patterns(series, field_name))
            elif field_type == 'textual':
                patterns.extend(self._extract_textual_patterns(series, field_name))
            elif field_type in ['ip_address', 'email', 'url']:
                patterns.extend(self._extract_formatted_patterns(series, field_name, field_type))
                
        except Exception as e:
            logger.warning(f"Failed to analyze field {field_name}: {e}")
        
        return patterns
    
    def _infer_field_type(self, series: pd.Series) -> str:
        """Infer the type of a data field."""
        # Check for specific patterns first
        sample_values = series.astype(str).head(10).tolist()
        
        for pattern_type, pattern in self.field_type_patterns.items():
            if sum(1 for val in sample_values if re.match(pattern, str(val))) > len(sample_values) * 0.7:
                return pattern_type
        
        # Check pandas inferred types
        try:
            # Try to convert to numeric
            pd.to_numeric(series)
            return 'numerical'
        except:
            pass
        
        try:
            # Try to convert to datetime
            pd.to_datetime(series)
            return 'timestamp'
        except:
            pass
        
        # Check cardinality for categorical vs textual
        unique_ratio = series.nunique() / len(series)
        if unique_ratio < 0.1:  # Low cardinality suggests categorical
            return 'categorical'
        else:
            return 'textual'
    
    def _extract_temporal_patterns(self, series: pd.Series, field_name: str) -> List[DataPattern]:
        """Extract temporal patterns from timestamp field."""
        patterns = []
        
        try:
            # Convert to datetime
            dt_series = pd.to_datetime(series)
            
            # Time range pattern
            time_range = dt_series.max() - dt_series.min()
            patterns.append(DataPattern(
                pattern_type='temporal',
                field_name=field_name,
                pattern_description=f'Time range spans {time_range}',
                examples=[dt_series.min(), dt_series.max()],
                confidence=1.0,
                metadata={'time_range_seconds': time_range.total_seconds()}
            ))
            
            # Time distribution patterns
            hour_dist = dt_series.dt.hour.value_counts()
            peak_hours = hour_dist.nlargest(3).index.tolist()
            patterns.append(DataPattern(
                pattern_type='temporal',
                field_name=field_name,
                pattern_description=f'Peak activity hours: {peak_hours}',
                examples=peak_hours,
                confidence=0.8,
                metadata={'hour_distribution': hour_dist.to_dict()}
            ))
            
            # Day of week patterns (if range > 1 week)
            if time_range.days >= 7:
                dow_dist = dt_series.dt.dayofweek.value_counts()
                peak_days = dow_dist.nlargest(2).index.tolist()
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                peak_day_names = [day_names[day] for day in peak_days]
                patterns.append(DataPattern(
                    pattern_type='temporal',
                    field_name=field_name,
                    pattern_description=f'Peak activity days: {peak_day_names}',
                    examples=peak_day_names,
                    confidence=0.7,
                    metadata={'dow_distribution': dow_dist.to_dict()}
                ))
            
        except Exception as e:
            logger.warning(f"Temporal pattern extraction failed for {field_name}: {e}")
        
        return patterns
    
    def _extract_categorical_patterns(self, series: pd.Series, field_name: str) -> List[DataPattern]:
        """Extract patterns from categorical field."""
        patterns = []
        
        try:
            value_counts = series.value_counts()
            
            # Top categories pattern
            top_categories = value_counts.head(5)
            patterns.append(DataPattern(
                pattern_type='categorical',
                field_name=field_name,
                pattern_description=f'Top categories: {top_categories.index.tolist()}',
                examples=top_categories.index.tolist(),
                confidence=0.9,
                metadata={'value_counts': top_categories.to_dict()}
            ))
            
            # Distribution pattern
            total_count = len(series)
            top_3_percentage = (top_categories.head(3).sum() / total_count) * 100
            if top_3_percentage > 80:
                patterns.append(DataPattern(
                    pattern_type='categorical',
                    field_name=field_name,
                    pattern_description=f'Highly skewed distribution - top 3 categories represent {top_3_percentage:.1f}%',
                    examples=top_categories.head(3).index.tolist(),
                    confidence=0.8,
                    metadata={'top_3_percentage': top_3_percentage}
                ))
            
            # Rare categories pattern
            rare_categories = value_counts[value_counts == 1]
            if len(rare_categories) > 0:
                patterns.append(DataPattern(
                    pattern_type='categorical',
                    field_name=field_name,
                    pattern_description=f'{len(rare_categories)} rare categories (single occurrence)',
                    examples=rare_categories.index.tolist()[:5],
                    confidence=0.7,
                    metadata={'rare_count': len(rare_categories)}
                ))
                
        except Exception as e:
            logger.warning(f"Categorical pattern extraction failed for {field_name}: {e}")
        
        return patterns
    
    def _extract_numerical_patterns(self, series: pd.Series, field_name: str) -> List[DataPattern]:
        """Extract patterns from numerical field."""
        patterns = []
        
        try:
            numeric_series = pd.to_numeric(series, errors='coerce').dropna()
            
            if len(numeric_series) == 0:
                return patterns
            
            # Statistical patterns
            stats = {
                'min': numeric_series.min(),
                'max': numeric_series.max(),
                'mean': numeric_series.mean(),
                'median': numeric_series.median(),
                'std': numeric_series.std()
            }
            
            patterns.append(DataPattern(
                pattern_type='numerical',
                field_name=field_name,
                pattern_description=f'Range: {stats["min"]:.2f} to {stats["max"]:.2f}, Mean: {stats["mean"]:.2f}',
                examples=[stats['min'], stats['max'], stats['mean']],
                confidence=1.0,
                metadata=stats
            ))
            
            # Distribution patterns
            q1 = numeric_series.quantile(0.25)
            q3 = numeric_series.quantile(0.75)
            iqr = q3 - q1
            
            # Outlier detection
            outlier_threshold_low = q1 - 1.5 * iqr
            outlier_threshold_high = q3 + 1.5 * iqr
            outliers = numeric_series[(numeric_series < outlier_threshold_low) | 
                                    (numeric_series > outlier_threshold_high)]
            
            if len(outliers) > 0:
                patterns.append(DataPattern(
                    pattern_type='numerical',
                    field_name=field_name,
                    pattern_description=f'{len(outliers)} outliers detected',
                    examples=outliers.head(3).tolist(),
                    confidence=0.8,
                    metadata={'outlier_count': len(outliers), 'outlier_percentage': len(outliers)/len(numeric_series)*100}
                ))
            
            # Zero/negative value patterns
            zero_count = (numeric_series == 0).sum()
            negative_count = (numeric_series < 0).sum()
            
            if zero_count > 0:
                patterns.append(DataPattern(
                    pattern_type='numerical',
                    field_name=field_name,
                    pattern_description=f'{zero_count} zero values ({zero_count/len(numeric_series)*100:.1f}%)',
                    examples=[0],
                    confidence=0.9,
                    metadata={'zero_count': zero_count, 'zero_percentage': zero_count/len(numeric_series)*100}
                ))
            
            if negative_count > 0:
                patterns.append(DataPattern(
                    pattern_type='numerical',
                    field_name=field_name,
                    pattern_description=f'{negative_count} negative values',
                    examples=numeric_series[numeric_series < 0].head(3).tolist(),
                    confidence=0.9,
                    metadata={'negative_count': negative_count}
                ))
                
        except Exception as e:
            logger.warning(f"Numerical pattern extraction failed for {field_name}: {e}")
        
        return patterns
    
    def _extract_textual_patterns(self, series: pd.Series, field_name: str) -> List[DataPattern]:
        """Extract patterns from textual field."""
        patterns = []
        
        try:
            # Length patterns
            lengths = series.astype(str).str.len()
            patterns.append(DataPattern(
                pattern_type='textual',
                field_name=field_name,
                pattern_description=f'Text length range: {lengths.min()} to {lengths.max()} characters',
                examples=[lengths.min(), lengths.max(), lengths.mean()],
                confidence=0.8,
                metadata={'length_stats': {'min': lengths.min(), 'max': lengths.max(), 'mean': lengths.mean()}}
            ))
            
            # Common words/phrases
            all_text = ' '.join(series.astype(str).tolist()).lower()
            words = re.findall(r'\b\w+\b', all_text)
            word_counts = Counter(words)
            common_words = word_counts.most_common(10)
            
            if common_words:
                patterns.append(DataPattern(
                    pattern_type='textual',
                    field_name=field_name,
                    pattern_description=f'Common words: {[word for word, count in common_words[:5]]}',
                    examples=[word for word, count in common_words[:5]],
                    confidence=0.7,
                    metadata={'word_frequencies': dict(common_words)}
                ))
            
            # Format patterns (simplified)
            sample_values = series.head(20).astype(str).tolist()
            
            # Check for common formats
            if all(len(val) == len(sample_values[0]) for val in sample_values[:5]):
                patterns.append(DataPattern(
                    pattern_type='textual',
                    field_name=field_name,
                    pattern_description=f'Fixed length format ({len(sample_values[0])} characters)',
                    examples=sample_values[:3],
                    confidence=0.8,
                    metadata={'fixed_length': len(sample_values[0])}
                ))
                
        except Exception as e:
            logger.warning(f"Textual pattern extraction failed for {field_name}: {e}")
        
        return patterns
    
    def _extract_formatted_patterns(self, series: pd.Series, field_name: str, format_type: str) -> List[DataPattern]:
        """Extract patterns from formatted fields (IP, email, etc.)."""
        patterns = []
        
        try:
            unique_values = series.unique()
            
            patterns.append(DataPattern(
                pattern_type='textual',
                field_name=field_name,
                pattern_description=f'{format_type} field with {len(unique_values)} unique values',
                examples=unique_values[:5].tolist(),
                confidence=0.9,
                metadata={'format_type': format_type, 'unique_count': len(unique_values)}
            ))
            
            # IP-specific patterns
            if format_type == 'ip_address':
                # Extract network prefixes
                network_prefixes = set()
                for ip in unique_values[:20]:  # Sample to avoid performance issues
                    parts = str(ip).split('.')
                    if len(parts) >= 3:
                        network_prefixes.add('.'.join(parts[:3]))
                
                if network_prefixes:
                    patterns.append(DataPattern(
                        pattern_type='textual',
                        field_name=field_name,
                        pattern_description=f'Network prefixes: {list(network_prefixes)[:5]}',
                        examples=list(network_prefixes)[:5],
                        confidence=0.8,
                        metadata={'network_prefixes': list(network_prefixes)}
                    ))
                    
        except Exception as e:
            logger.warning(f"Formatted pattern extraction failed for {field_name}: {e}")
        
        return patterns
    
    def _extract_structural_patterns(self, df: pd.DataFrame) -> List[DataPattern]:
        """Extract structural patterns across fields."""
        patterns = []
        
        try:
            # Field correlation patterns
            numeric_fields = df.select_dtypes(include=[np.number]).columns
            if len(numeric_fields) > 1:
                correlation_matrix = df[numeric_fields].corr()
                
                # Find high correlations
                high_correlations = []
                for i in range(len(correlation_matrix.columns)):
                    for j in range(i+1, len(correlation_matrix.columns)):
                        corr_val = correlation_matrix.iloc[i, j]
                        if abs(corr_val) > 0.7:  # Strong correlation
                            field1 = correlation_matrix.columns[i]
                            field2 = correlation_matrix.columns[j]
                            high_correlations.append((field1, field2, corr_val))
                
                if high_correlations:
                    patterns.append(DataPattern(
                        pattern_type='structural',
                        field_name='cross_field',
                        pattern_description=f'Strong correlations found: {high_correlations[:3]}',
                        examples=high_correlations[:3],
                        confidence=0.8,
                        metadata={'correlations': high_correlations}
                    ))
            
            # Missing value patterns
            missing_patterns = df.isnull().sum()
            fields_with_missing = missing_patterns[missing_patterns > 0]
            
            if len(fields_with_missing) > 0:
                patterns.append(DataPattern(
                    pattern_type='structural',
                    field_name='data_quality',
                    pattern_description=f'Fields with missing values: {fields_with_missing.index.tolist()}',
                    examples=fields_with_missing.to_dict(),
                    confidence=1.0,
                    metadata={'missing_value_counts': fields_with_missing.to_dict()}
                ))
                
        except Exception as e:
            logger.warning(f"Structural pattern extraction failed: {e}")
        
        return patterns
    
    def _extract_temporal_relationships(self, df: pd.DataFrame) -> List[DataPattern]:
        """Extract temporal relationships between fields."""
        patterns = []
        
        try:
            # Find timestamp fields
            timestamp_fields = []
            for col in df.columns:
                try:
                    pd.to_datetime(df[col].dropna().head(10))
                    timestamp_fields.append(col)
                except:
                    continue
            
            if len(timestamp_fields) > 1:
                patterns.append(DataPattern(
                    pattern_type='temporal',
                    field_name='temporal_relationships',
                    pattern_description=f'Multiple timestamp fields: {timestamp_fields}',
                    examples=timestamp_fields,
                    confidence=0.9,
                    metadata={'timestamp_fields': timestamp_fields}
                ))
                
        except Exception as e:
            logger.warning(f"Temporal relationship extraction failed: {e}")
        
        return patterns
    
    def calculate_field_statistics(self, data_samples: List[Dict[str, Any]]) -> Dict[str, FieldStatistics]:
        """Calculate comprehensive statistics for each field."""
        if not data_samples:
            return {}
        
        try:
            df = pd.DataFrame(data_samples)
            field_stats = {}
            
            for field_name in df.columns:
                series = df[field_name]
                
                # Basic statistics
                unique_count = series.nunique()
                null_count = series.isnull().sum()
                null_percentage = (null_count / len(series)) * 100
                
                # Sample non-null values
                non_null_series = series.dropna()
                sample_values = non_null_series.head(10).tolist() if len(non_null_series) > 0 else []
                
                # Infer data type
                data_type = self._infer_field_type(non_null_series) if len(non_null_series) > 0 else 'unknown'
                
                # Type-specific statistics
                type_stats = {}
                if data_type == 'numerical' and len(non_null_series) > 0:
                    try:
                        numeric_series = pd.to_numeric(non_null_series, errors='coerce').dropna()
                        if len(numeric_series) > 0:
                            type_stats = {
                                'min': float(numeric_series.min()),
                                'max': float(numeric_series.max()),
                                'mean': float(numeric_series.mean()),
                                'median': float(numeric_series.median()),
                                'std': float(numeric_series.std()) if len(numeric_series) > 1 else 0.0
                            }
                    except:
                        pass
                elif data_type == 'categorical' and len(non_null_series) > 0:
                    value_counts = non_null_series.value_counts()
                    type_stats = {
                        'unique_values': unique_count,
                        'most_common': value_counts.head(5).to_dict(),
                        'cardinality_ratio': unique_count / len(non_null_series)
                    }
                
                field_stats[field_name] = FieldStatistics(
                    field_name=field_name,
                    data_type=data_type,
                    unique_count=unique_count,
                    null_count=null_count,
                    null_percentage=null_percentage,
                    sample_values=sample_values,
                    statistics=type_stats
                )
                
        except Exception as e:
            logger.error(f"Field statistics calculation failed: {e}")
            return {}
        
        return field_stats
    
    def assess_data_quality(self, 
                           data_samples: List[Dict[str, Any]], 
                           schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """Assess data quality metrics."""
        quality_metrics = {
            'completeness': 0.0,
            'consistency': 0.0,
            'validity': 0.0,
            'accuracy_indicators': {},
            'quality_issues': []
        }
        
        if not data_samples:
            return quality_metrics
        
        try:
            df = pd.DataFrame(data_samples)
            
            # Completeness: percentage of non-null values
            total_cells = df.size
            non_null_cells = df.count().sum()
            quality_metrics['completeness'] = (non_null_cells / total_cells) * 100 if total_cells > 0 else 0
            
            # Consistency: check for data type consistency
            consistency_scores = []
            for field_name in df.columns:
                series = df[field_name].dropna()
                if len(series) > 0:
                    inferred_type = self._infer_field_type(series)
                    # Check if values match the inferred type
                    type_consistency = self._check_type_consistency(series, inferred_type)
                    consistency_scores.append(type_consistency)
            
            quality_metrics['consistency'] = np.mean(consistency_scores) * 100 if consistency_scores else 0
            
            # Validity: check against schema if provided
            if schema and 'properties' in schema:
                validity_score = self._check_schema_validity(df, schema)
                quality_metrics['validity'] = validity_score * 100
            else:
                quality_metrics['validity'] = 50  # Neutral score without schema
            
            # Identify quality issues
            quality_issues = []
            
            # High missing value rate
            missing_rates = df.isnull().sum() / len(df)
            high_missing = missing_rates[missing_rates > 0.2]
            if len(high_missing) > 0:
                quality_issues.append(f"High missing value rate in fields: {high_missing.index.tolist()}")
            
            # Duplicate records
            duplicate_count = df.duplicated().sum()
            if duplicate_count > 0:
                quality_issues.append(f"{duplicate_count} duplicate records found")
            
            # Fields with single value (no variance)
            single_value_fields = []
            for field in df.columns:
                if df[field].nunique() == 1:
                    single_value_fields.append(field)
            
            if single_value_fields:
                quality_issues.append(f"Fields with single value: {single_value_fields}")
            
            quality_metrics['quality_issues'] = quality_issues
            
        except Exception as e:
            logger.error(f"Data quality assessment failed: {e}")
            quality_metrics['error'] = str(e)
        
        return quality_metrics
    
    def _check_type_consistency(self, series: pd.Series, expected_type: str) -> float:
        """Check type consistency for a field."""
        try:
            if expected_type == 'numerical':
                numeric_count = pd.to_numeric(series, errors='coerce').notna().sum()
                return numeric_count / len(series)
            elif expected_type == 'timestamp':
                datetime_count = pd.to_datetime(series, errors='coerce').notna().sum()
                return datetime_count / len(series)
            elif expected_type in self.field_type_patterns:
                pattern = self.field_type_patterns[expected_type]
                match_count = sum(1 for val in series.astype(str) if re.match(pattern, val))
                return match_count / len(series)
            else:
                return 1.0  # Default to consistent for other types
        except:
            return 0.0
    
    def _check_schema_validity(self, df: pd.DataFrame, schema: Dict[str, Any]) -> float:
        """Check validity against Elasticsearch schema."""
        validity_scores = []
        
        schema_fields = schema.get('properties', {})
        
        for field_name, field_def in schema_fields.items():
            if field_name in df.columns:
                field_type = field_def.get('type', 'unknown')
                series = df[field_name].dropna()
                
                if len(series) > 0:
                    # Check type compatibility
                    if field_type == 'date':
                        try:
                            pd.to_datetime(series)
                            validity_scores.append(1.0)
                        except:
                            validity_scores.append(0.0)
                    elif field_type in ['integer', 'long', 'float', 'double']:
                        try:
                            pd.to_numeric(series)
                            validity_scores.append(1.0)
                        except:
                            validity_scores.append(0.0)
                    elif field_type == 'keyword':
                        # Check if values are reasonable for keyword field
                        avg_length = series.astype(str).str.len().mean()
                        validity_scores.append(1.0 if avg_length < 256 else 0.5)
                    else:
                        validity_scores.append(0.8)  # Default reasonable score
        
        return np.mean(validity_scores) if validity_scores else 0.5

class SchemaVisualizer:
    """
    Creates visual representations of schemas for multi-modal understanding.
    
    Generates schema diagrams and visualizations that can be processed
    by the visual analyzer.
    """
    
    def __init__(self):
        self.visualization_cache = {}
    
    def create_schema_visualization(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Create a visual representation of the schema."""
        visualization = {
            'visualization_type': 'schema_diagram',
            'elements': [],
            'layout': {},
            'metadata': {}
        }
        
        if 'properties' in schema:
            fields = schema['properties']
            
            # Create field elements
            y_position = 50
            for field_name, field_def in fields.items():
                field_type = field_def.get('type', 'unknown') if isinstance(field_def, dict) else 'unknown'
                
                element = {
                    'type': 'field_box',
                    'content': f'{field_name} ({field_type})',
                    'position': {'x': 50, 'y': y_position, 'width': 200, 'height': 30},
                    'metadata': {
                        'field_name': field_name,
                        'field_type': field_type,
                        'definition': field_def
                    }
                }
                
                visualization['elements'].append(element)
                y_position += 40
            
            # Add summary information
            visualization['metadata'] = {
                'total_fields': len(fields),
                'field_types': list(set(
                    field_def.get('type', 'unknown') if isinstance(field_def, dict) else 'unknown'
                    for field_def in fields.values()
                ))
            }
        
        return visualization
    
    def create_data_sample_visualization(self, 
                                       data_samples: List[Dict[str, Any]], 
                                       max_samples: int = 5) -> Dict[str, Any]:
        """Create a visual representation of data samples."""
        visualization = {
            'visualization_type': 'data_table',
            'elements': [],
            'layout': {},
            'metadata': {}
        }
        
        if not data_samples:
            return visualization
        
        # Use first sample to determine columns
        first_sample = data_samples[0]
        columns = list(first_sample.keys())
        
        # Create header element
        header_element = {
            'type': 'table_header',
            'content': ','.join(columns),
            'position': {'x': 10, 'y': 10, 'width': len(columns) * 100, 'height': 30},
            'metadata': {'columns': columns}
        }
        visualization['elements'].append(header_element)
        
        # Create row elements
        y_position = 50
        for i, sample in enumerate(data_samples[:max_samples]):
            row_values = [str(sample.get(col, '')) for col in columns]
            row_element = {
                'type': 'table_row',
                'content': ','.join(row_values),
                'position': {'x': 10, 'y': y_position, 'width': len(columns) * 100, 'height': 25},
                'metadata': {'row_index': i, 'values': row_values}
            }
            visualization['elements'].append(row_element)
            y_position += 30
        
        visualization['metadata'] = {
            'total_samples': len(data_samples),
            'displayed_samples': min(len(data_samples), max_samples),
            'columns': columns
        }
        
        return visualization

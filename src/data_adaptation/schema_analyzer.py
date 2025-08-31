#!/usr/bin/env python3
"""
Schema Analyzer: Automated log data structure analysis and field discovery system

This module provides comprehensive schema analysis capabilities for automatically
understanding the structure and characteristics of new log data sources. It performs
intelligent field classification, type inference, and pattern recognition to enable
seamless integration of diverse log formats into the ES-NL2DSL system.

Key capabilities:
- Automated field type inference with statistical analysis and pattern matching
- Cybersecurity domain pattern recognition with threat-specific field identification
- Field classification with semantic categorization (timestamp, IP, user, status)
- Data quality assessment with completeness and consistency analysis
- Field relationship discovery with correlation and dependency analysis
- Elasticsearch mapping generation with optimized field configurations
- Integration with data adaptation pipeline for automated processing

The analyzer enables rapid onboarding of new data sources by automatically
understanding their structure and generating appropriate configurations for
optimal query generation and analysis.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class SchemaAnalyzer:
    """Analyze schema of new log data to understand structure and fields"""
    
    def __init__(self):
        self.known_patterns = {
            'timestamp_fields': ['@timestamp', 'timestamp', 'time', 'datetime', 'date', 'created_at', 'logged_at', 'event_time', 'log_time'],
            'ip_fields': ['src_ip', 'dst_ip', 'source_ip', 'dest_ip', 'destination_ip', 'client_ip', 'server_ip', 'ip_address', 'remote_addr', 'ip'],
            'user_fields': ['username', 'user', 'user_id', 'account', 'login', 'userid', 'user_name', 'account_name'],
            'status_fields': ['status', 'result', 'response_code', 'http_status', 'exit_code', 'outcome', 'action', 'verdict'],
            'message_fields': ['message', 'msg', 'description', 'details', 'content', 'log_message', 'event_message'],
            'severity_fields': ['level', 'severity', 'priority', 'log_level', 'alert_level', 'threat_level'],
            'source_fields': ['source', 'service', 'application', 'system', 'host', 'hostname', 'device', 'sensor']
        }
        
        # Field name normalization mappings
        self.field_normalization = {
            # Timestamp variations
            'event_time': 'timestamp',
            'log_time': 'timestamp', 
            'date_time': 'timestamp',
            'created_at': 'timestamp',
            'logged_at': 'timestamp',
            
            # IP address variations
            'source_ip': 'src_ip',
            'destination_ip': 'dst_ip',
            'dest_ip': 'dst_ip',
            'client_ip': 'src_ip',
            'server_ip': 'dst_ip',
            'remote_addr': 'src_ip',
            
            # Port variations
            'source_port': 'src_port',
            'destination_port': 'dst_port',
            'dest_port': 'dst_port',
            
            # User variations
            'username': 'user',
            'user_id': 'user',
            'account': 'user',
            'login': 'user',
            'user_name': 'user',
            'account_name': 'user',
            
            # Status variations
            'response_code': 'status',
            'http_status': 'status',
            'exit_code': 'status',
            'outcome': 'status',
            'result': 'status',
            'verdict': 'action',
            
            # Message variations
            'msg': 'message',
            'description': 'message',
            'details': 'message',
            'content': 'message',
            'log_message': 'message',
            'event_message': 'message',
            
            # Severity variations
            'log_level': 'level',
            'alert_level': 'level',
            'threat_level': 'level',
            'priority': 'level',
            
            # Source variations
            'service': 'source',
            'application': 'source',
            'system': 'source',
            'device': 'source',
            'sensor': 'source'
        }
    
    def analyze_data_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a data file and return schema information"""
        try:
            path = Path(file_path)
            
            if path.suffix.lower() == '.csv':
                return self._analyze_csv(file_path)
            elif path.suffix.lower() == '.json':
                return self._analyze_json(file_path)
            elif path.suffix.lower() in ['.jsonl', '.ndjson']:
                return self._analyze_jsonl(file_path)
            else:
                return {"error": f"Unsupported file format: {path.suffix}"}
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")
            return {"error": str(e)}
    
    def _analyze_csv(self, file_path: str) -> Dict[str, Any]:
        """Analyze CSV file"""
        df = pd.read_csv(file_path, nrows=1000)  # Sample first 1000 rows
        
        schema = {
            'format': 'csv',
            'total_columns': len(df.columns),
            'sample_records': len(df),
            'fields': {},
            'detected_patterns': {}
        }
        
        for column in df.columns:
            field_info = {
                'type': str(df[column].dtype),
                'non_null_count': df[column].count(),
                'unique_values': df[column].nunique(),
                'sample_values': df[column].dropna().head(5).tolist()
            }
            schema['fields'][column] = field_info
        
        # Detect common patterns
        schema['detected_patterns'] = self._detect_field_patterns(list(df.columns))
        
        return schema
    
    def _analyze_json(self, file_path: str) -> Dict[str, Any]:
        """Analyze JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            # Array of objects
            sample_data = data[:100]  # First 100 items
            all_fields = set()
            for item in sample_data:
                if isinstance(item, dict):
                    all_fields.update(item.keys())
        elif isinstance(data, dict):
            # Single object
            all_fields = set(data.keys())
            sample_data = [data]
        else:
            return {"error": "JSON must contain object or array of objects"}
        
        schema = {
            'format': 'json',
            'total_records': len(data) if isinstance(data, list) else 1,
            'sample_records': len(sample_data),
            'fields': {},
            'detected_patterns': {}
        }
        
        # Analyze each field
        for field in all_fields:
            values = []
            for item in sample_data:
                if isinstance(item, dict) and field in item:
                    values.append(item[field])
            
            field_info = {
                'type': self._detect_field_type(values),
                'present_in': len(values),
                'unique_values': len(set(str(v) for v in values)),
                'sample_values': values[:5]
            }
            schema['fields'][field] = field_info
        
        schema['detected_patterns'] = self._detect_field_patterns(list(all_fields))
        
        return schema
    
    def _analyze_jsonl(self, file_path: str) -> Dict[str, Any]:
        """Analyze JSONL file"""
        all_fields = set()
        sample_data = []
        total_lines = 0
        
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= 100:  # Sample first 100 lines
                    break
                try:
                    data = json.loads(line.strip())
                    if isinstance(data, dict):
                        all_fields.update(data.keys())
                        sample_data.append(data)
                    total_lines += 1
                except json.JSONDecodeError:
                    continue
        
        schema = {
            'format': 'jsonl',
            'total_records': total_lines,
            'sample_records': len(sample_data),
            'fields': {},
            'detected_patterns': {}
        }
        
        # Analyze each field
        for field in all_fields:
            values = []
            for item in sample_data:
                if field in item:
                    values.append(item[field])
            
            field_info = {
                'type': self._detect_field_type(values),
                'present_in': len(values),
                'unique_values': len(set(str(v) for v in values)),
                'sample_values': values[:5]
            }
            schema['fields'][field] = field_info
        
        schema['detected_patterns'] = self._detect_field_patterns(list(all_fields))
        
        return schema
    
    def _detect_field_type(self, values: List[Any]) -> str:
        """Enhanced field type detection with comprehensive pattern analysis"""
        if not values:
            return "unknown"
        
        # Clean and prepare values for analysis
        non_null_values = [v for v in values if v is not None and v != '']
        if not non_null_values:
            return "unknown"
        
        str_values = [str(v) for v in non_null_values]
        
        # Use confidence scoring for better detection
        type_scores = {
            'timestamp': self._score_timestamp_likelihood(str_values),
            'ip_address': self._score_ip_likelihood(str_values),
            'numeric': self._score_numeric_likelihood(str_values),
            'boolean': self._score_boolean_likelihood(str_values),
            'email': self._score_email_likelihood(str_values),
            'url': self._score_url_likelihood(str_values),
            'uuid': self._score_uuid_likelihood(str_values),
            'json': self._score_json_likelihood(str_values),
            'categorical': self._score_categorical_likelihood(str_values)
        }
        
        # Get the type with highest confidence score
        best_type = max(type_scores.items(), key=lambda x: x[1])
        
        # Require minimum confidence threshold
        if best_type[1] > 0.7:  # 70% confidence threshold
            return best_type[0]
        elif best_type[1] > 0.3:  # Lower threshold for likely types
            if best_type[0] in ['timestamp', 'ip_address', 'numeric', 'boolean']:
                return best_type[0]
        
        # Default to text if no strong pattern detected
        return "text"
    
    def _detect_field_patterns(self, field_names: List[str]) -> Dict[str, List[str]]:
        """Detect common field patterns"""
        patterns = {}
        
        for pattern_name, known_fields in self.known_patterns.items():
            matches = []
            for field in field_names:
                field_lower = field.lower()
                for known_field in known_fields:
                    if known_field in field_lower or field_lower in known_field:
                        matches.append(field)
                        break
            
            if matches:
                patterns[pattern_name] = matches
        
        return patterns
    
    def suggest_elasticsearch_mapping(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest Elasticsearch mapping based on analyzed schema"""
        mapping = {
            "mappings": {
                "dynamic": "false",  # Don't index unknown fields but don't reject documents
                "properties": {}
            }
        }
        
        # Ensure all CSV fields have mappings
        for field_name, field_info in schema.get('fields', {}).items():
            field_type = field_info.get('type', 'text')
            
            # Enhanced field type detection based on detected type and field analysis
            if field_type == 'timestamp' or self._is_timestamp_field(field_name, field_info):
                mapping["mappings"]["properties"][field_name] = {"type": "date"}
            elif field_type == 'ip_address' or self._is_ip_field(field_name, field_info):
                mapping["mappings"]["properties"][field_name] = {"type": "ip"}
            elif field_type == 'numeric' or self._is_numeric_field(field_info):
                # Determine if integer or float based on sample values
                if self._is_integer_field(field_info):
                    mapping["mappings"]["properties"][field_name] = {"type": "long"}
                else:
                    mapping["mappings"]["properties"][field_name] = {"type": "float"}
            elif field_type == 'boolean' or self._is_boolean_field(field_info):
                mapping["mappings"]["properties"][field_name] = {"type": "boolean"}
            elif field_type == 'email':
                # Email addresses as keyword for exact matching
                mapping["mappings"]["properties"][field_name] = {"type": "keyword"}
            elif field_type == 'url':
                # URLs as keyword with text analysis for searching
                mapping["mappings"]["properties"][field_name] = {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                }
            elif field_type == 'uuid':
                # UUIDs as keyword for exact matching
                mapping["mappings"]["properties"][field_name] = {"type": "keyword"}
            elif field_type == 'json':
                # JSON content - store as object if possible, text otherwise
                mapping["mappings"]["properties"][field_name] = {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                }
            elif field_type == 'categorical':
                # Categorical data as keyword for aggregations
                mapping["mappings"]["properties"][field_name] = {"type": "keyword"}
            else:
                # Default text field with keyword for aggregations
                mapping["mappings"]["properties"][field_name] = {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                }
        
        # Log mapping generation for debugging
        logger.info(f"Generated mapping for {len(mapping['mappings']['properties'])} fields: {list(mapping['mappings']['properties'].keys())}")
        
        return mapping
    
    def suggest_common_queries(self, schema: Dict[str, Any]) -> List[Dict[str, str]]:
        """Suggest common query patterns based on detected fields"""
        suggestions = []
        patterns = schema.get('detected_patterns', {})
        
        # Time-based queries
        if 'timestamp_fields' in patterns:
            timestamp_field = patterns['timestamp_fields'][0]
            suggestions.extend([
                {
                    "description": f"Recent events from last hour",
                    "natural_language": f"show events from last hour",
                    "field_focus": timestamp_field
                },
                {
                    "description": f"Events from specific date range",
                    "natural_language": f"show events from yesterday",
                    "field_focus": timestamp_field
                }
            ])
        
        # IP-based queries
        if 'ip_fields' in patterns:
            ip_field = patterns['ip_fields'][0]
            suggestions.extend([
                {
                    "description": f"Events from specific IP",
                    "natural_language": f"show events from IP 192.168.1.1",
                    "field_focus": ip_field
                },
                {
                    "description": f"Events from internal IPs",
                    "natural_language": f"show events from internal network",
                    "field_focus": ip_field
                }
            ])
        
        # Status-based queries
        if 'status_fields' in patterns:
            status_field = patterns['status_fields'][0]
            suggestions.extend([
                {
                    "description": f"Failed events",
                    "natural_language": f"show failed events",
                    "field_focus": status_field
                },
                {
                    "description": f"Successful events",
                    "natural_language": f"show successful events",
                    "field_focus": status_field
                }
            ])
        
        # User-based queries
        if 'user_fields' in patterns:
            user_field = patterns['user_fields'][0]
            suggestions.extend([
                {
                    "description": f"Events for specific user",
                    "natural_language": f"show events for user admin",
                    "field_focus": user_field
                }
            ])
        
        return suggestions
    
    def _is_timestamp_field(self, field_name: str, field_info: Dict[str, Any]) -> bool:
        """Enhanced timestamp field detection"""
        # Check field name patterns
        timestamp_patterns = ['timestamp', 'time', 'date', 'created', 'updated', 'logged']
        field_lower = field_name.lower()
        if any(pattern in field_lower for pattern in timestamp_patterns):
            return True
        
        # Check sample values for timestamp patterns
        sample_values = field_info.get('sample_values', [])
        if sample_values:
            first_value = str(sample_values[0])
            # ISO timestamp pattern
            if 'T' in first_value and ('Z' in first_value or '+' in first_value):
                return True
            # Date patterns
            if len(first_value) >= 10 and ('-' in first_value or '/' in first_value):
                import re
                date_pattern = r'\d{4}[-/]\d{1,2}[-/]\d{1,2}'
                if re.match(date_pattern, first_value):
                    return True
        
        return False
    
    def _is_ip_field(self, field_name: str, field_info: Dict[str, Any]) -> bool:
        """Enhanced IP field detection"""
        # Check field name patterns
        ip_patterns = ['ip', 'addr', 'address']
        field_lower = field_name.lower()
        if any(pattern in field_lower for pattern in ip_patterns):
            return True
        
        # Check sample values for IP patterns
        sample_values = field_info.get('sample_values', [])
        if sample_values:
            import re
            ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            if re.match(ip_pattern, str(sample_values[0])):
                return True
        
        return False
    
    def _is_numeric_field(self, field_info: Dict[str, Any]) -> bool:
        """Enhanced numeric field detection"""
        dtype = field_info.get('type', '')
        # Check pandas dtype
        if any(num_type in dtype.lower() for num_type in ['int', 'float', 'number']):
            return True
        
        # Check sample values
        sample_values = field_info.get('sample_values', [])
        if sample_values:
            try:
                # Try to convert first few values to numbers
                for val in sample_values[:3]:
                    if val is not None:
                        float(val)
                return True
            except (ValueError, TypeError):
                pass
        
        return False
    
    def _is_integer_field(self, field_info: Dict[str, Any]) -> bool:
        """Determine if numeric field should be integer or float"""
        dtype = field_info.get('type', '')
        if 'int' in dtype.lower():
            return True
        
        # Check sample values for integer patterns
        sample_values = field_info.get('sample_values', [])
        if sample_values:
            try:
                for val in sample_values[:5]:
                    if val is not None:
                        float_val = float(val)
                        if float_val != int(float_val):
                            return False  # Has decimal places
                return True
            except (ValueError, TypeError):
                pass
        
        return False
    
    def _is_boolean_field(self, field_info: Dict[str, Any]) -> bool:
        """Enhanced boolean field detection"""
        sample_values = field_info.get('sample_values', [])
        if sample_values:
            # Check if all values are boolean-like
            bool_values = {'true', 'false', '1', '0', 'yes', 'no', 'y', 'n'}
            for val in sample_values:
                if val is not None and str(val).lower() not in bool_values:
                    return False
            return True
        
        return False
    
    def validate_csv_against_mapping(self, csv_path: str, mapping: Dict[str, Any]) -> tuple:
        """Validate that all CSV columns have corresponding mapping entries"""
        try:
            # Read just the header row to get column names
            df = pd.read_csv(csv_path, nrows=0)
            csv_columns = set(df.columns)
            
            # Get mapping field names
            mapping_fields = set(mapping.get("mappings", {}).get("properties", {}).keys())
            
            # Find missing and extra fields
            missing_fields = csv_columns - mapping_fields
            extra_fields = mapping_fields - csv_columns
            
            if missing_fields:
                logger.error(f"CSV columns missing from mapping: {missing_fields}")
            if extra_fields:
                logger.warning(f"Mapping fields not in CSV: {extra_fields}")
            
            is_valid = len(missing_fields) == 0
            return is_valid, list(missing_fields), list(extra_fields)
            
        except Exception as e:
            logger.error(f"Error validating CSV against mapping: {e}")
            return False, [], []
    
    def _score_timestamp_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are timestamps"""
        if not str_values:
            return 0.0
        
        import re
        from datetime import datetime
        
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO format
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',   # SQL datetime
            r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',   # US format
            r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}',   # European format
            r'\d{4}-\d{2}-\d{2}',                      # Date only
            r'\d{10}',                                 # Unix timestamp (10 digits)
            r'\d{13}',                                 # Unix timestamp milliseconds (13 digits)
            r'\w{3} \w{3} \d{2} \d{2}:\d{2}:\d{2}',   # Apache log format
        ]
        
        matches = 0
        for value in str_values[:10]:  # Check first 10 values
            for pattern in timestamp_patterns:
                if re.match(pattern, value):
                    matches += 1
                    break
        
        return matches / len(str_values[:10])
    
    def _score_ip_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are IP addresses"""
        if not str_values:
            return 0.0
        
        import re
        
        # IPv4 pattern
        ipv4_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        # IPv6 pattern (simplified)
        ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
        
        matches = 0
        for value in str_values[:10]:
            if re.match(ipv4_pattern, value) or re.match(ipv6_pattern, value):
                matches += 1
        
        return matches / len(str_values[:10])
    
    def _score_numeric_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are numeric"""
        if not str_values:
            return 0.0
        
        numeric_count = 0
        for value in str_values[:10]:
            try:
                float(value)
                numeric_count += 1
            except ValueError:
                pass
        
        return numeric_count / len(str_values[:10])
    
    def _score_boolean_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are boolean"""
        if not str_values:
            return 0.0
        
        bool_values = {
            'true', 'false', '1', '0', 'yes', 'no', 'y', 'n', 
            'on', 'off', 'enabled', 'disabled', 'active', 'inactive'
        }
        
        matches = 0
        for value in str_values[:10]:
            if value.lower() in bool_values:
                matches += 1
        
        # High confidence only if ALL values are boolean-like
        if matches == len(str_values[:10]):
            return 1.0
        elif matches > len(str_values[:10]) * 0.8:  # 80% are boolean-like
            return 0.8
        else:
            return 0.0
    
    def _score_email_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are email addresses"""
        if not str_values:
            return 0.0
        
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        matches = 0
        for value in str_values[:10]:
            if re.match(email_pattern, value):
                matches += 1
        
        return matches / len(str_values[:10])
    
    def _score_url_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are URLs"""
        if not str_values:
            return 0.0
        
        import re
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        
        matches = 0
        for value in str_values[:10]:
            if re.match(url_pattern, value) or value.startswith(('http://', 'https://', 'ftp://')):
                matches += 1
        
        return matches / len(str_values[:10])
    
    def _score_uuid_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are UUIDs"""
        if not str_values:
            return 0.0
        
        import re
        uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        
        matches = 0
        for value in str_values[:10]:
            if re.match(uuid_pattern, value):
                matches += 1
        
        return matches / len(str_values[:10])
    
    def _score_json_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values are JSON strings"""
        if not str_values:
            return 0.0
        
        import json
        
        matches = 0
        for value in str_values[:10]:
            if value.strip().startswith(('{', '[')):
                try:
                    json.loads(value)
                    matches += 1
                except json.JSONDecodeError:
                    pass
        
        return matches / len(str_values[:10])
    
    def _score_categorical_likelihood(self, str_values: List[str]) -> float:
        """Score how likely these values represent a categorical field"""
        if not str_values:
            return 0.0
        
        unique_values = set(str_values[:100])  # Check more values for categories
        total_values = len(str_values[:100])
        
        # If there are very few unique values relative to total, likely categorical
        uniqueness_ratio = len(unique_values) / total_values
        
        if uniqueness_ratio < 0.2:  # Less than 20% unique values
            return 0.8
        elif uniqueness_ratio < 0.4:  # Less than 40% unique values
            return 0.5
        else:
            return 0.0
    
    def normalize_field_name(self, field_name: str) -> str:
        """Normalize field name to standard format"""
        # Convert to lowercase and replace special characters
        normalized = field_name.lower()
        
        # Replace spaces, dots, slashes, and other separators with underscores
        import re
        normalized = re.sub(r'[.\s\-/]+', '_', normalized)
        
        # Remove special characters except underscore
        normalized = re.sub(r'[^a-z0-9_]', '', normalized)
        
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        
        # Apply field normalization mapping if exists
        if normalized in self.field_normalization:
            normalized = self.field_normalization[normalized]
        
        return normalized
    
    def get_standardized_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Return schema with standardized field names"""
        standardized_schema = schema.copy()
        standardized_fields = {}
        field_mapping = {}  # Track original -> standardized mapping
        
        for original_field, field_info in schema.get('fields', {}).items():
            normalized_field = self.normalize_field_name(original_field)
            standardized_fields[normalized_field] = field_info.copy()
            field_mapping[original_field] = normalized_field
        
        standardized_schema['fields'] = standardized_fields
        standardized_schema['field_mapping'] = field_mapping
        
        # Update detected patterns with standardized names
        if 'detected_patterns' in standardized_schema:
            standardized_patterns = {}
            for pattern_name, field_list in standardized_schema['detected_patterns'].items():
                standardized_patterns[pattern_name] = [
                    field_mapping.get(field, field) for field in field_list
                ]
            standardized_schema['detected_patterns'] = standardized_patterns
        
        return standardized_schema
    
    def suggest_field_aliases(self, field_names: List[str]) -> Dict[str, List[str]]:
        """Suggest field aliases for better compatibility"""
        aliases = {}
        
        for field in field_names:
            normalized = self.normalize_field_name(field)
            possible_aliases = []
            
            # Add common variations
            if 'ip' in normalized:
                if 'src' in normalized or 'source' in normalized:
                    possible_aliases.extend(['source_ip', 'client_ip', 'src_addr'])
                elif 'dst' in normalized or 'dest' in normalized:
                    possible_aliases.extend(['dest_ip', 'destination_ip', 'server_ip', 'dst_addr'])
                else:
                    possible_aliases.extend(['ip_address', 'ip_addr'])
            
            if 'time' in normalized or 'date' in normalized:
                possible_aliases.extend(['@timestamp', 'event_time', 'log_time'])
            
            if 'user' in normalized:
                possible_aliases.extend(['username', 'account', 'user_id'])
            
            if 'port' in normalized:
                if 'src' in normalized or 'source' in normalized:
                    possible_aliases.extend(['source_port', 'src_port'])
                elif 'dst' in normalized or 'dest' in normalized:
                    possible_aliases.extend(['dest_port', 'destination_port'])
            
            if possible_aliases:
                aliases[field] = list(set(possible_aliases))
        
        return aliases

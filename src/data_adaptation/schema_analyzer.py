#!/usr/bin/env python3
"""Schema Analyzer for new log data"""
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
            'timestamp_fields': ['@timestamp', 'timestamp', 'time', 'datetime', 'date', 'created_at', 'logged_at'],
            'ip_fields': ['src_ip', 'dst_ip', 'source_ip', 'dest_ip', 'client_ip', 'server_ip', 'ip_address', 'remote_addr'],
            'user_fields': ['username', 'user', 'user_id', 'account', 'login', 'userid'],
            'status_fields': ['status', 'result', 'response_code', 'http_status', 'exit_code', 'outcome'],
            'message_fields': ['message', 'msg', 'description', 'details', 'content', 'log_message'],
            'severity_fields': ['level', 'severity', 'priority', 'log_level', 'alert_level'],
            'source_fields': ['source', 'service', 'application', 'system', 'host', 'hostname']
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
            'sample_rows': len(df),
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
        """Detect the type of a field based on sample values"""
        if not values:
            return "unknown"
        
        # Check for common patterns
        str_values = [str(v).lower() for v in values if v is not None]
        
        # Check for timestamps
        if any(field in str_values[0] for field in ['timestamp', 'date', 'time']) or \
           any(char in str_values[0] for char in ['T', ':', '-'] if len(str_values[0]) > 10):
            return "timestamp"
        
        # Check for IPs
        if any('.' in str(v) and len(str(v).split('.')) == 4 for v in str_values[:3]):
            return "ip_address"
        
        # Check for numbers
        try:
            [float(v) for v in values[:3] if v is not None]
            return "numeric"
        except:
            pass
        
        # Check for boolean
        if all(str(v).lower() in ['true', 'false', '0', '1'] for v in str_values[:5]):
            return "boolean"
        
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
                "properties": {}
            }
        }
        
        for field_name, field_info in schema.get('fields', {}).items():
            field_type = field_info.get('type', 'text')
            
            if field_type == 'timestamp':
                mapping["mappings"]["properties"][field_name] = {"type": "date"}
            elif field_type == 'ip_address':
                mapping["mappings"]["properties"][field_name] = {"type": "ip"}
            elif field_type == 'numeric':
                mapping["mappings"]["properties"][field_name] = {"type": "long"}
            elif field_type == 'boolean':
                mapping["mappings"]["properties"][field_name] = {"type": "boolean"}
            else:
                # Text field with keyword for aggregations
                mapping["mappings"]["properties"][field_name] = {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword"
                        }
                    }
                }
        
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

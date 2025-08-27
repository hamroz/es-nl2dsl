#!/usr/bin/env python3
"""AI Assistant for helping with data adaptation and query generation"""
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AIAssistant:
    """AI Assistant to help adapt to new data and generate queries"""
    
    def __init__(self):
        self.model_cache = {}
    
    def analyze_data_with_ai(self, schema: Dict[str, Any], model: str = "llama3.1:latest") -> Dict[str, Any]:
        """Use AI to analyze data schema and provide insights"""
        try:
            from src.generators.constrained import call_local_model
            
            # Prepare analysis prompt
            prompt = self._create_analysis_prompt(schema)
            
            # Call the AI model
            response = call_local_model(prompt, model)
            
            # Parse AI response
            analysis = self._parse_analysis_response(response)
            
            return {
                "success": True,
                "model_used": model,
                "analysis": analysis,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def suggest_field_mappings(self, schema: Dict[str, Any], model: str = "llama3.1:latest") -> Dict[str, Any]:
        """Use AI to suggest field mappings for common log patterns"""
        try:
            from src.generators.constrained import call_local_model
            
            prompt = self._create_mapping_prompt(schema)
            response = call_local_model(prompt, model)
            
            mappings = self._parse_mapping_response(response)
            
            return {
                "success": True,
                "model_used": model,
                "suggested_mappings": mappings,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error in AI mapping suggestion: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_sample_queries(self, schema: Dict[str, Any], user_request: str, model: str = "llama3.1:latest") -> Dict[str, Any]:
        """Use AI to generate sample queries based on schema and user request"""
        try:
            from src.generators.constrained import call_local_model
            
            prompt = self._create_query_generation_prompt(schema, user_request)
            response = call_local_model(prompt, model)
            
            queries = self._parse_query_response(response)
            
            return {
                "success": True,
                "model_used": model,
                "generated_queries": queries,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error in AI query generation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_analysis_prompt(self, schema: Dict[str, Any]) -> str:
        """Create prompt for data analysis"""
        fields_info = []
        for field_name, field_info in schema.get('fields', {}).items():
            fields_info.append(f"- {field_name}: {field_info.get('type', 'unknown')} (samples: {field_info.get('sample_values', [])})")
        
        fields_text = '\n'.join(fields_info[:20])  # Limit to first 20 fields
        
        prompt = f"""Analyze this log data schema and provide insights:

Data Format: {schema.get('format', 'unknown')}
Total Fields: {len(schema.get('fields', {}))}
Sample Size: {schema.get('sample_records', 0)} records

Fields:
{fields_text}

Detected Patterns: {schema.get('detected_patterns', {})}

Please provide:
1. What type of system/application generated this data?
2. What are the most important fields for analysis?
3. What kind of queries would be most useful?
4. Any security or monitoring insights?

Respond in JSON format:
{{
    "system_type": "description of the system",
    "important_fields": ["field1", "field2"],
    "recommended_queries": ["query description 1", "query description 2"],
    "insights": ["insight 1", "insight 2"]
}}"""
        
        return prompt
    
    def _create_mapping_prompt(self, schema: Dict[str, Any]) -> str:
        """Create prompt for field mapping suggestions"""
        fields = list(schema.get('fields', {}).keys())[:30]  # Limit fields
        
        prompt = f"""Help map these log fields to common Elasticsearch field types:

Fields to map: {fields}

Common patterns to look for:
- Timestamp fields (should be 'date' type)
- IP addresses (should be 'ip' type) 
- Status/response codes (should be 'keyword' type)
- User IDs (should be 'keyword' type)
- Message/description fields (should be 'text' type)
- Numeric values (should be 'long' or 'double' type)

Respond in JSON format:
{{
    "field_mappings": {{
        "field_name": {{
            "type": "elasticsearch_type",
            "reason": "why this type was chosen"
        }}
    }}
}}"""
        
        return prompt
    
    def _create_query_generation_prompt(self, schema: Dict[str, Any], user_request: str) -> str:
        """Create prompt for query generation"""
        fields = list(schema.get('fields', {}).keys())
        patterns = schema.get('detected_patterns', {})
        
        prompt = f"""Generate Elasticsearch DSL queries for this data based on user request:

User Request: "{user_request}"

Available Fields: {fields[:20]}
Detected Patterns: {patterns}

Generate 3-5 useful Elasticsearch DSL queries that would help with the user's request.
Focus on practical queries that would be commonly used.

Respond in JSON format:
{{
    "queries": [
        {{
            "name": "Query name",
            "description": "What this query does",
            "dsl": {{
                "query": {{ "match_all": {{}} }}
            }}
        }}
    ]
}}"""
        
        return prompt
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse AI analysis response"""
        try:
            # Try to extract JSON from response
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                # Fallback to text analysis
                return {
                    "system_type": "Unknown - could not parse AI response",
                    "important_fields": [],
                    "recommended_queries": [],
                    "insights": [response[:500]]  # First 500 chars
                }
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return {
                "system_type": "Error parsing response",
                "important_fields": [],
                "recommended_queries": [],
                "insights": [str(e)]
            }
    
    def _parse_mapping_response(self, response: str) -> Dict[str, Any]:
        """Parse AI mapping response"""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                parsed = json.loads(json_str)
                return parsed.get('field_mappings', {})
            else:
                return {}
        except Exception as e:
            logger.error(f"Error parsing mapping response: {e}")
            return {}
    
    def _parse_query_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI query generation response"""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                parsed = json.loads(json_str)
                return parsed.get('queries', [])
            else:
                return []
        except Exception as e:
            logger.error(f"Error parsing query response: {e}")
            return []
    
    def create_adaptation_summary(self, schema: Dict[str, Any], ai_analysis: Dict[str, Any], mappings: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of the data adaptation process"""
        return {
            "data_overview": {
                "format": schema.get('format', 'unknown'),
                "total_fields": len(schema.get('fields', {})),
                "records_analyzed": schema.get('sample_records', 0),
                "system_type": ai_analysis.get('analysis', {}).get('system_type', 'Unknown')
            },
            "field_analysis": {
                "detected_patterns": schema.get('detected_patterns', {}),
                "important_fields": ai_analysis.get('analysis', {}).get('important_fields', []),
                "suggested_mappings": len(mappings)
            },
            "recommendations": {
                "queries": ai_analysis.get('analysis', {}).get('recommended_queries', []),
                "insights": ai_analysis.get('analysis', {}).get('insights', [])
            }
        }

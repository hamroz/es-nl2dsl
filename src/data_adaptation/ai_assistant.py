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
        # Initialize cybersecurity domain knowledge
        self.domain_knowledge = {
            "cybersecurity": {
                "threat_patterns": {
                    "brute_force": ["failed login", "authentication failure", "multiple attempts"],
                    "ddos": ["high volume", "traffic spike", "connection flood"],
                    "malware": ["suspicious file", "virus detected", "malicious payload"],
                    "insider_threat": ["unusual access", "privilege escalation", "data exfiltration"],
                    "network_scan": ["port scan", "network reconnaissance", "probe activity"]
                },
                "common_queries": {
                    "security_monitoring": [
                        "failed authentication attempts",
                        "suspicious IP addresses", 
                        "high-risk events",
                        "anomalous user behavior",
                        "network intrusion attempts"
                    ],
                    "incident_response": [
                        "events around specific time",
                        "activity from compromised systems",
                        "data access patterns",
                        "lateral movement indicators"
                    ]
                }
            }
        }
    
    def analyze_data_with_ai(self, schema: Dict[str, Any], model: str = "llama3.1:latest") -> Dict[str, Any]:
        """Use AI to analyze data schema and provide insights"""
        try:
            # Prepare analysis prompt
            prompt = self._create_analysis_prompt(schema)
            
            # Call the AI model (handle both local and external)
            response = self._call_ai_model(prompt, model)
            
            if response is None:
                return {
                    "success": False,
                    "error": f"Failed to get response from model: {model}"
                }
            
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
            prompt = self._create_mapping_prompt(schema)
            response = self._call_ai_model(prompt, model)
            
            if response is None:
                return {
                    "success": False,
                    "error": f"Failed to get response from model: {model}"
                }
            
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
            prompt = self._create_query_generation_prompt(schema, user_request)
            response = self._call_ai_model(prompt, model)
            
            if response is None:
                return {
                    "success": False,
                    "error": f"Failed to get response from model: {model}"
                }
            
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
    
    def _call_ai_model(self, prompt: str, model: str) -> Optional[str]:
        """Call AI model (local or external) with prompt"""
        try:
            # Check if it's an external model (has emoji prefix)
            if model.startswith("☁️ ") or model.startswith("External:"):
                # Extract model name
                if model.startswith("☁️ "):
                    external_model_name = model.replace("☁️ ", "")
                else:
                    external_model_name = model.replace("External: ", "")
                
                logger.info(f"Attempting to use external LLM: {external_model_name}")
                
                # Use external LLM manager
                from src.external.llm_manager import get_external_llm_manager
                manager = get_external_llm_manager()
                
                # Debug: Check if LLM exists and is enabled
                llm_config = manager.get_llm(external_model_name)
                if not llm_config:
                    logger.error(f"External LLM {external_model_name} not found in configuration")
                    available_llms = [llm.name for llm in manager.list_llms()]
                    logger.error(f"Available LLMs: {available_llms}")
                    return None
                
                if not llm_config.enabled:
                    logger.error(f"External LLM {external_model_name} is disabled")
                    return None
                
                if not llm_config.api_key:
                    logger.error(f"External LLM {external_model_name} has no API key")
                    return None
                
                logger.info(f"Calling external LLM {external_model_name} (provider: {llm_config.provider})")
                response = manager.call_llm(external_model_name, prompt)
                
                if response is None:
                    logger.error(f"External LLM {external_model_name} returned None")
                    if manager.last_error:
                        logger.error(f"Manager error: {manager.last_error}")
                else:
                    logger.info(f"External LLM {external_model_name} returned response of length {len(response)}")
                
                return response
                
            else:
                # Use local model
                from src.generators.constrained import call_local_model
                
                # Remove local prefix if present
                if model.startswith("🖥️ "):
                    local_model_name = model.replace("🖥️ ", "")
                else:
                    local_model_name = model
                
                logger.info(f"Calling local model: {local_model_name}")
                return call_local_model(prompt, local_model_name)
                
        except Exception as e:
            logger.error(f"Error calling AI model {model}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
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
    
    def generate_enhanced_queries(self, schema: Dict[str, Any], user_request: str, model: str = "llama3.1:latest") -> Dict[str, Any]:
        """Enhanced query generation using Phase 2 schema intelligence"""
        try:
            # Use Phase 2 enhanced schema analysis
            enhanced_context = self._build_enhanced_context(schema)
            
            # Create domain-aware prompt
            prompt = self._create_enhanced_query_prompt(schema, user_request, enhanced_context)
            
            response = self._call_ai_model(prompt, model)
            
            if response is None:
                return {
                    "success": False,
                    "error": f"Failed to get response from model: {model}"
                }
            
            # Parse queries with field validation
            queries = self._parse_enhanced_query_response(response, schema)
            
            # Apply query optimization
            optimized_queries = self._optimize_queries(queries, schema)
            
            return {
                "success": True,
                "model_used": model,
                "generated_queries": optimized_queries,
                "schema_context": enhanced_context,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced query generation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def suggest_field_aware_queries(self, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate field-aware query suggestions based on detected patterns"""
        suggestions = []
        patterns = schema.get('detected_patterns', {})
        field_types = self._extract_field_types(schema)
        
        # Time-based queries
        if 'timestamp_fields' in patterns:
            timestamp_field = patterns['timestamp_fields'][0]
            suggestions.extend([
                {
                    "name": "Recent Events",
                    "description": f"Show events from the last hour",
                    "category": "temporal",
                    "dsl": {
                        "query": {
                            "range": {
                                timestamp_field: {
                                    "gte": "now-1h",
                                    "lte": "now"
                                }
                            }
                        },
                        "sort": [{timestamp_field: {"order": "desc"}}]
                    }
                },
                {
                    "name": "Event Timeline",
                    "description": f"Timeline of events over the last 24 hours",
                    "category": "temporal",
                    "dsl": {
                        "query": {
                            "range": {
                                timestamp_field: {
                                    "gte": "now-24h",
                                    "lte": "now"
                                }
                            }
                        },
                        "aggs": {
                            "events_over_time": {
                                "date_histogram": {
                                    "field": timestamp_field,
                                    "fixed_interval": "1h"
                                }
                            }
                        }
                    }
                }
            ])
        
        # IP-based queries
        if 'ip_fields' in patterns:
            for ip_field in patterns['ip_fields']:
                suggestions.append({
                    "name": f"Top {ip_field.replace('_', ' ').title()}",
                    "description": f"Most active {ip_field} addresses",
                    "category": "network",
                    "dsl": {
                        "query": {"match_all": {}},
                        "aggs": {
                            f"top_{ip_field}": {
                                "terms": {
                                    "field": f"{ip_field}.keyword" if field_types.get(ip_field) == 'text' else ip_field,
                                    "size": 10
                                }
                            }
                        }
                    }
                })
        
        # Status/action based queries
        if 'status_fields' in patterns:
            for status_field in patterns['status_fields']:
                suggestions.extend([
                    {
                        "name": f"Failed {status_field.replace('_', ' ').title()}",
                        "description": f"Events with failed or error status",
                        "category": "security",
                        "dsl": {
                            "query": {
                                "bool": {
                                    "should": [
                                        {"match": {status_field: "failed"}},
                                        {"match": {status_field: "error"}},
                                        {"match": {status_field: "denied"}},
                                        {"match": {status_field: "blocked"}}
                                    ]
                                }
                            }
                        }
                    },
                    {
                        "name": f"{status_field.replace('_', ' ').title()} Distribution",
                        "description": f"Distribution of {status_field} values",
                        "category": "analytics",
                        "dsl": {
                            "query": {"match_all": {}},
                            "aggs": {
                                f"{status_field}_breakdown": {
                                    "terms": {
                                        "field": f"{status_field}.keyword" if field_types.get(status_field) == 'text' else status_field,
                                        "size": 20
                                    }
                                }
                            }
                        }
                    }
                ])
        
        # User-based queries
        if 'user_fields' in patterns:
            user_field = patterns['user_fields'][0]
            suggestions.extend([
                {
                    "name": "Top Active Users",
                    "description": f"Most active users by event count",
                    "category": "user_analytics",
                    "dsl": {
                        "query": {"match_all": {}},
                        "aggs": {
                            "top_users": {
                                "terms": {
                                    "field": f"{user_field}.keyword" if field_types.get(user_field) == 'text' else user_field,
                                    "size": 10
                                }
                            }
                        }
                    }
                },
                {
                    "name": "User Activity Pattern",
                    "description": f"User activity over time",
                    "category": "user_analytics",
                    "dsl": {
                        "query": {"match_all": {}},
                        "aggs": {
                            "users": {
                                "terms": {
                                    "field": f"{user_field}.keyword" if field_types.get(user_field) == 'text' else user_field,
                                    "size": 5
                                },
                                "aggs": {
                                    "activity_over_time": {
                                        "date_histogram": {
                                            "field": patterns.get('timestamp_fields', ['@timestamp'])[0],
                                            "fixed_interval": "1h"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            ])
        
        return suggestions
    
    def detect_domain_context(self, schema: Dict[str, Any]) -> str:
        """Detect the domain context of the data (cybersecurity, web logs, etc.)"""
        field_names = [name.lower() for name in schema.get('fields', {}).keys()]
        patterns = schema.get('detected_patterns', {})
        
        # Check for cybersecurity indicators
        security_indicators = [
            'threat', 'attack', 'malware', 'virus', 'intrusion', 'breach', 
            'vulnerability', 'incident', 'alert', 'suspicious', 'malicious',
            'firewall', 'ids', 'ips', 'siem', 'security', 'blocked', 'denied'
        ]
        
        web_indicators = [
            'http', 'url', 'browser', 'request', 'response', 'status_code',
            'user_agent', 'referer', 'path', 'method', 'cookie'
        ]
        
        network_indicators = [
            'packet', 'tcp', 'udp', 'port', 'protocol', 'bandwidth',
            'latency', 'router', 'switch', 'dns', 'dhcp'
        ]
        
        # Count matches for each domain
        security_score = sum(1 for indicator in security_indicators 
                           if any(indicator in field for field in field_names))
        web_score = sum(1 for indicator in web_indicators 
                       if any(indicator in field for field in field_names))
        network_score = sum(1 for indicator in network_indicators 
                           if any(indicator in field for field in field_names))
        
        # Determine domain based on highest score
        if security_score >= max(web_score, network_score) and security_score > 0:
            return "cybersecurity"
        elif web_score >= network_score and web_score > 0:
            return "web_logs"
        elif network_score > 0:
            return "network_logs"
        else:
            return "general"
    
    def _build_enhanced_context(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced context using Phase 2 schema analysis"""
        from .schema_analyzer import SchemaAnalyzer
        
        analyzer = SchemaAnalyzer()
        
        # Get standardized schema
        standardized_schema = analyzer.get_standardized_schema(schema)
        
        # Detect domain context
        domain = self.detect_domain_context(schema)
        
        # Get field aliases for better matching
        field_aliases = analyzer.suggest_field_aliases(list(schema.get('fields', {}).keys()))
        
        # Extract field types using Phase 2 detection
        field_types = {}
        for field_name, field_info in schema.get('fields', {}).items():
            detected_type = analyzer._detect_field_type(field_info.get('sample_values', []))
            field_types[field_name] = detected_type
        
        return {
            "domain": domain,
            "standardized_schema": standardized_schema,
            "field_aliases": field_aliases,
            "field_types": field_types,
            "detected_patterns": schema.get('detected_patterns', {}),
            "field_mapping": standardized_schema.get('field_mapping', {})
        }
    
    def _extract_field_types(self, schema: Dict[str, Any]) -> Dict[str, str]:
        """Extract field types from schema"""
        field_types = {}
        for field_name, field_info in schema.get('fields', {}).items():
            # Use detected type if available, otherwise infer from dtype
            field_type = field_info.get('detected_type', field_info.get('type', 'text'))
            field_types[field_name] = field_type
        return field_types
    
    def _create_enhanced_query_prompt(self, schema: Dict[str, Any], user_request: str, enhanced_context: Dict[str, Any]) -> str:
        """Create enhanced prompt for query generation with Phase 2 intelligence"""
        domain = enhanced_context.get('domain', 'general')
        field_types = enhanced_context.get('field_types', {})
        patterns = enhanced_context.get('detected_patterns', {})
        field_mapping = enhanced_context.get('field_mapping', {})
        
        # Build field information with types
        field_info_lines = []
        for field_name, field_type in field_types.items():
            original_name = field_name
            normalized_name = field_mapping.get(field_name, field_name)
            field_info_lines.append(f"  - {field_name} ({field_type})")
            if normalized_name != field_name:
                field_info_lines.append(f"    → normalized as: {normalized_name}")
        
        field_info = '\n'.join(field_info_lines[:25])  # Limit for readability
        
        # Domain-specific guidance
        domain_guidance = ""
        if domain == "cybersecurity":
            domain_guidance = """
CYBERSECURITY DOMAIN GUIDANCE:
- Focus on security events, threats, and anomalies
- Common query patterns: failed authentications, suspicious IPs, unusual activity
- Use threat hunting techniques: correlation, timeline analysis, behavioral analysis
- Consider MITRE ATT&CK framework concepts"""
        elif domain == "web_logs":
            domain_guidance = """
WEB LOGS DOMAIN GUIDANCE:
- Focus on HTTP requests, response codes, user agents
- Common patterns: error analysis, traffic patterns, bot detection
- Performance monitoring: response times, resource usage"""
        elif domain == "network_logs":
            domain_guidance = """
NETWORK LOGS DOMAIN GUIDANCE:
- Focus on traffic flows, protocols, ports
- Common patterns: bandwidth analysis, connection monitoring, protocol analysis"""
        
        prompt = f"""Generate advanced Elasticsearch DSL queries for this {domain} data:

USER REQUEST: "{user_request}"

DATA SCHEMA ANALYSIS:
Domain: {domain}
Total Fields: {len(field_types)}

AVAILABLE FIELDS WITH TYPES:
{field_info}

DETECTED PATTERNS:
{patterns}

{domain_guidance}

QUERY REQUIREMENTS:
1. Generate 3-5 practical, actionable queries
2. Use appropriate field types for optimal performance
3. Include both simple and aggregation queries
4. Focus on real-world use cases for {domain} data
5. Use proper Elasticsearch DSL syntax
6. Consider field mappings and normalization

OUTPUT FORMAT (JSON):
{{
    "queries": [
        {{
            "name": "Query Name",
            "description": "Clear description of what this query does",
            "category": "temporal|network|security|analytics|user_analytics",
            "complexity": "basic|intermediate|advanced",
            "use_case": "Description of when to use this query",
            "dsl": {{
                "query": {{ "match_all": {{}} }},
                "aggs": {{ ... }},
                "sort": [ ... ]
            }}
        }}
    ]
}}

Generate queries that directly address the user's request while leveraging the available field types and patterns."""
        
        return prompt
    
    def _parse_enhanced_query_response(self, response: str, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse enhanced query response with validation"""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                parsed = json.loads(json_str)
                queries = parsed.get('queries', [])
                
                # Validate and enhance each query
                validated_queries = []
                for query in queries:
                    if self._validate_query_fields(query, schema):
                        validated_queries.append(query)
                    else:
                        logger.warning(f"Query validation failed for: {query.get('name', 'Unknown')}")
                
                return validated_queries
            else:
                return []
        except Exception as e:
            logger.error(f"Error parsing enhanced query response: {e}")
            return []
    
    def _validate_query_fields(self, query: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate that query fields exist in schema"""
        try:
            dsl = query.get('dsl', {})
            available_fields = set(schema.get('fields', {}).keys())
            
            # Extract fields from query (basic validation)
            query_str = json.dumps(dsl)
            used_fields = []
            
            # Simple field extraction (could be enhanced)
            for field in available_fields:
                if f'"{field}"' in query_str:
                    used_fields.append(field)
            
            # If no fields detected or all fields exist, consider valid
            return len(used_fields) == 0 or all(field in available_fields for field in used_fields)
        except Exception as e:
            logger.error(f"Error validating query fields: {e}")
            return True  # Default to valid if validation fails
    
    def _optimize_queries(self, queries: List[Dict[str, Any]], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply query optimizations based on field types and schema"""
        optimized_queries = []
        field_types = self._extract_field_types(schema)
        
        for query in queries:
            try:
                optimized_query = query.copy()
                dsl = optimized_query.get('dsl', {})
                
                # Apply field-type specific optimizations
                optimized_dsl = self._optimize_dsl(dsl, field_types)
                optimized_query['dsl'] = optimized_dsl
                
                # Add performance hints
                optimized_query['performance_hints'] = self._generate_performance_hints(dsl, field_types)
                
                optimized_queries.append(optimized_query)
            except Exception as e:
                logger.error(f"Error optimizing query {query.get('name', 'Unknown')}: {e}")
                optimized_queries.append(query)  # Include original if optimization fails
        
        return optimized_queries
    
    def _optimize_dsl(self, dsl: Dict[str, Any], field_types: Dict[str, str]) -> Dict[str, Any]:
        """Optimize DSL based on field types"""
        optimized_dsl = dsl.copy()
        
        # Optimize aggregations for categorical fields
        if 'aggs' in optimized_dsl:
            optimized_dsl['aggs'] = self._optimize_aggregations(optimized_dsl['aggs'], field_types)
        
        # Add default size limit if not specified
        if 'size' not in optimized_dsl and 'aggs' not in optimized_dsl:
            optimized_dsl['size'] = 100
        
        return optimized_dsl
    
    def _optimize_aggregations(self, aggs: Dict[str, Any], field_types: Dict[str, str]) -> Dict[str, Any]:
        """Optimize aggregations based on field types"""
        optimized_aggs = {}
        
        for agg_name, agg_config in aggs.items():
            optimized_config = agg_config.copy()
            
            # Optimize terms aggregations for text fields
            if 'terms' in agg_config:
                field = agg_config['terms'].get('field', '')
                field_base = field.replace('.keyword', '')
                
                if field_base in field_types:
                    field_type = field_types[field_base]
                    if field_type in ['text', 'categorical'] and not field.endswith('.keyword'):
                        optimized_config['terms']['field'] = f"{field}.keyword"
            
            optimized_aggs[agg_name] = optimized_config
        
        return optimized_aggs
    
    def _generate_performance_hints(self, dsl: Dict[str, Any], field_types: Dict[str, str]) -> List[str]:
        """Generate performance optimization hints"""
        hints = []
        
        # Check for potential performance issues
        if 'aggs' in dsl and 'size' not in dsl:
            hints.append("Consider adding 'size': 0 for aggregation-only queries")
        
        if 'sort' in dsl and len(dsl.get('sort', [])) > 3:
            hints.append("Multiple sort fields may impact performance")
        
        # Check for wildcard queries on text fields
        query_str = json.dumps(dsl.get('query', {}))
        if '*' in query_str:
            hints.append("Wildcard queries can be slow on large datasets")
        
        return hints

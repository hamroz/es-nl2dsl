"""
Domain Adaptation Module for ES-NL2DSL

Handles domain-specific adaptations and schema learning for rapid
deployment to new environments and data sources.
"""

import json
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class DomainProfile:
    """Profile of a specific domain with its characteristics."""
    name: str
    description: str
    common_fields: List[str]
    field_patterns: Dict[str, str]  # field_name -> regex pattern
    temporal_patterns: List[str]
    aggregation_preferences: Dict[str, str]
    security_level: str  # 'low', 'medium', 'high'

class DomainAdapter:
    """
    Handles adaptation to different domains (security, networking, etc.).
    
    Provides domain-specific knowledge and adaptation strategies
    for rapid deployment in new environments.
    """
    
    def __init__(self):
        self.domain_profiles = self._initialize_domain_profiles()
        self.adaptation_history = {}
    
    def _initialize_domain_profiles(self) -> Dict[str, DomainProfile]:
        """Initialize built-in domain profiles."""
        profiles = {}
        
        # Security Domain
        profiles['security'] = DomainProfile(
            name='security',
            description='Cybersecurity and threat detection',
            common_fields=[
                'source_ip', 'destination_ip', 'src_port', 'dst_port',
                'protocol', 'attack_type', 'severity', 'event_type',
                'user', 'host', 'action', 'status'
            ],
            field_patterns={
                'ip': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
                'port': r'\b[0-9]{1,5}\b',
                'protocol': r'\b(tcp|udp|icmp|http|https|ssh|ftp)\b',
                'action': r'\b(allow|deny|block|permit|drop)\b'
            },
            temporal_patterns=[
                'last hour', 'past 24 hours', 'recent attacks',
                'during incident', 'between timestamps'
            ],
            aggregation_preferences={
                'ip_analysis': 'terms',
                'time_series': 'date_histogram',
                'attack_counts': 'cardinality'
            },
            security_level='high'
        )
        
        # Network Monitoring Domain
        profiles['networking'] = DomainProfile(
            name='networking',
            description='Network traffic and performance monitoring',
            common_fields=[
                'bytes', 'packets', 'duration', 'flow_id', 'bandwidth',
                'latency', 'jitter', 'packet_loss', 'throughput',
                'interface', 'vlan', 'qos_class'
            ],
            field_patterns={
                'bytes': r'\b[0-9]+\s*(bytes?|b|kb|mb|gb)\b',
                'bandwidth': r'\b[0-9]+\s*(bps|kbps|mbps|gbps)\b',
                'duration': r'\b[0-9]+\s*(ms|sec|min|hour)s?\b',
                'interface': r'\beth[0-9]+|wlan[0-9]+|lo[0-9]*\b'
            },
            temporal_patterns=[
                'peak hours', 'business hours', 'network congestion',
                'traffic patterns', 'performance windows'
            ],
            aggregation_preferences={
                'traffic_analysis': 'sum',
                'performance_metrics': 'avg',
                'top_talkers': 'terms'
            },
            security_level='medium'
        )
        
        # System Monitoring Domain
        profiles['system'] = DomainProfile(
            name='system',
            description='System performance and resource monitoring',
            common_fields=[
                'cpu_usage', 'memory_usage', 'disk_usage', 'process_name',
                'pid', 'user', 'command', 'path', 'file_size',
                'inode', 'permissions', 'load_average'
            ],
            field_patterns={
                'cpu': r'\b[0-9]+\.?[0-9]*\s*%?\b',
                'memory': r'\b[0-9]+\s*(kb|mb|gb|tb)\b',
                'process': r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',
                'path': r'/[a-zA-Z0-9_/.-]*'
            },
            temporal_patterns=[
                'system startup', 'high load periods', 'resource peaks',
                'maintenance windows', 'performance degradation'
            ],
            aggregation_preferences={
                'resource_usage': 'avg',
                'process_counts': 'cardinality',
                'system_health': 'percentiles'
            },
            security_level='low'
        )
        
        return profiles
    
    def detect_domain(self, 
                     schema: Dict[str, Any], 
                     sample_queries: List[str] = None) -> Tuple[str, float]:
        """
        Automatically detect the most likely domain based on schema and queries.
        
        Returns:
            (domain_name, confidence_score)
        """
        domain_scores = {}
        
        for domain_name, profile in self.domain_profiles.items():
            score = self._calculate_domain_score(profile, schema, sample_queries or [])
            domain_scores[domain_name] = score
        
        # Find best match
        best_domain = max(domain_scores, key=domain_scores.get)
        confidence = domain_scores[best_domain]
        
        logger.info(f"Domain detection: {best_domain} (confidence: {confidence:.3f})")
        return best_domain, confidence
    
    def _calculate_domain_score(self, 
                               profile: DomainProfile, 
                               schema: Dict[str, Any], 
                               sample_queries: List[str]) -> float:
        """Calculate how well a domain profile matches the given data."""
        score = 0.0
        total_checks = 0
        
        # Schema field matching
        if 'properties' in schema:
            schema_fields = set(schema['properties'].keys())
            profile_fields = set(profile.common_fields)
            
            field_overlap = len(schema_fields.intersection(profile_fields))
            total_fields = len(schema_fields.union(profile_fields))
            
            if total_fields > 0:
                field_score = field_overlap / total_fields
                score += field_score * 0.4  # 40% weight for field matching
                total_checks += 0.4
        
        # Query pattern matching
        if sample_queries:
            pattern_matches = 0
            total_patterns = len(profile.temporal_patterns)
            
            for query in sample_queries:
                query_lower = query.lower()
                for pattern in profile.temporal_patterns:
                    if pattern.lower() in query_lower:
                        pattern_matches += 1
                        break
            
            if total_patterns > 0:
                pattern_score = min(1.0, pattern_matches / len(sample_queries))
                score += pattern_score * 0.3  # 30% weight for pattern matching
                total_checks += 0.3
        
        # Field pattern validation
        if 'properties' in schema:
            pattern_matches = 0
            total_field_checks = 0
            
            for field_name, field_def in schema['properties'].items():
                for pattern_name, pattern_regex in profile.field_patterns.items():
                    if pattern_name in field_name.lower():
                        total_field_checks += 1
                        # In a real implementation, would validate against sample data
                        pattern_matches += 0.7  # Assume reasonable match
                        break
            
            if total_field_checks > 0:
                pattern_score = pattern_matches / total_field_checks
                score += pattern_score * 0.3  # 30% weight for field patterns
                total_checks += 0.3
        
        return score / total_checks if total_checks > 0 else 0.0
    
    def adapt_to_domain(self, 
                       domain_name: str, 
                       schema: Dict[str, Any],
                       custom_mappings: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Adapt generation strategy to a specific domain.
        
        Returns domain-specific adaptation configuration.
        """
        if domain_name not in self.domain_profiles:
            logger.warning(f"Unknown domain: {domain_name}. Using generic adaptation.")
            domain_name = 'system'  # Fallback to least restrictive
        
        profile = self.domain_profiles[domain_name]
        
        # Create adaptation configuration
        adaptation_config = {
            'domain': domain_name,
            'profile': profile,
            'field_mappings': self._create_field_mappings(profile, schema, custom_mappings),
            'generation_hints': self._create_generation_hints(profile),
            'validation_rules': self._create_validation_rules(profile),
            'security_constraints': self._create_security_constraints(profile)
        }
        
        # Store adaptation for learning
        self.adaptation_history[domain_name] = adaptation_config
        
        return adaptation_config
    
    def _create_field_mappings(self, 
                              profile: DomainProfile, 
                              schema: Dict[str, Any],
                              custom_mappings: Dict[str, str] = None) -> Dict[str, str]:
        """Create field mappings between common names and schema fields."""
        mappings = {}
        
        if 'properties' in schema:
            schema_fields = list(schema['properties'].keys())
            
            # Map profile fields to actual schema fields
            for common_field in profile.common_fields:
                best_match = self._find_best_field_match(common_field, schema_fields)
                if best_match:
                    mappings[common_field] = best_match
        
        # Apply custom mappings if provided
        if custom_mappings:
            mappings.update(custom_mappings)
            
        return mappings
    
    def _find_best_field_match(self, target_field: str, schema_fields: List[str]) -> Optional[str]:
        """Find the best matching field in schema for a target field."""
        target_lower = target_field.lower()
        
        # Exact match
        for field in schema_fields:
            if field.lower() == target_lower:
                return field
        
        # Partial match
        for field in schema_fields:
            field_lower = field.lower()
            if target_lower in field_lower or field_lower in target_lower:
                return field
        
        # Pattern-based matching
        for field in schema_fields:
            if self._fields_semantically_similar(target_field, field):
                return field
                
        return None
    
    def _fields_semantically_similar(self, field1: str, field2: str) -> bool:
        """Check if two field names are semantically similar."""
        # Define semantic mappings
        semantic_groups = [
            ['ip', 'address', 'addr'],
            ['port', 'portnum', 'port_number'],
            ['user', 'username', 'userid', 'uid'],
            ['time', 'timestamp', 'datetime', 'date'],
            ['size', 'length', 'bytes', 'count'],
            ['type', 'kind', 'category', 'class']
        ]
        
        field1_lower = field1.lower()
        field2_lower = field2.lower()
        
        for group in semantic_groups:
            if any(term in field1_lower for term in group) and \
               any(term in field2_lower for term in group):
                return True
                
        return False
    
    def _create_generation_hints(self, profile: DomainProfile) -> Dict[str, Any]:
        """Create domain-specific generation hints."""
        return {
            'preferred_aggregations': profile.aggregation_preferences,
            'temporal_focus': profile.temporal_patterns,
            'field_priorities': profile.common_fields[:5],  # Top 5 most important
            'complexity_preference': 'high' if profile.security_level == 'high' else 'medium'
        }
    
    def _create_validation_rules(self, profile: DomainProfile) -> List[Dict[str, Any]]:
        """Create domain-specific validation rules."""
        rules = []
        
        # Time window restrictions based on domain
        if profile.security_level == 'high':
            rules.append({
                'type': 'time_window',
                'max_range': '7d',
                'reason': 'Security queries should focus on recent events'
            })
        elif profile.security_level == 'medium':
            rules.append({
                'type': 'time_window',
                'max_range': '30d',
                'reason': 'Network queries can look further back for patterns'
            })
        
        # Field validation rules
        for field_name, pattern in profile.field_patterns.items():
            rules.append({
                'type': 'field_pattern',
                'field': field_name,
                'pattern': pattern,
                'reason': f'Validate {field_name} format for {profile.name} domain'
            })
        
        return rules
    
    def _create_security_constraints(self, profile: DomainProfile) -> Dict[str, Any]:
        """Create domain-specific security constraints."""
        constraints = {
            'allow_aggregations': profile.security_level != 'high',
            'max_result_size': 1000 if profile.security_level == 'high' else 10000,
            'required_time_bounds': profile.security_level == 'high',
            'allowed_fields': profile.common_fields if profile.security_level == 'high' else None
        }
        
        return constraints

class SchemaAdapter:
    """
    Handles adaptation to new Elasticsearch schemas.
    
    Learns schema patterns and creates adaptation strategies
    for rapid deployment to new indices.
    """
    
    def __init__(self):
        self.learned_schemas = {}
        self.schema_patterns = {}
    
    def analyze_schema(self, schema: Dict[str, Any], schema_name: str = None) -> Dict[str, Any]:
        """
        Analyze a schema and extract adaptation patterns.
        
        Returns schema analysis with adaptation recommendations.
        """
        analysis = {
            'schema_name': schema_name or f"schema_{len(self.learned_schemas)}",
            'field_analysis': self._analyze_fields(schema),
            'complexity_metrics': self._calculate_schema_complexity(schema),
            'adaptation_strategy': self._recommend_adaptation_strategy(schema),
            'compatibility_score': self._calculate_compatibility_score(schema)
        }
        
        # Store for future learning
        if schema_name:
            self.learned_schemas[schema_name] = analysis
            
        return analysis
    
    def _analyze_fields(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze field structure and types."""
        field_analysis = {
            'total_fields': 0,
            'field_types': {},
            'nested_fields': [],
            'temporal_fields': [],
            'text_fields': [],
            'keyword_fields': [],
            'numeric_fields': []
        }
        
        if 'properties' in schema:
            field_analysis['total_fields'] = len(schema['properties'])
            
            for field_name, field_def in schema['properties'].items():
                if isinstance(field_def, dict):
                    field_type = field_def.get('type', 'unknown')
                    field_analysis['field_types'][field_name] = field_type
                    
                    # Categorize fields
                    if field_type == 'nested':
                        field_analysis['nested_fields'].append(field_name)
                    elif field_type == 'date' or 'timestamp' in field_name.lower():
                        field_analysis['temporal_fields'].append(field_name)
                    elif field_type == 'text':
                        field_analysis['text_fields'].append(field_name)
                    elif field_type == 'keyword':
                        field_analysis['keyword_fields'].append(field_name)
                    elif field_type in ['integer', 'long', 'float', 'double']:
                        field_analysis['numeric_fields'].append(field_name)
        
        return field_analysis
    
    def _calculate_schema_complexity(self, schema: Dict[str, Any]) -> Dict[str, float]:
        """Calculate schema complexity metrics."""
        complexity = {
            'field_count_score': 0.0,
            'nesting_score': 0.0,
            'type_diversity_score': 0.0,
            'overall_complexity': 0.0
        }
        
        if 'properties' in schema:
            num_fields = len(schema['properties'])
            
            # Field count complexity (normalized)
            complexity['field_count_score'] = min(1.0, num_fields / 50.0)
            
            # Analyze nesting and type diversity
            type_counts = {}
            max_nesting = 0
            
            def analyze_nested(obj, depth=0):
                nonlocal max_nesting, type_counts
                max_nesting = max(max_nesting, depth)
                
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == 'type' and isinstance(value, str):
                            type_counts[value] = type_counts.get(value, 0) + 1
                        elif isinstance(value, dict):
                            analyze_nested(value, depth + 1)
            
            analyze_nested(schema)
            
            complexity['nesting_score'] = min(1.0, max_nesting / 5.0)
            complexity['type_diversity_score'] = min(1.0, len(type_counts) / 10.0)
            
            # Overall complexity (weighted average)
            complexity['overall_complexity'] = (
                complexity['field_count_score'] * 0.4 +
                complexity['nesting_score'] * 0.3 +
                complexity['type_diversity_score'] * 0.3
            )
        
        return complexity
    
    def _recommend_adaptation_strategy(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend adaptation strategy based on schema analysis."""
        field_analysis = self._analyze_fields(schema)
        complexity = self._calculate_schema_complexity(schema)
        
        strategy = {
            'approach': 'progressive',  # progressive, aggressive, conservative
            'focus_fields': [],
            'generation_complexity': 'medium',
            'validation_strictness': 'medium',
            'learning_priority': 'balanced'
        }
        
        # Determine approach based on complexity
        if complexity['overall_complexity'] > 0.7:
            strategy['approach'] = 'conservative'
            strategy['generation_complexity'] = 'low'
            strategy['validation_strictness'] = 'high'
        elif complexity['overall_complexity'] < 0.3:
            strategy['approach'] = 'aggressive'
            strategy['generation_complexity'] = 'high'
            strategy['validation_strictness'] = 'low'
        
        # Identify focus fields
        focus_fields = []
        focus_fields.extend(field_analysis['temporal_fields'][:2])  # Top 2 temporal
        focus_fields.extend(field_analysis['keyword_fields'][:3])   # Top 3 keyword
        focus_fields.extend(field_analysis['numeric_fields'][:2])   # Top 2 numeric
        
        strategy['focus_fields'] = focus_fields[:5]  # Limit to 5 most important
        
        return strategy
    
    def _calculate_compatibility_score(self, schema: Dict[str, Any]) -> float:
        """Calculate compatibility with existing learned schemas."""
        if not self.learned_schemas:
            return 1.0  # Perfect compatibility if no existing schemas
        
        compatibility_scores = []
        
        for learned_name, learned_analysis in self.learned_schemas.items():
            score = self._schema_similarity(schema, learned_analysis)
            compatibility_scores.append(score)
        
        return max(compatibility_scores) if compatibility_scores else 1.0
    
    def _schema_similarity(self, new_schema: Dict[str, Any], learned_analysis: Dict[str, Any]) -> float:
        """Calculate similarity between new schema and learned schema."""
        similarity = 0.0
        
        # Compare field types if both have field analysis
        if 'field_analysis' in learned_analysis:
            new_analysis = self._analyze_fields(new_schema)
            learned_field_analysis = learned_analysis['field_analysis']
            
            # Field type overlap
            new_types = set(new_analysis['field_types'].values())
            learned_types = set(learned_field_analysis['field_types'].values())
            
            if new_types or learned_types:
                type_overlap = len(new_types.intersection(learned_types))
                type_union = len(new_types.union(learned_types))
                similarity += (type_overlap / type_union) * 0.5
            
            # Field count similarity
            new_count = new_analysis['total_fields']
            learned_count = learned_field_analysis['total_fields']
            
            if max(new_count, learned_count) > 0:
                count_similarity = min(new_count, learned_count) / max(new_count, learned_count)
                similarity += count_similarity * 0.3
            
            # Structure similarity (temporal, keyword, numeric fields)
            structure_categories = ['temporal_fields', 'keyword_fields', 'numeric_fields']
            structure_similarity = 0.0
            
            for category in structure_categories:
                new_fields = set(new_analysis.get(category, []))
                learned_fields = set(learned_field_analysis.get(category, []))
                
                if new_fields or learned_fields:
                    overlap = len(new_fields.intersection(learned_fields))
                    union = len(new_fields.union(learned_fields))
                    structure_similarity += overlap / union if union > 0 else 0
            
            similarity += (structure_similarity / len(structure_categories)) * 0.2
        
        return min(1.0, similarity)
    
    def create_adaptation_template(self, schema: Dict[str, Any], domain: str = None) -> Dict[str, Any]:
        """
        Create an adaptation template for rapid deployment.
        
        Returns a template that can be used to quickly adapt
        to similar schemas in the future.
        """
        analysis = self.analyze_schema(schema)
        
        template = {
            'schema_fingerprint': self._create_schema_fingerprint(schema),
            'adaptation_config': {
                'field_mappings': self._extract_common_mappings(analysis),
                'generation_patterns': self._extract_generation_patterns(analysis),
                'validation_rules': self._extract_validation_patterns(analysis),
                'performance_hints': self._extract_performance_hints(analysis)
            },
            'domain_context': domain,
            'learning_metadata': {
                'creation_time': None,  # Would be set to current time
                'success_rate': 1.0,    # Initial optimistic score
                'adaptation_count': 0   # Number of times used
            }
        }
        
        return template
    
    def _create_schema_fingerprint(self, schema: Dict[str, Any]) -> str:
        """Create a unique fingerprint for schema structure."""
        # Create a simplified representation of the schema structure
        fingerprint_data = {
            'field_count': len(schema.get('properties', {})),
            'field_types': sorted(set(
                field_def.get('type', 'unknown')
                for field_def in schema.get('properties', {}).values()
                if isinstance(field_def, dict)
            ))
        }
        
        return str(hash(json.dumps(fingerprint_data, sort_keys=True)))
    
    def _extract_common_mappings(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Extract common field mappings from analysis."""
        mappings = {}
        field_analysis = analysis.get('field_analysis', {})
        
        # Map temporal fields
        for field in field_analysis.get('temporal_fields', []):
            mappings['timestamp'] = field
            break  # Use first temporal field as primary
        
        # Map key identifier fields
        for field in field_analysis.get('keyword_fields', []):
            if any(term in field.lower() for term in ['id', 'user', 'host', 'ip']):
                mappings[field.lower()] = field
        
        return mappings
    
    def _extract_generation_patterns(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract patterns for query generation."""
        patterns = []
        field_analysis = analysis.get('field_analysis', {})
        
        # Add patterns based on field types
        if field_analysis.get('temporal_fields'):
            patterns.append('time_range_queries')
        
        if field_analysis.get('keyword_fields'):
            patterns.append('term_matching')
        
        if field_analysis.get('numeric_fields'):
            patterns.append('range_queries')
        
        if field_analysis.get('text_fields'):
            patterns.append('full_text_search')
        
        return patterns
    
    def _extract_validation_patterns(self, analysis: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract validation patterns from analysis."""
        patterns = []
        complexity = analysis.get('complexity_metrics', {})
        
        # Add complexity-based validation
        if complexity.get('overall_complexity', 0) > 0.7:
            patterns.append({
                'type': 'complexity_limit',
                'rule': 'limit_nested_queries',
                'reason': 'High schema complexity requires simpler queries'
            })
        
        return patterns
    
    def _extract_performance_hints(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance optimization hints."""
        hints = {}
        field_analysis = analysis.get('field_analysis', {})
        
        # Suggest index hints based on field types
        if field_analysis.get('temporal_fields'):
            hints['temporal_optimization'] = True
            hints['suggested_sort_field'] = field_analysis['temporal_fields'][0]
        
        if len(field_analysis.get('keyword_fields', [])) > 10:
            hints['filter_optimization'] = True
            hints['primary_filter_fields'] = field_analysis['keyword_fields'][:5]
        
        return hints

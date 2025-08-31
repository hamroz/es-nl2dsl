#!/usr/bin/env python3
"""
Field Matcher: Intelligent natural language to Elasticsearch field mapping system

This module provides sophisticated field matching capabilities for translating natural
language terms into appropriate Elasticsearch field names. It uses advanced text
similarity algorithms, semantic analysis, and domain knowledge to accurately map
user expressions to structured field names within cybersecurity datasets.

Key capabilities:
- Intelligent field name mapping with fuzzy matching and similarity scoring
- Semantic field analysis with context-aware disambiguation
- Multi-term mapping support for complex field expressions
- Field type awareness with automatic .keyword and .text handling
- Custom field alias management with user-defined mappings
- Performance optimization with caching and preprocessing
- Integration with index profiling for dynamic field discovery

The matcher bridges the gap between natural language expressions and technical
field names, enabling intuitive query construction while maintaining precision
and accuracy in field selection.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Set
from difflib import get_close_matches, SequenceMatcher
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

logger = logging.getLogger(__name__)

class FieldMatcher:
    """Smart field matcher with fuzzy logic and domain knowledge"""
    
    def __init__(self):
        # Common field aliases and patterns
        self.field_aliases = {
            # Log/Event type fields
            'log type': ['log_type', 'logtype', 'type', 'event_type', 'event.type', 'category', 'log.type'],
            'event type': ['event_type', 'event.type', 'log_type', 'type', 'category'],
            'message type': ['message_type', 'msg_type', 'type'],
            'record type': ['record_type', 'type', 'log_type'],
            'entry type': ['entry_type', 'type', 'log_type'],
            
            # Action fields
            'action': ['action', 'operation', 'op', 'verb', 'activity'],
            'firewall action': ['firewall_action', 'fw_action', 'action', 'operation'],
            'security action': ['security_action', 'sec_action', 'action'],
            
            # IP Address fields
            'ip': ['ip', 'ip_address', 'address'],
            'source ip': ['source_ip', 'src_ip', 'srcip', 'src.ip', 'source.ip'],
            'destination ip': ['destination_ip', 'dest_ip', 'dst_ip', 'dstip', 'dest.ip', 'destination.ip'],
            'target ip': ['target_ip', 'dst_ip', 'destination_ip'],
            
            # Port fields
            'port': ['port'],
            'source port': ['source_port', 'src_port', 'srcport', 'src.port', 'source.port'],
            'destination port': ['destination_port', 'dest_port', 'dst_port', 'dstport', 'dest.port', 'destination.port'],
            'target port': ['target_port', 'dst_port', 'destination_port'],
            
            # User fields
            'user': ['user', 'username', 'user_name', 'userid', 'user_id', 'account'],
            'username': ['username', 'user_name', 'user', 'account', 'login'],
            
            # Host fields
            'host': ['host', 'hostname', 'host_name', 'server', 'machine'],
            'hostname': ['hostname', 'host_name', 'host', 'server'],
            
            # Status fields
            'status': ['status', 'state', 'result', 'outcome'],
            'result': ['result', 'status', 'outcome', 'response'],
            
            # Protocol fields
            'protocol': ['protocol', 'proto', 'network_protocol'],
            
            # Time fields
            'time': ['time', 'timestamp', '@timestamp', 'datetime', 'date'],
            'timestamp': ['timestamp', '@timestamp', 'time', 'datetime'],
            'date': ['date', '@timestamp', 'timestamp', 'datetime'],
            
            # Bytes/Size fields
            'bytes': ['bytes', 'size', 'length'],
            'size': ['size', 'bytes', 'length'],
            'data size': ['data_size', 'size', 'bytes'],
            'bytes transferred': ['bytes_transferred', 'bytes', 'size'],
            'packet size': ['packet_size', 'size', 'bytes'],
            
            # Security fields
            'threat': ['threat', 'threat_type', 'threat_label', 'malware'],
            'alert': ['alert', 'alert_type', 'threat', 'warning'],
            'severity': ['severity', 'level', 'priority', 'criticality'],
            'confidence': ['confidence', 'score', 'rating'],
            
            # Network fields  
            'mac': ['mac', 'mac_address', 'hardware_address'],
            'vlan': ['vlan', 'vlan_id'],
            'interface': ['interface', 'intf', 'if'],
            
            # Application fields
            'application': ['application', 'app', 'service', 'program'],
            'process': ['process', 'proc', 'process_name'],
            
            # File fields
            'file': ['file', 'filename', 'file_name', 'path'],
            'path': ['path', 'file_path', 'filepath', 'file'],
            
            # HTTP fields
            'url': ['url', 'uri', 'request_url', 'path'],
            'method': ['method', 'http_method', 'verb'],
            'user agent': ['user_agent', 'useragent', 'agent'],
            'referer': ['referer', 'referrer'],
        }
        
        # Value mappings for common terms
        self.value_mappings = {
            'firewall': ['firewall', 'fw', 'iptables', 'pf', 'ufw'],
            'web': ['web', 'http', 'https', 'www'],
            'dns': ['dns', 'domain', 'name_resolution'],
            'ssh': ['ssh', 'secure_shell'],
            'ftp': ['ftp', 'file_transfer'],
            'email': ['email', 'smtp', 'mail', 'pop3', 'imap'],
            'database': ['database', 'db', 'sql', 'mysql', 'postgres'],
            'malicious': ['malicious', 'malware', 'bad', 'evil', 'threat'],
            'benign': ['benign', 'good', 'clean', 'safe', 'normal'],
            'blocked': ['blocked', 'denied', 'rejected', 'dropped'],
            'allowed': ['allowed', 'permitted', 'accepted', 'passed'],
        }
        
        # Confidence thresholds
        self.exact_match_threshold = 1.0
        self.fuzzy_match_threshold = 0.7
        self.partial_match_threshold = 0.5
    
    def smart_match(self, user_term: str, available_fields: List[str], 
                   confidence_threshold: float = 0.6) -> Optional[Dict[str, any]]:
        """
        Find the best matching field for a user term
        
        Args:
            user_term: Natural language term (e.g., "log type")
            available_fields: List of actual field names in the index
            confidence_threshold: Minimum confidence to return a match
            
        Returns:
            Dictionary with match info or None if no good match found
        """
        user_term_lower = user_term.lower().strip()
        
        # 1. Exact match
        if user_term in available_fields:
            return {
                'field': user_term,
                'confidence': 1.0,
                'method': 'exact_match',
                'original_term': user_term
            }
        
        # 2. Check aliases for exact match (prefer .keyword fields)
        if user_term_lower in self.field_aliases:
            for candidate in self.field_aliases[user_term_lower]:
                # Check for .keyword version first (preferred for exact matching)
                keyword_field = f"{candidate}.keyword"
                if keyword_field in available_fields:
                    return {
                        'field': keyword_field,
                        'confidence': 0.98,  # Higher confidence for keyword fields
                        'method': 'alias_keyword',
                        'original_term': user_term
                    }
                
                # Fall back to non-keyword field
                if candidate in available_fields:
                    return {
                        'field': candidate,
                        'confidence': 0.95,
                        'method': 'alias_exact',
                        'original_term': user_term
                    }
        
        # 3. Fuzzy matching with available fields
        # Split user term into tokens for better matching
        user_tokens = set(re.findall(r'\w+', user_term_lower))
        
        best_match = None
        best_confidence = 0
        
        for field in available_fields:
            field_lower = field.lower()
            
            # Direct fuzzy match
            similarity = SequenceMatcher(None, user_term_lower, field_lower).ratio()
            
            # Token-based matching (better for multi-word terms)
            field_tokens = set(re.findall(r'\w+', field_lower))
            if user_tokens and field_tokens:
                token_overlap = len(user_tokens & field_tokens) / len(user_tokens | field_tokens)
                # Combine similarity scores
                combined_score = (similarity * 0.4) + (token_overlap * 0.6)
            else:
                combined_score = similarity
            
            # Boost score if field contains key tokens
            for token in user_tokens:
                if token in field_lower:
                    combined_score += 0.1
            
            # Special boost for common patterns
            if self._is_semantic_match(user_term_lower, field_lower):
                combined_score += 0.2
            
            # Prefer .keyword fields for exact matching
            if field.endswith('.keyword') and combined_score > 0.5:
                combined_score += 0.1
            
            if combined_score > best_confidence:
                best_confidence = combined_score
                best_match = field
        
        # 4. Partial word matching (for compound terms)
        if best_confidence < confidence_threshold:
            partial_matches = self._find_partial_matches(user_term_lower, available_fields)
            for field, score in partial_matches:
                if score > best_confidence:
                    best_confidence = score
                    best_match = field
        
        if best_match and best_confidence >= confidence_threshold:
            return {
                'field': best_match,
                'confidence': min(best_confidence, 1.0),
                'method': 'fuzzy_match',
                'original_term': user_term
            }
        
        return None
    
    def _is_semantic_match(self, user_term: str, field_name: str) -> bool:
        """Check if terms are semantically related"""
        semantic_groups = [
            {'ip', 'address', 'addr'},
            {'port', 'service'},
            {'time', 'timestamp', 'date', 'datetime'},
            {'type', 'category', 'class', 'kind'},
            {'action', 'operation', 'verb', 'activity'},
            {'user', 'username', 'account'},
            {'host', 'hostname', 'server', 'machine'},
            {'bytes', 'size', 'length'},
            {'status', 'state', 'result'},
            {'protocol', 'proto'},
            {'log', 'event', 'record', 'entry'},
        ]
        
        user_words = set(re.findall(r'\w+', user_term))
        field_words = set(re.findall(r'\w+', field_name))
        
        for group in semantic_groups:
            if (user_words & group) and (field_words & group):
                return True
        
        return False
    
    def _find_partial_matches(self, user_term: str, available_fields: List[str]) -> List[Tuple[str, float]]:
        """Find fields that partially match the user term"""
        matches = []
        user_words = re.findall(r'\w+', user_term)
        
        for field in available_fields:
            field_words = re.findall(r'\w+', field.lower())
            
            # Count matching words
            matching_words = 0
            for user_word in user_words:
                for field_word in field_words:
                    if user_word in field_word or field_word in user_word:
                        matching_words += 1
                        break
            
            if matching_words > 0:
                score = matching_words / len(user_words)
                if score >= 0.3:  # At least 30% word overlap
                    matches.append((field, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)
    
    def extract_field_value_pairs(self, prompt: str, available_fields: List[str]) -> List[Dict[str, any]]:
        """
        Extract all field-value pairs from a natural language prompt
        
        Returns:
            List of dictionaries with field matches and values
        """
        constraints = []
        
        # Enhanced patterns to match field-value pairs (ordered by specificity)
        patterns = [
            # Special IP patterns (most specific first) with context
            r'\b(?:source\s+ip|src\s+ip|from\s+ip|source|originating\s+from)\s+(?:is\s+|address\s+)?([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\b',
            r'\b(?:dest\s+ip|dst\s+ip|destination\s+ip|to\s+ip|destination|targeting)\s+(?:is\s+|address\s+)?([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\b',
            r'\b(?:ip|address)\s+(?:is\s+)?([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\b',
            r'\b([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\b',  # Standalone IP
            
            # Port patterns with ranges and lists
            r'\bports?\s+(?:are\s+|in\s+|include\s+)?(\d+(?:\s*,\s*\d+)*|\d+-\d+)\b',
            r'\b(?:source\s+port|src\s+port|from\s+port)\s+(?:is\s+)?(\d+)\b',
            r'\b(?:dest\s+port|dst\s+port|destination\s+port|to\s+port|target\s+port)\s+(?:is\s+)?(\d+)\b',
            r'\bport\s+(?:is\s+)?(\d+)\b',
            
            # Protocol patterns with variations
            r'\b(?:protocol|proto)\s+(?:is\s+|equals\s+)?(\w+)\b',
            r'\b(tcp|udp|icmp|http|https|ssh|ftp|dns)\s+(?:traffic|packets|connections)\b',
            
            # Enhanced field-value patterns with more natural language
            r'\b(log\s+type|event\s+type|message\s+type|record\s+type|entry\s+type)\s+(?:is\s+|equals\s+|of\s+|contains\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(action|activity|operation|verb)\s+(?:is\s+|was\s+|equals\s+|performed\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(status|state|result|outcome|response)\s+(?:is\s+|was\s+|equals\s+|shows\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(user|username|account|login)\s+(?:is\s+|was\s+|contains\s+|named\s+|equals\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(host|hostname|server|machine|computer)\s+(?:is\s+|was\s+|named\s+|equals\s+)?(?:"([^"]+)"|(\w+))\b',
            
            # Threat/Security specific patterns
            r'\b(threat|alert|warning|risk)\s+(?:is\s+|type\s+|level\s+|classified\s+as\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(malware|virus|trojan|attack)\s+(?:type\s+|named\s+|called\s+|is\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(severity|priority|confidence|score)\s+(?:is\s+|level\s+|of\s+|equals\s+)?(\d+(?:\.\d+)?|\w+)\b',
            
            # Firewall/Network specific patterns  
            r'\b(firewall|fw)\s+(?:action\s+|rule\s+|policy\s+)?(?:is\s+|shows\s+|equals\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(?:traffic|connection|session)\s+(?:is\s+|was\s+|marked\s+as\s+)?(?:allowed|permitted|denied|blocked|dropped)\b',
            
            # Byte/Size patterns with operators
            r'\b(bytes|size|length|data)\s+(?:transferred\s+|sent\s+|received\s+)?(?:is\s+|equals\s+|greater\s+than\s+|less\s+than\s+|over\s+|under\s+|above\s+|below\s+)?([0-9]+(?:\.[0-9]+)?[kmgtKMGT]?[bB]?)\b',
            
            # Time/Date patterns
            r'\b(?:on\s+|during\s+|at\s+|date\s+|time\s+)(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}:\d{2})?|\d{2}/\d{2}/\d{4})\b',
            r'\b(today|yesterday|last\s+week|this\s+week|last\s+month|this\s+month)\b',
            
            # Comparison operators with fields
            r'\b(\w+(?:\s+\w+){0,2})\s+(greater\s+than|more\s+than|over|above|less\s+than|below|under)\s+([0-9]+(?:\.[0-9]+)?)\b',
            r'\b(\w+(?:\s+\w+){0,2})\s+(equals?|is|matches?)\s+(?:"([^"]+)"|(\w+))\b',
            
            # Range patterns
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:between|from)\s+([0-9]+(?:\.[0-9]+)?)\s+(?:and|to)\s+([0-9]+(?:\.[0-9]+)?)\b',
            
            # "with/having field value" patterns
            r'\b(?:with|having)\s+(\w+(?:\s+\w+){0,2})\s+(?:of\s+|equals?\s+|is\s+)?(?:"([^"]+)"|(\w+))\b',
            
            # "where field = value" patterns with various operators
            r'\bwhere\s+(\w+(?:\s+\w+){0,2})\s*([=:<>!]+|equals?|is|contains?|matches?)\s*(?:"([^"]+)"|(\w+))\b',
            
            # SQL-like patterns
            r'\b(\w+(?:\s+\w+){0,2})\s*([=:<>!]+)\s*(?:"([^"]+)"|(\w+))\b',
            
            # List patterns (field in [value1, value2])
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:in|includes?|contains?|any\s+of)\s*\[\s*([^[\]]+)\s*\]\b',
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:in|includes?|contains?|any\s+of)\s*\(([^()]+)\)\b',
        ]
        
        processed_spans = set()  # Track processed text spans to avoid duplicates
        
        for pattern in patterns:
            matches = list(re.finditer(pattern, prompt, re.IGNORECASE))
            
            for match in matches:
                # Skip if this span overlaps with already processed text
                span = (match.start(), match.end())
                if any(self._spans_overlap(span, processed) for processed in processed_spans):
                    continue
                
                processed_spans.add(span)
                
                # Extract field hint and value from match groups
                field_hint = None
                value = None
                
                groups = [g for g in match.groups() if g is not None]
                
                if len(groups) == 1:
                    # Single group - could be IP, port, or standalone value
                    potential_value = groups[0].strip()
                    context = prompt[max(0, match.start()-30):match.end()+30].lower()
                    
                    if re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', potential_value):
                        # IP address - determine field from context or pattern
                        if any(term in pattern for term in ['source', 'src', 'from', 'originating']):
                            field_hint = 'source ip'
                        elif any(term in pattern for term in ['dest', 'dst', 'destination', 'to', 'targeting']):
                            field_hint = 'destination ip'
                        elif 'source' in context or 'src' in context or 'from' in context:
                            field_hint = 'source ip'
                        elif 'dest' in context or 'dst' in context or 'to' in context:
                            field_hint = 'destination ip'  
                        else:
                            field_hint = 'ip'
                        value = potential_value
                        
                    elif potential_value.isdigit():
                        # Port number - determine field from context or pattern
                        if any(term in pattern for term in ['source_port', 'src_port', 'from_port']):
                            field_hint = 'source port'
                        elif any(term in pattern for term in ['dest_port', 'dst_port', 'destination_port', 'target_port']):
                            field_hint = 'destination port'
                        else:
                            field_hint = 'port'
                        value = potential_value
                        
                    elif potential_value.lower() in ['tcp', 'udp', 'icmp', 'http', 'https', 'ssh', 'ftp', 'dns']:
                        # Protocol
                        field_hint = 'protocol'
                        value = potential_value.upper()
                        
                    elif re.match(r'^\d{4}-\d{2}-\d{2}', potential_value) or re.match(r'^\d{2}/\d{2}/\d{4}', potential_value):
                        # Date
                        field_hint = 'timestamp'
                        value = potential_value
                        
                    elif potential_value.lower() in ['today', 'yesterday', 'last week', 'this week', 'last month', 'this month']:
                        # Relative time
                        field_hint = 'timestamp'
                        value = potential_value
                        
                    else:
                        # Skip unknown single values
                        continue
                
                elif len(groups) >= 2:
                    # Field-value pairs
                    field_hint = groups[0].strip() if groups[0] else None
                    
                    # Handle patterns with multiple capture groups for values
                    # Find the first non-empty value group
                    for i in range(1, len(groups)):
                        if groups[i] and groups[i].strip():
                            value = groups[i].strip()
                            break
                    
                    # Special handling for firewall patterns
                    if not field_hint and 'firewall' in match.group(0).lower():
                        field_hint = 'action'
                        # Extract value from firewall context
                        firewall_match = re.search(r'(allowed|permitted|denied|blocked|dropped)', match.group(0), re.IGNORECASE)
                        if firewall_match:
                            value = firewall_match.group(1).lower()
                    
                    # Special handling for comparison operators
                    if len(groups) >= 3 and groups[1]:
                        operator = groups[1].strip().lower()
                        if operator in ['greater than', 'more than', 'over', 'above']:
                            # Convert to range query hint
                            value = f">{value}"
                        elif operator in ['less than', 'below', 'under']:
                            value = f"<{value}"
                        elif operator in ['between', 'from']:
                            # Handle range queries
                            if len(groups) >= 4 and groups[3]:
                                value = f"{value}-{groups[3]}"
                
                # Try to match field if we have both field hint and value
                if field_hint and value:
                    field_match = self.smart_match(field_hint, available_fields)
                    if field_match:
                        constraints.append({
                            'field_match': field_match,
                            'value': value,
                            'original_text': match.group(0),
                            'position': span,
                            'operator': 'term'  # Default, can be enhanced based on pattern
                        })
        
        # Remove duplicates based on field and value
        unique_constraints = []
        seen = set()
        for constraint in constraints:
            key = (constraint['field_match']['field'], constraint['value'])
            if key not in seen:
                seen.add(key)
                unique_constraints.append(constraint)
        
        return unique_constraints
    
    def _spans_overlap(self, span1: Tuple[int, int], span2: Tuple[int, int]) -> bool:
        """Check if two text spans overlap"""
        return not (span1[1] <= span2[0] or span2[1] <= span1[0])
    
    def suggest_field_corrections(self, available_fields: List[str]) -> Dict[str, str]:
        """
        Generate field corrections dictionary for the current index
        
        Returns:
            Dictionary mapping common terms to actual field names
        """
        corrections = {}
        
        # Generate corrections based on aliases and fuzzy matching
        for user_term, aliases in self.field_aliases.items():
            match = self.smart_match(user_term, available_fields)
            if match:
                corrections[user_term] = match['field']
                
                # Also add variations
                variations = [
                    user_term.replace(' ', '_'),
                    user_term.replace(' ', ''),
                    user_term.replace(' ', '.'),
                ]
                for variation in variations:
                    if variation != match['field']:
                        corrections[variation] = match['field']
        
        return corrections
    
    def get_field_suggestions(self, user_input: str, available_fields: List[str], 
                             max_suggestions: int = 5) -> List[Dict[str, any]]:
        """
        Get multiple field suggestions for ambiguous input
        
        Returns:
            List of potential matches sorted by confidence
        """
        suggestions = []
        
        # Get fuzzy matches with different thresholds
        for threshold in [0.8, 0.6, 0.4]:
            match = self.smart_match(user_input, available_fields, threshold)
            if match and not any(s['field'] == match['field'] for s in suggestions):
                suggestions.append(match)
                if len(suggestions) >= max_suggestions:
                    break
        
        # Add semantic matches
        user_words = set(re.findall(r'\w+', user_input.lower()))
        for field in available_fields:
            if field not in [s['field'] for s in suggestions]:
                field_words = set(re.findall(r'\w+', field.lower()))
                if user_words & field_words:  # Has common words
                    overlap = len(user_words & field_words)
                    suggestions.append({
                        'field': field,
                        'confidence': overlap / len(user_words | field_words),
                        'method': 'semantic',
                        'original_term': user_input
                    })
        
        # Sort by confidence and return top matches
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:max_suggestions]
    
    def analyze_boolean_logic(self, prompt: str) -> Dict[str, any]:
        """
        Analyze boolean logic patterns in the prompt (AND, OR, NOT)
        
        Returns:
            Dictionary with boolean logic information
        """
        prompt_lower = prompt.lower()
        
        # Detect boolean connectors
        has_and = bool(re.search(r'\b(?:and|with|plus|also|additionally)\b', prompt_lower))
        has_or = bool(re.search(r'\b(?:or|either|alternatively|any of)\b', prompt_lower))
        has_not = bool(re.search(r'\b(?:not|exclude|without|except|excluding|no)\b', prompt_lower))
        
        # Count constraints to infer logic
        constraints_count = len(re.findall(r'\b(?:where|with|and|or)\b', prompt_lower))
        
        # Determine primary logic
        if has_or and not has_and:
            primary_logic = 'OR'
        elif has_not:
            primary_logic = 'NOT'
        else:
            primary_logic = 'AND'  # Default
        
        return {
            'primary_logic': primary_logic,
            'has_and': has_and,
            'has_or': has_or,  
            'has_not': has_not,
            'constraint_count': constraints_count,
            'complexity': 'complex' if (has_or or has_not or constraints_count > 2) else 'simple'
        }
    
    def extract_negated_constraints(self, prompt: str, available_fields: List[str]) -> List[Dict[str, any]]:
        """
        Extract negated/excluded constraints from prompt
        
        Returns:
            List of constraints that should be negated in the query
        """
        negated_constraints = []
        
        # Negation patterns
        negation_patterns = [
            r'\b(?:not|exclude|without|except|excluding)\s+(\w+(?:\s+\w+){0,2})\s+(?:is\s+|equals?\s+)?(?:"([^"]+)"|(\w+))\b',
            r'\b(?:no|zero)\s+(\w+(?:\s+\w+){0,2})\b',
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:is\s+not|not\s+equal\s+to|!=)\s+(?:"([^"]+)"|(\w+))\b',
            r'\b(?:filter\s+out|remove|skip)\s+(\w+(?:\s+\w+){0,2})\s+(?:with\s+|equals?\s+)?(?:"([^"]+)"|(\w+))\b',
        ]
        
        for pattern in negation_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            
            for match in matches:
                groups = [g for g in match.groups() if g is not None]
                if len(groups) >= 1:
                    field_hint = groups[0].strip()
                    value = groups[1].strip() if len(groups) > 1 else None
                    
                    field_match = self.smart_match(field_hint, available_fields)
                    if field_match:
                        negated_constraints.append({
                            'field_match': field_match,
                            'value': value,
                            'original_text': match.group(0),
                            'operator': 'must_not'
                        })
        
        return negated_constraints
    
    def extract_range_constraints(self, prompt: str, available_fields: List[str]) -> List[Dict[str, any]]:
        """
        Extract range-based constraints (greater than, less than, between)
        
        Returns:
            List of range constraints
        """
        range_constraints = []
        
        # Range patterns
        range_patterns = [
            # "field greater than X"
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:greater\s+than|more\s+than|over|above|>)\s+([0-9]+(?:\.[0-9]+)?)\b',
            # "field less than X" 
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:less\s+than|below|under|<)\s+([0-9]+(?:\.[0-9]+)?)\b',
            # "field between X and Y"
            r'\b(\w+(?:\s+\w+){0,2})\s+(?:between|from)\s+([0-9]+(?:\.[0-9]+)?)\s+(?:and|to)\s+([0-9]+(?:\.[0-9]+)?)\b',
            # "X < field < Y" format
            r'\b([0-9]+(?:\.[0-9]+)?)\s*<\s*(\w+(?:\s+\w+){0,2})\s*<\s*([0-9]+(?:\.[0-9]+)?)\b',
        ]
        
        for pattern in range_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            
            for match in matches:
                groups = [g for g in match.groups() if g is not None]
                
                if 'greater than' in match.group(0).lower() or '>' in match.group(0):
                    field_hint = groups[0]
                    field_match = self.smart_match(field_hint, available_fields)
                    if field_match:
                        range_constraints.append({
                            'field_match': field_match,
                            'operator': 'range',
                            'range_type': 'gt',
                            'value': groups[1],
                            'original_text': match.group(0)
                        })
                        
                elif 'less than' in match.group(0).lower() or '<' in match.group(0):
                    field_hint = groups[0]
                    field_match = self.smart_match(field_hint, available_fields)
                    if field_match:
                        range_constraints.append({
                            'field_match': field_match,
                            'operator': 'range',
                            'range_type': 'lt',
                            'value': groups[1], 
                            'original_text': match.group(0)
                        })
                        
                elif 'between' in match.group(0).lower():
                    field_hint = groups[0]
                    field_match = self.smart_match(field_hint, available_fields)
                    if field_match:
                        range_constraints.append({
                            'field_match': field_match,
                            'operator': 'range',
                            'range_type': 'between',
                            'value_min': groups[1],
                            'value_max': groups[2],
                            'original_text': match.group(0)
                        })
        
        return range_constraints


# Singleton instance
_field_matcher_instance = None

def get_field_matcher() -> FieldMatcher:
    """Get or create singleton FieldMatcher instance"""
    global _field_matcher_instance
    if _field_matcher_instance is None:
        _field_matcher_instance = FieldMatcher()
    return _field_matcher_instance


# Convenience functions
def smart_match_field(user_term: str, available_fields: List[str]) -> Optional[str]:
    """Quick function to get best matching field name"""
    matcher = get_field_matcher()
    match = matcher.smart_match(user_term, available_fields)
    return match['field'] if match else None

def extract_constraints_from_prompt(prompt: str, available_fields: List[str]) -> List[Dict[str, any]]:
    """Quick function to extract field-value pairs from prompt"""
    matcher = get_field_matcher()
    return matcher.extract_field_value_pairs(prompt, available_fields)

def generate_field_corrections(available_fields: List[str]) -> Dict[str, str]:
    """Quick function to generate field corrections dictionary"""
    matcher = get_field_matcher()
    return matcher.suggest_field_corrections(available_fields)
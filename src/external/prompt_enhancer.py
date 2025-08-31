#!/usr/bin/env python3
"""
Prompt Enhancer: Advanced natural language processing for query intent extraction

This module provides sophisticated natural language processing capabilities for enhancing
user prompts and extracting structured query intent from conversational input. It performs
semantic analysis, constraint extraction, and prompt augmentation to improve DSL query
generation accuracy and reduce ambiguity in the ES-NL2DSL system.

Key capabilities:
- Semantic field mapping with extensive alias recognition
- Attack type classification with cybersecurity domain knowledge
- IP address and port number extraction with context awareness
- Numeric constraint parsing with operator recognition
- Temporal condition extraction (dates, times, weekdays)
- Structured constraint representation for query generation
- Prompt enhancement with explicit constraint specification
- Context-aware field disambiguation (source vs destination)

The enhancer bridges the gap between conversational language and structured queries,
enabling users to express complex cybersecurity analysis needs in natural language
while ensuring precise translation to Elasticsearch DSL queries.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import re
from typing import Dict, List, Tuple, Any

# Field mappings with aliases and patterns
FIELD_MAPPINGS = {
    'src_ip': ['source ip', 'source address', 'src ip', 'from ip', 'source_ip'],
    'dst_ip': ['destination ip', 'dest ip', 'dst ip', 'target ip', 'to ip', 'destination_ip'],
    'src_port': ['source port', 'src port', 'from port', 'source_port'],
    'dst_port': ['destination port', 'dest port', 'dst port', 'target port', 'to port', 'destination_port'],
    'protocol': ['protocol', 'proto'],
    'bytes_in': ['bytes in', 'incoming bytes', 'received bytes', 'bytes_in'],
    'bytes_out': ['bytes out', 'outgoing bytes', 'sent bytes', 'bytes_out'],
    'flow_packets_s': ['packet rate', 'packets per second', 'pps', 'flow_packets_s'],
    'flow_bytes_s': ['bandwidth', 'bytes per second', 'bps', 'data rate', 'flow_bytes_s'],
    'flow_duration': ['duration', 'flow duration', 'connection duration', 'flow_duration'],
    'syn_flag_count': ['syn flags', 'syn count', 'syn_flag_count'],
    'rst_flag_count': ['rst flags', 'reset flags', 'rst count', 'rst_flag_count'],
    'ack_flag_count': ['ack flags', 'ack count', 'ack_flag_count'],
    'total_packets': ['total packets', 'packet count', 'number of packets'],
    'day_of_week': ['day', 'weekday', 'day of week'],
    'hour_of_day': ['hour', 'time of day'],
}

# Attack type mappings
ATTACK_MAPPINGS = {
    'dos': ['ddos', 'dos', 'denial of service', 'distributed denial'],
    'scan': ['port scan', 'portscan', 'scanning', 'port scanning'],
    'bruteforce': ['brute force', 'bruteforce', 'password attack', 'ssh attack', 'ftp attack'],
    'web_attack': ['web attack', 'web application attack', 'sql injection', 'xss'],
    'infiltration': ['infiltration', 'infilteration'],
    'botnet': ['bot', 'botnet', 'zombie'],
}

# Comparison operators
OPERATORS = {
    'greater than': 'gt',
    'more than': 'gt',
    'over': 'gt',
    'above': 'gt',
    '>': 'gt',
    'less than': 'lt',
    'below': 'lt',
    'under': 'lt',
    '<': 'lt',
    'equals': 'term',
    'equal to': 'term',
    'is': 'term',
    '=': 'term',
    'between': 'range',
    'from': 'gte',
    'to': 'lte',
}

def extract_ip_addresses(prompt: str) -> List[Tuple[str, str]]:
    """Extract IP addresses from prompt"""
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    ips = re.findall(ip_pattern, prompt)
    
    results = []
    for ip in ips:
        # Determine if it's source or destination based on context
        ip_index = prompt.find(ip)
        context = prompt[max(0, ip_index-20):ip_index+20].lower()
        
        if any(term in context for term in ['source', 'src', 'from']):
            results.append(('src_ip', ip))
        elif any(term in context for term in ['destination', 'dest', 'dst', 'target', 'to']):
            results.append(('dst_ip', ip))
        else:
            # Default to dst_ip for attack targets
            results.append(('dst_ip', ip))
    
    return results

def extract_ports(prompt: str) -> List[Tuple[str, int]]:
    """Extract port numbers from prompt"""
    # Pattern for port numbers (1-65535)
    port_patterns = [
        r'port\s+is\s+(\d{1,5})',
        r'port\s+(\d{1,5})',
        r'ports?\s*[:=]\s*(\d{1,5})',
        r':(\d{1,5})\b',  # Colon notation like :443
    ]
    
    results = []
    prompt_lower = prompt.lower()
    seen_ports = set()
    
    for pattern in port_patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                # Determine if source or destination
                context = prompt_lower[max(0, match.start()-30):match.end()+10]
                
                if any(term in context for term in ['source', 'src', 'from']):
                    port_key = ('src_port', port)
                elif any(term in context for term in ['destination', 'dest', 'dst', 'target', 'to']):
                    port_key = ('dst_port', port)
                else:
                    # For attacks, usually we mean destination port
                    port_key = ('dst_port', port)
                
                # Avoid duplicates
                if port_key not in seen_ports:
                    results.append(port_key)
                    seen_ports.add(port_key)
    
    return results

def extract_numeric_conditions(prompt: str) -> List[Tuple[str, str, float]]:
    """Extract numeric conditions like 'packet rate > 100'"""
    prompt_lower = prompt.lower()
    results = []
    
    # Patterns for numeric conditions
    patterns = [
        # "field operator value" pattern
        r'([\w\s]+?)\s+(greater than|more than|over|above|less than|below|under|equals?|is)\s+(\d+(?:\.\d+)?)',
        # "field > value" pattern  
        r'([\w\s]+?)\s*([><=])\s*(\d+(?:\.\d+)?)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            field_text = match.group(1).strip()
            operator_text = match.group(2).strip()
            value = float(match.group(3))
            
            # Map field text to actual field name
            field = None
            for actual_field, aliases in FIELD_MAPPINGS.items():
                if any(alias in field_text for alias in aliases):
                    field = actual_field
                    break
            
            if field:
                # Map operator
                operator = OPERATORS.get(operator_text, 'term')
                results.append((field, operator, value))
    
    return results

def extract_time_conditions(prompt: str) -> Dict[str, Any]:
    """Extract time-related conditions"""
    prompt_lower = prompt.lower()
    conditions = {}
    
    # Day of week
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in days:
        if day in prompt_lower:
            conditions['day_of_week'] = day.capitalize()
    
    # Hour patterns
    hour_patterns = [
        r'at (\d{1,2})\s*(?:am|pm|:00)?',
        r'hour (\d{1,2})',
        r'between (\d{1,2})\s*(?:am|pm)?\s+and\s+(\d{1,2})\s*(?:am|pm)?',
    ]
    
    for pattern in hour_patterns:
        matches = re.finditer(pattern, prompt_lower)
        for match in matches:
            if len(match.groups()) == 1:
                hour = int(match.group(1))
                if 0 <= hour <= 23:
                    conditions['hour_of_day'] = hour
            elif len(match.groups()) == 2:
                start_hour = int(match.group(1))
                end_hour = int(match.group(2))
                if 0 <= start_hour <= 23 and 0 <= end_hour <= 23:
                    conditions['hour_range'] = (start_hour, end_hour)
    
    # Date patterns
    if '2017' in prompt:
        # Specific 2017 dates
        conditions['year'] = 2017
    elif any(term in prompt_lower for term in ['today', 'now', 'current', 'recent', 'last']):
        conditions['relative_time'] = True
    
    return conditions

def extract_attack_type(prompt: str) -> str:
    """Extract attack type from prompt"""
    prompt_lower = prompt.lower()
    
    for attack_type, keywords in ATTACK_MAPPINGS.items():
        for keyword in keywords:
            if keyword in prompt_lower:
                return attack_type
    
    # Check for malicious/benign
    if 'malicious' in prompt_lower or 'attack' in prompt_lower:
        return 'malicious'
    elif 'benign' in prompt_lower or 'normal' in prompt_lower:
        return 'normal'
    
    return None

def enhance_prompt(prompt: str) -> Dict[str, Any]:
    """
    Enhance a natural language prompt by extracting specific constraints
    Returns a structured representation of the query intent
    """
    enhancements = {
        'original_prompt': prompt,
        'attack_type': None,
        'field_constraints': [],
        'time_constraints': {},
        'ip_constraints': [],
        'port_constraints': [],
        'numeric_constraints': [],
    }
    
    # Extract attack type
    attack_type = extract_attack_type(prompt)
    if attack_type:
        enhancements['attack_type'] = attack_type
    
    # Extract IP addresses
    ip_constraints = extract_ip_addresses(prompt)
    enhancements['ip_constraints'] = ip_constraints
    
    # Extract ports
    port_constraints = extract_ports(prompt)
    enhancements['port_constraints'] = port_constraints
    
    # Extract numeric conditions
    numeric_constraints = extract_numeric_conditions(prompt)
    enhancements['numeric_constraints'] = numeric_constraints
    
    # Extract time conditions
    time_constraints = extract_time_conditions(prompt)
    enhancements['time_constraints'] = time_constraints
    
    # Combine all field constraints
    all_constraints = []
    
    # Add IP constraints
    for field, value in ip_constraints:
        all_constraints.append({
            'field': field,
            'operator': 'term',
            'value': value
        })
    
    # Add port constraints
    for field, value in port_constraints:
        all_constraints.append({
            'field': field,
            'operator': 'term',
            'value': value
        })
    
    # Add numeric constraints
    for field, operator, value in numeric_constraints:
        all_constraints.append({
            'field': field,
            'operator': operator,
            'value': value
        })
    
    enhancements['field_constraints'] = all_constraints
    
    return enhancements

def build_enhanced_prompt(original_prompt: str, enhancements: Dict[str, Any]) -> str:
    """
    Build an enhanced prompt that explicitly includes extracted constraints
    """
    parts = [original_prompt]
    
    # Always include attack type if found
    if enhancements['attack_type']:
        if enhancements['attack_type'] == 'scan':
            parts.append("\nThis is a port scan query (attack_type:scan)")
        elif enhancements['attack_type'] == 'dos':
            parts.append("\nThis is a DDoS attack query (attack_type:dos)")
        elif enhancements['attack_type'] == 'bruteforce':
            parts.append("\nThis is a brute force attack query (attack_type:bruteforce)")
    
    # Add explicit constraints to help the LLM
    seen_constraints = set()
    if enhancements['field_constraints']:
        parts.append("\nSpecific constraints to include:")
        for constraint in enhancements['field_constraints']:
            field = constraint['field']
            op = constraint['operator']
            value = constraint['value']
            
            # Avoid duplicates
            constraint_key = f"{field}:{op}:{value}"
            if constraint_key in seen_constraints:
                continue
            seen_constraints.add(constraint_key)
            
            if op == 'term':
                parts.append(f"- {field} must equal {value}")
            elif op in ['gt', 'gte']:
                parts.append(f"- {field} must be greater than {value}")
            elif op in ['lt', 'lte']:
                parts.append(f"- {field} must be less than {value}")
    
    if enhancements['time_constraints']:
        if 'day_of_week' in enhancements['time_constraints']:
            parts.append(f"- day_of_week must equal {enhancements['time_constraints']['day_of_week']}")
        if 'hour_of_day' in enhancements['time_constraints']:
            parts.append(f"- hour_of_day must equal {enhancements['time_constraints']['hour_of_day']}")
    
    return "\n".join(parts)

if __name__ == "__main__":
    # Test the enhancer
    test_prompts = [
        "Find port scans where destination port is 443",
        "Find DDoS attacks from IP 192.168.1.100",
        "Find traffic with packet rate greater than 1000",
        "Find brute force attacks on Tuesday between 9am and 5pm",
        "Find malicious traffic to port 80 or 8080",
        "Find flows with duration over 10 seconds and bytes > 1MB",
    ]
    
    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        print("-" * 50)
        enhancements = enhance_prompt(prompt)
        print(f"Attack type: {enhancements['attack_type']}")
        print(f"Field constraints: {enhancements['field_constraints']}")
        print(f"Time constraints: {enhancements['time_constraints']}")
        enhanced = build_enhanced_prompt(prompt, enhancements)
        print(f"Enhanced prompt:\n{enhanced}")
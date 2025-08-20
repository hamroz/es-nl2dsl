#!/usr/bin/env python3
"""
Query helper to provide suggestions when queries return no results
"""

from elasticsearch import Elasticsearch
import json
from typing import Dict, List, Tuple

def analyze_empty_result(query: Dict, index: str) -> Dict:
    """
    Analyze why a query returned no results and provide suggestions
    """
    es = Elasticsearch(
        ['http://localhost:9200'],
        basic_auth=('elastic', 'ChangeMe_123'),
        verify_certs=False
    )
    
    suggestions = {
        'possible_issues': [],
        'suggestions': [],
        'similar_data': []
    }
    
    # Extract constraints from query
    constraints = extract_constraints(query)
    
    # Check each constraint individually
    for constraint in constraints:
        field = constraint['field']
        value = constraint['value']
        
        # Check if this specific value exists
        if field in ['src_ip', 'dst_ip', 'attack_type', 'label']:
            exists = check_value_exists(es, index, field, value)
            if not exists:
                suggestions['possible_issues'].append(
                    f"No records found with {field}='{value}'"
                )
                
                # Get actual values that exist
                actual_values = get_top_values(es, index, field, 5)
                if actual_values:
                    suggestions['suggestions'].append(
                        f"Try using one of these {field} values: {', '.join(map(str, actual_values))}"
                    )
        
        elif field in ['dst_port', 'src_port']:
            exists = check_port_exists(es, index, field, value)
            if not exists:
                suggestions['possible_issues'].append(
                    f"No records found with {field}={value}"
                )
                
                # Get common ports
                common_ports = get_common_ports(es, index, field)
                if common_ports:
                    suggestions['suggestions'].append(
                        f"Common {field} values in data: {', '.join(map(str, common_ports[:5]))}"
                    )
        
        elif field in ['flow_packets_s', 'flow_bytes_s', 'flow_duration']:
            # Check if threshold is too high/low
            stats = get_field_stats(es, index, field)
            if stats:
                if 'gt' in str(constraint) or 'gte' in str(constraint):
                    if value > stats['max']:
                        suggestions['possible_issues'].append(
                            f"{field} threshold ({value}) exceeds maximum in data ({stats['max']:.2f})"
                        )
                        suggestions['suggestions'].append(
                            f"Try a lower threshold for {field}, max value is {stats['max']:.2f}"
                        )
                elif 'lt' in str(constraint) or 'lte' in str(constraint):
                    if value < stats['min']:
                        suggestions['possible_issues'].append(
                            f"{field} threshold ({value}) is below minimum in data ({stats['min']:.2f})"
                        )
                        suggestions['suggestions'].append(
                            f"Try a higher threshold for {field}, min value is {stats['min']:.2f}"
                        )
    
    # Check combinations
    if len(constraints) > 1:
        # The combination might be too restrictive
        suggestions['suggestions'].append(
            "Try removing some constraints - the combination might be too specific"
        )
        
        # Test each constraint individually to see which ones return results
        working_constraints = []
        for constraint in constraints:
            test_query = create_single_constraint_query(constraint)
            count = execute_count_query(es, index, test_query)
            if count > 0:
                working_constraints.append(f"{constraint['field']}={constraint['value']} ({count} results)")
        
        if working_constraints:
            suggestions['similar_data'] = working_constraints
    
    return suggestions

def extract_constraints(query: Dict) -> List[Dict]:
    """Extract individual constraints from a query"""
    constraints = []
    
    if 'query' in query and 'bool' in query['query']:
        filters = query['query']['bool'].get('filter', [])
        for f in filters:
            if 'term' in f:
                for field, value in f['term'].items():
                    if field != '@timestamp':
                        constraints.append({
                            'field': field,
                            'value': value,
                            'operator': 'term'
                        })
            elif 'terms' in f:
                for field, values in f['terms'].items():
                    constraints.append({
                        'field': field,
                        'value': values,
                        'operator': 'terms'
                    })
            elif 'range' in f:
                for field, conditions in f['range'].items():
                    if field != '@timestamp':
                        for op, value in conditions.items():
                            constraints.append({
                                'field': field,
                                'value': value,
                                'operator': op
                            })
    
    return constraints

def check_value_exists(es, index, field, value) -> bool:
    """Check if a specific value exists in a field"""
    try:
        result = es.count(
            index=index,
            body={"query": {"term": {field: value}}}
        )
        return result['count'] > 0
    except:
        return False

def check_port_exists(es, index, field, value) -> bool:
    """Check if a specific port exists"""
    try:
        result = es.count(
            index=index,
            body={"query": {"term": {field: int(value)}}}
        )
        return result['count'] > 0
    except:
        return False

def get_top_values(es, index, field, size=5) -> List:
    """Get most common values for a field"""
    try:
        result = es.search(
            index=index,
            size=0,
            body={
                "aggs": {
                    "top_values": {
                        "terms": {"field": field, "size": size}
                    }
                }
            }
        )
        return [b['key'] for b in result['aggregations']['top_values']['buckets']]
    except:
        return []

def get_common_ports(es, index, field) -> List[int]:
    """Get common port numbers"""
    try:
        result = es.search(
            index=index,
            size=0,
            body={
                "aggs": {
                    "ports": {
                        "terms": {"field": field, "size": 10}
                    }
                }
            }
        )
        return [b['key'] for b in result['aggregations']['ports']['buckets']]
    except:
        return []

def get_field_stats(es, index, field) -> Dict:
    """Get statistics for a numeric field"""
    try:
        result = es.search(
            index=index,
            size=0,
            body={
                "aggs": {
                    "field_stats": {
                        "stats": {"field": field}
                    }
                }
            }
        )
        return result['aggregations']['field_stats']
    except:
        return {}

def create_single_constraint_query(constraint: Dict) -> Dict:
    """Create a query with just one constraint"""
    if constraint['operator'] == 'term':
        return {"query": {"term": {constraint['field']: constraint['value']}}}
    elif constraint['operator'] == 'terms':
        return {"query": {"terms": {constraint['field']: constraint['value']}}}
    elif constraint['operator'] in ['gt', 'gte', 'lt', 'lte']:
        return {"query": {"range": {constraint['field']: {constraint['operator']: constraint['value']}}}}
    return {"query": {"match_all": {}}}

def execute_count_query(es, index, query) -> int:
    """Execute a count query"""
    try:
        result = es.count(index=index, body=query)
        return result['count']
    except:
        return 0

def get_helpful_examples(index: str) -> List[str]:
    """Get helpful example prompts based on actual data"""
    es = Elasticsearch(
        ['http://localhost:9200'],
        basic_auth=('elastic', 'ChangeMe_123'),
        verify_certs=False
    )
    
    examples = []
    
    # Get some actual attack data
    try:
        # DDoS examples
        dos_ips = get_top_values(es, index, 'src_ip', 3)
        if dos_ips:
            examples.append(f"Find DDoS attacks from {dos_ips[0]}")
        
        # Port examples
        ports = get_common_ports(es, index, 'dst_port')
        if ports:
            examples.append(f"Find traffic to port {ports[0]}")
        
        # Get realistic thresholds
        stats = get_field_stats(es, index, 'flow_packets_s')
        if stats:
            threshold = int(stats['avg'] * 2)  # Use 2x average as "high"
            examples.append(f"Find traffic with packet rate over {threshold}")
        
    except:
        pass
    
    return examples

if __name__ == "__main__":
    # Test with a query that returns no results
    test_query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"attack_type": "dos"}},
                    {"term": {"src_ip": "192.168.10.5"}},
                    {"range": {"flow_packets_s": {"gt": 100}}}
                ]
            }
        }
    }
    
    print("Testing query that returns no results...")
    print(json.dumps(test_query, indent=2))
    
    suggestions = analyze_empty_result(test_query, "logs_cic_ids2017")
    
    print("\n📊 Analysis Results:")
    print(json.dumps(suggestions, indent=2))
    
    print("\n💡 Helpful Examples:")
    examples = get_helpful_examples("logs_cic_ids2017")
    for ex in examples:
        print(f"  - {ex}")
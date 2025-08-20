#!/usr/bin/env python3
"""
Generate data-aware examples based on actual data in the index
This helps create realistic prompts that will return results
"""

from elasticsearch import Elasticsearch
import json

def get_data_statistics(index="logs_cic_ids2017"):
    """Get statistics about the actual data"""
    es = Elasticsearch(
        ['http://localhost:9200'],
        basic_auth=('elastic', 'ChangeMe_123'),
        verify_certs=False
    )
    
    stats = {}
    
    # Get attack types and counts
    result = es.search(
        index=index,
        size=0,
        body={
            "aggs": {
                "attack_types": {
                    "terms": {"field": "attack_type", "size": 20}
                }
            }
        }
    )
    stats['attack_types'] = {
        b['key']: b['doc_count'] 
        for b in result['aggregations']['attack_types']['buckets']
    }
    
    # Get common source IPs for attacks
    for attack_type in ['dos', 'scan', 'bruteforce']:
        result = es.search(
            index=index,
            size=0,
            body={
                "query": {"term": {"attack_type": attack_type}},
                "aggs": {
                    "src_ips": {
                        "terms": {"field": "src_ip", "size": 5}
                    }
                }
            }
        )
        stats[f'{attack_type}_src_ips'] = [
            b['key'] for b in result['aggregations']['src_ips']['buckets']
        ]
    
    # Get common destination ports
    result = es.search(
        index=index,
        size=0,
        body={
            "query": {"bool": {"must_not": {"term": {"attack_type": "normal"}}}},
            "aggs": {
                "dst_ports": {
                    "terms": {"field": "dst_port", "size": 10}
                }
            }
        }
    )
    stats['common_attack_ports'] = [
        b['key'] for b in result['aggregations']['dst_ports']['buckets']
    ]
    
    # Get packet rate ranges for DDoS
    result = es.search(
        index=index,
        size=0,
        body={
            "query": {"term": {"attack_type": "dos"}},
            "aggs": {
                "packet_rates": {
                    "percentiles": {
                        "field": "flow_packets_s",
                        "percents": [25, 50, 75, 90, 95, 99]
                    }
                }
            }
        }
    )
    stats['dos_packet_rate_percentiles'] = result['aggregations']['packet_rates']['values']
    
    return stats

def generate_realistic_examples(stats):
    """Generate realistic example prompts based on actual data"""
    examples = []
    
    # DDoS examples with real IPs and thresholds
    if 'dos_src_ips' in stats and stats['dos_src_ips']:
        src_ip = stats['dos_src_ips'][0]
        # Use 75th percentile as "high" threshold
        high_rate = int(stats['dos_packet_rate_percentiles'].get('75.0', 10))
        
        examples.append({
            'prompt': f"Find DDoS attacks from {src_ip}",
            'description': "DDoS with actual source IP from data",
            'expected_results': ">10000"
        })
        
        examples.append({
            'prompt': f"Find DDoS attacks with packet rate over {high_rate}",
            'description': "DDoS with realistic packet rate threshold",
            'expected_results': ">1000"
        })
    
    # Port scan examples with real ports
    if 'common_attack_ports' in stats and stats['common_attack_ports']:
        port = stats['common_attack_ports'][0]
        examples.append({
            'prompt': f"Find port scans targeting port {port}",
            'description': "Port scan with common target port",
            'expected_results': ">0"
        })
    
    # Brute force with real IPs
    if 'bruteforce_src_ips' in stats and stats['bruteforce_src_ips']:
        src_ip = stats['bruteforce_src_ips'][0]
        examples.append({
            'prompt': f"Find brute force attacks from {src_ip}",
            'description': "Brute force with actual source IP",
            'expected_results': ">0"
        })
    
    return examples

def main():
    print("=" * 60)
    print("DATA-AWARE EXAMPLE GENERATION")
    print("=" * 60)
    
    print("\nAnalyzing actual data in logs_cic_ids2017...")
    stats = get_data_statistics()
    
    print("\n📊 Data Statistics:")
    print(f"Attack types: {json.dumps(stats['attack_types'], indent=2)}")
    print(f"\nDDoS source IPs: {stats.get('dos_src_ips', [])[:3]}")
    print(f"Common attack ports: {stats.get('common_attack_ports', [])[:5]}")
    print(f"\nDDoS packet rate percentiles:")
    for p, v in stats.get('dos_packet_rate_percentiles', {}).items():
        print(f"  {p}%: {v:.2f} packets/s")
    
    print("\n✨ Realistic Example Prompts:")
    examples = generate_realistic_examples(stats)
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['prompt']}")
        print(f"   Description: {example['description']}")
        print(f"   Expected results: {example['expected_results']}")
    
    # Save examples for use in few-shot learning
    with open('artifacts/data_aware_examples.json', 'w') as f:
        json.dump({
            'statistics': stats,
            'examples': examples
        }, f, indent=2)
    
    print("\n✅ Data-aware examples saved to artifacts/data_aware_examples.json")
    
    return stats, examples

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Test complex query generation accuracy"""

import subprocess
import json
import sys
from pathlib import Path
import time

test_cases = [
    {
        "prompt": "Find port scans where destination port is 443",
        "expected_conditions": ["attack_type:scan", "dst_port:443"],
        "description": "Port scan with specific port"
    },
    {
        "prompt": "Find DDoS attacks from source IP 192.168.10.5",
        "expected_conditions": ["attack_type:dos", "src_ip:192.168.10.5"],
        "description": "DDoS with source IP"
    },
    {
        "prompt": "Find brute force attacks on port 22",
        "expected_conditions": ["attack_type:bruteforce", "dst_port:22"],
        "description": "SSH brute force"
    },
    {
        "prompt": "Find traffic to ports 80 or 443",
        "expected_conditions": ["dst_port", "[80, 443]"],
        "description": "Multiple ports"
    },
    {
        "prompt": "Find high packet rate traffic over 500 packets per second",
        "expected_conditions": ["flow_packets_s", "gte", "500"],
        "description": "Packet rate threshold"
    },
    {
        "prompt": "Find TCP traffic with SYN flags greater than 5",
        "expected_conditions": ["syn_flag_count", "gt", "5", "protocol:tcp"],
        "description": "TCP flags condition"
    },
    {
        "prompt": "Find attacks from 192.168.1.100 to port 3389",
        "expected_conditions": ["src_ip:192.168.1.100", "dst_port:3389"],
        "description": "IP and port combination"
    },
    {
        "prompt": "Find flows with duration over 10000 milliseconds",
        "expected_conditions": ["flow_duration", "gt", "10000"],
        "description": "Flow duration"
    },
    {
        "prompt": "Find traffic on Monday with high bandwidth over 1MB/s",
        "expected_conditions": ["day_of_week:Monday", "flow_bytes_s", "gt"],
        "description": "Day and bandwidth"
    },
    {
        "prompt": "Find port scans targeting ports 21, 22, 23, or 3389",
        "expected_conditions": ["attack_type:scan", "dst_port", "[21, 22, 23, 3389]"],
        "description": "Multiple target ports"
    }
]

def generate_query(prompt, index="logs_cic_ids2017"):
    """Generate query using enhanced generation"""
    task_id = f"complex_test_{int(time.time())}"
    cmd = [
        sys.executable, "src/generate_constrained.py",
        "--prompt", prompt,
        "--index", index,
        "--task-id", task_id
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            query_file = Path(f"artifacts/generated/{task_id}.json")
            if query_file.exists():
                with open(query_file) as f:
                    return json.load(f), None
        return None, result.stderr
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

def check_conditions(query, expected_conditions):
    """Check if query contains expected conditions"""
    query_str = json.dumps(query, indent=2)
    missing = []
    found = []
    
    for condition in expected_conditions:
        if condition in query_str:
            found.append(condition)
        else:
            # Check for numeric values without quotes
            if condition.replace('"', '') in query_str:
                found.append(condition)
            else:
                missing.append(condition)
    
    return len(missing) == 0, found, missing

def main():
    print("=" * 70)
    print("COMPLEX QUERY GENERATION TEST")
    print("=" * 70)
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['description']}")
        print(f"Prompt: {test['prompt']}")
        print("-" * 50)
        
        # Generate query
        query, error = generate_query(test['prompt'])
        
        if error or not query:
            print(f"❌ Generation failed: {error}")
            results.append({"test": i, "success": False, "reason": "generation_failed"})
            continue
        
        if "abstain" in query:
            print(f"❌ Query abstained: {query.get('reason')}")
            results.append({"test": i, "success": False, "reason": "abstained"})
            continue
        
        # Check conditions
        all_found, found, missing = check_conditions(query, test['expected_conditions'])
        
        if all_found:
            print(f"✅ All conditions found: {found}")
            results.append({"test": i, "success": True})
        else:
            print(f"⚠️  Some conditions missing:")
            print(f"   Found: {found}")
            print(f"   Missing: {missing}")
            results.append({"test": i, "success": False, "missing": missing})
        
        # Display generated query
        print("Generated query:")
        print(json.dumps(query, indent=2))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total} ({passed*100/total:.1f}%)")
    
    for i, r in enumerate(results, 1):
        status = "✅" if r["success"] else "❌"
        reason = ""
        if not r["success"]:
            if "missing" in r:
                reason = f" - Missing: {r['missing']}"
            else:
                reason = f" - {r.get('reason', 'unknown')}"
        print(f"{status} Test {i}: {test_cases[i-1]['description']}{reason}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
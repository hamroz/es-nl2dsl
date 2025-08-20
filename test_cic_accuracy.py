#!/usr/bin/env python3
"""Test query accuracy for CIC-IDS2017 data"""

import subprocess
import json
import sys
from pathlib import Path
import time

# Test cases for CIC queries
test_cases = [
    {
        "prompt": "Find all DDoS attacks",
        "expected_fields": ["attack_type:dos"],
        "expected_count_min": 10000
    },
    {
        "prompt": "Find port scan attacks", 
        "expected_fields": ["attack_type:scan"],
        "expected_count_min": 200
    },
    {
        "prompt": "Find brute force attacks",
        "expected_fields": ["attack_type:bruteforce"],
        "expected_count_min": 3000
    },
    {
        "prompt": "Find web attacks",
        "expected_fields": ["label:Web Attack"],
        "expected_count_min": 500
    },
    {
        "prompt": "Find traffic with high packet rate over 500 packets per second",
        "expected_fields": ["flow_packets_s", "range"],
        "expected_count_min": 1
    },
    {
        "prompt": "Find TCP traffic with SYN flags greater than 3",
        "expected_fields": ["syn_flag_count", "protocol:tcp"],
        "expected_count_min": 1
    },
    {
        "prompt": "Find malicious traffic (not benign)",
        "expected_fields": ["must_not", "normal"],
        "expected_count_min": 10000
    },
    {
        "prompt": "Find flows with duration over 1 second",
        "expected_fields": ["flow_duration", "1000"],
        "expected_count_min": 100
    }
]

def generate_query(prompt, task_id):
    """Generate query using constrained generation"""
    cmd = [
        sys.executable, "src/generate_constrained.py",
        "--prompt", prompt,
        "--index", "logs_cic_ids2017",
        "--task-id", task_id
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    
    if result.returncode != 0:
        return None, result.stderr
    
    # Load generated query
    query_file = Path(f"artifacts/generated/{task_id}.json")
    if query_file.exists():
        with open(query_file) as f:
            return json.load(f), None
    
    return None, "Query file not found"

def execute_query(query):
    """Execute query against Elasticsearch"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(query, f)
        temp_path = f.name
    
    cmd = [
        "curl", "-s", "-u", "reader:ReaderPwd_123",
        "-X", "POST", "http://localhost:9200/logs_cic_ids2017/_search?size=0",
        "-H", "Content-Type: application/json",
        "-d", f"@{temp_path}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(temp_path).unlink()
    
    if result.returncode == 0:
        try:
            response = json.loads(result.stdout)
            return response.get("hits", {}).get("total", {}).get("value", 0)
        except:
            return 0
    return 0

def check_query_contains(query, expected_fields):
    """Check if query contains expected fields/values"""
    query_str = json.dumps(query).lower()
    missing = []
    for field in expected_fields:
        if field.lower() not in query_str:
            missing.append(field)
    return len(missing) == 0, missing

def main():
    print("=" * 60)
    print("CIC-IDS2017 Query Accuracy Test")
    print("=" * 60)
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['prompt']}")
        print("-" * 40)
        
        task_id = f"accuracy_test_{i}_{int(time.time())}"
        
        # Generate query
        print("Generating query...")
        query, error = generate_query(test["prompt"], task_id)
        
        if error or not query:
            print(f"❌ Generation failed: {error}")
            results.append({"test": i, "success": False, "reason": "generation_failed"})
            continue
        
        if "abstain" in query:
            print(f"❌ Query abstained: {query.get('reason')}")
            results.append({"test": i, "success": False, "reason": "abstained"})
            continue
        
        # Check query structure
        contains_fields, missing = check_query_contains(query, test["expected_fields"])
        if not contains_fields:
            print(f"⚠️  Missing expected fields: {missing}")
        
        # Execute query
        print("Executing query...")
        count = execute_query(query)
        print(f"Results found: {count:,}")
        
        # Check if count meets expectations
        success = count >= test["expected_count_min"]
        if success:
            print(f"✅ Test passed (expected >= {test['expected_count_min']:,})")
        else:
            print(f"❌ Test failed (expected >= {test['expected_count_min']:,}, got {count:,})")
        
        # Show generated query
        print("Generated query:")
        print(json.dumps(query, indent=2))
        
        results.append({
            "test": i,
            "prompt": test["prompt"],
            "success": success,
            "count": count,
            "expected_min": test["expected_count_min"],
            "contains_fields": contains_fields
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"Tests passed: {passed}/{total} ({passed*100/total:.1f}%)")
    print("\nDetailed results:")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} Test {r['test']}: {r.get('count', 0):,} results (expected >= {r.get('expected_min', 0):,})")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
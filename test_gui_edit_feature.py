#!/usr/bin/env python3
"""
Test the query editing feature by generating and modifying queries
"""

import json
import subprocess
import time

def test_query_editing():
    """Test the query editing workflow"""
    
    print("=" * 60)
    print("QUERY EDITING FEATURE TEST")
    print("=" * 60)
    
    # 1. Generate a query that will return no results
    print("\n1. Generating query with non-existent data...")
    original_prompt = "Find DDoS attacks from 192.168.10.5"
    
    cmd = [
        "python", "src/generate_constrained.py",
        "--prompt", original_prompt,
        "--index", "logs_cic_ids2017",
        "--task-id", f"edit_test_{int(time.time())}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Query generated successfully")
        # Extract the generated query
        for line in result.stdout.split('\n'):
            if line.strip().startswith('{'):
                generated_query = json.loads(result.stdout[result.stdout.index('{'):])
                break
        
        print("Generated query:")
        print(json.dumps(generated_query, indent=2))
    else:
        print("❌ Generation failed")
        return
    
    # 2. Show what needs to be edited
    print("\n2. Query will return 0 results because:")
    print("   - DDoS attacks in data come from 172.16.0.1, not 192.168.10.5")
    
    # 3. Create corrected query
    print("\n3. Corrected query (what user would edit to):")
    corrected_query = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"attack_type": "dos"}},
                    {"term": {"src_ip": "172.16.0.1"}},  # Corrected IP
                    {"range": {"@timestamp": {"gte": "2017-01-01", "lte": "2017-12-31"}}}
                ]
            }
        }
    }
    print(json.dumps(corrected_query, indent=2))
    
    # 4. Test both queries
    print("\n4. Testing query execution:")
    
    # Test original (should return 0)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(generated_query, f)
        original_file = f.name
    
    cmd = [
        "curl", "-s", "-u", "reader:ReaderPwd_123",
        "-X", "POST", "http://localhost:9200/logs_cic_ids2017/_search?size=0",
        "-H", "Content-Type: application/json",
        "-d", f"@{original_file}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        response = json.loads(result.stdout)
        original_hits = response.get("hits", {}).get("total", {}).get("value", 0)
        print(f"   Original query results: {original_hits} hits")
    
    # Test corrected (should return results)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(corrected_query, f)
        corrected_file = f.name
    
    cmd[7] = f"@{corrected_file}"
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        response = json.loads(result.stdout)
        corrected_hits = response.get("hits", {}).get("total", {}).get("value", 0)
        print(f"   Corrected query results: {corrected_hits} hits")
    
    # Clean up
    import os
    os.unlink(original_file)
    os.unlink(corrected_file)
    
    print("\n" + "=" * 60)
    print("GUI WORKFLOW:")
    print("=" * 60)
    print("""
1. User enters prompt: "Find DDoS attacks from 192.168.10.5"
2. System generates query with src_ip: "192.168.10.5"
3. Query appears in EDITABLE text area
4. User sees 0 results and helpful suggestions
5. User edits src_ip to "172.16.0.1" in the text area
6. User clicks "Execute Query" again
7. System uses the EDITED query
8. Results show 12,561 DDoS attacks ✅

Key Features:
- ✏️ Editable query text area
- 🔄 Reset to Original button
- ✅ JSON validation in real-time
- 💡 Helpful suggestions when no results
- 📊 Export edited query
""")

if __name__ == "__main__":
    test_query_editing()
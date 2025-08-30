#!/usr/bin/env python3
"""
Test script for Phase 1: Dynamic Field Discovery
Tests if the system can discover fields from any index
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.generators.index_analyzer import get_index_analyzer
from src.generators.constrained import build_prompt, get_field_catalog_for_index

def test_index_discovery(index_name):
    """Test field discovery for a specific index"""
    print(f"\n{'='*60}")
    print(f"Testing index: {index_name}")
    print('='*60)
    
    analyzer = get_index_analyzer()
    
    # Test 1: Get all fields
    print("\n1. Field Discovery:")
    fields = analyzer.get_index_fields(index_name)
    
    if fields:
        print(f"   ✅ Found {len(fields)} fields")
        # Show first 10 fields
        field_list = list(fields.items())[:10]
        for field_name, field_info in field_list:
            print(f"      - {field_name}: {field_info['type']} - {field_info['description'][:50]}...")
        if len(fields) > 10:
            print(f"      ... and {len(fields) - 10} more fields")
    else:
        print(f"   ❌ No fields found")
        return False
    
    # Test 2: Build field catalog
    print("\n2. Field Catalog:")
    catalog = analyzer.build_field_catalog(index_name)
    
    if catalog:
        print(f"   ✅ Catalog built successfully")
        print(f"      - Total fields: {catalog['field_count']}")
        print(f"      - Keyword fields: {len(catalog.get('keyword_fields', []))}")
        print(f"      - Numeric fields: {len(catalog.get('numeric_fields', []))}")
        print(f"      - Date fields: {len(catalog.get('timestamp_fields', []))}")
        print(f"      - Primary timestamp: {catalog.get('primary_timestamp', 'None')}")
        
        if catalog.get('common_patterns'):
            print(f"      - Field patterns found:")
            for pattern, fields in catalog['common_patterns'].items():
                if fields:
                    print(f"        • {pattern}: {len(fields)} fields")
    else:
        print(f"   ❌ Failed to build catalog")
        return False
    
    # Test 3: Test if constrained.py uses the fields
    print("\n3. Prompt Generation with Dynamic Fields:")
    test_prompt = "Show all records with log type firewall and source IP 192.168.1.225"
    
    prompt = build_prompt(test_prompt, index=index_name)
    
    # Check if the prompt includes actual fields
    if "ALL AVAILABLE FIELDS:" in prompt or "available fields" in prompt.lower():
        print(f"   ✅ Dynamic fields included in prompt")
        
        # Check for specific field types that might map to "log type"
        potential_log_type_fields = []
        for field_name in fields.keys():
            if any(term in field_name.lower() for term in ['type', 'log', 'category', 'class']):
                potential_log_type_fields.append(field_name)
        
        if potential_log_type_fields:
            print(f"   ✅ Found potential 'log type' fields: {potential_log_type_fields[:5]}")
        else:
            print(f"   ⚠️  No obvious 'log type' fields found, but LLM might still map it")
    else:
        print(f"   ❌ Dynamic fields not included in prompt")
    
    # Test 4: Check field catalog function
    print("\n4. Field Catalog Function:")
    catalog_fields = get_field_catalog_for_index(index_name)
    
    if catalog_fields and len(catalog_fields) > 10:  # More than static catalog
        print(f"   ✅ get_field_catalog_for_index() returns dynamic fields: {len(catalog_fields)} fields")
    else:
        print(f"   ⚠️  get_field_catalog_for_index() returned static catalog: {len(catalog_fields) if catalog_fields else 0} fields")
    
    return True

def main():
    """Run tests on various indices"""
    print("\n" + "="*60)
    print("PHASE 1 TEST: Dynamic Field Discovery")
    print("="*60)
    
    # Test with different indices
    test_indices = [
        "logs_net",           # Standard test index
        "logs_cic_ids2017",   # CIC dataset
        # Add more indices as needed
    ]
    
    # First, check what indices are available
    from elasticsearch import Elasticsearch
    from src.utils.config import get_es_client_config
    
    try:
        es = Elasticsearch(**get_es_client_config(use_admin=False))
        indices_info = es.indices.get_alias(index="*")
        if isinstance(indices_info, dict):
            available_indices = list(indices_info.keys())
        else:
            available_indices = []
        
        # Filter out system indices
        available_indices = [idx for idx in available_indices if not idx.startswith('.')]
        
        print(f"\nAvailable indices in Elasticsearch: {available_indices[:10]}")
        if len(available_indices) > 10:
            print(f"... and {len(available_indices) - 10} more")
        
        # Test each configured index that exists
        for index in test_indices:
            if index in available_indices:
                success = test_index_discovery(index)
                if not success:
                    print(f"\n⚠️ Test failed for {index}")
            else:
                print(f"\n⚠️ Index '{index}' not found in Elasticsearch")
        
        # Test with first available user index if different from test indices
        if available_indices and available_indices[0] not in test_indices:
            print(f"\n📝 Testing with first available index: {available_indices[0]}")
            test_index_discovery(available_indices[0])
            
    except Exception as e:
        print(f"\n❌ Error connecting to Elasticsearch: {e}")
        print("Make sure Elasticsearch is running and accessible")
        return
    
    print("\n" + "="*60)
    print("PHASE 1 TEST COMPLETE")
    print("="*60)
    print("\n✅ If you see fields discovered above, Phase 1 is working!")
    print("✅ The system can now discover ALL fields from any index")
    print("\n🔍 Next: Test actual query generation with a prompt like:")
    print('   python src/generate_constrained.py --prompt "Show all records with log type firewall" --index YOUR_INDEX')

if __name__ == "__main__":
    main()
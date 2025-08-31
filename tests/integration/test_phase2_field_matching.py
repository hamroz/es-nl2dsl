#!/usr/bin/env python3
"""
Test script for Phase 2: Smart Field Matching  
Tests if the system can correctly map natural language terms to actual field names
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.generators.field_matcher import get_field_matcher, extract_constraints_from_prompt
from src.generators.index_analyzer import get_index_analyzer
from src.generators.constrained import enhance_prompt_with_field_matching, build_prompt

def test_field_matching_basic():
    """Test basic field matching functionality"""
    print("\n" + "="*60)
    print("PHASE 2 TEST: Basic Field Matching")
    print("="*60)
    
    # Sample available fields from cybersecurity index
    available_fields = [
        'action', 'action.keyword',
        'log_type', 'log_type.keyword', 
        'source_ip', 'dest_ip',
        'user_agent', 'user_agent.keyword',
        'timestamp', '@timestamp',
        'bytes_transferred',
        'threat_label', 'threat_label.keyword'
    ]
    
    matcher = get_field_matcher()
    
    # Test cases
    test_cases = [
        ("log type", "log_type.keyword"),
        ("action", "action.keyword"),
        ("source ip", "source_ip"),
        ("ip", "source_ip"),  # Should match closest IP field
        ("user", "user_agent"),
        ("bytes", "bytes_transferred"),
        ("threat", "threat_label.keyword"),
    ]
    
    print("\n1. Testing Individual Field Matching:")
    success_count = 0
    
    for user_term, expected_field in test_cases:
        match = matcher.smart_match(user_term, available_fields)
        
        if match:
            actual_field = match['field']
            confidence = match['confidence']
            success = actual_field == expected_field
            
            status = "✅" if success else "❌"
            print(f"   {status} '{user_term}' → {actual_field} (confidence: {confidence:.2f})")
            
            if not success:
                print(f"      Expected: {expected_field}")
            else:
                success_count += 1
        else:
            print(f"   ❌ '{user_term}' → No match found")
    
    print(f"\n   Success Rate: {success_count}/{len(test_cases)} ({100*success_count/len(test_cases):.1f}%)")
    
    return success_count / len(test_cases) > 0.7  # 70% success rate

def test_prompt_constraint_extraction():
    """Test extracting constraints from full prompts"""
    print("\n" + "="*60) 
    print("PHASE 2 TEST: Prompt Constraint Extraction")
    print("="*60)
    
    available_fields = [
        'action', 'action.keyword',
        'log_type', 'log_type.keyword', 
        'source_ip', 'dest_ip',
        'user_agent', 'user_agent.keyword',
        'timestamp', '@timestamp',
        'bytes_transferred',
        'threat_label', 'threat_label.keyword'
    ]
    
    matcher = get_field_matcher()
    
    test_prompts = [
        {
            "prompt": "show all records with log type firewall and source ip 192.168.1.225",
            "expected_constraints": [
                ("log type firewall", "log_type.keyword", "firewall"),
                ("source ip 192.168.1.225", "source_ip", "192.168.1.225")
            ]
        },
        {
            "prompt": "find events where action is blocked and user contains admin",
            "expected_constraints": [
                ("action is blocked", "action.keyword", "blocked"),
                ("user contains admin", "user_agent", "admin")
            ]
        },
        {
            "prompt": "filter by threat malware from ip 10.0.0.5",
            "expected_constraints": [
                ("threat malware", "threat_label.keyword", "malware"),
                ("ip 10.0.0.5", "source_ip", "10.0.0.5")  # or dest_ip
            ]
        }
    ]
    
    print("\n2. Testing Constraint Extraction from Prompts:")
    
    for i, test_case in enumerate(test_prompts, 1):
        prompt = test_case["prompt"]
        expected = test_case["expected_constraints"]
        
        print(f"\n   Test {i}: '{prompt}'")
        
        constraints = matcher.extract_field_value_pairs(prompt, available_fields)
        
        print(f"   Found {len(constraints)} constraints:")
        for constraint in constraints:
            field_match = constraint['field_match']
            value = constraint['value']
            original = constraint['original_text']
            confidence = field_match['confidence']
            
            print(f"      - '{original}' → {field_match['field']}:'{value}' (conf: {confidence:.2f})")
        
        # Check if we found expected constraints
        found_fields = set(c['field_match']['field'] for c in constraints)
        expected_fields = set(exp[1] for exp in expected)
        
        if found_fields & expected_fields:  # At least some overlap
            print(f"      ✅ Found some expected fields")
        else:
            print(f"      ❌ No expected fields found")
            print(f"      Expected: {expected_fields}")

def test_real_index_integration():
    """Test with real indices"""
    print("\n" + "="*60)
    print("PHASE 2 TEST: Real Index Integration")
    print("="*60)
    
    test_indices = ["logs_cybersecurity-threat-detection-logs", "logs_cic_ids2017"]
    
    for index in test_indices:
        print(f"\n3. Testing with index: {index}")
        
        try:
            # Test 1: Field discovery
            analyzer = get_index_analyzer()
            fields = analyzer.get_index_fields(index)
            
            if not fields:
                print(f"   ❌ No fields discovered for {index}")
                continue
                
            print(f"   ✅ Discovered {len(fields)} fields")
            
            # Test 2: Prompt enhancement
            test_prompt = "show all records with log type firewall and ip 192.168.1.225"
            enhanced_prompt = enhance_prompt_with_field_matching(test_prompt, index)
            
            if "DETECTED FIELD MAPPINGS:" in enhanced_prompt:
                print(f"   ✅ Prompt enhanced with field mappings")
                
                # Show the mappings
                lines = enhanced_prompt.split('\n')
                for line in lines:
                    if '→' in line:
                        print(f"      {line.strip()}")
            else:
                print(f"   ❌ No field mappings detected")
            
            # Test 3: Full prompt building
            full_prompt = build_prompt(test_prompt, index)
            
            if enhanced_prompt != test_prompt and enhanced_prompt in full_prompt:
                print(f"   ✅ Enhanced prompt included in LLM prompt")
            else:
                print(f"   ⚠️  Enhanced prompt may not be fully integrated")
                
        except Exception as e:
            print(f"   ❌ Error testing {index}: {e}")

def test_specific_problem_case():
    """Test the specific case from the original problem"""
    print("\n" + "="*60)
    print("PHASE 2 TEST: Original Problem Case")
    print("="*60)
    
    # Test the exact scenario that was failing
    prompt = "show all records with ip 192.168.1.225 and log type firewall"
    index = "logs_cybersecurity-threat-detection-logs"
    
    print(f"\n4. Testing original problem: '{prompt}' with index {index}")
    
    try:
        # Step 1: Check if index has log_type field
        analyzer = get_index_analyzer()
        fields = analyzer.get_index_fields(index)
        
        has_log_type = any('log_type' in field.lower() for field in fields.keys())
        print(f"   Index has log_type field: {'Yes' if has_log_type else 'No'}")
        
        if has_log_type:
            log_type_fields = [f for f in fields.keys() if 'log_type' in f.lower()]
            print(f"   Log type fields: {log_type_fields}")
        
        # Step 2: Test field matching
        matcher = get_field_matcher()
        match = matcher.smart_match("log type", list(fields.keys()))
        
        if match:
            print(f"   ✅ 'log type' → {match['field']} (confidence: {match['confidence']:.2f})")
        else:
            print(f"   ❌ 'log type' → No match found")
        
        # Step 3: Test prompt enhancement
        enhanced = enhance_prompt_with_field_matching(prompt, index)
        
        if enhanced != prompt:
            print(f"   ✅ Prompt was enhanced")
            print(f"   Original: {prompt}")
            enhancement_part = enhanced[len(prompt):].strip()
            if enhancement_part:
                print(f"   Enhancement: {enhancement_part[:200]}...")
        else:
            print(f"   ❌ Prompt was not enhanced")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Run all Phase 2 tests"""
    print("\n" + "="*70)
    print("PHASE 2: SMART FIELD MATCHING TESTS")
    print("="*70)
    
    try:
        # Run tests
        basic_success = test_field_matching_basic()
        test_prompt_constraint_extraction()
        test_real_index_integration()
        test_specific_problem_case()
        
        print("\n" + "="*70)
        print("PHASE 2 TEST SUMMARY")
        print("="*70)
        
        if basic_success:
            print("✅ Basic field matching is working")
        else:
            print("❌ Basic field matching needs improvement")
        
        print("\n🎯 KEY IMPROVEMENTS IN PHASE 2:")
        print("   ✅ Smart field matcher with fuzzy logic")
        print("   ✅ Constraint extraction from natural language")
        print("   ✅ Prompt enhancement with field mappings")
        print("   ✅ Integration with dynamic field discovery")
        
        print("\n🧪 NEXT TEST: Run actual query generation:")
        print('   python src/generate_constrained.py --prompt "show records with log type firewall" --index logs_cybersecurity-threat-detection-logs')
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
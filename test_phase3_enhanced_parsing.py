#!/usr/bin/env python3
"""
Test script for Phase 3: Enhanced Prompt Parser & Complex Query Support
Tests boolean logic, negations, ranges, and complex natural language patterns
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.generators.field_matcher import get_field_matcher
from src.generators.constrained import enhance_prompt_with_field_matching

def test_complex_patterns():
    """Test enhanced pattern matching"""
    print("\n" + "="*70)
    print("PHASE 3 TEST: Enhanced Pattern Matching")
    print("="*70)
    
    available_fields = [
        'action', 'action.keyword',
        'log_type', 'log_type.keyword', 
        'source_ip', 'dest_ip',
        'src_port', 'dst_port',
        'user_agent', 'user_agent.keyword',
        'timestamp', '@timestamp',
        'bytes_transferred', 'packet_count',
        'threat_label', 'threat_label.keyword',
        'severity', 'protocol'
    ]
    
    matcher = get_field_matcher()
    
    test_cases = [
        # Enhanced field-value patterns
        {
            "prompt": 'show events with log type "firewall" and action blocked',
            "expected_constraints": 2
        },
        {
            "prompt": "find traffic from source ip 10.0.0.1 to destination ip 192.168.1.100",
            "expected_constraints": 2
        },
        {
            "prompt": "bytes transferred greater than 1000000",
            "expected_constraints": 1,
            "expected_types": ["range"]
        },
        {
            "prompt": "severity between 5 and 8",
            "expected_constraints": 1,
            "expected_types": ["range"]
        },
        {
            "prompt": "threat level high or critical",
            "expected_constraints": 1,
            "has_or": True
        },
        {
            "prompt": "exclude user admin and not protocol tcp",
            "expected_constraints": 2,
            "has_not": True
        }
    ]
    
    print("\n1. Testing Enhanced Pattern Matching:")
    
    for i, test_case in enumerate(test_cases, 1):
        prompt = test_case["prompt"]
        expected = test_case["expected_constraints"]
        
        print(f"\n   Test {i}: '{prompt}'")
        
        # Test constraint extraction
        constraints = matcher.extract_field_value_pairs(prompt, available_fields)
        negated = matcher.extract_negated_constraints(prompt, available_fields)
        ranges = matcher.extract_range_constraints(prompt, available_fields)
        
        total_constraints = len(constraints) + len(negated) + len(ranges)
        
        print(f"   Found {total_constraints} total constraints:")
        
        for constraint in constraints:
            field = constraint['field_match']['field']
            value = constraint['value']
            original = constraint['original_text']
            print(f"      - Regular: '{original}' → {field}:'{value}'")
        
        for constraint in negated:
            field = constraint['field_match']['field']
            value = constraint.get('value', 'any')
            original = constraint['original_text']
            print(f"      - Negated: '{original}' → must_not {field}:'{value}'")
        
        for constraint in ranges:
            field = constraint['field_match']['field']
            range_type = constraint['range_type']
            original = constraint['original_text']
            if range_type == 'between':
                print(f"      - Range: '{original}' → range {field} [{constraint['value_min']} TO {constraint['value_max']}]")
            else:
                print(f"      - Range: '{original}' → range {field} {range_type}:{constraint['value']}")
        
        # Check results
        if total_constraints >= expected:
            print(f"      ✅ Expected {expected}, found {total_constraints}")
        else:
            print(f"      ❌ Expected {expected}, found {total_constraints}")

def test_boolean_logic_analysis():
    """Test boolean logic detection"""
    print("\n" + "="*70)
    print("PHASE 3 TEST: Boolean Logic Analysis")
    print("="*70)
    
    matcher = get_field_matcher()
    
    test_prompts = [
        ("simple AND: show logs with type firewall and action blocked", "AND", "simple"),
        ("OR logic: find events with severity high or critical", "OR", "complex"),
        ("NOT logic: exclude user admin and not protocol tcp", "NOT", "complex"),
        ("complex: show (type firewall or type dns) and not user admin", "NOT", "complex"),  # Has both OR and NOT
        ("simple single: find logs with type error", "AND", "simple")
    ]
    
    print("\n2. Testing Boolean Logic Detection:")
    
    for prompt, expected_logic, expected_complexity in test_prompts:
        print(f"\n   Testing: '{prompt}'")
        
        logic = matcher.analyze_boolean_logic(prompt)
        
        print(f"      Detected logic: {logic['primary_logic']}")
        print(f"      Complexity: {logic['complexity']}")
        print(f"      Has AND: {logic['has_and']}, OR: {logic['has_or']}, NOT: {logic['has_not']}")
        
        logic_correct = logic['primary_logic'] == expected_logic
        complexity_correct = logic['complexity'] == expected_complexity
        
        status = "✅" if (logic_correct and complexity_correct) else "❌"
        print(f"      {status} Expected: {expected_logic}/{expected_complexity}")

def test_enhanced_prompt_generation():
    """Test the enhanced prompt generation with complex patterns"""
    print("\n" + "="*70)
    print("PHASE 3 TEST: Enhanced Prompt Generation")
    print("="*70)
    
    complex_prompts = [
        {
            "prompt": 'show logs with log type firewall and bytes transferred greater than 100000',
            "description": "Regular constraint + Range constraint"
        },
        {
            "prompt": "find events with action blocked or denied but exclude user admin",
            "description": "OR logic + Negation"
        },
        {
            "prompt": "severity between 3 and 7 and protocol tcp but not from source ip 10.0.0.1",
            "description": "Range + Regular + Negation"
        }
    ]
    
    print("\n3. Testing Enhanced Prompt Generation:")
    
    for i, test_case in enumerate(complex_prompts, 1):
        prompt = test_case["prompt"]
        description = test_case["description"]
        
        print(f"\n   Test {i}: {description}")
        print(f"   Prompt: '{prompt}'")
        
        try:
            enhanced = enhance_prompt_with_field_matching(prompt, 'logs_cybersecurity-threat-detection-logs')
            
            if enhanced != prompt:
                print(f"      ✅ Prompt was enhanced")
                
                # Show key parts of enhancement
                enhancement_lines = enhanced.split('\n')
                in_mappings = False
                mapping_count = 0
                
                for line in enhancement_lines:
                    if 'MANDATORY FIELD MAPPINGS' in line:
                        in_mappings = True
                    elif '=====' in line and in_mappings:
                        in_mappings = False
                    elif in_mappings and '→' in line and 'MUST use' in line:
                        mapping_count += 1
                        print(f"         {line.strip()}")
                
                print(f"      Found {mapping_count} field mappings")
                
                # Check for boolean logic detection
                if 'BOOLEAN LOGIC:' in enhanced:
                    logic_line = next(line for line in enhancement_lines if 'BOOLEAN LOGIC:' in line)
                    print(f"      Boolean Logic: {logic_line.split(':', 1)[1].strip()}")
                
                # Check for constraint types
                if 'NEGATED CONSTRAINTS' in enhanced:
                    print(f"      ✅ Detected negated constraints")
                if 'RANGE CONSTRAINTS' in enhanced:
                    print(f"      ✅ Detected range constraints")
                    
            else:
                print(f"      ⚠️  Prompt was not enhanced (no constraints detected)")
                
        except Exception as e:
            print(f"      ❌ Error: {e}")

def test_real_world_examples():
    """Test with realistic cybersecurity queries"""
    print("\n" + "="*70)
    print("PHASE 3 TEST: Real-World Cybersecurity Queries")
    print("="*70)
    
    realistic_queries = [
        "Show all firewall events where action is blocked and source IP is not from internal networks",
        "Find malware detections with severity high or critical but exclude false positives",
        "Display network traffic with bytes transferred greater than 1MB and protocol TCP",
        "Show failed authentication attempts where user is not service account and attempts greater than 5",
        "Find DDoS attacks or port scans targeting our web servers between 2017-07-01 and 2017-07-31"
    ]
    
    print("\n4. Testing Real-World Cybersecurity Queries:")
    
    for i, query in enumerate(realistic_queries, 1):
        print(f"\n   Query {i}: {query}")
        
        try:
            enhanced = enhance_prompt_with_field_matching(query, 'logs_cybersecurity-threat-detection-logs')
            
            if enhanced != query:
                print(f"      ✅ Successfully parsed complex query")
                
                # Count different constraint types
                regular_count = enhanced.count('MUST use field')
                negated_count = enhanced.count('must_not')
                range_count = enhanced.count('range')
                
                print(f"         Regular constraints: {regular_count}")
                print(f"         Negated constraints: {negated_count}")
                print(f"         Range constraints: {range_count}")
                
                if 'BOOLEAN LOGIC:' in enhanced:
                    print(f"         ✅ Boolean logic detected")
                    
            else:
                print(f"      ⚠️  Query not enhanced (may be too complex for current patterns)")
                
        except Exception as e:
            print(f"      ❌ Error processing query: {e}")

def main():
    """Run all Phase 3 tests"""
    print("\n" + "="*80)
    print("PHASE 3: ENHANCED PROMPT PARSER & COMPLEX QUERY SUPPORT")
    print("="*80)
    
    try:
        test_complex_patterns()
        test_boolean_logic_analysis()
        test_enhanced_prompt_generation()
        test_real_world_examples()
        
        print("\n" + "="*80)
        print("PHASE 3 TEST SUMMARY")
        print("="*80)
        
        print("\n🎯 KEY ENHANCEMENTS IN PHASE 3:")
        print("   ✅ Enhanced pattern matching with natural language support")
        print("   ✅ Boolean logic detection (AND, OR, NOT)")
        print("   ✅ Range constraint support (greater than, less than, between)")
        print("   ✅ Negation handling (exclude, not, without)")
        print("   ✅ Complex prompt analysis and structured guidance to LLM")
        print("   ✅ Cybersecurity-specific pattern recognition")
        
        print("\n📈 IMPROVEMENTS OVER PHASE 2:")
        print("   • More sophisticated field-value extraction")
        print("   • Boolean logic awareness and instruction generation")
        print("   • Range query support for numeric fields")
        print("   • Negation constraint detection")
        print("   • Enhanced LLM instruction compliance")
        
        print("\n🧪 NEXT: Test actual query generation with complex prompts:")
        print('   python src/generate_constrained.py --prompt "logs with severity > 5 and not user admin" --index logs_cybersecurity-threat-detection-logs')
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
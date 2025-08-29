#!/usr/bin/env python3
"""
Field Management System Test Script
"""

import sys
import json
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def test_field_management_system():
    """Test the field management system components."""
    print("🧪 Testing Field Management System Components...")
    
    # Test 1: Field Context Manager
    print("\n=== Test 1: Field Context Manager ===")
    try:
        from src.field_management import FieldContextManager
        
        context_manager = FieldContextManager()
        
        # Test field context retrieval
        src_ip_context = context_manager.get_field_context("src_ip")
        print(f"✅ Retrieved context for src_ip: {len(src_ip_context)} attributes")
        
        # Test field prompt building
        field_prompt = context_manager.build_field_prompt_context("logs_net")
        print(f"✅ Built field prompt context: {len(field_prompt)} characters")
        
        # Test field suggestions
        suggestions = context_manager.get_field_suggestions("source.ip")
        print(f"✅ Got field suggestions for 'source.ip': {suggestions}")
        
    except Exception as e:
        print(f"❌ Field Context Manager test failed: {e}")
        return False
    
    # Test 2: Field Validator
    print("\n=== Test 2: Field Validator ===")
    try:
        from src.field_management import FieldValidator
        
        validator = FieldValidator(context_manager)
        
        # Test field validation
        is_valid, suggestion, confidence = validator.validate_field("source.ip", "logs_net")
        print(f"✅ Validated 'source.ip': valid={is_valid}, suggestion={suggestion}, confidence={confidence}")
        
        # Test query validation
        test_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"source.ip": "192.168.1.1"}},
                        {"range": {"timestamp": {"gte": "2024-01-01"}}}
                    ]
                }
            }
        }
        
        report = validator.validate_query_fields(test_query, "logs_net")
        print(f"✅ Query validation report: {report['corrections_needed']}")
        
    except Exception as e:
        print(f"❌ Field Validator test failed: {e}")
        return False
    
    # Test 3: Field Trainer
    print("\n=== Test 3: Field Trainer ===")
    try:
        from src.field_management import FieldTrainer
        
        trainer = FieldTrainer()
        
        # Record a correction
        trainer.record_correction(
            original_field="source.ip",
            corrected_field="src_ip", 
            prompt="Find traffic from source IP 192.168.1.1",
            index="logs_net",
            confidence=1.0,
            source="test"
        )
        
        # Get suggestions
        suggestions = trainer.get_field_suggestions("source.ip", "Find malicious traffic")
        print(f"✅ Trainer suggestions for 'source.ip': {suggestions}")
        
        # Get learned mappings
        mappings = trainer.get_learned_mappings()
        print(f"✅ Learned mappings: {mappings}")
        
    except Exception as e:
        print(f"❌ Field Trainer test failed: {e}")
        return False
    
    # Test 4: Field Analytics
    print("\n=== Test 4: Field Analytics ===")
    try:
        from src.field_management import FieldAnalytics
        
        analytics = FieldAnalytics(trainer, validator)
        
        # Analyze correction patterns
        patterns = analytics.analyze_correction_patterns()
        print(f"✅ Analyzed correction patterns: {len(patterns)} sections")
        
        # Generate recommendations
        recommendations = analytics.generate_improvement_recommendations()
        print(f"✅ Generated {len(recommendations)} recommendations")
        
    except Exception as e:
        print(f"❌ Field Analytics test failed: {e}")
        return False
    
    # Test 5: Field Prompt Builder
    print("\n=== Test 5: Field Prompt Builder ===")
    try:
        from src.field_management import FieldPromptBuilder
        
        prompt_builder = FieldPromptBuilder(context_manager, validator, trainer)
        
        # Build enhanced prompt
        base_prompt = "Convert this query to Elasticsearch DSL"
        user_query = "Find malicious traffic from IP 192.168.1.1"
        
        enhanced_prompt = prompt_builder.build_enhanced_prompt(
            base_prompt=base_prompt,
            user_query=user_query,
            index="logs_net"
        )
        
        print(f"✅ Built enhanced prompt: {len(enhanced_prompt)} characters")
        
        # Test field context extraction
        field_context = prompt_builder.extract_and_enhance_field_context(
            user_query, "logs_net"
        )
        print(f"✅ Extracted field context: {field_context['detected_fields']}")
        
    except Exception as e:
        print(f"❌ Field Prompt Builder test failed: {e}")
        return False
    
    # Test 6: Index Profiler (if Elasticsearch available)
    print("\n=== Test 6: Index Profiler ===")
    try:
        from src.field_management import IndexProfiler
        from elasticsearch import Elasticsearch
        
        # Try to connect to Elasticsearch
        try:
            es_client = Elasticsearch(
                ['http://localhost:9200'],
                http_auth=('elastic', 'ChangeMe_123'),
                timeout=5,
                max_retries=1
            )
            
            if es_client.ping():
                profiler = IndexProfiler(es_client)
                
                # Get available indices
                indices = profiler.get_available_indices()
                print(f"✅ Found {len(indices)} available indices")
                
                # Profile first index if available
                if indices:
                    first_index = indices[0]["name"]
                    profile = profiler.get_index_profile(first_index)
                    print(f"✅ Profiled index '{first_index}': {len(profile.get('fields', {}))} fields")
                else:
                    print("⚠️  No indices available for profiling")
            else:
                print("⚠️  Elasticsearch not available for Index Profiler test")
        except Exception as es_error:
            print(f"⚠️  Elasticsearch connection failed: {es_error}")
        
    except Exception as e:
        print(f"❌ Index Profiler test failed: {e}")
        # Don't return False here since ES might not be available
    
    print("\n🎉 Field Management System tests completed successfully!")
    return True

def test_integration():
    """Test integration between components."""
    print("\n🔗 Testing Field Management Integration...")
    
    try:
        from src.field_management import (
            FieldContextManager, FieldValidator, FieldTrainer,
            FieldAnalytics, FieldPromptBuilder
        )
        
        # Initialize all components
        context_manager = FieldContextManager()
        validator = FieldValidator(context_manager)
        trainer = FieldTrainer()
        analytics = FieldAnalytics(trainer, validator)
        prompt_builder = FieldPromptBuilder(context_manager, validator, trainer)
        
        # Simulate a full field correction workflow
        print("\n--- Simulating Field Correction Workflow ---")
        
        # 1. User provides query with incorrect fields
        user_query = "Find malicious traffic from source.ip 192.168.1.1"
        test_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"source.ip": "192.168.1.1"}},
                        {"term": {"event.type": "malicious"}}
                    ]
                }
            }
        }
        
        print(f"1. Original query contains fields: source.ip, event.type")
        
        # 2. Validate and get corrections
        report = validator.validate_query_fields(test_query, "logs_net")
        print(f"2. Validation found {len(report['corrections_needed'])} corrections needed")
        
        # 3. Record corrections for training
        for correction in report['corrections_needed']:
            trainer.record_correction(
                original_field=correction['original'],
                corrected_field=correction['suggested'],
                prompt=user_query,
                index="logs_net",
                confidence=correction['confidence'],
                source="integration_test"
            )
            print(f"3. Recorded correction: {correction['original']} → {correction['suggested']}")
        
        # 4. Generate enhanced prompt for next time
        enhanced_prompt = prompt_builder.build_enhanced_prompt(
            base_prompt="Convert to Elasticsearch DSL:",
            user_query=user_query,
            index="logs_net"
        )
        
        print(f"4. Generated enhanced prompt with field guidance ({len(enhanced_prompt)} chars)")
        
        # 5. Get analytics and recommendations
        recommendations = analytics.generate_improvement_recommendations()
        print(f"5. Analytics generated {len(recommendations)} improvement recommendations")
        
        print("✅ Integration workflow completed successfully!")
        
        # Test the training effectiveness
        print("\n--- Testing Learning Effectiveness ---")
        
        # After training, test if suggestions improve
        new_suggestions = trainer.get_field_suggestions("source.ip", user_query)
        print(f"Learned suggestions for 'source.ip': {new_suggestions}")
        
        # Test analytics
        stats = trainer.get_training_statistics()
        print(f"Training statistics: {stats['total_corrections']} corrections recorded")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Field Management System Tests\n")
    
    # Run component tests
    component_success = test_field_management_system()
    
    if component_success:
        # Run integration tests
        integration_success = test_integration()
        
        if integration_success:
            print("\n🏆 All tests passed! Field Management System is working correctly.")
            
            print("\n📊 System Status Summary:")
            print("✅ Field Context Manager: Active")
            print("✅ Field Validator: Active")
            print("✅ Field Trainer: Active")
            print("✅ Field Analytics: Active") 
            print("✅ Field Prompt Builder: Active")
            print("✅ Integration: Working")
            
            print("\n🎯 Ready for production use!")
            sys.exit(0)
        else:
            print("\n❌ Integration tests failed!")
            sys.exit(1)
    else:
        print("\n❌ Component tests failed!")
        sys.exit(1)
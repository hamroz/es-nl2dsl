#!/usr/bin/env python3
"""Test script to verify enhanced evaluation works with all models"""

from src.enhanced_evaluation import EnhancedEvaluator

def test_model_generation():
    """Test that models can generate queries successfully"""
    evaluator = EnhancedEvaluator()
    
    # Test prompt
    test_prompt = "Find all malicious events from port 443 in the last 24 hours"
    
    # Test different models and methods
    test_cases = [
        ("llama3.1:latest", "constrained"),
        ("llama3.1:latest", "rules"),
        ("llama3.1:latest", "zeroshot"),
        # Uncomment to test larger models (will take longer)
        # ("deepseek-r1:14b", "constrained"),
        # ("gpt-oss:20b", "constrained"),
    ]
    
    print("Testing Enhanced Evaluation with Different Models")
    print("=" * 60)
    
    for model, method in test_cases:
        print(f"\nTesting {model} with {method} method...")
        print("-" * 40)
        
        try:
            # Generate query
            query, gen_time, error = evaluator.generate_query_with_model(
                prompt=test_prompt,
                method=method,
                model=model,
                index="logs_net"
            )
            
            if error:
                print(f"❌ Error: {error}")
            elif query:
                print(f"✅ Success! Generated in {gen_time:.2f}s")
                print(f"Query preview: {str(query)[:200]}...")
            else:
                print(f"⚠️ No query generated")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    test_model_generation()
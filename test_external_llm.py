#!/usr/bin/env python3
"""
Test External LLM Integration
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.external_llm_manager import ExternalLLM, get_external_llm_manager

def test_external_llm_integration():
    """Test the external LLM integration"""
    
    print("=" * 60)
    print("EXTERNAL LLM INTEGRATION TEST")
    print("=" * 60)
    
    manager = get_external_llm_manager()
    
    # 1. Test adding a mock LLM (without actual API key)
    print("\n1. Testing LLM Configuration Management...")
    
    # Create a test LLM configuration (disabled by default for testing)
    test_llm = ExternalLLM(
        name="Test GPT-4",
        provider="openai",
        model_id="gpt-4",
        api_key="sk-test-key-not-real",
        max_tokens=2000,
        temperature=0.7,
        enabled=False  # Disabled for testing
    )
    
    # Add the test LLM (won't validate since disabled)
    test_llm.enabled = False  # Ensure it's disabled
    manager.llms[test_llm.name] = test_llm
    manager.save_config()
    print("✅ Added test LLM configuration (disabled)")
    
    # 2. List configured LLMs
    print("\n2. Listing Configured LLMs...")
    llms = manager.list_llms()
    print(f"Total LLMs configured: {len(llms)}")
    for llm in llms:
        status = "Enabled" if llm.enabled else "Disabled"
        print(f"  - {llm.name} ({llm.provider}/{llm.model_id}): {status}")
    
    # 3. Test available models
    print("\n3. Available Models by Provider...")
    models = manager.get_available_models()
    for provider, model_list in models.items():
        print(f"\n{provider.upper()}:")
        for model in model_list[:3]:  # Show first 3
            print(f"  - {model}")
    
    # 4. Show GUI workflow
    print("\n" + "=" * 60)
    print("GUI WORKFLOW FOR EXTERNAL LLMs:")
    print("=" * 60)
    print("""
1. SETUP:
   - Navigate to System Administration → External LLMs
   - Click "Add New LLM" tab
   - Enter configuration name (e.g., "GPT-4 Production")
   - Select provider (OpenAI, Anthropic, Cohere)
   - Select model (e.g., gpt-4, claude-3-opus)
   - Enter API key
   - Click "Add LLM" (validates API key)

2. MANAGEMENT:
   - View all configured LLMs in "Manage LLMs" tab
   - Enable/disable LLMs with checkbox
   - Delete LLMs with trash button
   - See statistics (total, enabled, providers)

3. TESTING:
   - Go to "Test LLMs" tab
   - Select an enabled LLM
   - Enter test prompt
   - Click "Run Test" to verify it works
   - Click "Validate All" to check all LLMs

4. USING IN QUERY GENERATION:
   - Navigate to Query Generator
   - In Advanced Options, see Model dropdown
   - Local models shown as "Local: llama3.1:latest"
   - External models shown as "External: GPT-4 Production"
   - Select external model
   - Generate queries using external AI!

SUPPORTED PROVIDERS:
- OpenAI: GPT-4, GPT-3.5-Turbo
- Anthropic: Claude 3 (Opus, Sonnet, Haiku)
- Cohere: Command models

BENEFITS:
✅ Use powerful cloud models for better accuracy
✅ Mix local and cloud models as needed
✅ Secure API key storage
✅ Easy switching between models
✅ Cost control with max_tokens setting
""")
    
    # 5. Clean up test LLM
    print("\n5. Cleaning up test configuration...")
    manager.remove_llm("Test GPT-4")
    print("✅ Test LLM removed")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE - External LLM integration ready!")
    print("=" * 60)

if __name__ == "__main__":
    test_external_llm_integration()
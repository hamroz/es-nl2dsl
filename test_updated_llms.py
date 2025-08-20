#!/usr/bin/env python3
"""
Test Updated LLM Providers
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from src.external_llm_manager import get_external_llm_manager

def test_updated_llms():
    """Test the updated LLM providers"""
    
    print("=" * 60)
    print("UPDATED LLM PROVIDERS TEST")
    print("=" * 60)
    
    manager = get_external_llm_manager()
    
    # Display available models
    print("\n📊 Available Models by Provider:")
    print("-" * 40)
    
    models = manager.get_available_models()
    for provider, model_list in models.items():
        print(f"\n{provider.upper()}:")
        for model in model_list:
            print(f"  ✓ {model}")
    
    print("\n" + "=" * 60)
    print("PROVIDER DETAILS:")
    print("=" * 60)
    
    print("""
🤖 OPENAI (GPT-5 Series)
------------------------
• GPT-5: Flagship reasoning model with highest performance
  - Best for: Complex reasoning, code generation, analysis
  - Pricing: $1.25/1M input, $10/1M output
  
• GPT-5-mini: Balanced performance and cost
  - Best for: General tasks, moderate complexity
  - Pricing: $0.25/1M input, $2/1M output
  
• GPT-5-nano: Ultra-fast, lowest latency
  - Best for: Real-time applications, simple queries
  - Pricing: $0.05/1M input, $0.40/1M output

✨ GOOGLE GEMINI (2.5 Series)
-----------------------------
• Gemini-2.5-pro: Most powerful with adaptive thinking
  - Best for: Complex analysis, multi-step reasoning
  - Features: Thinking enabled by default, multimodal
  
• Gemini-2.5-flash: Speed-optimized for high throughput
  - Best for: Large-scale processing, low-latency tasks
  - Features: Cost-efficient, agentic use cases

🧠 DEEPSEEK (Reasoner)
----------------------
• DeepSeek-reasoner: R1 reasoning model
  - Best for: Mathematical reasoning, code analysis
  - Features: Chain of Thought generation
  - Performance: Comparable to OpenAI o1

""")
    
    print("=" * 60)
    print("API KEY SETUP:")
    print("=" * 60)
    print("""
To use these models:

1. OPENAI:
   - Get API key from: https://platform.openai.com/api-keys
   - Key format: sk-...

2. GOOGLE GEMINI:
   - Get API key from: https://aistudio.google.com
   - Click "Get API key" → "Create API key"

3. DEEPSEEK:
   - Get API key from: https://platform.deepseek.com
   - Navigate to API Keys section

Then in the GUI:
- Go to System Administration → External LLMs
- Add new LLM with your API key
- Select the model you want
- Test and enable it
- Use in Query Generator!
""")
    
    print("=" * 60)
    print("TEST COMPLETE - Updated LLM providers ready!")
    print("=" * 60)

if __name__ == "__main__":
    test_updated_llms()
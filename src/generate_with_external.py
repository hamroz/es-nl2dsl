#!/usr/bin/env python3
"""
External LLM Generation CLI: Direct entry point for multi-provider AI query generation

This CLI entry point provides direct access to external Large Language Model providers
for query generation, enabling users to leverage state-of-the-art AI models including
OpenAI GPT-4, Anthropic Claude, Google Gemini, and others for Elasticsearch DSL
generation with enterprise-grade integration and management.

Key capabilities:
- Direct CLI access to external LLM generation engine
- Multi-provider AI model support with intelligent selection
- Advanced prompt engineering and provider-specific optimization
- Cost monitoring and budget management for API usage
- Rate limiting and API compliance management
- Integration with existing validation and security frameworks

The CLI is designed for users requiring access to cutting-edge AI capabilities
while maintaining integration with the ES-NL2DSL validation and security
framework for production deployment.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.external import main

if __name__ == "__main__":
    main()
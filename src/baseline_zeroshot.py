#!/usr/bin/env python3
"""
Zero-Shot Query Generation CLI: Direct entry point for LLM-based DSL generation

This CLI entry point provides direct access to the zero-shot query generation system,
enabling users to generate Elasticsearch DSL queries using Large Language Models without
fine-tuning or domain-specific training. It leverages the inherent capabilities of
modern LLMs to understand natural language and generate appropriate query structures.

Key capabilities:
- Direct CLI access to zero-shot generation engine
- Pure LLM-based query generation without domain constraints
- Support for multiple LLM providers and models
- Minimal preprocessing with maximum flexibility
- Baseline comparison capability for evaluation frameworks
- Integration with existing testing and benchmarking systems

The CLI is designed for research comparisons, baseline establishment, and scenarios
where unconstrained LLM generation is desired for experimental purposes.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.zero_shot import main

if __name__ == "__main__":
    main()
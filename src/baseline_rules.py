#!/usr/bin/env python3
"""
Rules-Based Query Generation CLI: Direct entry point for rule-based DSL generation

This CLI entry point provides direct access to the rules-based query generation system,
enabling users to generate Elasticsearch DSL queries using predefined rule templates
and pattern matching. It serves as a lightweight alternative to the enhanced constrained
generation method for scenarios requiring fast, deterministic query generation.

Key capabilities:
- Direct CLI access to rules-based generation engine
- Template-driven query construction with cybersecurity domain rules
- Fast execution suitable for batch processing and automation
- Deterministic output based on pattern matching algorithms
- Integration with existing evaluation and testing frameworks
- Support for all standard ES-NL2DSL parameters and configurations

The CLI is designed for automated workflows, testing scenarios, and situations
where deterministic rule-based generation is preferred over AI-powered methods.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.rules_based import main

if __name__ == "__main__":
    main()
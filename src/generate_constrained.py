#!/usr/bin/env python3
"""
Constrained Query Generation CLI: Direct entry point for enhanced constrained DSL generation

This CLI entry point provides direct access to the enhanced constrained query generation
system, serving as the primary interface for generating high-quality Elasticsearch DSL
queries with domain constraints, field validation, and security enforcement. It represents
the main production entry point for the ES-NL2DSL system's core functionality.

Key capabilities:
- Direct CLI access to enhanced constrained generation engine
- Comprehensive field validation and constraint enforcement
- Security filtering and input validation
- Integration with all system validation and evaluation frameworks
- Production-ready error handling and logging
- Support for all ES-NL2DSL parameters and configurations

The CLI is designed as the primary production interface for automated systems,
scripts, and users requiring reliable, high-quality query generation with
comprehensive validation and security enforcement.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.constrained import main

if __name__ == "__main__":
    main()
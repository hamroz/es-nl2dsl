#!/usr/bin/env python3
"""
Query Validator CLI: Direct entry point for comprehensive DSL validation

This CLI entry point provides direct access to the comprehensive query validation system,
enabling users to validate Elasticsearch DSL queries against defined rules, constraints,
and security policies. It serves as a critical quality assurance tool for ensuring
query correctness, security compliance, and performance optimization.

Key capabilities:
- Direct CLI access to comprehensive validation framework
- Rule-based validation against cybersecurity domain constraints
- Security policy enforcement with threat detection
- Performance optimization validation with cost analysis
- Field validation with schema compliance checking
- Integration with quality assurance and testing frameworks

The CLI is designed for developers, QA teams, and automated systems requiring
reliable query validation before deployment or execution.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.validator import main

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""CLI entry point for zero-shot query generation"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.generators.zero_shot import main

if __name__ == "__main__":
    main()
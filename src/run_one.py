#!/usr/bin/env python3
"""CLI entry point for single scenario evaluation"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cli.run_one import main

if __name__ == "__main__":
    main()
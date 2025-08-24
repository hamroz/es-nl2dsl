#!/usr/bin/env python3
"""Create DP indices for different epsilon values"""
import subprocess
import sys
from pathlib import Path

EPSILON_VALUES = [0.5, 1.0, 2.0]

def create_dp_index(epsilon):
    """Create a DP index for a specific epsilon value"""
    index_name = f"logs_net_dp_eps{str(epsilon).replace('.', '')}"
    
    print(f"\nCreating DP index with ε={epsilon} -> {index_name}")
    
    result = subprocess.run([
        sys.executable, "src/dp_synth.py",
        "--input", "data_raw/sample_extended.csv",
        "--index", index_name,
        "--epsilon", str(epsilon),
        "--timestamp-jitter", "30"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ Successfully created {index_name}")
        print(result.stdout.split('\n')[-5:])  # Show last few lines
        return True
    else:
        print(f"✗ Failed to create {index_name}")
        print(result.stderr)
        return False

def main():
    print("=== Creating DP Index Grid ===")
    print(f"Epsilon values: {EPSILON_VALUES}")
    
    success_count = 0
    
    for epsilon in EPSILON_VALUES:
        if create_dp_index(epsilon):
            success_count += 1
    
    print(f"\n=== Summary ===")
    print(f"Created {success_count}/{len(EPSILON_VALUES)} DP indices")
    
    if success_count == len(EPSILON_VALUES):
        print("\n✓ All DP indices created successfully!")
        print("\nTo test privacy-utility tradeoff:")
        for epsilon in EPSILON_VALUES:
            index_name = f"logs_net_dp_eps{str(epsilon).replace('.', '')}"
            print(f"  python src/run_one.py --id scan-001 --index {index_name}")
    else:
        print("\n⚠️  Some indices failed to create")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
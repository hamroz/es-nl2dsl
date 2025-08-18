#!/bin/bash

# Orchestration script for running evaluation suite

set -e  # Exit on error

echo "=== ES-NL2DSL Evaluation Suite ==="
echo "Starting at $(date)"
echo

# Create necessary directories
mkdir -p artifacts/generated
mkdir -p artifacts/results

# Check if Elasticsearch is running
echo "Checking Elasticsearch connectivity..."
python src/smoke_es.py
if [ $? -ne 0 ]; then
    echo "Error: Elasticsearch is not accessible. Please start it with: docker-compose up -d"
    exit 1
fi

# Run standard scenarios
echo
echo "=== Running Standard Scenarios ==="
for scenario in scan-001 scan-002 scan-003; do
    echo
    echo "Running scenario: $scenario"
    python src/run_one.py --id $scenario --gen
    if [ $? -eq 0 ]; then
        echo "✓ $scenario completed successfully"
    else
        echo "✗ $scenario failed"
    fi
done

# Schema drift test (if drift index exists)
echo
echo "=== Testing Schema Drift Robustness ==="
# Check if drift index exists
curl -s -u elastic:ChangeMe_123 -X HEAD "localhost:9200/logs_net_drift" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Running scan-001 against drift index..."
    python src/run_one.py --id scan-001 --index logs_net_drift --gen
    if [ $? -eq 0 ]; then
        echo "✓ Drift test completed"
    else
        echo "✗ Drift test failed (expected - schema mismatch)"
    fi
else
    echo "Skipping drift test (logs_net_drift index not found)"
fi

# DP synthetic test (if DP index exists)
echo
echo "=== Testing DP Synthetic Data ==="
# Check if DP index exists
curl -s -u elastic:ChangeMe_123 -X HEAD "localhost:9200/logs_net_dp" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Running scan-001 against DP index..."
    python src/run_one.py --id scan-001 --index logs_net_dp --gen
    if [ $? -eq 0 ]; then
        echo "✓ DP test completed"
    else
        echo "✗ DP test failed"
    fi
else
    echo "Skipping DP test (logs_net_dp index not found)"
    echo "To create DP index, run: python src/dp_synth.py"
fi

# Generate results table
echo
echo "=== Generating Results Summary ==="
python src/render_tables.py
if [ $? -eq 0 ]; then
    echo "✓ Results table generated"
else
    echo "✗ Failed to generate results table"
fi

echo
echo "=== Suite Complete ==="
echo "Finished at $(date)"
echo "Results available in artifacts/results/"
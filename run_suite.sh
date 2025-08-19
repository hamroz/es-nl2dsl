#!/bin/bash

# Orchestration script for running evaluation suite

set -e  # Exit on error

echo "=== ES-NL2DSL Evaluation Suite ==="
echo "Starting at $(date)"
echo

# Create necessary directories
mkdir -p artifacts/generated
mkdir -p artifacts/results
mkdir -p artifacts/ground_truth

# Check if Elasticsearch is running with proper HTTP status check
echo "Checking Elasticsearch connectivity..."
ES_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u elastic:ChangeMe_123 "localhost:9200/_cluster/health")
if [ "$ES_STATUS" != "200" ]; then
    echo "Error: Elasticsearch is not accessible (HTTP status: $ES_STATUS)"
    echo "Please start it with: docker-compose up -d"
    exit 1
fi

python src/smoke_es.py
if [ $? -ne 0 ]; then
    echo "Error: Elasticsearch connectivity check failed"
    exit 1
fi
echo "✓ Elasticsearch is healthy"

# Array to track results
declare -a RESULTS
PASSED=0
FAILED=0

# Generate ground truth if needed
if [ ! -f "artifacts/ground_truth/scan-001.json" ]; then
    echo
    echo "Generating ground truth for all scenarios..."
    python src/generate_ground_truth.py
fi

# Run all standard scenarios
echo
echo "=== Running Standard Scenarios ==="
ALL_SCENARIOS="scan-001 scan-002 scan-003 scan-004 scan-005 scan-006 scan-007 scan-008 scan-009 scan-010 scan-011 scan-012"

for scenario in $ALL_SCENARIOS; do
    echo
    echo "----------------------------------------"
    echo "Running scenario: $scenario"
    python src/run_one.py --id $scenario --gen
    if [ $? -eq 0 ]; then
        echo "✓ $scenario: PASS"
        RESULTS+=("$scenario: PASS")
        ((PASSED++))
    else
        echo "✗ $scenario: FAIL"
        RESULTS+=("$scenario: FAIL")
        ((FAILED++))
    fi
done

# Schema drift test (if drift index exists)
echo
echo "=== Testing Schema Drift Robustness ==="
DRIFT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u elastic:ChangeMe_123 "localhost:9200/logs_net_drift")
if [ "$DRIFT_STATUS" == "200" ]; then
    echo "Running scan-001 against drift index..."
    python src/run_one.py --id scan-001 --index logs_net_drift --gen
    if [ $? -eq 0 ]; then
        echo "✓ Drift test completed (unexpected success - schema adapted?)"
    else
        echo "✓ Drift test failed as expected (schema mismatch detected)"
    fi
else
    echo "Skipping drift test (logs_net_drift index not found - HTTP $DRIFT_STATUS)"
    echo "To create drift index, run: python src/create_drift_index.py"
fi

# DP synthetic test with epsilon grid
echo
echo "=== Testing DP Synthetic Data ==="
for epsilon in 0.5 1.0 2.0; do
    INDEX_NAME="logs_net_dp_eps$(echo $epsilon | tr -d '.')"
    DP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u elastic:ChangeMe_123 "localhost:9200/$INDEX_NAME")
    
    if [ "$DP_STATUS" == "200" ]; then
        echo "Running scan-001 against DP index (ε=$epsilon)..."
        python src/run_one.py --id scan-001 --index $INDEX_NAME --gen
        if [ $? -eq 0 ]; then
            echo "✓ DP test (ε=$epsilon) completed"
        else
            echo "✗ DP test (ε=$epsilon) failed"
        fi
    else
        echo "Skipping DP test for ε=$epsilon ($INDEX_NAME not found - HTTP $DP_STATUS)"
    fi
done

# Generate results table
echo
echo "=== Generating Results Summary ==="
python src/render_tables.py
if [ $? -eq 0 ]; then
    echo "✓ Results table generated"
else
    echo "✗ Failed to generate results table"
fi

# Final summary
echo
echo "=== Suite Complete ==="
echo "Finished at $(date)"
echo
echo "Results Summary:"
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo
echo "Scenario Results:"
for result in "${RESULTS[@]}"; do
    echo "  $result"
done
echo
echo "Results available in artifacts/results/"
echo "View summary: cat artifacts/results/results_table_*.md | head -50"
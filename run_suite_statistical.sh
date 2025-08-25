#!/bin/bash

# Enhanced orchestration script for statistical evaluation suite

set -e  # Exit on error

echo "=== ES-NL2DSL Statistical Evaluation Suite ==="
echo "Starting at $(date)"
echo

# Parse arguments
RUNS_PER_SCENARIO=5
SCENARIOS="scan-001 scan-002 scan-003"  # Start with subset for testing
METHODS="constrained"
OUTPUT_DIR="artifacts/statistical_results"

while [[ $# -gt 0 ]]; do
    case $1 in
        --runs)
            RUNS_PER_SCENARIO="$2"
            shift 2
            ;;
        --scenarios)
            SCENARIOS="$2"
            shift 2
            ;;
        --methods)
            METHODS="$2"
            shift 2
            ;;
        --all-scenarios)
            SCENARIOS="scan-001 scan-002 scan-003 scan-004 scan-005 scan-006 scan-007 scan-008 scan-009 scan-010 scan-011 scan-012"
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --runs N              Number of runs per scenario (default: 5)"
            echo "  --scenarios LIST      Space-separated scenario list (default: scan-001 scan-002 scan-003)"
            echo "  --all-scenarios       Use all 12 scenarios"
            echo "  --methods LIST        Space-separated method list (default: constrained)"
            echo "  --output DIR          Output directory (default: artifacts/statistical_results)"
            echo "  -h, --help           Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Configuration:"
echo "  Runs per scenario: $RUNS_PER_SCENARIO"
echo "  Scenarios: $SCENARIOS"
echo "  Methods: $METHODS"
echo "  Output directory: $OUTPUT_DIR"
echo

# Create necessary directories
mkdir -p artifacts/generated
mkdir -p artifacts/results
mkdir -p artifacts/ground_truth
mkdir -p "$OUTPUT_DIR"

# Check if Elasticsearch is running
echo "Checking Elasticsearch connectivity..."
ES_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u elastic:ChangeMe_123 "localhost:9200/_cluster/health")
if [ "$ES_STATUS" != "200" ]; then
    echo "Error: Elasticsearch is not accessible (HTTP status: $ES_STATUS)"
    echo "Please start it with: docker-compose up -d"
    exit 1
fi

python src/utils/health_check.py
if [ $? -ne 0 ]; then
    echo "Error: Elasticsearch connectivity check failed"
    exit 1
fi
echo "✓ Elasticsearch is healthy"

# Generate ground truth if needed
if [ ! -f "artifacts/ground_truth/scan-001.json" ]; then
    echo
    echo "Generating ground truth for all scenarios..."
    python src/cli/generate_ground_truth.py
fi

# Array to track results
declare -a STATISTICAL_RESULTS
TOTAL_RUNS=0
SUCCESSFUL_RUNS=0

echo
echo "=== Running Statistical Evaluation ==="

for method in $METHODS; do
    echo
    echo "Method: $method"
    echo "----------------------------------------"
    
    for scenario in $SCENARIOS; do
        echo
        echo "Running statistical evaluation: $scenario with $method ($RUNS_PER_SCENARIO runs)"
        
        # Run multiple evaluation runs
        SCENARIO_RESULTS=()
        SCENARIO_SUCCESS=0
        
        for ((run=1; run<=RUNS_PER_SCENARIO; run++)); do
            SEED=$((42 + run))
            echo "  Run $run/$RUNS_PER_SCENARIO (seed=$SEED)"
            
            # Run evaluation
            if python src/cli/run_one.py --id "$scenario" --gen --seed "$SEED" > /tmp/eval_output_${scenario}_${method}_${run}.txt 2>&1; then
                echo "    ✓ Success"
                SCENARIO_SUCCESS=$((SCENARIO_SUCCESS + 1))
                SUCCESSFUL_RUNS=$((SUCCESSFUL_RUNS + 1))
            else
                echo "    ✗ Failed"
                # Still count as attempted
            fi
            TOTAL_RUNS=$((TOTAL_RUNS + 1))
        done
        
        # Run statistical analysis
        echo "  Analyzing $SCENARIO_SUCCESS/$RUNS_PER_SCENARIO successful runs..."
        STAT_OUTPUT="$OUTPUT_DIR/statistical_${scenario}_${method}.json"
        
        if python src/analysis/statistical_analysis.py \
            --scenario "$scenario" \
            --method "$method" \
            --runs "$RUNS_PER_SCENARIO" \
            --output "$STAT_OUTPUT"; then
            echo "  ✓ Statistical analysis saved to $STAT_OUTPUT"
            STATISTICAL_RESULTS+=("$scenario:$method:$STAT_OUTPUT")
        else
            echo "  ✗ Statistical analysis failed"
        fi
    done
done

# Generate comprehensive statistical report
echo
echo "=== Generating Comprehensive Report ==="
REPORT_FILE="$OUTPUT_DIR/comprehensive_statistical_report.json"

cat > /tmp/generate_report.py << 'EOF'
import json
import sys
from pathlib import Path
sys.path.append(str(Path('.').absolute()))

from src.analysis.statistical_analysis import StatisticalAnalyzer
import glob

# Load all statistical results
statistical_results = []
analyzer = StatisticalAnalyzer()

# Find all statistical result files
result_files = glob.glob(sys.argv[1] + "/statistical_*.json")

for file_path in result_files:
    try:
        with open(file_path) as f:
            data = json.load(f)
        
        # Convert back to MultiRunEvaluationResult for analysis
        from src.analysis.statistical_analysis import MultiRunEvaluationResult, StatisticalResult
        
        # This is a simplified version - in practice you'd reconstruct the full objects
        statistical_results.append(data)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")

# Generate comprehensive report
if statistical_results:
    report = {
        "timestamp": __import__("time").time(),
        "summary": {
            "total_scenario_method_combinations": len(statistical_results),
            "total_individual_runs": sum(r.get("sample_size", 0) for r in statistical_results)
        },
        "statistical_results": statistical_results
    }
    
    with open(sys.argv[2], 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Comprehensive report saved to {sys.argv[2]}")
else:
    print("No statistical results found")
EOF

if python /tmp/generate_report.py "$OUTPUT_DIR" "$REPORT_FILE"; then
    echo "✓ Comprehensive statistical report generated: $REPORT_FILE"
else
    echo "✗ Failed to generate comprehensive report"
fi

# Final summary
echo
echo "=== Statistical Evaluation Complete ==="
echo "Finished at $(date)"
echo
echo "Summary:"
echo "  Total runs: $TOTAL_RUNS"
echo "  Successful runs: $SUCCESSFUL_RUNS"
echo "  Success rate: $(( SUCCESSFUL_RUNS * 100 / TOTAL_RUNS ))%"
echo "  Statistical result files: ${#STATISTICAL_RESULTS[@]}"
echo
echo "Results available in: $OUTPUT_DIR"
echo "View comprehensive report: cat $REPORT_FILE | head -50"

# Cleanup
rm -f /tmp/eval_output_*.txt
rm -f /tmp/generate_report.py

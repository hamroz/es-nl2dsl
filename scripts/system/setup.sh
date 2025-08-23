#!/bin/bash

# Complete setup script for ES-NL2DSL system
# Run this after starting Elasticsearch with docker-compose up -d

set -e

# Get the project root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "=== ES-NL2DSL Setup Script ==="
echo "Setting up complete evaluation environment..."
echo "📍 Project root: $PROJECT_ROOT"
echo

# Check if Elasticsearch is running
echo "1. Checking Elasticsearch connectivity..."
ES_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -u elastic:ChangeMe_123 "localhost:9200/_cluster/health" || echo "000")
if [ "$ES_STATUS" != "200" ]; then
    echo "❌ Elasticsearch not accessible (HTTP $ES_STATUS)"
    echo "Please start Elasticsearch first:"
    echo "  docker-compose up -d"
    echo "  # Wait 30-60 seconds for startup"
    exit 1
fi
echo "✅ Elasticsearch is running"

# Setup reader user and roles
echo
echo "2. Setting up Elasticsearch users and roles..."
"$SCRIPT_DIR/setup_reader.sh"
echo "✅ Reader user configured"

# Create main index
echo
echo "3. Creating main index with mappings..."
curl -X DELETE "localhost:9200/logs_net" -u elastic:ChangeMe_123 2>/dev/null || true
curl -X PUT "localhost:9200/logs_net" -H 'Content-Type: application/json' -u elastic:ChangeMe_123 -d @"$PROJECT_ROOT/artifacts/mappings.json"
echo "✅ Main index created"

# Ingest sample data
echo
echo "4. Ingesting sample data..."
cd "$PROJECT_ROOT" && python src/ingest.py --file data/sample_extended.csv --index logs_net
echo "✅ Sample data ingested"

# Generate ground truth
echo
echo "5. Generating ground truth for all scenarios..."
cd "$PROJECT_ROOT" && python src/generate_ground_truth.py
echo "✅ Ground truth generated"

# Create schema drift index
echo
echo "6. Creating schema drift index..."
cd "$PROJECT_ROOT" && python src/create_drift_index.py
echo "✅ Schema drift index created"

# Create DP indices
echo
echo "7. Creating differential privacy indices..."
cd "$PROJECT_ROOT" && python src/create_dp_grid.py
echo "✅ DP indices created"

# Verify setup
echo
echo "8. Verifying setup..."
cd "$PROJECT_ROOT" && python src/smoke_es.py
echo "✅ Setup verification complete"

# Check Ollama
echo
echo "9. Checking Ollama model availability..."
if command -v ollama &> /dev/null; then
    if ollama list | grep -q "llama3.1:latest"; then
        echo "✅ Ollama model ready"
    else
        echo "⚠️  Ollama model not found. Please run:"
        echo "  ollama pull llama3.1:latest"
    fi
else
    echo "⚠️  Ollama not installed. Please install and run:"
    echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    echo "  ollama pull llama3.1:latest"
fi

echo
echo "=== Setup Complete! ==="
echo
echo "Quick test commands:"
echo "  python src/run_one.py --id scan-001 --gen"
echo "  ./run_suite.sh"
echo "  python src/redteam_runner.py"
echo
echo "View results:"
echo "  python src/render_tables.py"
echo "  cat artifacts/results/results_table_*.md"
echo
echo "System is ready for evaluation!"
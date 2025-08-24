# ES-NL2DSL Makefile - Convenience commands for common tasks

.PHONY: help setup start stop clean test experiment security privacy drift baseline all

# Default target
help:
	@echo "ES-NL2DSL Makefile Commands:"
	@echo ""
	@echo "Setup Commands:"
	@echo "  setup     - Complete system setup (run once after clone)"
	@echo "  start     - Start Elasticsearch"
	@echo "  stop      - Stop Elasticsearch"
	@echo "  clean     - Clean all generated artifacts"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test      - Run single test scenario"
	@echo "  all       - Run complete evaluation suite"
	@echo "  experiment - Run baseline comparison experiments"
	@echo ""
	@echo "Advanced Testing:"
	@echo "  security  - Run red team security tests"
	@echo "  privacy   - Run privacy-utility analysis"
	@echo "  drift     - Test schema drift robustness"
	@echo "  baseline  - Compare all baseline methods"
	@echo ""
	@echo "Analysis:"
	@echo "  results   - Generate results tables"
	@echo "  status    - Check system status"

# Setup and infrastructure
setup:
	@echo "Setting up ES-NL2DSL system..."
	./setup.sh

start:
	@echo "Starting Elasticsearch..."
	docker-compose up -d
	@echo "Waiting for Elasticsearch to be ready..."
	@sleep 30
	@curl -s -u elastic:ChangeMe_123 http://localhost:9200/_cluster/health | grep -q "green\|yellow" && echo "✅ Elasticsearch ready" || echo "❌ Elasticsearch not ready"

stop:
	@echo "Stopping Elasticsearch..."
	docker-compose down

clean:
	@echo "Cleaning generated artifacts..."
	rm -rf artifacts/generated/*
	rm -rf artifacts/results/*.json
	rm -rf artifacts/results/*.csv
	rm -rf artifacts/results/*.md
	@echo "✅ Artifacts cleaned"

# Testing commands
test:
	@echo "Running single test scenario (scan-001)..."
	python src/cli/run_one.py --id scan-001 --gen

all:
	@echo "Running complete evaluation suite..."
	./run_suite.sh

experiment:
	@echo "Running baseline comparison experiments..."
	python src/analysis/experiments.py

# Advanced testing
security:
	@echo "Running red team security tests..."
	python src/analysis/security.py

privacy:
	@echo "Running privacy-utility analysis..."
	@for eps in 05 10 20; do \
		echo "Testing ε=0.$${eps#0}..."; \
		python src/cli/run_one.py --id scan-001 --index logs_net_dp_eps$$eps --gen; \
	done

drift:
	@echo "Testing schema drift robustness..."
	python src/cli/run_one.py --id scan-001 --index logs_net_drift --gen

baseline:
	@echo "Comparing baseline methods..."
	@echo "1. Rules baseline..."
	python src/generators/rules_based.py --prompt "Find malicious events on 2017-07-04" --task-id baseline-test
	@echo "2. Zero-shot baseline..."
	python src/generators/zero_shot.py --prompt "Find malicious events on 2017-07-04" --task-id baseline-test
	@echo "3. Constrained method..."
	python src/cli/run_one.py --id scan-001 --gen

# Analysis
results:
	@echo "Generating results tables..."
	python src/analysis/tables.py
	@echo "View results:"
	@echo "  cat artifacts/results/results_table_*.md"

status:
	@echo "=== System Status ==="
	@echo "Elasticsearch:"
	@curl -s -u elastic:ChangeMe_123 http://localhost:9200/_cluster/health 2>/dev/null | grep -q "cluster_name" && echo "  ✅ Running" || echo "  ❌ Not running"
	@echo "Ollama:"
	@command -v ollama >/dev/null 2>&1 && echo "  ✅ Installed" || echo "  ❌ Not installed"
	@ollama list 2>/dev/null | grep -q "llama3.1:latest" && echo "  ✅ Model ready" || echo "  ❌ Model not available"
	@echo "Indices:"
	@curl -s -u elastic:ChangeMe_123 http://localhost:9200/_cat/indices 2>/dev/null | grep -q "logs_net" && echo "  ✅ Main index exists" || echo "  ❌ Main index missing"
	@curl -s -u elastic:ChangeMe_123 http://localhost:9200/_cat/indices 2>/dev/null | grep -q "logs_net_drift" && echo "  ✅ Drift index exists" || echo "  ❌ Drift index missing"

# Quick demo for examiners
demo:
	@echo "=== ES-NL2DSL Quick Demo ==="
	@echo "1. Testing basic query generation..."
	python src/run_one.py --id scan-001 --gen
	@echo ""
	@echo "2. Testing ambiguity detection..."
	python src/generate_constrained.py --prompt "Find events from yesterday" --task-id demo-ambiguous
	@echo ""
	@echo "3. Testing validation..."
	python src/validator.py --dsl artifacts/queries/good.json || true
	@echo ""
	@echo "Demo complete! Check artifacts/results/ for outputs."
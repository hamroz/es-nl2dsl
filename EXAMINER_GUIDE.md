# Examiner Quick Start Guide

This guide provides the fastest path to evaluate the ES-NL2DSL system for thesis examination.

## ⚡ 5-Minute Quick Start

### Prerequisites Check
```bash
# Verify requirements (2 minutes)
docker --version    # Should show Docker 20.0+
python3 --version   # Should show Python 3.10+
curl --version      # Should show curl 7.0+
```

### Installation & Setup (2 minutes)
```bash
# 1. Clone and enter directory
git clone <repository-url>
cd es-nl2dsl

# 2. Start Elasticsearch
docker-compose up -d

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Ollama model (one-time, may take 10+ minutes)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:latest

# 5. Complete setup
./setup.sh
```

### Basic Verification (1 minute)
```bash
# Test single query generation
make test

# Check system status
make status
```

## 🔍 Core Functionality Demonstration

### 1. Natural Language Translation (30 seconds)
```bash
# Generate query from natural language
python src/run_one.py --id scan-001 --gen

# Expected: Perfect F1 score, valid Elasticsearch query
```

### 2. Security Validation (30 seconds)
```bash
# Test ambiguity detection
python src/generate_constrained.py --prompt "Find events from yesterday" --task-id ambiguous

# Expected: Abstention with clear reason
```

### 3. Privacy Preservation (1 minute)
```bash
# Test privacy-utility tradeoff
python src/run_one.py --id scan-001 --index logs_net_dp_eps05

# Expected: Lower F1 score due to noise, but valid results
```

### 4. Robustness Testing (1 minute)
```bash
# Test schema drift handling
python src/run_one.py --id scan-001 --index logs_net_drift

# Expected: Graceful failure due to field mismatches
```

## 📊 Comprehensive Evaluation

### Full System Test (5-10 minutes)
```bash
# Run complete evaluation suite
./run_suite.sh

# Expected: 
# - 12 scenarios tested
# - Pass/fail summary
# - Results in artifacts/results/
```

### Baseline Comparison (3-5 minutes)
```bash
# Compare all methods
make baseline

# Expected: Rules < Zero-shot < Constrained accuracy
```

### Security Assessment (2-3 minutes)
```bash
# Test adversarial prompt resistance
python src/redteam_runner.py

# Expected: >95% block rate on adversarial prompts
```

## 📈 Results Inspection

### View Generated Queries
```bash
# See constrained generation output
cat artifacts/queries/candidate_scan-001.json

# See rules baseline output
cat artifacts/generated/rules_scan-001.json
```

### View Metrics
```bash
# Generate comprehensive results table
python src/render_tables.py

# View summary
cat artifacts/results/results_table_*.md | head -30
```

### Check Security Logs
```bash
# View validation events
cat artifacts/results/validator_events.jsonl | tail -10

# View red team results
cat artifacts/results/redteam_results.json
```

## 🎯 Key Evaluation Points

### 1. **Accuracy** (scan-001 to scan-012)
- **Metric**: F1 scores in results table
- **Expected**: >0.8 for most scenarios
- **Location**: `artifacts/results/results_table_*.md`

### 2. **Security** (Red team testing)
- **Metric**: Block rate percentage
- **Expected**: ≥95% adversarial prompts blocked
- **Location**: `artifacts/results/redteam_results.json`

### 3. **Privacy** (DP indices)
- **Metric**: F1 degradation with lower ε
- **Expected**: ε=0.5 < ε=1.0 < ε=2.0 utility
- **Command**: Compare DP results across epsilon values

### 4. **Robustness** (Schema drift)
- **Metric**: Graceful failure handling
- **Expected**: Clear error messages, no crashes
- **Command**: `python src/run_one.py --id scan-001 --index logs_net_drift`

## 🐛 Common Issues & Solutions

### Elasticsearch Won't Start
```bash
# Check port availability
sudo lsof -i :9200

# Reset if needed
docker-compose down -v
docker-compose up -d
```

### Ollama Model Issues
```bash
# Verify model availability
ollama list

# Re-download if needed
ollama pull llama3.1:latest
```

### Generation Timeouts
```bash
# Check Ollama is running
ollama serve

# Try simpler model
ollama pull llama3.2:latest
# Update model in scripts if needed
```

## 📝 Expected Outputs

### Successful Single Query
```
Running scenario: scan-001
Prompt: Find events labeled malicious on 2017-07-04.
Generating query...
Using candidate: artifacts/queries/candidate_scan-001.json
Validating query...
Validation passed
Evaluating queries...

Results Summary:
  Jaccard Similarity: 1.000
  F1 Score: 1.000
  Precision: 1.000
  Recall: 1.000
  Validator Status: PASS
```

### Successful Ambiguity Detection
```
Generation abstained: Ambiguous prompt: Ambiguous time reference detected: 'yesterday'
Metrics: 0 attempts, 0.00s
```

### Successful Suite Run
```
=== Suite Complete ===
Results Summary:
  Passed: 12
  Failed: 0

Scenario Results:
  scan-001: PASS
  scan-002: PASS
  ...
  scan-012: PASS
```

## 📚 Documentation Structure

- **README.md**: Complete user guide and system overview
- **MODELS.md**: Model dependencies and configuration
- **EXAMINER_GUIDE.md**: This quick start guide
- **CLAUDE.md**: Development instructions for AI assistants
- **environment.yml / requirements.txt**: Exact dependency versions

## 💡 Advanced Exploration

### Custom Queries
```bash
# Test your own prompts
python src/generate_constrained.py --prompt "YOUR_QUERY_HERE" --task-id custom
```

### Add New Scenarios
```bash
# Edit tasks/prompts.yaml
# Regenerate ground truth
python src/generate_ground_truth.py
```

### Performance Analysis
```bash
# Check generation metrics
ls artifacts/generated/*.metrics.json
cat artifacts/generated/scan-001.metrics.json
```

---

**For questions or issues during examination, check the Troubleshooting section in README.md or review the logged outputs in artifacts/results/**
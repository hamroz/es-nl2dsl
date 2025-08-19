# ES-NL2DSL: Natural Language to Elasticsearch DSL Translation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Elasticsearch 8.11](https://img.shields.io/badge/elasticsearch-8.11-orange.svg)](https://www.elastic.co/)

A production-ready framework for translating natural language queries into Elasticsearch DSL with built-in security, privacy preservation, and comprehensive evaluation capabilities.

## 🎯 Overview

ES-NL2DSL enables secure translation of human-readable queries into Elasticsearch queries for cybersecurity log analysis. The system provides:

- **Constrained Generation**: LLM-based translation with schema and security validation
- **Security Guardrails**: Ambiguity detection, adversarial prompt blocking, field validation
- **Privacy Preservation**: Differential privacy with configurable ε parameters
- **Robustness Testing**: Schema drift detection and adaptation
- **Comprehensive Evaluation**: 12 test scenarios with multiple baselines

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Web GUI](#-web-gui)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [Basic Usage](#-basic-usage)
- [Advanced Features](#-advanced-features)
- [Evaluation & Testing](#-evaluation--testing)
- [Architecture](#-architecture)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## 🚀 Quick Start

```bash
# 1. Start Elasticsearch
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup Elasticsearch
./setup.sh

# 4. Run a single query
python src/run_one.py --id scan-001 --gen

# 5. Run full evaluation suite
./run_suite.sh
```

## 🌐 Web GUI

ES-NL2DSL now includes a comprehensive **Streamlit-based web interface** that provides an intuitive way to interact with all system capabilities through your browser.

### Features
- **🤖 Interactive Query Generator** - Convert natural language to DSL with real-time validation
- **📊 Evaluation Dashboard** - Run comprehensive evaluations with parallel processing
- **🛡️ Security Testing Panel** - Test against adversarial prompts with live monitoring
- **🔒 Privacy Analysis Tools** - Visualize privacy-utility tradeoffs across epsilon values
- **⚙️ System Administration** - Complete system monitoring and management

### Quick Start GUI

```bash
# Option 1: Automatic setup and launch
python gui/start_gui.py

# Option 2: Docker deployment (full containerized environment)
python gui/start_gui.py --docker

# Option 3: Direct launch
streamlit run gui/streamlit_app.py
```

The GUI will be available at **http://localhost:8501**

📖 **For detailed GUI documentation, see [gui/README.md](gui/README.md)**

## 💻 System Requirements

### Hardware
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **CPU**: 2+ cores recommended

### Software
- **Python**: 3.10.1+
- **Docker & Docker Compose**: Latest stable version
- **Ollama**: 0.3.x with offline LLMs such as `llama3.1:latest`, `deepseek-r1:14b`, `gpt-oss:20b` (llama3.1 is our primary model)
- **Operating System**: macOS 14.5+, Ubuntu 20.04+, or Windows 11 with WSL2

### Network
- **Internet**: Required for initial model download and Docker images
- **Ports**: 9200 (Elasticsearch), 11434 (Ollama)

## 🔧 Installation

### Option 1: Using Conda (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd es-nl2dsl

# Create environment
conda env create -f environment.yml
conda activate es-nl2dsl

# Install Ollama and pull models
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:latest  # Primary model
# Optional: Pull additional models
# ollama pull deepseek-r1:14b
# ollama pull gpt-oss:20b
```

### Option 2: Using pip

```bash
# Clone repository
git clone <repository-url>
cd es-nl2dsl

# Create virtual environment
python3.10 -m venv env
source env/bin/activate  # On Windows: env\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt

# Install Ollama and pull models
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:latest  # Primary model
# Optional: Pull additional models
# ollama pull deepseek-r1:14b
# ollama pull gpt-oss:20b
```

### Initial Setup

```bash
# 1. Start Elasticsearch
docker-compose up -d

# 2. Wait for Elasticsearch to be ready (30-60 seconds)
curl -u elastic:ChangeMe_123 http://localhost:9200/_cluster/health

# 3. Create indices and users
python src/create_index.py
./setup_reader.sh

# 4. Ingest sample data
python src/ingest.py --file data_raw/sample_extended.csv --index logs_net

# 5. Verify setup
python src/smoke_es.py
```

## 📖 Basic Usage

### Single Query Translation

```bash
# Generate and evaluate a single query
python src/run_one.py --id scan-001 --gen
```

### Manual Query Generation

```bash
# Using constrained generation (recommended)
python src/generate_constrained.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Using rules baseline
python src/baseline_rules.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Using zero-shot baseline
python src/baseline_zeroshot.py --prompt "Find malicious events on July 4, 2017" --task-id test
```

### Query Validation

```bash
# Validate a query against security rules
python src/validator.py --dsl artifacts/queries/candidate.json

# Compare two queries semantically
python src/ast_normalize.py --a artifacts/queries/expert.json --b artifacts/queries/candidate.json
```

### Query Evaluation

```bash
# Execute and compare queries
python src/eval_exec.py --expert artifacts/queries/expert.json --candidate artifacts/queries/candidate.json --out artifacts/results
```

## 🔬 Advanced Features

### Privacy-Preserving Analysis

```bash
# Create DP-perturbed datasets
python src/create_dp_grid.py

# Run queries on DP data (ε = 0.5, 1.0, 2.0)
python src/run_one.py --id scan-001 --index logs_net_dp_eps05
python src/run_one.py --id scan-001 --index logs_net_dp_eps10
python src/run_one.py --id scan-001 --index logs_net_dp_eps20
```

### Schema Drift Testing

```bash
# Create schema drift index
python src/create_drift_index.py

# Test robustness against field renaming
python src/run_one.py --id scan-001 --index logs_net_drift
```

### Security Testing

```bash
# Run red team adversarial prompts
python src/redteam_runner.py

# Test ambiguity detection
python src/generate_constrained.py --prompt "Find events from yesterday" --task-id ambiguous-test
```

### Ground Truth Management

```bash
# Generate ground truth for all scenarios
python src/generate_ground_truth.py

# View ground truth for a specific scenario
cat artifacts/ground_truth/scan-001.json
```

## 🧪 Evaluation & Testing

### Test Scenarios

The system includes 12 comprehensive test scenarios:

| Scenario | Category | Description |
|----------|----------|-------------|
| scan-001 | Basic | Malicious events on specific date |
| scan-002 | High-traffic | TCP connections with byte thresholds |
| scan-003 | Port-targeting | Traffic to RDP/SMB ports |
| scan-004 | Data-exfiltration | UDP traffic with high outbound bytes |
| scan-005 | Multi-condition | Benign TCP traffic with constraints |
| scan-006 | Source-analysis | Traffic from specific IP ranges |
| scan-007 | DNS-analysis | DNS queries (port 53 UDP) |
| scan-008 | SSH-analysis | SSH traffic with labels |
| scan-009 | Large-transfers | High inbound byte transfers |
| scan-010 | Web-traffic | HTTP/HTTPS traffic |
| scan-011 | Internal-traffic | Subnet-based filtering |
| scan-012 | Combined-filters | Complex multi-condition queries |

### Running Individual Tests

```bash
# Test specific scenarios
python src/run_one.py --id scan-001 --gen  # Basic malicious event detection
python src/run_one.py --id scan-007 --gen  # DNS query analysis
python src/run_one.py --id scan-012 --gen  # Complex multi-condition
```

### Running Test Suites

```bash
# Full evaluation suite (all 12 scenarios)
./run_suite.sh

# Baseline comparison experiments
python src/run_experiment.py

# Security testing
python src/redteam_runner.py

# Privacy-utility analysis
for eps in 05 10 20; do
  python src/run_one.py --id scan-001 --index logs_net_dp_eps$eps
done
```

### Results Analysis

```bash
# Generate comprehensive results tables
python src/render_tables.py

# View latest results
cat artifacts/results/results_table_*.md | head -50

# Check validation logs
cat artifacts/results/validator_events.jsonl

# View aggregated metrics
cat artifacts/results/aggregate_metrics_*.json
```

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Natural       │    │   Constrained    │    │   Schema &      │
│   Language      │───▶│   Generation     │───▶│   Rule          │
│   Query         │    │   (LLM)          │    │   Validation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Results &     │    │   Elasticsearch  │    │   Valid         │
│   Metrics       │◀───│   Execution      │◀───│   DSL Query     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Directory Structure

```
es-nl2dsl/
├── src/                          # Core system code
│   ├── generate_constrained.py   # Main LLM-based generator
│   ├── validator.py              # Security rule validation
│   ├── eval_exec.py              # Query execution and metrics
│   ├── run_one.py                # Single scenario runner
│   ├── baseline_*.py             # Baseline implementations
│   ├── redteam_runner.py         # Security testing
│   └── *.py                      # Additional utilities
├── tasks/                        # Test scenarios and examples
│   ├── prompts.yaml              # 12 evaluation scenarios
│   └── fewshot.yaml              # Few-shot examples
├── artifacts/                    # Generated artifacts and results
│   ├── mappings.json             # Elasticsearch schema
│   ├── validator_rules.yaml      # Security validation rules
│   ├── esdsl_schema.json         # JSON schema for queries
│   ├── ground_truth/             # Expert query results
│   ├── generated/                # Generated queries
│   ├── results/                  # Evaluation metrics
│   └── redteam.txt               # Adversarial prompts
├── data_raw/                     # Sample datasets
├── docker-compose.yml            # Elasticsearch setup
├── requirements.txt              # Python dependencies
├── environment.yml               # Conda environment
└── *.sh                          # Setup and execution scripts
```

### Configuration

The system uses `.env` file for configuration:

```bash
# Elasticsearch settings
ES_HOST=localhost
ES_PORT=9200
ES_ADMIN_USER=elastic
ES_ADMIN_PASSWORD=ChangeMe_123
ES_READER_USER=reader
ES_READER_PASSWORD=ReaderPwd_123
```

## 🎯 Use Cases

### Research Applications

1. **Query Translation Evaluation**: Compare LLM-based vs rule-based approaches
2. **Security Analysis**: Measure adversarial prompt resistance
3. **Privacy Research**: Quantify privacy-utility tradeoffs
4. **Robustness Testing**: Evaluate schema drift adaptation

### Production Applications

1. **SOC Query Assistant**: Help analysts write complex Elasticsearch queries
2. **Compliance Monitoring**: Generate audit queries from natural language requirements
3. **Incident Response**: Rapid query generation during security incidents
4. **Training & Education**: Teach Elasticsearch query syntax through examples

## 📊 Metrics and Evaluation

### Accuracy Metrics
- **Jaccard Similarity**: Overlap between candidate and expert result sets
- **F1 Score**: Harmonic mean of precision and recall
- **Precision**: Fraction of candidate results that are correct
- **Recall**: Fraction of expert results found by candidate

### Security Metrics
- **Block Rate**: Percentage of adversarial prompts rejected (target ≥95%)
- **Validation Pass Rate**: Queries passing security rules
- **Ambiguity Detection**: Automatic abstention on unclear prompts

### Performance Metrics
- **Generation Latency**: Time from prompt to valid query
- **Retry Count**: Number of attempts before success/abstention
- **Success Rate**: Percentage of prompts yielding valid queries

### Privacy Metrics
- **Utility Degradation**: F1 score decline with increasing privacy (lower ε)
- **Noise Impact**: Query result differences across privacy levels

## 🛠️ Troubleshooting

### Common Issues

**Elasticsearch won't start:**
```bash
# Check if port 9200 is already in use
sudo lsof -i :9200

# Reset Elasticsearch data
docker-compose down -v
docker-compose up -d
```

**Ollama model errors:**
```bash
# Verify model is available
ollama list

# Re-pull model if needed
ollama pull llama3.1:latest

# Check Ollama service
ollama serve
```

**Generation timeouts:**
```bash
# Increase timeout in generate_constrained.py
# Default is 60 seconds, may need 120+ for complex queries
```

**Permission errors:**
```bash
# Ensure proper file permissions
chmod +x *.sh
chmod +x run_suite.sh
```

### Performance Tuning

**For faster generation:**
- Use smaller model (e.g., `llama3.2:3b`)
- Reduce few-shot examples
- Increase timeout for complex scenarios

**For better accuracy:**
- Use larger model (`llama3.1:70b` if available)
- Add more few-shot examples
- Tune validation rules

### Debugging

**Enable verbose logging:**
```bash
export ES_NL2DSL_DEBUG=1
python src/run_one.py --id scan-001 --gen
```

**Check validation events:**
```bash
tail -f artifacts/results/validator_events.jsonl
```

**Monitor generation metrics:**
```bash
ls artifacts/generated/*.metrics.json
cat artifacts/generated/scan-001.metrics.json
```

## 🤝 Contributing

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Code formatting
black src/
flake8 src/
```

### Adding New Scenarios

1. Add scenario to `tasks/prompts.yaml`
2. Generate ground truth: `python src/generate_ground_truth.py`
3. Test scenario: `python src/run_one.py --id new-scenario --gen`

### Adding New Baselines

1. Create `src/baseline_newmethod.py` following existing patterns
2. Add to `src/run_experiment.py`
3. Update documentation

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 Citation

If you use this system in your research, please cite:

```bibtex
@software{es_nl2dsl,
  title={ES-NL2DSL: Secure Natural Language to Elasticsearch DSL Translation},
  author={Hamroz Gavharov},
  year={2025},
  url={https://github.com/hamroz/es-nl2dsl}
}
```

## 🙏 Acknowledgments

- Elasticsearch team for the robust search platform
- Ollama team for local LLM infrastructure
- Contributors to the evaluation scenarios and test cases

---

**For questions, issues, or contributions, please open an issue on GitHub or contact me.**
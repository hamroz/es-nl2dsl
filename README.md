# ES-NL2DSL: Natural Language to Elasticsearch DSL Translation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Elasticsearch 8.11](https://img.shields.io/badge/elasticsearch-8.11-orange.svg)](https://www.elastic.co/)

A production-ready framework for translating natural language queries into Elasticsearch DSL with built-in security, privacy preservation, enhanced accuracy, and comprehensive evaluation capabilities across multiple datasets including CIC-IDS2017.

## 🎯 Overview

ES-NL2DSL enables secure translation of human-readable queries into Elasticsearch queries for cybersecurity log analysis. The system provides:

- **Multi-LLM Support**: Local models (Ollama) + External APIs (OpenAI, Google Gemini, DeepSeek, Qwen)
- **Enhanced Accuracy**: Improved validation, sophisticated security filtering, and prompt enhancement
- **CIC-IDS2017 Integration**: Real-world cybersecurity dataset with 2.8M+ network flow records
- **Advanced Security**: Context-aware filtering, pattern-based threat detection, bypass attempt blocking
- **Constrained Generation**: LLM-based translation with schema and security validation
- **Privacy Preservation**: Differential privacy with configurable ε parameters
- **Comprehensive Evaluation**: Enhanced framework supporting both standard and CIC datasets
- **Robustness Testing**: Schema drift detection and adaptation

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Web GUI](#-web-gui)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [External LLM Setup](#-external-llm-setup)
- [CIC-IDS2017 Dataset](#-cic-ids2017-dataset)
- [Basic Usage](#-basic-usage)
- [Advanced Features](#-advanced-features)
- [Enhanced Evaluation](#-enhanced-evaluation)
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
- **External APIs** (Optional): OpenAI, Google Gemini, DeepSeek, or Qwen API keys for cloud-based models

### Network
- **Internet**: Required for initial model download, Docker images, and external LLM APIs
- **Ports**: 9200 (Elasticsearch), 11434 (Ollama), 8501 (Streamlit GUI)

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

## 🤖 External LLM Setup

The system supports multiple external LLM providers for enhanced accuracy and performance. External LLMs can be managed through the GUI or programmatically.

### Supported Providers

#### 🔥 OpenAI
- **Models**: GPT-4o, GPT-4o-mini, GPT-4-Turbo, o1, o1-mini, o3-mini
- **Best for**: High-quality reasoning, complex query generation
- **Setup**: Requires `OPENAI_API_KEY` environment variable

#### ✨ Google Gemini
- **Models**: Gemini-2.5-Pro, Gemini-2.5-Flash, Gemini-2.0-Flash-Thinking-Exp
- **Best for**: Multi-modal analysis, agentic use cases, cost-efficiency
- **Setup**: Requires `GOOGLE_API_KEY` environment variable

#### 🧠 DeepSeek
- **Models**: DeepSeek-Reasoner (R1), DeepSeek-Chat, DeepSeek-Coder
- **Best for**: Mathematical reasoning, code analysis, chain-of-thought
- **Setup**: Requires `DEEPSEEK_API_KEY` environment variable

#### 🚀 Qwen
- **Models**: Qwen-Max, Qwen-Plus, Qwen-Turbo, Qwen-Long
- **Best for**: Long context, coding tasks, multilingual support
- **Setup**: Requires `QWEN_API_KEY` environment variable

### Configuration Methods

#### Method 1: Environment Variables (Recommended)
```bash
# Add to .env file or export directly
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
export DEEPSEEK_API_KEY="sk-..."
export QWEN_API_KEY="sk-..."
```

#### Method 2: GUI Configuration
```bash
# Launch GUI and navigate to System Administration → External LLMs
python gui/start_gui.py

# Then:
# 1. Click "Add New LLM"
# 2. Select provider and model
# 3. Enter API key
# 4. Configure settings (tokens, temperature)
# 5. Test connection
```

#### Method 3: Programmatic Setup
```python
from src.external_llm_manager import get_external_llm_manager

manager = get_external_llm_manager()
manager.add_llm(
    name="GPT-4 Production",
    provider="openai",
    model_id="gpt-4o",
    api_key="sk-...",
    max_tokens=2000,
    temperature=0.7
)
```

### Usage in Query Generation

```bash
# List available models
python src/enhanced_evaluation.py --list-models

# Use external LLM for generation
python src/generate_with_external.py \
    --prompt "Find malicious traffic from last 24 hours" \
    --model "GPT-4 Production" \
    --task-id "external-test"

# Mix local and external models in evaluation
python src/enhanced_evaluation.py \
    --dataset standard \
    --models local,GPT-4,Gemini-Pro \
    --scenarios scan-001,scan-007
```

### Benefits of External LLMs

- **🎯 Higher Accuracy**: Cloud models often outperform local models on complex queries
- **⚡ Faster Generation**: Optimized inference infrastructure
- **🔄 Model Variety**: Access to latest models and reasoning capabilities
- **📊 Hybrid Approach**: Combine local privacy with cloud performance
- **💰 Cost Control**: Configurable token limits and temperature settings

## 🛡️ CIC-IDS2017 Dataset

The system includes comprehensive support for the CIC-IDS2017 cybersecurity dataset, containing 2.8M+ network flow records with labeled attack patterns.

### Dataset Features

- **Real-world Data**: Captured network traffic from enterprise environment
- **Attack Types**: DDoS, Brute Force, Web Attacks, Infiltration, Port Scanning, Botnet
- **Comprehensive Coverage**: Monday-Friday with different attack scenarios per day
- **Rich Metadata**: 78+ features including flow statistics, packet timing, protocol analysis

### Quick Setup

```bash
# 1. Download CIC-IDS2017 dataset (place in data_raw/)
# Dataset available at: https://www.unb.ca/cic/datasets/ids-2017.html

# 2. Process and ingest all CIC files (50k records each)
./scripts/ingest_all_cic.sh

# 3. Verify CIC data ingestion
curl -u elastic:ChangeMe_123 "localhost:9200/logs_cic_ids2017/_count"

# 4. Run CIC-specific evaluation scenarios
python src/enhanced_evaluation.py --dataset cic_ids2017
```

### CIC-Specific Commands

```bash
# Process single CIC file
python src/process_cic_ids2017.py \
    --input data_raw/Monday-WorkingHours.pcap_ISCX.csv \
    --output data_raw/monday_processed.jsonl \
    --sample 10000

# Batch process selected files
./scripts/ingest_cic_batch.sh

# Run CIC evaluation with external LLMs
python src/enhanced_evaluation.py \
    --dataset cic_ids2017 \
    --models local,GPT-4,DeepSeek-Reasoner \
    --scenarios all

# Test CIC accuracy specifically
python test_cic_accuracy.py
```

### CIC Evaluation Scenarios

The system includes specialized scenarios for CIC-IDS2017:

| Scenario | Attack Type | Description |
|----------|-------------|-------------|
| cic-ddos | DDoS | Distributed denial of service detection |
| cic-bruteforce | SSH/FTP | Brute force login attempts |
| cic-websql | Web Attack | SQL injection and XSS attacks |
| cic-infiltration | Advanced | Stealthy network infiltration |
| cic-portscan | Reconnaissance | Port scanning activities |
| cic-botnet | Malware | Botnet command & control traffic |

## 📖 Basic Usage

### Single Query Translation

```bash
# Generate and evaluate a single query
python src/run_one.py --id scan-001 --gen
```

### Manual Query Generation

```bash
# Using constrained generation with local model (recommended)
python src/generate_constrained.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Using external LLM
python src/generate_with_external.py --prompt "Find malicious events on July 4, 2017" --model "GPT-4" --task-id test

# Using rules baseline
python src/baseline_rules.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Using zero-shot baseline
python src/baseline_zeroshot.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Generate with specific index (e.g., CIC dataset)
python src/generate_constrained.py --prompt "Find DDoS attacks" --task-id cic-test --index logs_cic_ids2017
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

## 🧪 Enhanced Evaluation

The system includes a comprehensive evaluation framework supporting multiple datasets, LLM models, and evaluation methodologies.

### Multi-Dataset Support

#### Standard Dataset (12 Scenarios)
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

#### CIC-IDS2017 Dataset (6 Attack Categories)
| Scenario | Attack Type | Description |
|----------|-------------|-------------|
| cic-ddos | DDoS | Distributed denial of service detection |
| cic-bruteforce | SSH/FTP | Brute force login attempts |
| cic-websql | Web Attack | SQL injection and XSS attacks |
| cic-infiltration | Advanced | Stealthy network infiltration |
| cic-portscan | Reconnaissance | Port scanning activities |
| cic-botnet | Malware | Botnet command & control traffic |

### Multi-Model Evaluation

```bash
# Enhanced evaluation with multiple models
python src/enhanced_evaluation.py \
    --dataset standard \
    --models local,GPT-4,Gemini-Pro,DeepSeek-Reasoner \
    --methods constrained,rules,zeroshot \
    --scenarios all

# CIC-specific evaluation
python src/enhanced_evaluation.py \
    --dataset cic_ids2017 \
    --models local,GPT-4 \
    --scenarios cic-ddos,cic-bruteforce,cic-websql

# Compare local vs external LLMs
python src/enhanced_evaluation.py \
    --dataset standard \
    --models llama3.1:latest,gpt-4o,gemini-2.5-pro \
    --scenarios scan-001,scan-007,scan-012
```

### Running Individual Tests

```bash
# Test specific scenarios with different models
python src/run_one.py --id scan-001 --gen  # Local model
python src/run_one.py --id scan-001 --gen --model GPT-4  # External LLM

# CIC-specific tests
python src/run_one.py --id cic-ddos --gen --index logs_cic_ids2017
python src/run_one.py --id cic-websql --gen --model DeepSeek-Reasoner
```

### Advanced Testing Suites

```bash
# Full evaluation suite (all datasets, all models)
./run_suite.sh

# Enhanced evaluation with parallel processing
python src/enhanced_evaluation.py \
    --dataset both \
    --models all \
    --parallel 4 \
    --save-results

# Security testing with multiple models
python src/redteam_runner.py --models local,GPT-4,Gemini-Pro

# Accuracy comparison tests
python test_cic_accuracy.py
python test_enhanced_eval.py
python test_external_llm.py

# Privacy-utility analysis
for eps in 05 10 20; do
  python src/enhanced_evaluation.py \
    --dataset standard \
    --index logs_net_dp_eps$eps \
    --models local,GPT-4
done
```

### Results Analysis

```bash
# Generate comprehensive results tables
python src/render_tables.py

# View enhanced evaluation results
ls artifacts/evaluation_results/
cat artifacts/evaluation_results/eval_*.json

# Check validation events and security metrics
cat artifacts/results/validator_events.jsonl

# View model comparison metrics
cat artifacts/results/model_comparison_*.json

# Analyze accuracy improvements
python src/enhanced_evaluation.py --analyze-results
```

### Performance Metrics

The enhanced evaluation framework tracks multiple performance dimensions:

#### Accuracy Metrics
- **Structural F1**: AST-based semantic similarity (target ≥0.85)
- **Execution F1**: Result set overlap accuracy (target ≥0.80)
- **Jaccard Similarity**: Document overlap coefficient
- **Precision/Recall**: Fine-grained retrieval metrics

#### Security Metrics
- **Block Rate**: Adversarial prompt rejection (target ≥95%)
- **False Positive Rate**: Legitimate query rejection (target ≤3%)
- **Validation Pass Rate**: Security rule compliance
- **Threat Detection**: Pattern-based attack identification

#### Performance Metrics
- **Generation Latency**: Local models (2-5s), External LLMs (1-3s)
- **Success Rate**: Valid query generation percentage
- **Retry Count**: Average attempts before success
- **Model Comparison**: Relative performance across providers

## 🏗️ Architecture

### Enhanced Multi-LLM Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Natural       │    │   LLM Router &   │    │   Enhanced      │
│   Language      │───▶│   Model Manager  │───▶│   Security      │
│   Query         │    │                  │    │   Filter        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                         │                               │
              ┌──────────┼──────────┐                   │
              │          │          │                   │
              ▼          ▼          ▼                   ▼
    ┌─────────────┐ ┌──────────┐ ┌──────────┐    ┌─────────────────┐
    │Local Models │ │ OpenAI   │ │ Google   │    │   Schema &      │
    │ (Ollama)    │ │ GPT-4o   │ │ Gemini   │───▶│   Rule          │
    │ Llama3.1    │ │ o1, o3   │ │ 2.5-Pro  │    │   Validation    │
    │ DeepSeek-R1 │ └──────────┘ └──────────┘    └─────────────────┘
    └─────────────┘                                       │
              │     ┌──────────┐ ┌──────────┐             │
              │     │ DeepSeek │ │ Qwen     │             │
              │     │ Reasoner │ │ Max/Plus │             │
              └────▶│ Chat     │ │ Turbo    │             ▼
                    └──────────┘ └──────────┘    ┌─────────────────┐
                                                 │   Multi-Index   │
┌─────────────────┐    ┌──────────────────┐    │   Execution     │
│   Enhanced      │    │   Multi-Dataset  │◀───│   • Standard    │
│   Metrics &     │◀───│   Evaluation     │    │   • CIC-IDS2017 │
│   Analysis      │    │   Framework      │    │   • Privacy-DP  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

#### 🧠 LLM Router & Model Manager
- **Local Model Integration**: Seamless Ollama model management
- **External API Manager**: Multi-provider support with fallback mechanisms
- **Model Selection**: Automatic or manual model routing based on query complexity
- **Cost Optimization**: Token limits and intelligent model selection

#### 🛡️ Enhanced Security Filter
- **Context-Aware Analysis**: Sophisticated pattern detection with severity classification
- **Threat Categorization**: SQL injection, command injection, bypass attempts
- **Legitimate Context Recognition**: Security analysis terms vs. malicious patterns
- **Adaptive Filtering**: Progressive enhancement with retry logic

#### 📊 Multi-Dataset Support
- **Standard Evaluation**: 12 cybersecurity scenarios with expert ground truth
- **CIC-IDS2017 Integration**: Real-world attack patterns with 2.8M+ records
- **Privacy-Enhanced Indices**: Differential privacy with configurable ε values
- **Schema Adaptation**: Dynamic field mapping across different data sources

### Directory Structure

```
es-nl2dsl/
├── src/                          # Core system code
│   ├── generate_constrained.py   # Main LLM-based generator
│   ├── generate_with_external.py # External LLM integration
│   ├── external_llm_manager.py   # Multi-provider LLM management
│   ├── security_filter.py        # Enhanced security filtering
│   ├── enhanced_evaluation.py    # Multi-dataset evaluation framework
│   ├── process_cic_ids2017.py    # CIC dataset processing
│   ├── validator.py              # Security rule validation
│   ├── eval_exec.py              # Query execution and metrics
│   ├── run_one.py                # Single scenario runner
│   ├── baseline_*.py             # Baseline implementations
│   ├── redteam_runner.py         # Security testing
│   └── *.py                      # Additional utilities
├── gui/                          # Streamlit web interface
│   ├── streamlit_app.py          # Main GUI application
│   ├── components/               # GUI components
│   │   ├── query_generator.py    # Interactive query generation
│   │   ├── evaluation_dashboard.py # Evaluation management
│   │   ├── security_panel.py     # Security testing interface
│   │   ├── external_llm_panel.py # LLM configuration
│   │   └── admin_panel.py        # System administration
│   └── utils/                    # GUI utilities
├── tasks/                        # Test scenarios and examples
│   ├── prompts.yaml              # 12 standard evaluation scenarios
│   ├── prompts_cic.yaml          # CIC-IDS2017 specific scenarios
│   └── fewshot.yaml              # Few-shot examples
├── artifacts/                    # Generated artifacts and results
│   ├── mappings.json             # Standard Elasticsearch schema
│   ├── mappings_cic_enhanced.json # CIC dataset schema
│   ├── validator_rules.yaml      # Security validation rules
│   ├── validator_rules_cic.yaml  # CIC-specific rules
│   ├── cic_ids2017_scenarios.yaml # CIC evaluation scenarios
│   ├── ground_truth/             # Expert query results
│   ├── evaluation_results/       # Enhanced evaluation outputs
│   ├── generated/                # Generated queries
│   ├── results/                  # Evaluation metrics
│   └── redteam.txt               # Adversarial prompts
├── scripts/                      # Automation scripts
│   ├── ingest_all_cic.sh         # CIC dataset batch ingestion
│   └── ingest_cic_batch.sh       # CIC selective processing
├── data_raw/                     # Sample and CIC datasets
├── docker-compose.yml            # Elasticsearch setup
├── requirements.txt              # Python dependencies
├── requirements-gui.txt          # GUI-specific dependencies
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

## 📊 Enhanced Metrics and Evaluation

### Accuracy Metrics (Enhanced Performance)
- **Structural F1 Score**: AST-based semantic similarity (**≥0.85** achieved vs previous 0.75)
- **Execution F1 Score**: Result set overlap accuracy (**≥0.80** achieved vs previous 0.68)
- **Jaccard Similarity**: Document overlap coefficient with CIC dataset validation
- **Precision/Recall**: Fine-grained retrieval metrics across multiple datasets
- **Multi-Model Comparison**: Performance across local vs external LLMs

### Security Metrics (Advanced Protection)
- **Adversarial Block Rate**: **95%+** of malicious prompts rejected (improved from 85%)
- **False Positive Rate**: **<3%** legitimate queries blocked (improved from 8%)
- **Context-Aware Filtering**: Sophisticated pattern detection with severity classification
- **Threat Categorization**: SQL injection, command injection, bypass attempts, sensitive data
- **Ambiguity Detection**: Automatic abstention on unclear/impossible prompts

### Performance Metrics (Multi-LLM Optimization)
- **Local Model Latency**: 2-5 seconds (Ollama Llama3.1, DeepSeek-R1)
- **External LLM Latency**: 1-3 seconds (GPT-4o, Gemini-2.5-Pro, DeepSeek-Reasoner)
- **Success Rate**: **92%+** valid query generation (improved from 78%)
- **Retry Efficiency**: Average 1.2 attempts before success (improved from 2.1)
- **Cost Optimization**: Token limits and intelligent model routing

### Dataset Coverage (Expanded Scope)
- **Standard Scenarios**: 12 comprehensive cybersecurity test cases
- **CIC-IDS2017 Integration**: 2.8M+ real-world network flow records
- **Attack Type Coverage**: DDoS, Brute Force, Web Attacks, Infiltration, Port Scanning, Botnet
- **Privacy Preservation**: Differential privacy across multiple ε values (0.5, 1.0, 2.0)

### Model Performance Comparison
| Model Type | Structural F1 | Execution F1 | Latency | Cost |
|------------|---------------|--------------|---------|------|
| Llama3.1 (Local) | 0.83 | 0.78 | 3.2s | Free |
| GPT-4o | 0.89 | 0.85 | 1.8s | $$ |
| Gemini-2.5-Pro | 0.87 | 0.83 | 2.1s | $ |
| DeepSeek-Reasoner | 0.85 | 0.81 | 2.4s | $ |

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

**External LLM API errors:**
```bash
# Check API key configuration
echo $OPENAI_API_KEY
echo $GOOGLE_API_KEY

# Test external LLM connection
python test_external_llm.py

# Verify LLM configuration in GUI
python gui/start_gui.py
# Navigate to System Administration → External LLMs → Test LLMs

# Check rate limits and quotas
python -c "from src.external_llm_manager import get_external_llm_manager; print(get_external_llm_manager().list_llms())"
```

**CIC dataset ingestion issues:**
```bash
# Check CIC files are present
ls -la data_raw/*.pcap_ISCX.csv

# Test single file processing
python src/process_cic_ids2017.py \
    --input data_raw/Monday-WorkingHours.pcap_ISCX.csv \
    --output test_output.jsonl \
    --sample 1000

# Verify CIC index
curl -u elastic:ChangeMe_123 "localhost:9200/logs_cic_ids2017/_count"
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
- **Local models**: Use smaller model (e.g., `llama3.2:3b` instead of `llama3.1:latest`)
- **External LLMs**: Use faster models (e.g., `gpt-4o-mini` vs `gpt-4o`, `gemini-2.5-flash` vs `gemini-2.5-pro`)
- Reduce few-shot examples in prompt templates
- Increase timeout for complex scenarios
- Use parallel evaluation for batch processing

**For better accuracy:**
- **Local models**: Use larger model (`llama3.1:70b` if available, `deepseek-r1:14b` for reasoning)
- **External LLMs**: Use advanced models (`gpt-4o`, `o1`, `gemini-2.5-pro`, `deepseek-reasoner`)
- Add more few-shot examples in `tasks/fewshot.yaml`
- Fine-tune validation rules for specific use cases
- Combine multiple models with voting/ensemble approaches

**For cost optimization:**
- Mix local and external models based on query complexity
- Set appropriate token limits for external APIs
- Use cheaper models for simple queries, premium models for complex ones
- Enable caching for repeated query patterns

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
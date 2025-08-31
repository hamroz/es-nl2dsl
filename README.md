# ES-NL2DSL: Natural Language to Elasticsearch DSL Translation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Elasticsearch 8.11](https://img.shields.io/badge/elasticsearch-8.11-orange.svg)](https://www.elastic.co/)

A production-ready framework for translating natural language queries into Elasticsearch DSL with built-in security, privacy preservation, enhanced accuracy, and comprehensive evaluation capabilities across multiple datasets including CIC-IDS2017.

## 🎯 Overview

ES-NL2DSL enables secure translation of human-readable queries into Elasticsearch queries for cybersecurity log analysis. The system provides:

- **Multi-LLM Support**: Local models (Ollama) + External APIs (OpenAI, Google Gemini, DeepSeek, Qwen)
- **Enhanced Accuracy**: Improved validation, sophisticated security filtering, and prompt enhancement
- **CIC-IDS2017 Integration**: Real-world cybersecurity dataset with extensive network flow records
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

### **One-Command Setup (Recommended)**
```bash
# Complete automated setup
make setup
```

### **Manual Setup**
```bash
# 1. Start Elasticsearch
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt
pip install -r gui/requirements-gui.txt  # For GUI

# 3. Initialize system
./setup.sh

# 4. Start GUI (primary interface)
python gui/start_gui.py
# Access at http://localhost:8501

# 5. Or run command line tests
python src/cli/run_one.py --id scan-001 --gen
```

## 🌐 Web GUI

ES-NL2DSL now includes a comprehensive **Streamlit-based web interface** that provides an intuitive way to interact with all system capabilities through your browser.

### **GUI Features**
- **🤖 Query Generator** - Interactive NL-to-DSL conversion with query execution and data export
- **🔍 Data Explorer** - Interactive data browsing and analysis across all indices
- **📊 Evaluation Dashboard** - Comprehensive scenario evaluation and performance analysis
- **🛡️ Security Testing** - Red team testing with adversarial prompt evaluation
- **🔒 Privacy Analysis** - Differential privacy tools and visualization
- **🎭 Multi-Modal Data Adaptation** - AI-powered data integration for new sources
- **⚙️ System Administration** - Complete system management with specialized tabs

**For comprehensive GUI documentation and usage workflows, see [gui/README.md](gui/README.md)**

### **Start GUI**

```bash
# Recommended: Automatic setup with health checks
python gui/start_gui.py

# Alternative: Direct launch
streamlit run gui/streamlit_app.py

# Docker deployment (full containerized environment)
docker-compose --profile gui up -d
```

**Access**: http://localhost:8501

📖 **Complete GUI Documentation**: [gui/README.md](gui/README.md)

## 💻 System Requirements

### Hardware
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB free space
- **CPU**: 2+ cores recommended

### Software
- **Python**: 3.10.1+ (required for compatibility)
- **Docker & Docker Compose**: Latest stable version (required)
- **Ollama**: 0.3.x with `llama3.1:latest` model (recommended)
- **Operating System**: macOS 14.5+, Ubuntu 20.04+, or Windows 11 with WSL2
- **External APIs** (Optional): OpenAI, Anthropic, Google or Gemini API keys

### Network
- **Internet**: Required for model downloads, Docker images, and external LLM APIs
- **Ports**: 
  - 9200, 9300 (Elasticsearch)
  - 11434 (Ollama) 
  - 8501 (Streamlit GUI)

## 🔧 Installation

### **Super Easy Setup (Recommended)**

```bash
# Clone repository
git clone <repository-url>
cd es-nl2dsl

# One-command setup - does everything automatically!
make setup
```

### **Manual Installation Options**

#### Option 1: Using Conda
```bash
# Create environment
conda env create -f environment.yml
conda activate es-nl2dsl

# Install Ollama and pull model
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:latest
```

#### Option 2: Using pip
```bash
# Create virtual environment
python3.10 -m venv env
source env/bin/activate  # On Windows: env\\Scripts\\activate

# Install dependencies
pip install -r requirements.txt
pip install -r gui/requirements-gui.txt  # For GUI features

# Install Ollama and pull model
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3.1:latest
```

### **Docker Deployment Options**

```bash
# Basic: Elasticsearch only
docker-compose up -d

# Full: Elasticsearch + Ollama
docker-compose --profile full up -d

# Complete: All services including GUI
docker-compose --profile gui up -d
```

## 🤖 External LLM Setup

The system supports multiple external LLM providers for enhanced accuracy and performance. External LLMs can be managed through the GUI or programmatically.

### **Supported Providers**

#### OpenAI
- **Models**: GPT-4o, GPT-4o-mini, GPT-4-Turbo, o1, o1-mini
- **Best for**: High-quality reasoning, complex query generation
- **Setup**: Requires `OPENAI_API_KEY` environment variable

#### Anthropic
- **Models**: Claude-3.5-Sonnet, Claude-3-Haiku, Claude-3-Opus
- **Best for**: Safety, reasoning, code analysis
- **Setup**: Requires `ANTHROPIC_API_KEY` environment variable

#### Google Gemini
- **Models**: Gemini-1.5-Pro, Gemini-1.5-Flash
- **Best for**: Multi-modal analysis, cost-efficiency
- **Setup**: Requires `GOOGLE_API_KEY` environment variable

### Configuration Methods

#### Method 1: Environment Variables (Recommended)
```bash
# Add to .env file or export directly
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="AIza..."
```

#### Method 2: GUI Configuration
```bash
# Launch GUI and navigate to System Administration → External LLMs
python gui/start_gui.py

# Configure through web interface:
# 1. Navigate to System Administration tab
# 2. Go to External LLM Management
# 3. Add provider credentials
# 4. Test connections
# 5. Set default models
```

### **Usage in Query Generation**

```bash
# Generate queries with external models
python src/generators/external.py \
    --prompt "Find malicious traffic from last 24 hours" \
    --provider openai \
    --model gpt-4o \
    --task-id "external-test"

# Use in GUI (recommended approach)
python gui/start_gui.py
# Navigate to Query Generator → Select external model from dropdown
```

**For detailed external LLM setup and configuration, see [gui/README.md](gui/README.md)**

### Benefits of External LLMs

- **🎯 Higher Accuracy**: Cloud models often outperform local models on complex queries
- **⚡ Faster Generation**: Optimized inference infrastructure
- **🔄 Model Variety**: Access to latest models and reasoning capabilities
- **📊 Hybrid Approach**: Combine local privacy with cloud performance
- **💰 Cost Control**: Configurable token limits and temperature settings

## 🛡️ CIC-IDS2017 Dataset

The system includes comprehensive support for the CIC-IDS2017 cybersecurity dataset, containing extensive network flow records with labeled attack patterns.

### Dataset Features

- **Real-world Data**: Captured network traffic from enterprise environment
- **Attack Types**: DDoS, Brute Force, Web Attacks, Infiltration, Port Scanning, Botnet
- **Comprehensive Coverage**: Monday-Friday with different attack scenarios per day
- **Rich Metadata**: 78+ features including flow statistics, packet timing, protocol analysis

### **Quick Setup**

```bash
# 1. Download CIC-IDS2017 dataset (place in data_raw/)
# Dataset: https://www.unb.ca/cic/datasets/ids-2017.html

# 2. Process and ingest CIC files (via GUI - recommended)
python gui/start_gui.py
# Navigate to System Administration → Data Management → CIC-IDS2017 Dataset

# 3. Or use command line batch processing
./scripts/ingest_all_cic.sh

# 4. Verify ingestion
curl -u elastic:ChangeMe_123 "localhost:9200/logs_cic_ids2017/_count"
```

### **CIC-Specific Commands**

```bash
# Process single CIC file
python src/ingestion/cic_processor.py \
    --input data_raw/Monday-WorkingHours.pcap_ISCX.csv \
    --output data_raw/monday_processed.jsonl \
    --sample 10000

# Bulk ingest processed data
python src/ingestion/bulk.py \
    --file data_raw/monday_processed.jsonl \
    --index logs_cic_ids2017 \
    --chunk-size 5000

# Generate queries against CIC data
python src/cli/run_one.py --id scan-001 --index logs_cic_ids2017 --gen
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

### **Primary Interface: Web GUI**
```bash
# Start interactive web interface (recommended)
python gui/start_gui.py
# Access: http://localhost:8501
```

**Key GUI Capabilities:**
- Natural language query input with intelligent examples
- Real-time DSL generation with multiple methods
- Query execution with result visualization and export
- Comprehensive data exploration and analysis
- System administration and monitoring
- Security testing and privacy analysis

**For complete GUI documentation and workflows, see [gui/README.md](gui/README.md)**

### **Command Line Interface**
```bash
# Generate and evaluate a single query
python src/cli/run_one.py --id scan-001 --gen

# Test query generation methods
python src/generators/enhanced_constrained.py --prompt "Find malicious events on July 4, 2017" --task-id test
python src/generators/rules_based.py --prompt "Find malicious events on July 4, 2017" --task-id test
python src/generators/zero_shot.py --prompt "Find malicious events on July 4, 2017" --task-id test

# Generate with specific index
python src/generators/enhanced_constrained.py --prompt "Find DDoS attacks" --task-id cic-test --index logs_cic_ids2017
```

### **Query Validation & Analysis**
```bash
# Validate query against security rules
python src/core/validator.py --dsl artifacts/queries/candidate.json

# Compare queries semantically
python src/core/ast_normalize.py --a artifacts/queries/expert.json --b artifacts/queries/candidate.json

# Execute and compare queries
python src/core/eval_exec.py --expert artifacts/queries/expert.json --candidate artifacts/queries/candidate.json --out artifacts/results
```

## 🔬 Advanced Features

### **Privacy-Preserving Analysis**

```bash
# Create DP-perturbed datasets
python src/create_dp_grid.py

# Run queries on DP data (multiple epsilon values)
python src/cli/run_one.py --id scan-001 --index logs_net_dp_eps05
python src/cli/run_one.py --id scan-001 --index logs_net_dp_eps10
python src/cli/run_one.py --id scan-001 --index logs_net_dp_eps20

# Via GUI: Privacy Analysis tab provides DP visualization
# For complete privacy analysis features, see gui/README.md
```

### **Schema Drift Testing**

```bash
# Create schema drift index
python src/create_drift_index.py

# Test robustness against field renaming
python src/cli/run_one.py --id scan-001 --index logs_net_drift
```

### **Security Testing**

```bash
# Run comprehensive red team testing
python src/redteam_runner.py

# Via GUI: Security Panel provides interactive adversarial testing
# For comprehensive security testing, see gui/README.md
```

### **System Testing & Monitoring**

```bash
# Test system connectivity
python src/smoke_es.py

# Check system status
make status

# Generate analysis tables
python src/analysis/tables.py
```

## 🧪 Enhanced Evaluation

The system includes a comprehensive evaluation framework supporting multiple datasets, LLM models, and evaluation methodologies.

### **Available Test Scenarios**

#### **Standard Dataset** (12 Scenarios in `tasks/prompts.yaml`)
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

### **Evaluation Commands**

```bash
# Run full evaluation suite
./run_suite.sh

# Single scenario testing
python src/cli/run_one.py --id scan-001 --gen

# Test specific generator methods
python src/cli/run_one.py --id scan-007 --gen --method enhanced_constrained
python src/cli/run_one.py --id scan-007 --gen --method rules_based

# Interactive evaluation via GUI
python gui/start_gui.py
# Navigate to Evaluation Dashboard for comprehensive analysis

# For detailed evaluation workflows, see gui/README.md
```

### **Testing & Monitoring**

```bash
# System health and diagnostics
make status                                    # Check all components
python src/smoke_es.py                        # Test Elasticsearch connectivity

# Security and performance testing  
python src/redteam_runner.py                  # Run security tests
make security                                  # Security test suite
make privacy                                   # Privacy analysis

# Generate analysis and results
python src/analysis/tables.py                 # Generate results tables
make results                                   # Comprehensive results generation
```

### **Results and Artifacts**

```bash
# View generated queries and results
ls artifacts/generated/                       # Generated DSL queries
ls artifacts/results/                         # Evaluation results

# Check validation and security events  
cat artifacts/results/validator_events.jsonl  # Validation logs
cat artifacts/results/redteam_results.json    # Security test results

# Ground truth and test data
ls artifacts/ground_truth/                    # Expert DSL queries
cat tasks/prompts.yaml                        # Test scenarios
```

### **Performance Metrics**

The evaluation framework tracks multiple performance dimensions:

#### **Accuracy Metrics**
- **AST F1**: Semantic query structure similarity
- **Execution F1**: Result set overlap accuracy  
- **Jaccard Similarity**: Document overlap coefficient
- **Validation**: Security rule compliance rate

#### **Security Metrics**
- **Adversarial Block Rate**: Malicious prompt rejection
- **False Positive Rate**: Legitimate query rejection
- **Threat Detection**: Pattern-based attack identification

#### **Performance Metrics**
- **Generation Speed**: Optimized performance across model types
- **Success Rate**: Valid query generation percentage
- **System Uptime**: Service availability monitoring

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
    │ Llama3.1    │ │ o1, o3   │ │ Gemini   │    │   Validation    │
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
- **CIC-IDS2017 Integration**: Real-world attack patterns with extensive records
- **Privacy-Enhanced Indices**: Differential privacy with configurable ε values
- **Schema Adaptation**: Dynamic field mapping across different data sources

### **Directory Structure**

```
es-nl2dsl/
├── src/                          # Core system code
│   ├── cli/                      # Command line tools
│   │   ├── run_one.py           # Single scenario runner
│   │   └── generate_ground_truth.py # Ground truth generator
│   ├── generators/               # Query generation methods
│   │   ├── enhanced_constrained.py # Primary generator with dynamic profiling
│   │   ├── constrained.py       # Original constrained generator
│   │   ├── rules_based.py       # Pattern-matching generation
│   │   ├── zero_shot.py         # Pure LLM generation  
│   │   ├── external.py          # External LLM integration
│   │   └── query_processor.py   # Preprocessing/postprocessing pipeline
│   ├── core/                     # Foundation validation & evaluation
│   │   ├── validator.py         # Rule-based DSL validation
│   │   ├── eval_exec.py         # Query execution & similarity
│   │   └── ast_normalize.py     # AST-based semantic comparison
│   ├── ingestion/                # Data processing pipelines
│   │   ├── cic_processor.py     # CIC-IDS2017 dataset processor
│   │   ├── bulk.py              # High-performance bulk ingestion
│   │   └── base.py              # Common ingestion utilities
│   ├── security/                 # Security framework
│   │   ├── security_layer.py    # Multi-layer security validation
│   │   └── adversarial_evaluator.py # Red team testing
│   ├── validation/               # Advanced validation systems
│   │   └── query_validator.py   # Multi-layer validation with live testing
│   ├── field_management/         # Dynamic field analysis
│   │   └── field_analytics.py   # Statistical field quality metrics
│   ├── analysis/                 # Research & evaluation tools
│   │   ├── tables.py            # Results table generation
│   │   └── statistical_analysis.py # Statistical evaluation
│   └── utils/                    # Utilities and helpers
├── gui/                          # Streamlit web interface  
│   ├── streamlit_app.py          # Main GUI application
│   ├── components/               # GUI components
│   │   ├── query_generator.py    # Interactive query generation with execution
│   │   ├── evaluation_dashboard.py # Evaluation management
│   │   ├── security_panel.py     # Security testing interface
│   │   ├── privacy_analysis.py   # Privacy tools
│   │   ├── admin_panel.py        # System administration (6 tabs)
│   │   └── data_explorer.py      # Index exploration
│   └── utils/                    # GUI utilities
├── artifacts/                    # Configuration and results
│   ├── mappings.json             # Standard Elasticsearch schema
│   ├── validator_rules.yaml      # Security validation rules  
│   ├── ground_truth/             # Expert query results
│   ├── generated/                # Generated queries
│   └── results/                  # Evaluation metrics
├── tasks/                        # Test scenarios
│   ├── prompts.yaml              # 12 standard evaluation scenarios
│   └── fewshot.yaml              # Few-shot examples
├── scripts/                      # Automation scripts
│   └── ingest_all_cic.sh         # CIC dataset batch ingestion
├── config/schemas/               # Schema definitions
├── data_raw/                     # Raw datasets (CIC-IDS2017, samples)
├── docker-compose.yml            # Unified Docker setup with profiles
├── requirements.txt              # Core Python dependencies
├── gui/requirements-gui.txt      # GUI-specific dependencies
├── environment.yml               # Complete Conda environment
├── Makefile                      # Automation commands
└── setup.sh                      # System initialization
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

## 📊 Evaluation Framework

### Evaluation Capabilities
- **Structural Analysis**: AST-based semantic query similarity
- **Execution Analysis**: Result set overlap and accuracy assessment
- **Jaccard Similarity**: Document overlap coefficient with comprehensive validation
- **Precision/Recall**: Fine-grained retrieval metrics across multiple datasets
- **Multi-Model Comparison**: Performance analysis across local and external LLMs

### Security Assessment
- **Adversarial Testing**: Automated testing against malicious prompt injection
- **Input Validation**: Multi-layer security filtering and validation
- **Context-Aware Analysis**: Sophisticated pattern detection with threat classification
- **Security Controls**: Protection against SQL injection, command injection, and bypass attempts
- **Abstention Logic**: Intelligent handling of ambiguous or malicious inputs

### Performance Analysis
- **Generation Speed**: Optimized performance across local and cloud models
- **Success Rate**: High-quality query generation with validation
- **Retry Logic**: Intelligent error handling and recovery mechanisms
- **Cost Management**: Token optimization and intelligent model routing

### Dataset Coverage
- **Standard Scenarios**: Comprehensive cybersecurity test cases
- **Real-World Data**: CIC-IDS2017 integration with extensive network flow records
- **Attack Coverage**: DDoS, Brute Force, Web Attacks, Infiltration, Port Scanning, Botnet
- **Privacy Support**: Differential privacy with configurable parameters

## 🛠️ Troubleshooting

### **Common Issues**

**Elasticsearch won't start:**
```bash
# Check system status
make status

# Check port usage
sudo lsof -i :9200

# Reset Elasticsearch
docker-compose down -v
docker-compose up -d
```

**Ollama model errors:**
```bash
# Check available models
ollama list

# Re-pull primary model
ollama pull llama3.1:latest

# Test Ollama connectivity
ollama run llama3.1:latest "test"
```

**GUI won't start:**
```bash
# Check dependencies
pip install -r gui/requirements-gui.txt

# Start with debugging
python gui/start_gui.py --debug

# Check port availability
sudo lsof -i :8501
```

**For detailed GUI troubleshooting, see [gui/README.md](gui/README.md)**

**CIC dataset issues:**
```bash
# Verify CIC files exist
ls -la data_raw/*.csv

# Test single file processing
python src/ingestion/cic_processor.py \
    --input data_raw/Monday-WorkingHours.pcap_ISCX.csv \
    --output test.jsonl --sample 100

# Use GUI for easier processing
python gui/start_gui.py
# Navigate to System Administration → Data Management
```

**Permission errors:**
```bash
# Fix script permissions
chmod +x *.sh scripts/*.sh
```

### **Performance Tuning**

**For optimal generation:**
- Use GUI for interactive feedback and iteration
- Local models for privacy-sensitive scenarios
- External LLMs for complex query requirements

**For better accuracy:**  
- Use enhanced constrained generator (primary method)
- Add domain-specific validation rules
- Test with CIC-IDS2017 real-world data

**For cost optimization:**
- Local models for standard use cases
- External LLMs for enhanced accuracy when needed
- GUI provides usage monitoring and cost controls

### **Debugging & Monitoring**

**System debugging:**
```bash
# Enable verbose logging
export ES_NL2DSL_DEBUG=1

# Check system health
make status
python src/smoke_es.py

# Monitor through GUI
python gui/start_gui.py
# Navigate to System Administration → System Health

# For complete system monitoring features, see gui/README.md
```

**View logs and metrics:**
```bash
# Validation events
tail -f artifacts/results/validator_events.jsonl

# Generated queries and metrics  
ls artifacts/generated/
cat artifacts/results/*.json
```

## 🤝 Contributing

### **Development Setup**

```bash
# Install all dependencies
pip install -r requirements.txt
pip install -r gui/requirements-gui.txt

# Run tests
python -m pytest tests/ --verbose

# Start development environment
make setup                    # Initial setup
python gui/start_gui.py      # GUI development
```

### **Adding New Test Scenarios**

1. Add to `tasks/prompts.yaml` with expert DSL query
2. Generate ground truth: `python src/cli/generate_ground_truth.py`
3. Test: `python src/cli/run_one.py --id new-scenario --gen`
4. Validate with GUI evaluation dashboard

### **Adding New Generator Methods**

1. Create `src/generators/new_method.py` following existing patterns
2. Add integration in `src/generators/enhanced_constrained.py`
3. Test via CLI and GUI interfaces
4. Update validation rules as needed

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 Citation

If you use this system in your research, please cite:

```bibtex
@software{es_nl2dsl,
  title={ES-NL2DSL: Natural Language to Elasticsearch DSL Translation Framework},
  author={Your Name},
  year={2025},
  url={https://github.com/your-username/es-nl2dsl},
  note={Production-ready framework for cybersecurity log analysis with GUI interface}
}
```

## 🌟 **What Makes ES-NL2DSL Special**

✅ **Production-Ready**: Complete system with GUI, not just a research prototype  
✅ **Real Data**: Handles actual CIC-IDS2017 cybersecurity datasets with comprehensive coverage  
✅ **Query Execution**: Not just generation - executes queries and shows actual results  
✅ **Data Export**: One-click CSV/JSON export of query results  
✅ **Multi-LLM**: Local models + 4 external providers with intelligent routing  
✅ **Security-First**: Multi-layer validation with red team testing  
✅ **Super Easy Setup**: One-command deployment with Docker profiles  
✅ **Interactive GUI**: Full-featured web interface for all operations  

## 🙏 Acknowledgments

- Elasticsearch team for the robust search platform
- Ollama team for local LLM infrastructure  
- Streamlit team for the excellent web framework
- CIC-IDS2017 dataset contributors for real-world cybersecurity data

---

🚀 **Ready to translate natural language to Elasticsearch queries?**  
Start with: `make setup` then `python gui/start_gui.py`
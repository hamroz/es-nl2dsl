# ES-NL2DSL Complete Setup Guide

🚀 **Super Easy Reproducible Setup** - Updated for all recent changes

## 🎯 One-Command Setup (Recommended)

```bash
# Clone and setup everything
git clone <repository-url>
cd es-nl2dsl

# Complete automated setup
make setup
```

## 📋 Manual Setup (Step by Step)

### 1. Prerequisites

- **Docker & Docker Compose** (required)
- **Python 3.10.1+** (required)
- **Ollama** (optional - for local models)

### 2. Start Services

```bash
# Basic setup (Elasticsearch only)
docker-compose up -d

# Full setup (with Ollama)
docker-compose --profile full up -d

# With GUI (includes Ollama)
docker-compose --profile gui up -d
```

### 3. Install Dependencies

Choose one method:

**Option A: pip (recommended)**
```bash
pip install -r requirements.txt
pip install -r gui/requirements-gui.txt  # If using GUI
```

**Option B: conda**
```bash
conda env create -f environment.yml
conda activate es-nl2dsl
```

### 4. Initialize System

```bash
./setup.sh
```

## 🖥️ Usage Options

### Command Line Interface
```bash
# Run single test
python src/cli/run_one.py --id scan-001 --gen

# Run full test suite
./run_suite.sh

# Run security tests
make security

# Generate analysis
make results
```

### Graphical Interface
```bash
# Start GUI locally
python gui/start_gui.py

# Or via Docker
docker-compose --profile gui up -d
# Access: http://localhost:8501
```

## 📊 Available Services

| Service | Port | Purpose | Access |
|---------|------|---------|---------|
| Elasticsearch | 9200 | Data storage | elastic:ChangeMe_123 |
| Ollama | 11434 | Local LLM | API endpoint |
| Streamlit GUI | 8501 | Web interface | http://localhost:8501 |

## 🔄 Docker Profiles

- **Default**: Elasticsearch only
- **full**: + Ollama service  
- **gui**: + GUI application

```bash
# Start specific profiles
docker-compose --profile full up -d
docker-compose --profile gui up -d
```

## 📁 Directory Structure

```
es-nl2dsl/
├── src/                    # Core application code
│   ├── cli/               # Command line tools
│   ├── generators/        # Query generation methods
│   ├── analysis/         # Research & evaluation tools
│   ├── security/         # Security framework
│   └── ...
├── gui/                   # Streamlit web interface
├── artifacts/             # Generated results & configs
├── data_raw/             # Raw data files
├── docker-compose.yml    # Unified Docker config
├── requirements.txt      # Python dependencies
└── setup.sh             # Automated setup script
```

## 🧪 Testing Commands

```bash
# Basic functionality
make test

# Complete evaluation
make all

# Security testing
make security

# Privacy analysis
make privacy

# Schema drift test
make drift

# System status
make status
```

## 🔧 Troubleshooting

### Elasticsearch Issues
```bash
# Check status
curl -u elastic:ChangeMe_123 http://localhost:9200/_cluster/health

# Reset data
docker-compose down -v
docker-compose up -d
```

### Permission Issues
```bash
# Fix script permissions
chmod +x *.sh scripts/*.sh
```

### Dependency Issues
```bash
# Clean install
pip install --force-reinstall -r requirements.txt
```

## 📈 Advanced Features

### CIC-IDS2017 Dataset
```bash
# Process real cybersecurity data
python src/process_cic_ids2017.py --input data_raw/Monday.csv --output data_raw/processed.jsonl
python src/ingest_large.py --file data_raw/processed.jsonl --index logs_cic_ids2017
```

### External LLMs
Configure API keys in GUI or use environment variables:
```bash
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
```

## 📋 Quick Verification

After setup, verify everything works:

```bash
# 1. Check services
make status

# 2. Run basic test
python src/cli/run_one.py --id scan-001 --gen

# 3. Start GUI
python gui/start_gui.py
```

## 🆘 Getting Help

- Check system status: `make status`
- View logs: `docker-compose logs`
- Test connectivity: `python src/smoke_es.py`
- Run diagnostics: See CLAUDE.md

---

✅ **System is now fully reproducible with automated setup!**
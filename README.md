# ES-NL2DSL: Natural Language to Elasticsearch DSL Translation

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Elasticsearch 8.11](https://img.shields.io/badge/elasticsearch-8.11-orange.svg)](https://www.elastic.co/)
[![Django 5.1](https://img.shields.io/badge/django-5.1-green.svg)](https://www.djangoproject.com/)
[![React 18](https://img.shields.io/badge/react-18-blue.svg)](https://reactjs.org/)

A production-ready framework for translating natural language queries into Elasticsearch DSL with enterprise-grade web application, built-in security, privacy preservation, and comprehensive evaluation capabilities across multiple datasets including CIC-IDS2017.

## 🎯 Overview

ES-NL2DSL enables secure translation of human-readable queries into Elasticsearch queries for cybersecurity log analysis. The system provides:

- **Production Web Application**: Django REST API backend with React TypeScript frontend
- **Enterprise Authentication**: JWT-based auth with role-based access control (RBAC)
- **Async Processing**: Celery-based background tasks with Redis broker
- **Multi-LLM Support**: Local models (Ollama) + External APIs (OpenAI, Google Gemini, DeepSeek, Qwen)
- **Enhanced Accuracy**: Improved validation, sophisticated security filtering, and prompt enhancement
- **CIC-IDS2017 Integration**: Real-world cybersecurity dataset with 2.8M+ network flow records
- **Advanced Security**: Context-aware filtering, pattern-based threat detection, bypass attempt blocking
- **Constrained Generation**: LLM-based translation with schema and security validation
- **Privacy Preservation**: Differential privacy with configurable ε parameters
- **Comprehensive Evaluation**: Enhanced framework supporting both standard and CIC datasets

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [System Requirements](#-system-requirements)
- [Installation](#-installation)
- [Web Application](#-web-application)
- [External LLM Setup](#-external-llm-setup)
- [CIC-IDS2017 Dataset](#-cic-ids2017-dataset)
- [API Usage](#-api-usage)
- [Core Scripts](#-core-scripts)
- [Advanced Features](#-advanced-features)
- [Enhanced Evaluation](#-enhanced-evaluation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/es-nl2dsl.git
cd es-nl2dsl

# Start the complete system (recommended)
./start_system.sh

# This will:
# 1. Start Docker services (Elasticsearch, PostgreSQL, Redis)
# 2. Set up Django backend with migrations
# 3. Create admin user (admin@es-nl2dsl.local / admin123)
# 4. Start Celery worker for async processing
# 5. Start Django API server (port 8000)
# 6. Start React frontend (port 3000)

# Access the application:
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/api/v1/
# Admin: admin@es-nl2dsl.local / admin123

# Stop the system
./stop_system.sh
```

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (Port 3000)              │
│                    TypeScript + Material-UI                 │
└─────────────────┬───────────────────────────────────────────┘
                  │ HTTP/WebSocket
┌─────────────────▼───────────────────────────────────────────┐
│              Django REST API Backend (Port 8000)            │
│                  JWT Auth + Role-Based Access               │
└──────┬──────────┬──────────────┬────────────────────────────┘
       │          │              │
┌──────▼────┐ ┌──▼───┐ ┌────────▼────────┐
│PostgreSQL │ │Redis │ │ Celery Workers  │
│ Database  │ │Cache │ │ Async Processing│
└───────────┘ └──────┘ └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │ Core Scripts    │
                        │ (src/*.py)      │
                        └────────┬────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Elasticsearch       │
                    │    (Data Storage)       │
                    └─────────────────────────┘
```

### Technology Stack

- **Backend**: Django 5.1, Django REST Framework, Celery
- **Frontend**: React 18, TypeScript, Material-UI, Vite
- **Database**: PostgreSQL 15 (application), Elasticsearch 8.11 (search)
- **Cache/Queue**: Redis 7
- **Authentication**: JWT (djangorestframework-simplejwt)
- **WebSocket**: Django Channels for real-time updates
- **Containerization**: Docker & Docker Compose

## 💻 System Requirements

### Hardware
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 20GB free space
- **CPU**: 4+ cores recommended

### Software
- **Python**: 3.10+ (3.11 recommended)
- **Node.js**: 18+ (for React frontend)
- **Docker & Docker Compose**: Latest stable version
- **Ollama**: 0.3.x with models like `llama3.1:latest`
- **Operating System**: macOS 14.5+, Ubuntu 20.04+, or Windows 11 with WSL2

### Network Ports
- **3000**: React frontend
- **8000**: Django backend
- **9200**: Elasticsearch
- **5432**: PostgreSQL
- **6379**: Redis
- **11434**: Ollama

## 📦 Installation

### Prerequisites

1. **Install Docker & Docker Compose**
   ```bash
   # macOS
   brew install docker docker-compose
   
   # Ubuntu
   sudo apt-get update
   sudo apt-get install docker.io docker-compose
   ```

2. **Install Python 3.10+**
   ```bash
   # macOS
   brew install python@3.11
   
   # Ubuntu
   sudo apt-get install python3.11 python3.11-venv
   ```

3. **Install Node.js 18+**
   ```bash
   # macOS
   brew install node@18
   
   # Ubuntu
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install nodejs
   ```

4. **Install Ollama (for local LLMs)**
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull required model
   ollama pull llama3.1:latest
   ```

### Full System Setup

```bash
# Clone repository
git clone https://github.com/yourusername/es-nl2dsl.git
cd es-nl2dsl

# Start everything with one command
./start_system.sh

# Verify installation
python test_core_functionality.py
```

### Manual Setup (Development)

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Backend setup
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements-auth.txt
pip install django djangorestframework channels channels-redis
python manage.py migrate
python manage.py createsuperuser

# 3. Start backend services
celery -A es_nl2dsl_api worker --loglevel=info &
python manage.py runserver 8000 &

# 4. Frontend setup
cd ../frontend
npm install
npm start

# 5. Create Elasticsearch indices
curl -X PUT "localhost:9200/logs_net" -H 'Content-Type: application/json' \
     -u elastic:ChangeMe_123 -d @artifacts/mappings.json
```

## 🌐 Web Application

### Accessing the Application

1. **Start the system**: `./start_system.sh`
2. **Open browser**: http://localhost:3000
3. **Login**: admin@es-nl2dsl.local / admin123

### Main Features

#### 🤖 Query Generator
- Natural language to Elasticsearch DSL conversion
- Multiple generation methods (constrained, rules, zero-shot)
- Real-time validation and execution
- Export results as CSV/JSON

#### 📊 Evaluation Dashboard  
- Run comprehensive evaluations
- Compare methods and models
- View metrics (F1 score, precision, recall)
- Batch evaluation support

#### 🛡️ Security Testing
- Red team adversarial testing
- Security boundary validation
- Abstain rate monitoring

#### 🔒 Privacy Analysis
- Differential privacy configuration
- Privacy-utility tradeoff visualization
- Noise injection testing

#### ⚙️ System Administration
- User management and RBAC
- System health monitoring
- Index management
- Audit logging

## 🔌 API Usage

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@es-nl2dsl.local", "password": "admin123"}'

# Returns JWT tokens:
# {
#   "access": "eyJ0eXAiOiJKV1Q...",
#   "refresh": "eyJ0eXAiOiJKV1Q..."
# }
```

### Query Generation

```bash
# Generate query (async)
curl -X POST http://localhost:8000/api/v1/queries/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Find malicious events from 2017-07-04",
    "method": "constrained",
    "index": "logs_net",
    "model": "llama3.1:latest"
  }'

# Check status
curl http://localhost:8000/api/v1/queries/<task_id>/ \
  -H "Authorization: Bearer <access_token>"

# Execute query
curl -X POST http://localhost:8000/api/v1/queries/<task_id>/execute/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"max_size": 1000}'

# Export results
curl http://localhost:8000/api/v1/queries/<task_id>/export/csv/ \
  -H "Authorization: Bearer <access_token>" \
  --output results.csv
```

## 🛠️ Core Scripts

The original query generation scripts are preserved and integrated:

```bash
# Generate constrained query
python src/generate_constrained.py \
  --prompt "Find malicious traffic from IP 192.168.1.1" \
  --model llama3.1:latest

# Validate query
python src/validator.py \
  --dsl artifacts/queries/generated.json \
  --rules artifacts/validator_rules.yaml

# Evaluate queries
python src/eval_exec.py \
  --expert artifacts/queries/expert.json \
  --candidate artifacts/queries/generated.json
```

## 🔧 External LLM Setup

### OpenAI GPT-4
```bash
export OPENAI_API_KEY="your-api-key"
python src/generate_constrained.py --prompt "..." --model gpt-4o
```

### Google Gemini
```bash
export GOOGLE_API_KEY="your-api-key"
python src/generate_constrained.py --prompt "..." --model gemini-2.0-flash
```

### DeepSeek
```bash
export DEEPSEEK_API_KEY="your-api-key"
python src/generate_constrained.py --prompt "..." --model deepseek-reasoner
```

## 📊 CIC-IDS2017 Dataset

### Setup
```bash
# Download dataset
wget https://www.unb.ca/cic/datasets/ids-2017.html

# Process CSV files
python src/process_cic_ids2017.py \
  --input data_raw/Monday-WorkingHours.pcap_ISCX.csv \
  --output data_raw/processed_monday.jsonl

# Create index
curl -X PUT "localhost:9200/logs_cic_ids2017" \
  -H 'Content-Type: application/json' \
  -u elastic:ChangeMe_123 \
  -d @artifacts/mappings_cic_enhanced.json

# Ingest data
python src/ingest_large.py \
  --file data_raw/processed_monday.jsonl \
  --index logs_cic_ids2017
```

## 🧪 Enhanced Evaluation

### Run Full Evaluation Suite
```bash
# Standard dataset evaluation
make test

# CIC-IDS2017 evaluation
make test-cic

# Security testing
make security

# Privacy analysis
make privacy

# Generate comprehensive report
make results
```

### Metrics
- **Structural F1 Score**: ≥0.85 (AST-based semantic similarity)
- **Execution F1 Score**: ≥0.80 (Result set overlap)
- **Adversarial Block Rate**: 95%+ malicious prompts rejected
- **False Positive Rate**: <3% legitimate queries blocked

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check if ports are in use
   lsof -i :3000 :8000 :9200 :5432 :6379
   
   # Kill conflicting processes
   kill -9 <PID>
   ```

2. **Docker issues**
   ```bash
   # Reset Docker services
   docker-compose down -v
   docker-compose up -d
   ```

3. **Database migrations**
   ```bash
   cd backend
   source venv/bin/activate
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Celery not processing tasks**
   ```bash
   # Check Celery logs
   tail -f backend/logs/celery_worker.log
   
   # Restart Celery
   pkill -f celery
   cd backend && celery -A es_nl2dsl_api worker --loglevel=info &
   ```

## 📚 Documentation

- **[CORE.md](CORE.md)**: Technical design and architecture details
- **[CLAUDE.md](CLAUDE.md)**: Development guide for AI assistants
- **[Migration Guide](docs/MIGRATION.md)**: Upgrading from older versions

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Elasticsearch for powerful search capabilities
- Ollama for local LLM support
- CIC-IDS2017 dataset from Canadian Institute for Cybersecurity
- Django and React communities for excellent frameworks
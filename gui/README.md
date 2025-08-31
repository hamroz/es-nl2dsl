# ES-NL2DSL Streamlit GUI

A comprehensive web interface for the ES-NL2DSL framework, providing an intuitive way to interact with all system capabilities through a modern browser interface with advanced query execution, data visualization, and real-time system management.

## 🚀 Key Features

### 🤖 Query Generator
- **Natural Language Input**: Convert plain English queries to Elasticsearch DSL
- **Dynamic Index Selection**: Real-time discovery and selection from all available Elasticsearch indices
- **Multiple Generation Methods**: Enhanced constrained, rules-based, zero-shot, and external LLM approaches
- **Query Execution**: Execute generated queries against selected indices with configurable result limits (10-10,000 docs)
- **Multi-Format Results**: View results in Table, JSON, or Raw Data formats with syntax highlighting
- **One-Click Export**: Download query results as CSV or JSON with proper formatting
- **External LLM Integration**: Support for OpenAI, Anthropic, Google Gemini, DeepSeek, and Qwen
- **Performance Metrics**: Real-time execution timing and hit count monitoring
- **Interactive Examples**: Pre-built cybersecurity query examples with smart suggestions

### 🔍 Data Explorer
- **Interactive Index Browsing**: Real-time data retrieval and exploration across all indices
- **Advanced Filtering**: Field-specific search with type-aware filtering options
- **Dynamic Field Discovery**: Automatic schema detection with intelligent field mapping
- **Data Visualization**: Customizable charts and statistical analysis
- **Sample Inspection**: Expandable document views with detailed field analysis
- **Index Statistics**: Health monitoring and performance metrics
- **Custom Query Builder**: DSL generation with real-time validation
- **Time-Series Analysis**: Temporal filtering and aggregations for cybersecurity data

### 📊 Evaluation Dashboard
- **Multi-Scenario Testing**: Run evaluations across all 12 standard test scenarios plus CIC-IDS2017
- **Method Comparison**: Side-by-side analysis of different generation approaches
- **Real-time Progress**: Live updates during evaluation runs with detailed metrics
- **Interactive Visualizations**: Advanced charts for performance analysis and statistical insights
- **Results Management**: Comprehensive export capabilities (CSV, JSON) with historical tracking
- **Statistical Analysis**: F1-scores, precision, recall, Jaccard similarity, and AST comparison
- **Batch Processing**: Parallel execution with configurable worker threads

### 🛡️ Security Testing
- **Red Team Testing**: Automated testing against 20+ adversarial prompts with threat classification
- **Custom Security Scenarios**: Test your own security prompts and attack patterns
- **Real-time Analysis**: Live monitoring of block rates and security metrics
- **Threat Categorization**: Automatic classification of SQL injection, command injection, and bypass attempts
- **Security Reports**: Comprehensive security assessment with detailed threat analysis
- **Abstain Rate Monitoring**: Track system behavior on ambiguous or malicious inputs
- **Context-Aware Filtering**: Advanced pattern detection with severity classification

### 🔒 Privacy Analysis
- **Differential Privacy**: Analysis across multiple epsilon values (0.5, 1.0, 2.0) with utility comparisons
- **Privacy-Utility Curves**: Visual representation of privacy-accuracy tradeoffs
- **Comparative Analysis**: Side-by-side comparison of privacy levels with performance impact
- **Interactive Charts**: Plotly-powered visualizations with drill-down capabilities
- **Privacy Reports**: Detailed analysis exports with statistical validation
- **DP Index Creation**: Automated creation of differentially private datasets
- **Noise Analysis**: Impact assessment of privacy noise on query accuracy

### 🎭 Multi-Modal Data Adaptation
- **AI-Powered Analysis**: Automatic schema discovery and data source adaptation
- **Multi-Format Ingestion**: Support for CSV, JSON, Syslog, and custom formats
- **Intelligent Field Mapping**: Semantic analysis with automated field suggestions
- **Real-time Profiling**: Statistical analysis with quality assessment and anomaly detection
- **Custom Index Creation**: Optimized mappings for new data sources
- **Adaptation History**: Historical tracking with configuration management
- **Integration Testing**: Validation with existing query generation pipelines

### ⚙️ System Administration
**6 Specialized Management Tabs:**

#### 🔧 System Status
- **Real-time Monitoring**: Elasticsearch, Ollama, and service health with automatic refresh
- **Resource Tracking**: CPU, memory, disk usage with performance alerts
- **Connection Testing**: Comprehensive connectivity diagnostics with detailed error reporting
- **Component Dashboard**: Status indicators for all system components

#### 📊 Data Management
- **General CSV Upload**: Standard CSV file ingestion with preview and validation
- **CIC-IDS2017 Integration**: Specialized cybersecurity dataset processing with:
  - File selection with preview and metadata analysis
  - Batch processing with real-time progress tracking
  - Configurable sampling and chunk sizes
  - Automatic index creation with enhanced mappings
  - Real-time conversion from CIC format to network log format
  - Bulk ingestion with comprehensive error handling
- **Data Validation**: Quality checks and format validation before ingestion

#### 🗂️ Index Management
- **Index Overview**: View all indices with document counts, sizes, and health status
- **Specialized Index Creation**: 
  - Differential Privacy indices with configurable epsilon values
  - Schema drift indices for robustness testing
  - Custom index creation with advanced mapping options
- **Index Operations**: Safe deletion with confirmation dialogs and backup options
- **Mapping Analysis**: Schema inspection and field analysis tools

#### 🤖 External LLM Management
- **Multi-Provider Support**: Configuration for OpenAI, Anthropic, Google, DeepSeek, Qwen
- **Secure Credential Management**: Environment variable integration with validation
- **Real-time Health Checking**: Provider availability and model validation
- **Performance Monitoring**: Response times, success rates, and usage tracking
- **Model Selection**: Interactive provider and model selection with availability status
- **Configuration Export/Import**: Deployment automation and backup capabilities

#### 🔄 Maintenance & Monitoring
- **System Cleanup**: Generated file cleanup with selective deletion options
- **Performance Benchmarking**: System performance analysis and optimization
- **Docker Integration**: Container logs inspection and health monitoring
- **Elasticsearch Cluster Management**: Cluster health and optimization tools
- **Log Monitoring**: Real-time system and application log viewing

#### 📋 Live Logs
- **Real-time Log Streaming**: Live monitoring of system operations and user activities
- **Multi-Level Filtering**: Component-specific log filtering with severity levels
- **Error Tracking**: Comprehensive error logging with detailed stack traces
- **Performance Analytics**: Request timing and system performance metrics

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10.1+** (required for compatibility) with required packages:
   ```bash
   pip install -r requirements.txt -r gui/requirements-gui.txt
   ```

2. **Elasticsearch** running on localhost:9200 with authentication
3. **Ollama** with models (llama3.1:latest is primary, also supports deepseek-r1:14b, deepseek-r1:1.5b)

### Startup Options

**Recommended - Automated startup with health checks:**
```bash
python gui/start_gui.py
```

**Alternative - Direct Streamlit launch:**
```bash
streamlit run gui/streamlit_app.py
```

**Docker Deployment:**
```bash
# Complete environment with all services
docker-compose --profile gui up -d
```

This will start:
- Elasticsearch (localhost:9200)
- Ollama (localhost:11434)  
- ES-NL2DSL GUI (localhost:8501)

## 📖 Usage Guide

### Navigation Structure

The GUI provides **7 main sections** accessible via the sidebar navigation:

1. **🤖 Query Generator**: Interactive query creation with execution and export
2. **🔍 Data Explorer**: Direct data browsing and analysis across all indices  
3. **📊 Evaluation Dashboard**: Comprehensive scenario evaluation and comparison
4. **🛡️ Security Testing**: Adversarial testing and security validation
5. **🔒 Privacy Analysis**: Differential privacy analysis and visualization
6. **🎭 Multi-Modal Data Adaptation**: AI-powered data integration for new sources
7. **⚙️ System Administration**: Complete system management with 6 specialized tabs

### Real-time System Status

The header displays live status of all system components:
- **Elasticsearch**: Connection status, authentication, and index count
- **Ollama**: Service status and loaded model information
- **Indices**: Number of available data indices with health indicators  
- **Models**: Active LLM models with availability status

### Complete Query Workflow

#### Step 1: Query Generation
1. **Navigate** to 🤖 Query Generator
2. **Select Index** from dropdown (logs_net, logs_cic_ids2017, custom indices)
3. **Enter Query** in natural language (e.g., "Find malicious events on July 4, 2017")
4. **Choose Method** (Enhanced Constrained recommended)
5. **Configure Advanced Options** (external LLMs, validation, few-shot examples)
6. **Generate Query** - View generated Elasticsearch DSL with validation results

#### Step 2: Query Execution & Analysis  
1. **Execute Query** against selected index with configurable limits
2. **Choose Display Format**:
   - **Table View**: Structured data with truncated fields for overview
   - **JSON View**: Pretty-printed JSON with syntax highlighting
   - **Raw Data**: Expandable document sections for detailed inspection
3. **Monitor Performance**: View execution time, hit counts, and query complexity
4. **Export Results**: One-click CSV or JSON download with proper formatting

#### Step 3: Data Exploration
1. **Navigate** to 🔍 Data Explorer for deeper analysis
2. **Browse Index Data** with advanced filtering capabilities
3. **Analyze Field Distributions** with statistical visualizations
4. **Create Custom Filters** for targeted data exploration

### Evaluation & Testing Workflow

1. **Scenario Testing** via 📊 Evaluation Dashboard
   - Select test scenarios (standard or CIC-IDS2017)
   - Compare generation methods with statistical analysis
   - Export comprehensive results for research

2. **Security Validation** via 🛡️ Security Testing  
   - Run red team testing against adversarial prompts
   - Validate security controls and abstain behavior
   - Generate security assessment reports

3. **Privacy Analysis** via 🔒 Privacy Analysis
   - Create differential privacy indices with configurable epsilon
   - Analyze privacy-utility tradeoffs with interactive visualizations
   - Export privacy impact assessments

### System Administration Workflow

1. **Health Monitoring** via ⚙️ System Administration → 🔧 System Status
2. **Data Integration** via 📊 Data Management:
   - Upload standard CSV files with preview
   - Process CIC-IDS2017 datasets with specialized handling
   - Monitor ingestion progress with error handling
3. **Index Operations** via 🗂️ Index Management
4. **External LLM Setup** via 🤖 External LLMs with secure credential management  
5. **System Maintenance** via 🔄 Maintenance with cleanup and optimization
6. **Live Monitoring** via 📋 Live Logs for real-time system observation

## 🔧 Configuration

### Environment Variables

```bash
# Core system configuration
ES_HOST=localhost:9200
ES_ADMIN_USER=elastic
ES_ADMIN_PASSWORD=ChangeMe_123  
ES_READER_USER=reader
ES_READER_PASSWORD=ReaderPwd_123
OLLAMA_HOST=localhost:11434
STREAMLIT_SERVER_PORT=8501

# External LLM providers (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
QWEN_API_KEY=sk-...
```

### Advanced Customization

- **Themes**: Modify CSS styling in `streamlit_app.py`
- **Components**: Extend functionality by adding components in `gui/components/`
- **Backend Integration**: Customize system integration in `gui/utils/backend_interface.py`
- **Logging**: Configure logging levels and outputs in `gui/utils/logging_utils.py`

## 🛠️ Troubleshooting

### Common Issues

**GUI won't start:**
```bash
# Check dependencies
pip install -r requirements.txt -r gui/requirements-gui.txt

# Verify Streamlit installation  
streamlit --version

# Check port availability
sudo lsof -i :8501
```

**System status shows offline:**
```bash
# Elasticsearch
docker-compose up -d

# Ollama  
ollama serve
# Or check Docker container: docker ps
```

**Query generation fails:**
```bash
# Ensure Ollama model is available
ollama pull llama3.1:latest

# Test connectivity
python src/smoke_es.py

# Check authentication
curl -u elastic:ChangeMe_123 "localhost:9200/_cluster/health"
```

**Query execution errors:**
- Verify index selection matches available indices
- Check result limit settings (10-10,000 range)
- Review query validation messages in interface
- Monitor system resources during large queries

**CIC dataset processing issues:**
- Verify CIC CSV files are in `data_raw/` directory
- Use GUI data management for easier processing
- Start with smaller sample sizes for testing
- Check Elasticsearch disk space for large ingestions

### Performance Optimization

**For faster query generation:**
- Use GUI interface for immediate feedback and iteration
- Leverage external LLMs for complex queries (faster inference)
- Start with smaller indices for development and testing

**For better accuracy:**
- Use Enhanced Constrained generator (primary method)  
- Add domain-specific examples in advanced options
- Test with CIC-IDS2017 real-world data for validation

**For optimal resource usage:**
- Monitor system resources through admin panel
- Use appropriate result limits for query execution
- Leverage parallel processing in evaluation dashboard
- Regular system cleanup via maintenance tools

### Debugging & Monitoring

**Live system monitoring:**
- Use 📋 Live Logs tab for real-time system observation
- Monitor component status in header for immediate feedback
- Access comprehensive diagnostics via 🔧 System Status

**Performance analysis:**
- View query execution metrics in Query Generator
- Use Data Explorer for index performance analysis
- Monitor resource usage through System Administration

**Error diagnostics:**
- Check Live Logs for detailed error messages and stack traces
- Review validation messages in query generation interface
- Use health checks in System Administration for connectivity issues

## 🏗️ Architecture

### Component Structure

```
gui/
├── streamlit_app.py              # Main application with 7-section navigation
├── components/                   # Complete UI component suite
│   ├── query_generator.py        # Enhanced query interface with execution
│   ├── data_explorer.py          # Interactive data browsing and analysis
│   ├── evaluation_dashboard.py   # Comprehensive evaluation management
│   ├── security_panel.py         # Security testing and validation
│   ├── privacy_analysis.py       # Differential privacy analysis
│   ├── multimodal_dashboard.py   # AI-powered data adaptation
│   ├── admin_panel.py            # 6-tab system administration
│   └── external_llm_panel.py     # Multi-provider LLM management
├── utils/                        # Enhanced utilities and backend integration
│   ├── backend_interface.py      # Complete backend API with query execution
│   └── logging_utils.py          # Comprehensive logging framework
├── start_gui.py                  # Intelligent startup with health checks
├── requirements-gui.txt          # Streamlit-specific dependencies
└── README.md                     # This comprehensive documentation
```

### Technology Stack

- **Frontend**: Streamlit 1.28+ with custom CSS and responsive design
- **Visualization**: Plotly, Matplotlib, Seaborn with interactive charts
- **Data Processing**: Pandas, NumPy with optimized data handling
- **Backend Integration**: Direct API calls with comprehensive error handling
- **Security**: Multi-layer validation with real-time threat detection
- **External APIs**: OpenAI, Anthropic, Google, DeepSeek, Qwen integration
- **Containerization**: Docker Compose with multi-profile support

## 🔒 Security Features

- **Query Validation**: Multi-layer security validation before execution
- **Authentication**: Secure Elasticsearch credential management
- **Input Sanitization**: Advanced input validation and sanitization
- **Threat Detection**: Real-time detection of malicious patterns
- **Privacy Protection**: Differential privacy with configurable parameters
- **Secure API Management**: External LLM credential protection
- **Audit Logging**: Comprehensive activity logging for security analysis

## 📈 Performance Features

- **Parallel Processing**: Concurrent evaluation and data processing
- **Intelligent Caching**: Optimized data retrieval and storage
- **Resource Monitoring**: Real-time system resource tracking
- **Query Optimization**: Elasticsearch query performance optimization
- **Streaming Data**: Efficient handling of large datasets
- **Background Processing**: Non-blocking operations with progress tracking

## 🚀 Development & Extension

### Adding New Components

1. **Create Component**: Add new module in `gui/components/`
2. **Update Navigation**: Modify navigation in `streamlit_app.py`
3. **Backend Integration**: Extend `backend_interface.py` with new capabilities
4. **Add Documentation**: Update this README with new features
5. **Testing**: Comprehensive testing with both local and Docker deployments

### Contributing Guidelines

- Follow existing code structure and naming conventions
- Add comprehensive docstrings and inline documentation
- Implement proper error handling and user feedback
- Test with multiple data sources and edge cases
- Update documentation for all new features
- Ensure security best practices in all implementations

---

**🌐 Access the GUI**: http://localhost:8501

**📚 Complete Framework Documentation**: See main [README.md](../README.md) in project root

**🛡️ Production-Ready**: Complete cybersecurity analysis platform with real-world data support
# ES-NL2DSL Streamlit GUI

A comprehensive web interface for the ES-NL2DSL framework, providing an intuitive way to interact with all system capabilities through a modern browser interface.

## Features

### 🤖 Query Generator
- **Natural Language Input**: Convert plain English queries to Elasticsearch DSL
- **Multiple Methods**: Support for constrained generation, rules-based, and zero-shot approaches
- **Real-time Validation**: Immediate feedback on query syntax and compliance
- **Example Gallery**: Pre-built examples for common cybersecurity queries
- **Export Functionality**: Download generated queries as JSON files

### 📊 Evaluation Dashboard
- **Multi-Scenario Testing**: Run evaluations across all 12 test scenarios
- **Parallel Execution**: Efficient batch processing with configurable workers
- **Real-time Progress**: Live updates during evaluation runs
- **Interactive Visualizations**: Charts and graphs for performance analysis
- **Results Export**: CSV and JSON export for further analysis

### 🛡️ Security Testing
- **Red Team Testing**: Automated testing against 20+ adversarial prompts
- **Custom Prompts**: Test your own security scenarios
- **Real-time Analysis**: Live monitoring of block rates and security metrics
- **Threat Categorization**: Automatic classification of attack types
- **Security Reports**: Comprehensive security assessment downloads

### 🔒 Privacy Analysis
- **Differential Privacy**: Analysis across multiple epsilon values (0.5, 1.0, 2.0)
- **Privacy-Utility Curves**: Visual representation of tradeoffs
- **Comparative Analysis**: Side-by-side comparison of privacy levels
- **Interactive Charts**: Plotly-powered visualizations
- **Privacy Reports**: Detailed analysis exports

### ⚙️ System Administration
- **Component Status**: Real-time monitoring of Elasticsearch and Ollama
- **Data Management**: CSV upload, data ingestion, and export capabilities
- **Index Operations**: Create, manage, and delete Elasticsearch indices
- **System Health**: Comprehensive health checks and diagnostics
- **Maintenance Tools**: Cleanup operations and performance monitoring

## Quick Start

### Prerequisites

1. **Python 3.8+** with required packages:
   ```bash
   pip install -r requirements.txt -r requirements-gui.txt
   ```

2. **Elasticsearch** running on localhost:9200
3. **Ollama** with offline LLMs (llama3.1:latest is primary, also supports deepseek-r1:14b, gpt-oss:20b, etc.)

### Local Startup

The easiest way to start the GUI:

```bash
python gui/start_gui.py
```

This script will:
- Check all dependencies and services
- Set up required directories
- Pull missing Ollama models if needed
- Start the Streamlit interface

**Manual startup:**
```bash
streamlit run gui/streamlit_app.py
```

### Docker Deployment

For a complete containerized environment:

```bash
# Start all services with Docker Compose
docker-compose -f docker-compose.gui.yml up -d

# Or use the startup script with Docker mode
python gui/start_gui.py --docker
```

This will start:
- Elasticsearch (localhost:9200)
- Ollama (localhost:11434)
- ES-NL2DSL GUI (localhost:8501)

## Usage Guide

### Navigation

The GUI is organized into five main sections accessible via the sidebar:

1. **🤖 Query Generator**: Interactive query creation and testing
2. **📊 Evaluation Dashboard**: Comprehensive scenario evaluation
3. **🛡️ Security Testing**: Adversarial prompt testing and security analysis
4. **🔒 Privacy Analysis**: Differential privacy evaluation and visualization
5. **⚙️ System Administration**: System management and monitoring

### System Status

The header shows real-time status of all system components:
- **Elasticsearch**: Connection status and index count
- **Ollama**: Service status and available models
- **Indices**: Number of available data indices
- **Models**: Loaded LLM models

### Query Generation Workflow

1. **Enter Query**: Type your natural language query in the input box
2. **Select Method**: Choose from constrained, rules, or zero-shot generation
3. **Configure Options**: Set advanced parameters like schema validation
4. **Generate**: Click the generate button to create the DSL query
5. **Review Results**: Examine the generated JSON and metrics
6. **Export**: Download the query for external use

### Evaluation Workflow

1. **Select Scenarios**: Choose which test scenarios to evaluate
2. **Choose Methods**: Pick generation methods to compare
3. **Configure Execution**: Set parallel processing options
4. **Run Evaluation**: Execute the evaluation suite
5. **Analyze Results**: Review metrics and visualizations
6. **Export Data**: Download results for further analysis

## Configuration

### Environment Variables

- `ES_HOST`: Elasticsearch host (default: localhost:9200)
- `OLLAMA_HOST`: Ollama host (default: localhost:11434)
- `STREAMLIT_SERVER_PORT`: GUI port (default: 8501)

### Customization

- **Themes**: Modify CSS in `streamlit_app.py` for custom styling
- **Components**: Extend functionality by adding new components in `gui/components/`
- **Backend**: Customize system integration in `gui/utils/backend_interface.py`

## Troubleshooting

### Common Issues

**GUI won't start:**
- Check Python dependencies: `pip install -r requirements-gui.txt`
- Verify Streamlit installation: `streamlit --version`

**System status shows offline:**
- Elasticsearch: `docker-compose up -d elasticsearch`
- Ollama: `ollama serve` or check Docker container

**Generation fails:**
- Ensure Ollama model is available: `ollama pull llama3.1:latest`
- Check Elasticsearch connectivity and authentication

**Performance issues:**
- Reduce parallel workers in evaluation dashboard
- Check system resources (CPU, memory)
- Optimize Elasticsearch index settings

### Logs and Debugging

- **Streamlit logs**: Check terminal output where GUI was started
- **Elasticsearch logs**: `docker-compose logs elasticsearch`
- **System diagnostics**: Use the health check in System Administration

## Architecture

### Component Structure

```
gui/
├── streamlit_app.py          # Main application entry point
├── components/               # UI components
│   ├── query_generator.py    # Query generation interface
│   ├── evaluation_dashboard.py # Evaluation management
│   ├── security_panel.py     # Security testing interface
│   ├── privacy_analysis.py   # Privacy analysis tools
│   └── admin_panel.py        # System administration
├── utils/                    # Utilities
│   └── backend_interface.py  # Backend integration
├── start_gui.py              # Startup script
├── Dockerfile                # Container definition
└── README.md                 # This file
```

### Technology Stack

- **Frontend**: Streamlit with custom CSS
- **Visualization**: Plotly, Matplotlib, Seaborn
- **Data Processing**: Pandas, NumPy
- **Backend Integration**: Subprocess calls to core framework
- **Containerization**: Docker and Docker Compose

## Development

### Adding New Features

1. **Create Component**: Add new component in `gui/components/`
2. **Update Navigation**: Modify sidebar in `streamlit_app.py`
3. **Backend Integration**: Extend `backend_interface.py` as needed
4. **Testing**: Test all functionality before deployment

### Contributing

- Follow existing code structure and naming conventions
- Add comprehensive docstrings and comments
- Test with both local and Docker deployments
- Update this README for new features

## Security Notes

- The GUI inherits all security measures from the core framework
- Red team testing validates security controls
- All generated queries undergo validation before execution
- Docker deployment provides additional isolation

## Performance Optimization

- Use parallel execution for batch operations
- Implement caching for frequently accessed data
- Monitor system resources through admin panel
- Optimize Elasticsearch queries for large datasets

---

For more information about the ES-NL2DSL framework, see the main [README.md](../README.md) in the project root.
# Model Dependencies and Setup

## Required Models

### Primary Model: Llama 3.1 Latest

**Model**: `llama3.1:latest`  
**Provider**: Ollama  
**Size**: ~4.7GB download  
**Purpose**: Natural language to Elasticsearch DSL translation

#### Installation
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the model (this may take 10-30 minutes)
ollama pull llama3.1:latest

# Verify installation
ollama list
```

#### Alternative Models

If `llama3.1:latest` is not available, these alternatives can be used:

1. **Llama 3.2 (Smaller, Faster)**
   ```bash
   ollama pull llama3.2:latest  # ~2GB
   ```
   - Update `--model llama3.2:latest` in scripts
   - Faster generation, potentially lower accuracy

2. **Llama 3.1 70B (Larger, More Accurate)**
   ```bash
   ollama pull llama3.1:70b  # ~40GB, requires 64GB+ RAM
   ```
   - Best accuracy for complex queries
   - Significantly slower generation

3. **Code Llama (Code-Specialized)**
   ```bash
   ollama pull codellama:latest  # ~3.8GB
   ```
   - May perform better on structured query generation

#### Model Configuration

The model is configured in `src/generate_constrained.py`:

```python
def call_local_model(prompt, model="llama3.1:latest"):
    # Timeout: 60 seconds (increase for complex queries)
    # Max retries: 2 (increase for better reliability)
```

To change the default model:
```bash
# Option 1: Environment variable
export ES_NL2DSL_MODEL="llama3.2:latest"

# Option 2: Command line argument
python src/generate_constrained.py --model llama3.2:latest --prompt "your query"
```

## Elasticsearch Version

**Version**: 8.11.1  
**Distribution**: Official Elastic Docker image  
**Configuration**: Single-node cluster with security enabled

### Features Used
- **Search API**: Query execution and result retrieval
- **Mapping API**: Schema validation and field type checking
- **Security**: User roles and authentication
- **Count API**: Cost estimation for validation

### Compatibility
- **Minimum**: Elasticsearch 8.0+
- **Tested**: 8.11.1, 8.11.3
- **Maximum**: Should work with 8.x series

## Python Dependencies

### Core Requirements
- **Python**: 3.10.1+ (tested up to 3.11)
- **Elasticsearch client**: 8.11.1
- **JSON processing**: orjson 3.10.7 (faster than standard json)
- **Data handling**: pandas 2.2.2
- **Schema validation**: jsonschema 4.22.0

### Dependency Rationale

1. **elasticsearch==8.11.1**: Official client matching ES version
2. **orjson==3.10.7**: High-performance JSON parsing for query processing
3. **pandas==2.2.2**: CSV data ingestion and manipulation
4. **PyYAML==6.0.2**: Configuration file parsing
5. **jsonschema==4.22.0**: Query schema validation
6. **python-dotenv==1.0.1**: Environment configuration management
7. **tabulate==0.9.0**: Results table formatting

### Version Pinning

All versions are pinned for reproducibility:
- **Major versions**: Ensure compatibility
- **Minor versions**: Consistent behavior across environments
- **Patch versions**: Reproducible results

### Installation Troubleshooting

**Common Issues:**

1. **Conflicting dependencies**:
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

2. **ARM64 macOS issues**:
   ```bash
   # Use conda for better ARM64 support
   conda env create -f environment.yml
   ```

3. **Elasticsearch client SSL issues**:
   ```bash
   # Disable SSL verification (development only)
   export PYTHONHTTPSVERIFY=0
   ```

## Performance Recommendations

### Hardware Requirements

**Minimum** (Development):
- **RAM**: 4GB (2GB for ES, 2GB for Python + model)
- **CPU**: 2 cores
- **Storage**: 10GB

**Recommended** (Production/Research):
- **RAM**: 16GB (4GB for ES, 8GB for model, 4GB for Python)
- **CPU**: 8+ cores (parallel processing)
- **Storage**: 50GB (models, data, results)
- **GPU**: Optional (can accelerate Ollama)

### Optimization Tips

1. **Model Performance**:
   - Use GPU acceleration if available: `ollama serve --gpu`
   - Increase model context: Modify Ollama settings
   - Use quantized models for speed: `llama3.1:latest-q4_0`

2. **Elasticsearch Performance**:
   - Increase JVM heap: `ES_JAVA_OPTS=-Xms4g -Xmx4g`
   - Use SSD storage for better I/O
   - Optimize mapping for query patterns

3. **Python Performance**:
   - Use `orjson` instead of standard `json`
   - Enable pandas optimizations: `pd.set_option('mode.copy_on_write', True)`
   - Use multiprocessing for batch operations

## Deployment Considerations

### Development Environment
- Local Ollama installation
- Docker Compose for Elasticsearch
- Virtual environment for Python

### CI/CD Environment
- Use Ollama Docker containers
- GitHub Actions with adequate resources
- Cached model downloads

### Production Environment
- Dedicated Ollama server with GPU
- Elasticsearch cluster (3+ nodes)
- Load balancing for query generation

### Security Considerations
- Model access controls
- API rate limiting
- Input sanitization
- Result validation

## Model Updates

### Updating Llama Model
```bash
# Check for updates
ollama list

# Update to latest
ollama pull llama3.1:latest

# Verify compatibility
python src/run_one.py --id scan-001 --gen
```

### Updating Elasticsearch
```bash
# Update docker image
docker-compose pull
docker-compose up -d

# Verify compatibility
python src/smoke_es.py
```

### Testing After Updates
```bash
# Run test suite
make test

# Check metrics consistency
python src/render_tables.py
```

## Model Licensing

### Llama 3.1
- **License**: Custom Llama license (commercial use allowed)
- **Attribution**: Meta AI
- **Restrictions**: See official license terms

### Research Use
- Academic use generally permitted
- Cite appropriate papers and models
- Follow institutional guidelines

### Commercial Use
- Review Llama license terms
- Consider data privacy implications
- Implement appropriate safeguards

## Support and Updates

### Model Issues
- Check Ollama documentation: https://ollama.ai/docs
- Model-specific issues: https://huggingface.co/meta-llama

### Elasticsearch Issues
- Official documentation: https://www.elastic.co/guide/
- Client issues: https://github.com/elastic/elasticsearch-py

### Integration Issues
- Check system logs: `docker-compose logs`
- Verify model availability: `ollama list`
- Test connectivity: `make status`
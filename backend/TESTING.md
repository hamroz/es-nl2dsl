# ES-NL2DSL Backend Testing Guide

This document provides comprehensive information about the Django backend testing infrastructure for the ES-NL2DSL project.

## Overview

The backend testing suite provides comprehensive coverage for all Django applications including:

- **Authentication**: User management, JWT tokens, sessions, security policies
- **Queries**: Query generation, execution, validation, and export
- **Evaluation**: Scenario evaluation, batch processing, metrics calculation
- **Security**: Security testing, threat detection, validation
- **Privacy**: Privacy features and data protection
- **Data Management**: Data ingestion, processing, and index management
- **System Admin**: System monitoring, health checks, and administration
- **Analytics**: System metrics and analytics

## Test Infrastructure

### Test Configuration
- **Test Settings**: `es_nl2dsl_api.test_settings.py`
- **Pytest Configuration**: `pytest.ini`
- **Coverage Configuration**: Auto-generated `.coveragerc`
- **Test Factories**: `tests/factories.py` with Factory Boy
- **Fixtures**: `conftest.py` with pytest fixtures

### Test Database
- Uses SQLite in-memory database for speed
- Migrations disabled during tests
- Database isolation between tests
- Fast password hashers for performance

### Dependencies
- **pytest**: Modern test framework
- **pytest-django**: Django integration
- **pytest-cov**: Coverage reporting  
- **pytest-xdist**: Parallel test execution
- **factory-boy**: Test data factories
- **responses**: HTTP request mocking
- **freezegun**: Time-based testing
- **model-bakery**: Alternative model factory

## Running Tests

### Quick Start
```bash
# From project root
./run_backend_tests.sh

# From backend directory  
python run_tests.py
```

### Test Execution Options

#### Basic Usage
```bash
./run_backend_tests.sh                 # All tests with coverage
./run_backend_tests.sh --fast          # All tests without coverage
./run_backend_tests.sh --parallel      # Parallel execution
./run_backend_tests.sh --keepdb        # Keep test DB between runs
./run_backend_tests.sh --verbose       # Verbose output
```

#### Test Filtering
```bash
./run_backend_tests.sh --app queries          # Specific app
./run_backend_tests.sh --test authentication  # Pattern matching
./run_backend_tests.sh --html                 # HTML coverage report
```

#### Advanced Options
```bash
# Fast development workflow
./run_backend_tests.sh --fast --parallel --keepdb

# Comprehensive coverage analysis
./run_backend_tests.sh --html --verbose

# Specific test categories
python run_tests.py --unit          # Unit tests only
python run_tests.py --integration   # Integration tests only
python run_tests.py --api          # API tests only
```

## Test Structure

### Test Organization
```
backend/
├── tests/
│   ├── __init__.py
│   └── factories.py           # Centralized test factories
├── authentication/tests/
│   ├── __init__.py
│   ├── test_authentication.py  # Existing comprehensive tests
│   ├── test_models.py          # Model tests
│   ├── test_services.py        # Service and utility tests
│   └── test_performance.py     # Performance tests
├── queries/tests.py            # Comprehensive query tests
├── evaluation/tests.py         # Evaluation system tests
├── security/tests.py          # Security feature tests
├── privacy/tests.py           # Privacy feature tests
├── data_management/tests.py   # Data processing tests
├── system_admin/tests.py      # Admin interface tests
├── analytics/tests.py         # Analytics tests
├── conftest.py               # Pytest configuration
├── pytest.ini               # Test settings
└── run_tests.py             # Advanced test runner
```

### Test Categories

#### Unit Tests (`@pytest.mark.unit`)
- Model field validation
- Method behavior
- Property calculations
- Serializer validation
- Utility functions

#### Integration Tests (`@pytest.mark.integration`)
- Complete workflows
- Cross-app interactions
- External service integration
- End-to-end scenarios

#### API Tests (`@pytest.mark.api`)
- REST endpoint functionality
- Authentication/authorization
- Request/response validation
- Error handling

#### Performance Tests (`@pytest.mark.slow`)
- Load testing
- Query performance
- Memory usage
- Concurrent operations

## Test Factories

### Available Factories
```python
from tests.factories import (
    UserFactory, AdminUserFactory, ViewerUserFactory,
    QueryTaskFactory, GeneratedQueryFactory, QueryExecutionFactory,
    EvaluationScenarioFactory, EvaluationRunFactory, EvaluationBatchFactory,
    SecurityTestFactory, DataIngestionTaskFactory,
    SystemMetricFactory
)
```

### Usage Examples
```python
# Create test users
user = UserFactory()
admin = AdminUserFactory()

# Create query with results
task = QueryTaskFactory(method='constrained')
query = GeneratedQueryFactory(task=task, validation_status='PASS')
execution = QueryExecutionFactory(task=task, total_hits=100)

# Create evaluation scenario
scenario = EvaluationScenarioFactory(category='security')
run = EvaluationRunFactory(scenario=scenario, f1_score=0.92)
```

## Mock Services

### Elasticsearch Mocking
```python
@responses.activate
def test_query_execution():
    responses.add(
        responses.POST,
        'http://localhost:9200/logs_net/_search',
        json={'hits': {'total': {'value': 100}}},
        status=200
    )
    # Test code here
```

### Celery Task Mocking
```python
@patch('queries.tasks.generate_query_task.delay')
def test_async_generation(mock_task):
    mock_task.return_value.id = 'test-task-id'
    # Test code here
```

### External Service Mocking
```python
@patch('requests.post')
def test_external_api(mock_requests):
    mock_requests.return_value.json.return_value = {'success': True}
    # Test code here
```

## Coverage Reporting

### Coverage Configuration
- **Source**: All application code
- **Exclusions**: Migrations, settings, test files, virtual environments
- **Minimum**: 75% coverage required
- **Reports**: Terminal, HTML, XML formats

### HTML Coverage Reports
```bash
./run_backend_tests.sh --html
# Open htmlcov/index.html in browser
```

### Coverage Analysis
- Line coverage tracking
- Branch coverage analysis
- Missing line identification
- Exclude pragma support

## Testing Best Practices

### Test Naming
```python
def test_user_creation_with_valid_data():
    """Test creating user with all valid fields"""

def test_query_execution_returns_correct_results():
    """Test that query execution returns expected result format"""

def test_authentication_fails_with_invalid_credentials():
    """Test authentication rejection with wrong password"""
```

### Test Structure
```python
class TestQueryGeneration:
    """Test query generation functionality"""
    
    def test_valid_generation(self):
        """Test successful query generation"""
        # Arrange
        task = QueryTaskFactory(method='constrained')
        
        # Act
        result = generate_query(task.prompt, task.method)
        
        # Assert
        assert result['status'] == 'success'
        assert 'query' in result
```

### Fixtures and Factories
```python
@pytest.fixture
def completed_query_task():
    """Provide a completed query task for testing"""
    task = QueryTaskFactory(status='completed')
    GeneratedQueryFactory(task=task, validation_status='PASS')
    return task

def test_export_functionality(completed_query_task):
    """Test exporting completed query results"""
    # Test uses the fixture
```

### Mocking Guidelines
- Mock external services (Elasticsearch, Redis, etc.)
- Mock file system operations
- Mock time-dependent operations
- Use patch decorators for clarity

## Performance Testing

### Database Query Optimization
```python
def test_query_performance():
    """Test that queries are optimized"""
    with django.test.utils.override_settings(DEBUG=True):
        from django.db import connection
        with connection.cursor() as cursor:
            # Test code
            assert len(connection.queries) < 5  # Maximum queries
```

### Memory Usage Testing
```python
import psutil

def test_memory_usage():
    """Test memory consumption stays within limits"""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    # Test operations
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    assert memory_increase < 50 * 1024 * 1024  # 50MB limit
```

## Debugging Tests

### Verbose Output
```bash
./run_backend_tests.sh --verbose
```

### Interactive Debugging
```python
import pytest

def test_something():
    # Add breakpoint
    pytest.set_trace()
    # Test code here
```

### Test Isolation Issues
```bash
# Run single test
pytest queries/tests.py::TestQueryGeneration::test_valid_generation -v

# Run with database recreation
pytest --reuse-db=false

# Clear cache between tests
pytest --cache-clear
```

## Continuous Integration

### GitHub Actions Integration
```yaml
- name: Run Backend Tests
  run: |
    cd backend
    python run_tests.py --parallel --coverage-xml
```

### Coverage Reporting
- Upload coverage reports to services
- Fail builds on coverage threshold
- Track coverage trends over time

## Maintenance

### Adding New Tests
1. Create test files following naming conventions
2. Use appropriate markers (`@pytest.mark.unit`, etc.)
3. Add factories for new models
4. Update this documentation

### Updating Dependencies
1. Update requirements.txt
2. Test with new versions
3. Update CI configuration
4. Document breaking changes

### Performance Optimization
- Profile slow tests with `pytest --durations=10`
- Optimize database queries
- Use appropriate fixtures
- Consider parallel execution

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure Django settings are correct
export DJANGO_SETTINGS_MODULE=es_nl2dsl_api.test_settings

# Check Python path
export PYTHONPATH=$PWD:$PYTHONPATH
```

#### Database Issues
```bash
# Reset test database
rm -f test_*.db
python manage.py migrate --settings=es_nl2dsl_api.test_settings
```

#### Coverage Issues
```bash
# Clear coverage data
rm -rf .coverage htmlcov/
# Run tests with fresh coverage
./run_backend_tests.sh --html
```

#### Parallel Execution Issues
```bash
# Disable parallel execution for debugging
./run_backend_tests.sh --verbose
```

### Getting Help
- Check test output for detailed error messages
- Use `--verbose` flag for more information
- Review test logs for debugging information
- Check Django test documentation for advanced features

## Summary

The ES-NL2DSL backend testing infrastructure provides:

✅ **Comprehensive Coverage**: All Django apps tested  
✅ **Modern Tooling**: Pytest with advanced features  
✅ **Easy Execution**: Simple scripts for all workflows  
✅ **Performance**: Parallel execution and optimized setup  
✅ **Reporting**: HTML and terminal coverage reports  
✅ **Mocking**: External service isolation  
✅ **Factories**: Consistent test data generation  
✅ **Documentation**: Clear usage examples and best practices  

The testing suite ensures production-ready code quality and provides confidence for continuous development and deployment.
"""
Pytest configuration for ES-NL2DSL backend tests
"""

import pytest
import tempfile
import os
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from unittest.mock import patch


@pytest.fixture(scope='session')
def db_with_migrations(django_db_setup, django_db_blocker):
    """Set up test database for the session with proper migrations"""
    from django.core.management import call_command
    from django.db import connection
    
    with django_db_blocker.unblock():
        # Force Django to create the database with migrations
        print("\n🔧 Setting up test database with migrations...")
        call_command('migrate', verbosity=0, interactive=False)
        
        # Verify critical tables exist
        cursor = connection.cursor()
        tables = connection.introspection.table_names(cursor)
        
        # Check for essential tables
        required_tables = ['auth_users', 'django_content_type', 'auth_permission']
        missing_tables = [table for table in required_tables if table not in tables]
        
        if missing_tables:
            raise RuntimeError(f"❌ Critical tables missing after migration: {missing_tables}")
        
        print(f"✅ Test database setup complete. Tables created: {len(tables)}")
        print(f"📋 Key tables: {[t for t in tables if 'auth' in t or 'django' in t][:5]}...")
    
    yield


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db, db_with_migrations):
    """Enable database access for all tests with proper migrations"""
    pass


@pytest.fixture
def temp_media_root():
    """Provide a temporary media root for file uploads"""
    with tempfile.TemporaryDirectory() as tmpdir:
        with override_settings(MEDIA_ROOT=tmpdir):
            yield tmpdir


@pytest.fixture
def temp_artifacts_path():
    """Provide a temporary artifacts path for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_path = Path(tmpdir) / 'artifacts'
        artifacts_path.mkdir()
        with override_settings(ARTIFACTS_PATH=artifacts_path):
            yield artifacts_path


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test"""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch requests for tests"""
    with patch('requests.post') as mock_post:
        # Default successful response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'took': 5,
            'timed_out': False,
            'hits': {
                'total': {'value': 100, 'relation': 'eq'},
                'hits': []
            }
        }
        yield mock_post


@pytest.fixture
def mock_celery_task():
    """Mock Celery task execution for tests"""
    with patch('celery.current_app.send_task') as mock_task:
        mock_task.return_value.id = 'test-task-id'
        mock_task.return_value.status = 'SUCCESS'
        yield mock_task


@pytest.fixture
def sample_query():
    """Provide a sample Elasticsearch query for tests"""
    return {
        "query": {
            "bool": {
                "must": [
                    {"match": {"message": "error"}}
                ],
                "filter": [
                    {"range": {"@timestamp": {"gte": "2024-01-01", "lte": "2024-01-02"}}}
                ]
            }
        }
    }


@pytest.fixture
def sample_es_results():
    """Provide sample Elasticsearch results for tests"""
    return {
        "took": 5,
        "timed_out": False,
        "hits": {
            "total": {"value": 100, "relation": "eq"},
            "hits": [
                {
                    "_index": "logs_net",
                    "_id": "1",
                    "_score": 1.0,
                    "_source": {
                        "@timestamp": "2024-01-01T10:00:00Z",
                        "message": "error in authentication",
                        "src_ip": "192.168.1.100",
                        "dst_ip": "10.0.0.1",
                        "src_port": 12345,
                        "dst_port": 80
                    }
                }
            ]
        }
    }


# Markers for test categorization
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "api: API tests")
    config.addinivalue_line("markers", "celery: Celery task tests")
    config.addinivalue_line("markers", "elasticsearch: Tests requiring Elasticsearch")
    config.addinivalue_line("markers", "security: Security tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Slow tests")


# Test collection
def pytest_collection_modifyitems(config, items):
    """Modify test items during collection"""
    # Add slow marker to integration tests
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.slow)
        
        # Add unit marker to model and serializer tests
        if any(keyword in item.name.lower() for keyword in ["model", "serializer"]):
            if "unit" not in item.keywords:
                item.add_marker(pytest.mark.unit)
        
        # Add api marker to view and API tests
        if any(keyword in item.name.lower() for keyword in ["view", "api", "endpoint"]):
            if "api" not in item.keywords:
                item.add_marker(pytest.mark.api)
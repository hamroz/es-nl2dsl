"""
Django settings for es_nl2dsl_api tests.
This file is used specifically for running tests.
"""

from .settings import *
import os
import tempfile

# Override database settings for testing
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

# Enable migrations during testing to create tables
# For speed, we could disable this later but for now we need the tables
# MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
SECRET_KEY = 'test-secret-key-for-testing-only'
DEBUG = True
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast hasher for tests
]

# Disable caching during tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Use local memory for Celery during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
BROKER_BACKEND = 'memory'

# Channel layers for testing
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# Temporary directory for test file uploads
TEST_MEDIA_ROOT = tempfile.mkdtemp()
MEDIA_ROOT = TEST_MEDIA_ROOT

# Test file paths
TEST_ARTIFACTS_PATH = Path(tempfile.mkdtemp()) / "test_artifacts"
TEST_DATA_PATH = Path(tempfile.mkdtemp()) / "test_data"

# Override for testing
ARTIFACTS_PATH = TEST_ARTIFACTS_PATH
DATA_PATH = TEST_DATA_PATH

# Disable rate limiting during tests
RATE_LIMITING = {
    'DEFAULT_RATE': '1000/min',
    'LOGIN_RATE': '1000/min',
    'QUERY_GENERATION_RATE': '1000/min',
    'QUERY_EXECUTION_RATE': '1000/min',
    'DATA_EXPORT_RATE': '1000/min',
}

# Disable security middleware during tests
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Mock external services for testing
ELASTICSEARCH_HOST = "mock-elasticsearch:9200"
ELASTICSEARCH_USER = "test-user"
ELASTICSEARCH_PASSWORD = "test-password"

# Disable audit logging during tests (unless specifically testing it)
AUDIT_LOGGING = {
    'ENABLED': False,
    'LOG_SENSITIVE_DATA': False,
    'RETENTION_DAYS': 30,
    'LOG_SUCCESSFUL_LOGINS': False,
    'LOG_FAILED_LOGINS': False,
    'LOG_QUERY_OPERATIONS': False,
}

# Logging configuration for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',  # Reduce database query logging
            'handlers': ['console'],
            'propagate': False,
        },
        'elasticsearch': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'celery': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}
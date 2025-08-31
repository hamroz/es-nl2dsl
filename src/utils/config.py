#!/usr/bin/env python3
"""
Configuration Manager: Centralized system configuration and credential management

This module provides centralized configuration management for the ES-NL2DSL system,
handling environment variables, credential management, and connection parameters
for Elasticsearch and other system components. It ensures secure credential handling
with environment-based configuration and provides consistent connection settings
across all system modules.

Key capabilities:
- Environment-based configuration with .env file support
- Secure credential management with role-based access (admin/reader)
- Elasticsearch connection configuration with SSL/TLS support
- Default index and system parameter management
- Centralized configuration access for all system components
- Development and production environment support

The module implements security best practices by loading sensitive credentials
from environment variables and providing appropriate access levels for different
system operations (admin for index management, reader for query execution).

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Elasticsearch configuration
ES_CONFIG = {
    'host': os.getenv('ES_HOST', 'localhost'),
    'port': int(os.getenv('ES_PORT', 9200)),
    'scheme': os.getenv('ES_SCHEME', 'http'),
}

# Admin credentials (for index operations)
ES_ADMIN_CREDS = {
    'user': os.getenv('ES_ADMIN_USER', 'elastic'),
    'password': os.getenv('ES_ADMIN_PASSWORD', 'ChangeMe_123'),
}

# Reader credentials (for query operations)
ES_READER_CREDS = {
    'user': os.getenv('ES_READER_USER', 'reader'),
    'password': os.getenv('ES_READER_PASSWORD', 'ReaderPwd_123'),
}

# Default index
ES_DEFAULT_INDEX = os.getenv('ES_DEFAULT_INDEX', 'logs_net')

def get_es_client_config(use_admin=False):
    """Get Elasticsearch client configuration"""
    creds = ES_ADMIN_CREDS if use_admin else ES_READER_CREDS
    return {
        'hosts': [{
            'host': ES_CONFIG['host'],
            'port': ES_CONFIG['port'],
            'scheme': ES_CONFIG['scheme']
        }],
        'basic_auth': (creds['user'], creds['password']),
        'verify_certs': False
    }
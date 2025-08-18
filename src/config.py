#!/usr/bin/env python3
"""Configuration loader for ES-NL2DSL using .env file"""

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
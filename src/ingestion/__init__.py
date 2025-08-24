"""Data ingestion and processing for ES-NL2DSL"""
from .base import ingest_csv
from .bulk import ingest_bulk
from .cic_processor import process_cic_dataset
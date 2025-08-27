"""Data Adaptation Module

Simple, focused tools for adapting to new log data from different systems.
"""

from .schema_analyzer import SchemaAnalyzer
from .data_adapter import DataAdapter
from .ai_assistant import AIAssistant

__all__ = [
    'SchemaAnalyzer',
    'DataAdapter', 
    'AIAssistant'
]

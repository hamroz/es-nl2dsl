"""Simplified logging utilities for GUI components

Provides clean, simple logging for user actions and system operations.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import streamlit as st
import json

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure the main GUI logger
def setup_gui_logger(name: str = "gui") -> logging.Logger:
    """Setup and configure the GUI logger with comprehensive formatting"""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler for real-time visibility
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # File handler for persistent logging
    file_handler = logging.FileHandler(logs_dir / "gui_activity.log", mode='a')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    
    # Debug file handler
    debug_handler = logging.FileHandler(logs_dir / "gui_debug.log", mode='a')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(debug_handler)
    
    return logger

# Global logger instance
gui_logger = setup_gui_logger()

class GUILogger:
    """Enhanced GUI logging class with structured logging capabilities"""
    
    def __init__(self, component_name: str):
        self.component = component_name
        self.logger = gui_logger
        self.session_id = self._get_session_id()
        
    def _get_session_id(self) -> str:
        """Get or create a session ID for tracking user sessions"""
        if 'session_id' not in st.session_state:
            st.session_state.session_id = f"session_{int(time.time())}"
        return st.session_state.session_id
        
    def _format_message(self, action: str, details: str = "", emoji: str = "") -> str:
        """Format log message with simple, clean structure"""
        if details:
            return f"{emoji} {action}: {details}"
        else:
            return f"{emoji} {action}"
        
    def _format_simple_details(self, **kwargs) -> str:
        """Format details into a simple readable string"""
        if not kwargs:
            return ""
        
        parts = []
        for key, value in kwargs.items():
            if value is not None and value != "":
                if isinstance(value, (int, float)):
                    parts.append(f"{key}={value}")
                elif isinstance(value, str) and len(value) < 50:
                    parts.append(f"{key}={value}")
                elif isinstance(value, (list, tuple)):
                    parts.append(f"{key}=[{len(value)} items]")
                else:
                    parts.append(f"{key}=<data>")
        
        return ", ".join(parts)

    # User Interaction Logging
    def log_user_action(self, action: str, **kwargs):
        """Log user interactions like button clicks, form submissions"""
        details = self._format_simple_details(**kwargs)
        msg = self._format_message(action, details, "👤")
        self.logger.info(msg)
    
    def log_button_click(self, button_name: str, **kwargs):
        """Log button click events"""
        details = self._format_simple_details(**kwargs)
        msg = self._format_message(f"Clicked {button_name}", details, "🔘")
        self.logger.info(msg)
    
    def log_selection_change(self, element_type: str, old_value: Any, new_value: Any, **kwargs):
        """Log dropdown/selectbox changes"""
        if str(new_value) != str(old_value):
            msg = self._format_message(f"Selected {new_value} from {element_type}", "", "📋")
            self.logger.info(msg)
    
    def log_input_change(self, input_type: str, input_name: str, value_length: int = None, **kwargs):
        """Log form input changes (without logging actual content for privacy)"""
        details = f"{input_name}" + (f" ({value_length} chars)" if value_length else "")
        msg = self._format_message(f"Updated {input_type}", details, "✏️")
        self.logger.info(msg)
    
    def log_file_upload(self, filename: str, file_size: int, file_type: str):
        """Log file upload events"""
        size_mb = file_size / (1024 * 1024)
        details = f"{filename} ({size_mb:.1f}MB, {file_type})"
        msg = self._format_message("Uploaded file", details, "📤")
        self.logger.info(msg)
    
    def log_download(self, filename: str, data_type: str):
        """Log file download events"""
        details = f"{filename} ({data_type})"
        msg = self._format_message("Downloaded", details, "📥")
        self.logger.info(msg)

    # Navigation Logging
    def log_page_load(self, page_name: str, **kwargs):
        """Log page/component loads"""
        msg = self._format_message(f"Navigated to {page_name}", "", "📄")
        self.logger.info(msg)
    
    def log_tab_switch(self, from_tab: str, to_tab: str):
        """Log tab navigation"""
        msg = self._format_message(f"Switched tab to {to_tab}", "", "🔄")
        self.logger.info(msg)
    
    def log_navigation(self, from_page: str, to_page: str):
        """Log main navigation changes"""
        msg = self._format_message(f"Navigated from {from_page} to {to_page}", "", "🧭")
        self.logger.info(msg)

    # System Operation Logging
    def log_system_operation(self, operation: str, **kwargs):
        """Log backend system operations"""
        details = self._format_simple_details(**kwargs)
        msg = self._format_message(operation, details, "⚙️")
        self.logger.info(msg)
    
    def log_query_generation(self, method: str, model: str, prompt_length: int, **kwargs):
        """Log query generation requests"""
        details = f"method={method}, model={model}, prompt_length={prompt_length}"
        msg = self._format_message("Query generation started", details, "⚙️")
        self.logger.info(msg)
    
    def log_query_execution(self, index: str, query_type: str = "query", **kwargs):
        """Log Elasticsearch query executions"""
        details = self._format_simple_details(index=index, **kwargs)
        msg = self._format_message("Query executed", details, "⚙️")
        self.logger.info(msg)
    
    def log_data_operation(self, operation: str, data_source: str, record_count: int = None, **kwargs):
        """Log data ingestion and processing operations"""
        details = self._format_simple_details(data_source=data_source, record_count=record_count, **kwargs)
        msg = self._format_message(f"Data {operation}", details, "⚙️")
        self.logger.info(msg)

    # State and Configuration Logging
    def log_state_change(self, state_name: str, old_value: Any, new_value: Any):
        """Log session state changes"""
        if str(new_value) != str(old_value):
            msg = self._format_message(f"State changed: {state_name}={new_value}", "", "🔧")
            self.logger.debug(msg)
    
    def log_configuration_change(self, config_name: str, new_value: Any, **kwargs):
        """Log configuration changes"""
        msg = self._format_message(f"Config changed: {config_name}={new_value}", "", "⚙️")
        self.logger.info(msg)

    # Performance Logging
    def log_performance(self, operation: str, duration_ms: float, **kwargs):
        """Log performance metrics"""
        details = f"{operation} took {duration_ms:.1f}ms"
        extra_details = self._format_simple_details(**kwargs)
        if extra_details:
            details += f", {extra_details}"
        msg = self._format_message("Performance", details, "⏱️")
        self.logger.info(msg)

    # Error and Warning Logging
    def log_error(self, error_type: str, error_message: str, **kwargs):
        """Log errors with context"""
        details = f"{error_type}: {error_message}"
        msg = self._format_message("Error", details, "❌")
        self.logger.error(msg)
    
    def log_warning(self, warning_type: str, warning_message: str, **kwargs):
        """Log warnings with context"""
        details = f"{warning_type}: {warning_message}"
        msg = self._format_message("Warning", details, "⚠️")
        self.logger.warning(msg)

    # Success and Status Logging
    def log_success(self, operation: str, **kwargs):
        """Log successful operations"""
        details = self._format_simple_details(**kwargs)
        msg = self._format_message(f"{operation} completed", details, "✅")
        self.logger.info(msg)
    
    def log_status(self, status_type: str, status_message: str, **kwargs):
        """Log general status information"""
        details = f"{status_type}: {status_message}"
        msg = self._format_message("Status", details, "📊")
        self.logger.info(msg)

    # Utility Methods
    def get_user_context(self) -> Dict[str, Any]:
        """Get current user session context for logging"""
        context = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "component": self.component
        }
        
        # Add Streamlit session state info (non-sensitive)
        if hasattr(st.session_state, 'current_page'):
            context["current_page"] = st.session_state.current_page
            
        return context

# Convenience functions for direct use
def get_gui_logger(component_name: str) -> GUILogger:
    """Get a GUI logger instance for a specific component"""
    return GUILogger(component_name)

# Performance measurement decorator
def log_performance(component_name: str, operation_name: str):
    """Decorator to automatically log function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_gui_logger(component_name)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(f"{operation_name}::{func.__name__}", duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.log_error(f"{operation_name}::{func.__name__}", str(e), duration_ms=duration_ms)
                raise
                
        return wrapper
    return decorator

# Context manager for logging operations
class LogOperation:
    """Context manager for logging start/end of operations"""
    
    def __init__(self, logger: GUILogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        self.logger.log_system_operation(f"{self.operation} started", **self.context)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            self.logger.log_success(f"{self.operation} completed", 
                                   **self.context, duration_ms=duration_ms)
        else:
            self.logger.log_error(f"{self.operation} failed", str(exc_val), 
                                 **self.context, duration_ms=duration_ms)
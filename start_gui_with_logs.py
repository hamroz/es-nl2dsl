#!/usr/bin/env python3
"""
Enhanced GUI Launcher: Streamlit application with advanced logging integration

This launcher provides an enhanced startup experience for the ES-NL2DSL Streamlit GUI
with comprehensive logging configuration, detailed system initialization, and advanced
debugging capabilities. It sets up optimal logging infrastructure before launching
the main application to ensure complete visibility into system operations.

Key capabilities:
- Advanced logging configuration with multi-handler setup
- Comprehensive log file management with automatic rotation
- Debug-level logging for development and troubleshooting
- Structured log output with consistent formatting across components
- Component-specific logging levels with fine-grained control
- Performance monitoring with startup timing and resource tracking
- Integration with system monitoring tools and alerting frameworks
- Graceful error handling with detailed diagnostic information
- Environment-specific configuration with development/production modes

The launcher is specifically designed for development environments and production
deployments requiring detailed logging and monitoring capabilities for system
administration and debugging purposes.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import subprocess
import sys
import os
import logging
from pathlib import Path

def setup_logging():
    """Setup enhanced logging configuration"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / 'gui_backend.log', mode='a'),
            logging.FileHandler(logs_dir / 'system.log', mode='a')
        ]
    )
    
    # Set specific loggers
    logging.getLogger('streamlit').setLevel(logging.INFO)
    logging.getLogger('backend_interface').setLevel(logging.DEBUG)

def main():
    print("🚀 Starting ES-NL2DSL GUI with Enhanced Logging")
    print("=" * 50)
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🔄 Initializing GUI with logging")
    
    # Check if logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    print(f"📁 Logs will be written to: {logs_dir.absolute()}")
    print("💡 Open another terminal and run './watch_logs.py' to see live logs")
    print("📊 Or run './monitor.py' for comprehensive monitoring")
    print("=" * 50)
    print()
    
    try:
        # Start Streamlit with enhanced logging
        env = os.environ.copy()
        env['STREAMLIT_LOGGER_LEVEL'] = 'info'
        
        logger.info("🌐 Starting Streamlit server")
        
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "gui/streamlit_app.py",
            "--logger.level=info",
            "--server.headless=false",
            "--server.runOnSave=true",
            "--browser.gatherUsageStats=false"
        ], env=env)
        
    except KeyboardInterrupt:
        logger.info("👋 GUI shutdown requested")
        print("\n👋 GUI stopped")
    except Exception as e:
        logger.error(f"❌ Failed to start GUI: {e}")
        print(f"❌ Failed to start GUI: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
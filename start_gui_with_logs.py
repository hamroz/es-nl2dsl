#!/usr/bin/env python3
"""Start the GUI with enhanced logging"""

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
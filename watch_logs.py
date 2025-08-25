#!/usr/bin/env python3
"""Live log viewer for ES-NL2DSL GUI"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    log_file = Path("logs/gui_backend.log")
    
    print("🔍 ES-NL2DSL Live Log Viewer")
    print("=" * 50)
    print(f"📁 Watching: {log_file.absolute()}")
    print("💡 Tip: Open another terminal and run 'python gui/start_gui.py' to see logs")
    print("🚀 Start using the GUI to see live activity logs!")
    print("=" * 50)
    print()
    
    # Create logs directory if it doesn't exist
    log_file.parent.mkdir(exist_ok=True)
    
    # Create empty log file if it doesn't exist
    if not log_file.exists():
        log_file.touch()
        print("📝 Created new log file")
    
    try:
        if sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
            # Use tail -f on Unix systems
            subprocess.run(['tail', '-f', str(log_file)])
        else:
            # Fallback for Windows or other systems
            print("⚠️  Using Python-based log tailing (less efficient)")
            import time
            with open(log_file, 'r') as f:
                f.seek(0, 2)  # Go to end of file
                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())
                    else:
                        time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n👋 Log viewer stopped")
    except Exception as e:
        print(f"❌ Error watching logs: {e}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Comprehensive monitoring script for ES-NL2DSL system"""

import subprocess
import sys
import os
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import signal

class SystemMonitor:
    def __init__(self):
        self.log_files = [
            "logs/gui_backend.log",
            "logs/system.log"
        ]
        self.running = True
        
    def signal_handler(self, signum, frame):
        print("\n👋 Monitoring stopped")
        self.running = False
        
    def watch_log_file(self, log_file):
        """Watch a single log file"""
        log_path = Path(log_file)
        if not log_path.exists():
            log_path.parent.mkdir(exist_ok=True)
            log_path.touch()
            
        try:
            proc = subprocess.Popen(['tail', '-f', str(log_path)], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE,
                                  text=True)
            
            while self.running:
                output = proc.stdout.readline()
                if output:
                    print(f"[{log_path.name}] {output.rstrip()}")
                else:
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Error watching {log_file}: {e}")
            
    def check_system_status(self):
        """Check system status periodically"""
        while self.running:
            try:
                # Check Elasticsearch
                es_result = subprocess.run([
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "-u", "elastic:ChangeMe_123",
                    "http://localhost:9200/_cluster/health"
                ], capture_output=True, text=True, timeout=5)
                
                es_status = "🟢" if es_result.stdout.strip() == "200" else "🔴"
                
                # Check Ollama
                ollama_result = subprocess.run(
                    ["ollama", "list"], 
                    capture_output=True, text=True, timeout=5
                )
                ollama_status = "🟢" if ollama_result.returncode == 0 else "🔴"
                
                # Check Docker containers
                docker_result = subprocess.run([
                    "docker", "ps", "--filter", "name=elasticsearch", 
                    "--format", "{{.Status}}"
                ], capture_output=True, text=True, timeout=5)
                
                docker_status = "🟢" if "Up" in docker_result.stdout else "🔴"
                
                status_line = f"📊 Status: ES {es_status} | Ollama {ollama_status} | Docker {docker_status}"
                print(f"\r{status_line}", end="", flush=True)
                
            except Exception as e:
                print(f"\r❌ Status check failed: {e}", end="", flush=True)
                
            time.sleep(30)  # Check every 30 seconds
            
    def run(self):
        """Run the monitoring system"""
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print("🔍 ES-NL2DSL System Monitor")
        print("=" * 60)
        print("📁 Monitoring log files:")
        for log_file in self.log_files:
            print(f"   • {log_file}")
        print("📊 System status checks every 30 seconds")
        print("💡 Start the GUI in another terminal to see activity")
        print("=" * 60)
        print()
        
        with ThreadPoolExecutor(max_workers=len(self.log_files) + 1) as executor:
            # Start log watchers
            for log_file in self.log_files:
                executor.submit(self.watch_log_file, log_file)
                
            # Start system status checker
            executor.submit(self.check_system_status)
            
            # Keep main thread alive
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.running = False

def main():
    monitor = SystemMonitor()
    monitor.run()

if __name__ == "__main__":
    main()
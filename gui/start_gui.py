#!/usr/bin/env python3
"""Startup script for ES-NL2DSL GUI with system checks and setup"""
import subprocess
import sys
import time
import json
from pathlib import Path
import argparse

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        "streamlit", "plotly", "pandas", "yaml", "ollama", "elasticsearch"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt -r requirements-gui.txt")
        return False
    
    print("✅ All dependencies found")
    return True

def check_elasticsearch():
    """Check if Elasticsearch is running"""
    print("🔍 Checking Elasticsearch...")
    
    try:
        result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-u", "elastic:ChangeMe_123", 
            "http://localhost:9200/_cluster/health"
        ], capture_output=True, text=True, timeout=10)
        
        if result.stdout.strip() == "200":
            print("✅ Elasticsearch is running")
            return True
        else:
            print("❌ Elasticsearch not responding")
            return False
    except:
        print("❌ Elasticsearch not accessible")
        return False

def check_ollama():
    """Check if Ollama is running and has models"""
    print("🔍 Checking Ollama...")
    
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            models = []
            for line in result.stdout.split('\n')[1:]:
                if line.strip():
                    models.append(line.split()[0])
            
            if models:
                print(f"✅ Ollama running with models: {', '.join(models)}")
                return True
            else:
                print("⚠️ Ollama running but no models found")
                print("  Install a model with: ollama pull llama3.1:latest")
                return False
        else:
            print("❌ Ollama not responding")
            return False
    except:
        print("❌ Ollama not accessible")
        return False

def setup_directories():
    """Create necessary directories"""
    print("📁 Setting up directories...")
    
    directories = [
        "artifacts/generated",
        "artifacts/results", 
        "data_raw",
        "gui/components"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {dir_path}")

def check_configuration():
    """Check if configuration files exist"""
    print("🔍 Checking configuration files...")
    
    required_files = [
        "artifacts/validator_rules.yaml",
        "artifacts/mappings.json", 
        "artifacts/esdsl_schema.json",
        "tasks/prompts.yaml"
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️ Missing configuration files: {', '.join(missing_files)}")
        print("Please ensure all configuration files are present")
        return False
    
    return True

def start_services_docker():
    """Start services using Docker Compose"""
    print("🐳 Starting services with Docker Compose...")
    
    try:
        # Start Elasticsearch and Ollama
        result = subprocess.run([
            "docker-compose", "-f", "docker-compose.gui.yml", "up", "-d"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Services started successfully")
            
            # Wait for services to be ready
            print("⏳ Waiting for services to be ready...")
            time.sleep(30)
            
            return True
        else:
            print(f"❌ Failed to start services: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error starting services: {e}")
        return False

def pull_ollama_model():
    """Pull required Ollama model if not present"""
    print("🤖 Checking for required Ollama model...")
    
    try:
        # Check if llama3.1 is available
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, text=True, timeout=10
        )
        
        if "llama3.1" not in result.stdout:
            print("📥 Pulling llama3.1:latest model...")
            pull_result = subprocess.run(
                ["ollama", "pull", "llama3.1:latest"],
                timeout=600  # 10 minutes timeout
            )
            
            if pull_result.returncode == 0:
                print("✅ Model pulled successfully")
                return True
            else:
                print("❌ Failed to pull model")
                return False
        else:
            print("✅ Model already available")
            return True
            
    except subprocess.TimeoutExpired:
        print("⏳ Model pull is taking longer than expected, continuing...")
        return True
    except Exception as e:
        print(f"⚠️ Error checking/pulling model: {e}")
        return True  # Continue anyway

def start_streamlit():
    """Start the Streamlit application"""
    print("🚀 Starting Streamlit GUI...")
    
    try:
        # Change to project root directory
        project_root = Path(__file__).parent.parent
        
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            "gui/streamlit_app.py",
            "--server.port", "8501",
            "--server.address", "0.0.0.0",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ]
        
        print(f"Running: {' '.join(cmd)}")
        print("🌐 GUI will be available at: http://localhost:8501")
        print("👆 Click the link above or open it in your browser")
        print("\nPress Ctrl+C to stop the application")
        
        # Start Streamlit
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error starting Streamlit: {e}")

def main():
    """Main startup function"""
    parser = argparse.ArgumentParser(description="Start ES-NL2DSL GUI")
    parser.add_argument("--docker", action="store_true", help="Start with Docker Compose")
    parser.add_argument("--skip-checks", action="store_true", help="Skip system checks")
    parser.add_argument("--port", type=int, default=8501, help="Streamlit port (default: 8501)")
    
    args = parser.parse_args()
    
    print("🔍 ES-NL2DSL GUI Startup")
    print("=" * 50)
    
    # Setup directories
    setup_directories()
    
    if not args.skip_checks:
        # Check dependencies
        if not check_dependencies():
            sys.exit(1)
        
        # Check configuration
        if not check_configuration():
            print("⚠️ Some configuration files are missing, but continuing...")
    
    if args.docker:
        # Docker mode
        if not start_services_docker():
            sys.exit(1)
    else:
        # Local mode
        if not args.skip_checks:
            # Check services
            es_ok = check_elasticsearch()
            ollama_ok = check_ollama()
            
            if not es_ok:
                print("\n💡 To start Elasticsearch:")
                print("   docker-compose up -d elasticsearch")
            
            if not ollama_ok:
                print("\n💡 To start Ollama:")
                print("   ollama serve")
                if not pull_ollama_model():
                    print("   ollama pull llama3.1:latest")
            
            if not (es_ok and ollama_ok):
                print("\n⚠️ Some services are not ready. The GUI will still start but some features may not work.")
                print("You can check service status in the System Administration tab.")
    
    # Start Streamlit
    start_streamlit()

if __name__ == "__main__":
    main()
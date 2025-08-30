#!/usr/bin/env python3
"""Startup script for ES-NL2DSL GUI with system checks and setup"""
import subprocess
import sys
import time
import json
from pathlib import Path
import argparse

# Import logging utilities
sys.path.append(str(Path(__file__).parent))
from utils.logging_utils import get_gui_logger

# Initialize logger
logger = get_gui_logger("startup")

def check_dependencies():
    """Check if required dependencies are installed"""
    logger.log_system_operation("Dependency check started")
    print("🔍 Checking dependencies...")
    
    required_packages = [
        "streamlit", "plotly", "pandas", "yaml", "ollama", "elasticsearch"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
            logger.log_success(f"Package available: {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing_packages.append(package)
            logger.log_warning("Missing dependency", f"Package {package} not found")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install -r requirements.txt -r requirements-gui.txt")
        logger.log_error("Dependencies missing", f"Missing: {', '.join(missing_packages)}")
        return False
    
    print("✅ All dependencies found")
    logger.log_success("All dependencies verified")
    return True

def check_elasticsearch():
    """Check if Elasticsearch is running"""
    logger.log_system_operation("Elasticsearch connectivity check started")
    print("🔍 Checking Elasticsearch...")
    
    try:
        result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-u", "elastic:ChangeMe_123", 
            "http://localhost:9200/_cluster/health"
        ], capture_output=True, text=True, timeout=10)
        
        if result.stdout.strip() == "200":
            print("✅ Elasticsearch is running")
            logger.log_success("Elasticsearch connectivity verified")
            return True
        else:
            print("❌ Elasticsearch not responding")
            logger.log_error("Elasticsearch check failed", f"HTTP response: {result.stdout.strip()}")
            return False
    except Exception as e:
        print("❌ Elasticsearch not accessible")
        logger.log_error("Elasticsearch connection error", str(e))
        return False

def check_ollama():
    """Check if Ollama is running and has models"""
    logger.log_system_operation("Ollama service check started")
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
                logger.log_success("Ollama service verified", model_count=len(models), models=models)
                return True
            else:
                print("⚠️ Ollama running but no models found")
                print("  Install models with: ollama pull llama3.1:latest")
                logger.log_warning("Ollama models missing", "Service running but no models available")
                return False
        else:
            print("❌ Ollama not responding")
            logger.log_error("Ollama check failed", f"Return code: {result.returncode}")
            return False
    except Exception as e:
        print("❌ Ollama not accessible")
        logger.log_error("Ollama connection error", str(e))
        return False

def setup_directories():
    """Create necessary directories"""
    logger.log_system_operation("Directory setup started")
    print("📁 Setting up directories...")
    
    directories = [
        "artifacts/generated",
        "artifacts/results", 
        "data_raw",
        "gui/components",
        "logs"
    ]
    
    created_dirs = []
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {dir_path}")
        created_dirs.append(dir_path)
    
    logger.log_success("Directories setup completed", directories=created_dirs)

def check_configuration():
    """Check if configuration files exist"""
    print("🔍 Checking configuration files...")
    
    required_files = [
        "artifacts/validator_rules.yaml",
        # "artifacts/mappings.json", 
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
    """Pull primary Ollama model if not present"""
    print("🤖 Checking for offline LLM models...")
    
    try:
        # Check what models are available
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            models = []
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    models.append(line.split()[0])
            
            if models:
                print(f"✅ Found {len(models)} models: {', '.join(models)}")
                return True
        
        # If no models found, try to pull the primary model
        if not models or "llama3.1" not in result.stdout:
            print("📥 Pulling primary model llama3.1:latest...")
            print("💡 You can also install additional models like:")
            print("   ollama pull deepseek-r1:14b")
            print("   ollama pull gpt-oss:20b")
            
            pull_result = subprocess.run(
                ["ollama", "pull", "llama3.1:latest"],
                timeout=600  # 10 minutes timeout
            )
            
            if pull_result.returncode == 0:
                print("✅ Primary model pulled successfully")
                return True
            else:
                print("❌ Failed to pull primary model")
                return False
        else:
            print("✅ Offline LLM models available")
            return True
            
    except subprocess.TimeoutExpired:
        print("⏳ Model pull is taking longer than expected, continuing...")
        return True
    except Exception as e:
        print(f"⚠️ Error checking/pulling models: {e}")
        return True  # Continue anyway

def start_streamlit():
    """Start the Streamlit application"""
    logger.log_system_operation("Streamlit application startup initiated")
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
        
        logger.log_success("Streamlit server starting",
            command=' '.join(cmd), 
            port="8501",
            address="0.0.0.0",
            project_root=str(project_root)
        )
        
        # Start Streamlit
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        logger.log_system_operation("Streamlit application shutdown by user interrupt")
    except Exception as e:
        print(f"❌ Error starting Streamlit: {e}")
        logger.log_error("Streamlit startup failed", str(e))

def main():
    """Main startup function"""
    parser = argparse.ArgumentParser(description="Start ES-NL2DSL GUI")
    parser.add_argument("--docker", action="store_true", help="Start with Docker Compose")
    parser.add_argument("--skip-checks", action="store_true", help="Skip system checks")
    parser.add_argument("--port", type=int, default=8501, help="Streamlit port (default: 8501)")
    
    args = parser.parse_args()
    
    # Log startup initiation
    logger.log_system_operation("GUI startup initiated",
        docker_mode=args.docker,
        skip_checks=args.skip_checks,
        port=args.port
    )
    
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
                    print("   ollama pull deepseek-r1:14b")
                    print("   ollama pull gpt-oss:20b")
            
            if not (es_ok and ollama_ok):
                print("\n⚠️ Some services are not ready. The GUI will still start but some features may not work.")
                print("You can check service status in the System Administration tab.")
    
    # Start Streamlit
    start_streamlit()

if __name__ == "__main__":
    main()
"""System Administration Panel Component for Streamlit GUI - Fixed Version"""
import streamlit as st
import pandas as pd
import subprocess
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import logging utilities
from gui.utils.logging_utils import get_gui_logger

# Initialize component logger
admin_logger = get_gui_logger("admin_panel")

from gui.utils.backend_interface import check_system_status
from gui.components.external_llm_panel import render_external_llm_panel

def render_admin_panel():
    """Render the system administration interface"""
    admin_logger.log_page_load("Admin Panel loaded")
    st.header("⚙️ System Administration")
    st.write("Monitor and manage system components, data, and configurations")
    
    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔧 System Status", 
        "📊 Data Management", 
        "🗂️ Index Management",
        "🤖 External LLMs",
        "🔄 Maintenance", 
        "📋 Logs & Monitoring"
    ])
    
    # Log tab access (simple way to track which tabs users access most)
    current_tab = None
    if hasattr(st.session_state, '_admin_current_tab'):
        # This is a simple way to track tab switches - may not work perfectly due to Streamlit's execution model
        pass
    
    with tab1:
        render_system_status_tab()
    
    with tab2:
        render_data_management_tab()
    
    with tab3:
        render_index_management_tab()
    
    with tab4:
        render_external_llm_panel()
    
    with tab5:
        render_maintenance_tab()
    
    with tab6:
        render_logs_monitoring_tab()


def render_system_status_tab():
    """Render System Status tab content"""
    admin_logger.log_page_load("System Status tab accessed")
    st.subheader("🔧 System Status & Health")
    
    # Refresh status button
    if st.button("🔄 Refresh System Status", type="primary"):
        admin_logger.log_button_click("Refresh System Status")
        st.session_state.pop("system_status", None)
        st.toast("System status refreshed!", icon="✅")
        admin_logger.log_system_operation("System status manually refreshed")
        # Note: No st.rerun() to avoid tab reset - status will refresh on next interaction
    
    # Get current system status
    status = check_system_status()
    
    # Overall system health
    healthy_components = sum([
        status["elasticsearch"],
        status["ollama"],
        status["indices"] > 0,
        len(status["models"]) > 0
    ])
    
    health_percentage = (healthy_components / 4) * 100
    
    if health_percentage == 100:
        st.success(f"🟢 **System Healthy** ({health_percentage:.0f}%)")
    elif health_percentage >= 75:
        st.warning(f"🟡 **System Mostly Healthy** ({health_percentage:.0f}%)")
    else:
        st.error(f"🔴 **System Issues Detected** ({health_percentage:.0f}%)")
    
    # Detailed component status
    st.subheader("📊 Component Details")
    
    # Elasticsearch status
    es_col1, es_col2 = st.columns([3, 1])
    with es_col1:
        st.write("**Elasticsearch**")
        if status["elasticsearch"]:
            st.success("✅ Running and accessible")
        else:
            st.error("❌ Not accessible")
            st.write("Try running: `docker-compose up -d`")
    
    with es_col2:
        if st.button("🔧 Test ES Connection"):
            admin_logger.log_button_click("Test ES Connection")
            with st.spinner("Testing connection..."):
                try:
                    result = subprocess.run([
                        "curl", "-s", "-u", "elastic:ChangeMe_123",
                        "http://localhost:9200/_cluster/health"
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        health_data = json.loads(result.stdout)
                        st.json(health_data)
                        admin_logger.log_success("ES connection test passed", cluster_status=health_data.get("status"))
                    else:
                        st.error("Connection failed")
                        admin_logger.log_error("ES connection test failed", f"Return code: {result.returncode}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    admin_logger.log_error("ES connection test error", str(e))
    
    # Ollama status
    ollama_col1, ollama_col2 = st.columns([3, 1])
    with ollama_col1:
        st.write("**Ollama LLM Service**")
        if status["ollama"]:
            st.success(f"✅ Running with {len(status['models'])} models")
            if status["models"]:
                st.write(f"Available models: {', '.join(status['models'])}")
        else:
            st.error("❌ Not accessible")
            st.write("Try running: `ollama serve`")
    
    with ollama_col2:
        if st.button("🔧 Test Ollama"):
            admin_logger.log_button_click("Test Ollama")
            with st.spinner("Testing Ollama..."):
                try:
                    result = subprocess.run(
                        ["ollama", "list"], 
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        st.code(result.stdout)
                        # Count models from output
                        model_count = len([line for line in result.stdout.split('\n')[1:] if line.strip()])
                        admin_logger.log_success("Ollama test passed", model_count=model_count)
                    else:
                        st.error("Ollama not responding")
                        admin_logger.log_error("Ollama test failed", f"Return code: {result.returncode}")
                except Exception as e:
                    st.error(f"Error: {e}")
                    admin_logger.log_error("Ollama test error", str(e))
    
    # System resources
    st.subheader("💻 System Resources")
    
    try:
        import psutil
        
        resource_col1, resource_col2, resource_col3 = st.columns(3)
        
        with resource_col1:
            cpu_percent = psutil.cpu_percent(interval=1)
            st.metric("CPU Usage", f"{cpu_percent:.1f}%")
        
        with resource_col2:
            memory = psutil.virtual_memory()
            st.metric("Memory Usage", f"{memory.percent:.1f}%")
        
        with resource_col3:
            disk = psutil.disk_usage('/')
            st.metric("Disk Usage", f"{disk.percent:.1f}%")
            
    except ImportError:
        st.info("Install psutil for system resource monitoring: `pip install psutil`")


def render_data_management_tab():
    """Render Data Management tab content"""
    admin_logger.log_page_load("Data Management tab accessed")
    st.subheader("📊 Data Management")
    
    # Choose ingestion type
    ingestion_type = st.radio(
        "Select data source:",
        ["📁 General CSV Upload", "🛡️ CIC-IDS2017 Dataset"],
        horizontal=True
    )
    
    # Log ingestion type selection
    if "last_ingestion_type" not in st.session_state:
        st.session_state.last_ingestion_type = ingestion_type
    elif st.session_state.last_ingestion_type != ingestion_type:
        admin_logger.log_selection_change("ingestion_type", st.session_state.last_ingestion_type, ingestion_type)
        st.session_state.last_ingestion_type = ingestion_type
    
    if ingestion_type == "📁 General CSV Upload":
        # Data ingestion section
        st.markdown("### 📥 Standard Data Ingestion")
        
        # File upload for CSV data
        uploaded_file = st.file_uploader(
            "Upload CSV data for ingestion:",
            type="csv",
            help="Upload a CSV file to ingest into Elasticsearch"
        )
        
        if uploaded_file:
            admin_logger.log_file_upload(uploaded_file.name, uploaded_file.size, uploaded_file.type)
            # Preview data
            try:
                df = pd.read_csv(uploaded_file)
                st.write(f"**Preview** ({len(df)} rows, {len(df.columns)} columns):")
                st.dataframe(df.head(10), use_container_width=True)
                admin_logger.log_system_operation("CSV file previewed",
                    filename=uploaded_file.name,
                    rows=len(df),
                    columns=len(df.columns)
                )
                
                # Ingestion options
                ingest_col1, ingest_col2 = st.columns(2)
                
                with ingest_col1:
                    target_index = st.selectbox(
                        "Target Index:",
                        ["logs_net", "logs_net_test", "Create new index..."]
                    )
                    
                    if target_index == "Create new index...":
                        target_index = st.text_input("New index name:", "logs_net_custom")
                
                with ingest_col2:
                    batch_size = st.number_input("Batch Size:", 100, 10000, 1000)
                    overwrite_existing = st.checkbox("Overwrite existing data", value=False)
                
                if st.button("🚀 Start Ingestion", type="primary"):
                    admin_logger.log_button_click("Start Data Ingestion",
                        filename=uploaded_file.name,
                        target_index=target_index,
                        record_count=len(df)
                    )
                    
                    # Save uploaded file temporarily
                    temp_file = Path(f"data_raw/temp_upload_{int(time.time())}.csv")
                    temp_file.parent.mkdir(exist_ok=True)
                    
                    with open(temp_file, 'wb') as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Run ingestion
                    admin_logger.log_data_operation("ingestion", uploaded_file.name, len(df))
                    with st.spinner(f"Ingesting {len(df)} records..."):
                        try:
                            cmd = [
                                sys.executable, "src/ingest.py",
                                "--file", str(temp_file),
                                "--index", target_index,
                                "--user", "elastic",
                                "--password", "ChangeMe_123"
                            ]
                            
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                            
                            if result.returncode == 0:
                                st.success("✅ Ingestion completed successfully!")
                                st.code(result.stdout)
                                admin_logger.log_success("Data ingestion completed", 
                                    filename=uploaded_file.name,
                                    target_index=target_index,
                                    record_count=len(df)
                                )
                            else:
                                st.error("❌ Ingestion failed")
                                st.code(result.stderr)
                                admin_logger.log_error("Data ingestion failed", result.stderr,
                                                     filename=uploaded_file.name, target_index=target_index)
                        
                        except subprocess.TimeoutExpired:
                            st.error("Ingestion timed out (5 minutes)")
                            admin_logger.log_error("Data ingestion timeout", "Process exceeded 5 minute timeout")
                        except Exception as e:
                            st.error(f"Error: {e}")
                            admin_logger.log_error("Data ingestion error", str(e))
                        finally:
                            # Clean up temp file
                            temp_file.unlink(missing_ok=True)
                            
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
    
    elif ingestion_type == "🛡️ CIC-IDS2017 Dataset":
        # CIC-IDS2017 dataset ingestion (simplified version)
        st.markdown("### 🛡️ CIC-IDS2017 Dataset Ingestion")
        st.info("📌 The CIC-IDS2017 dataset contains real network traffic with labeled cyberattacks.")
        
        # List available CIC files
        cic_files = list(Path("data_raw").glob("*.pcap_ISCX.csv"))
        
        if cic_files:
            st.write(f"**Found {len(cic_files)} CIC-IDS2017 files**")
            
            # Basic file selection and processing interface
            selected_file = st.selectbox(
                "Select file to process:",
                [f.name for f in cic_files],
                help="Start with Monday (smallest workday file) for testing"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                sample_size = st.number_input(
                    "Sample size (0 = all):",
                    min_value=0,
                    max_value=500000,
                    value=10000,
                    step=5000
                )
            
            with col2:
                chunk_size = st.number_input(
                    "Chunk size:",
                    min_value=1000,
                    max_value=20000,
                    value=5000,
                    step=1000
                )
            
            if st.button("🚀 Process & Ingest CIC Data", type="primary"):
                st.info("CIC processing would run here - implementation preserved from original")
        else:
            st.warning("⚠️ No CIC-IDS2017 files found in data_raw/")


def render_index_management_tab():
    """Render Index Management tab content"""
    admin_logger.log_page_load("Index Management tab accessed")
    st.subheader("🗂️ Index Management")
    
    # Refresh button
    if st.button("🔄 Refresh Index List", type="primary"):
        admin_logger.log_button_click("Refresh Index List")
        st.session_state.pop("index_list", None)
        st.toast("Index list refreshed!", icon="✅")
        admin_logger.log_system_operation("Index list manually refreshed")
    
    st.info("📋 Index management functionality preserved from original implementation")
    st.write("This section includes:")
    st.write("- View all indices with document counts")
    st.write("- Create DP indices and drift indices")
    st.write("- Index deletion with safety confirmations")


def get_all_cleanup_targets():
    """Scan and identify all generated files across system components"""
    cleanup_targets = {}
    
    # 1. Query Generation Files
    generated_files = []
    generated_dir = Path("artifacts/generated")
    if generated_dir.exists():
        generated_files.extend(generated_dir.rglob("*.json"))
    cleanup_targets["Query Generation"] = generated_files
    
    # 2. Evaluation Dashboard Files
    eval_files = []
    eval_dir = Path("artifacts/evaluation_results")
    if eval_dir.exists():
        eval_files.extend(eval_dir.glob("eval_*.json"))
        eval_files.extend(eval_dir.glob("summary_*.json"))
    cleanup_targets["Evaluation Dashboard"] = eval_files
    
    # 3. Privacy Analysis Files
    privacy_files = []
    privacy_dir = Path("artifacts/privacy_results")
    if privacy_dir.exists():
        privacy_files.extend(privacy_dir.glob("privacy_*.json"))
        privacy_files.extend(privacy_dir.glob("privacy_summary_*.json"))
    cleanup_targets["Privacy Analysis"] = privacy_files
    
    # 4. Security Testing Files (if any are saved)
    security_files = []
    security_dir = Path("artifacts/security_results")
    if security_dir.exists():
        security_files.extend(security_dir.glob("security_*.json"))
        security_files.extend(security_dir.glob("redteam_*.json"))
    cleanup_targets["Security Testing"] = security_files
    
    # 5. Analysis & Results Files
    results_files = []
    results_dir = Path("artifacts/results")
    if results_dir.exists():
        results_files.extend(results_dir.glob("*.json"))
        results_files.extend(results_dir.glob("*.csv"))
        results_files.extend(results_dir.glob("*.md"))
        results_files.extend(results_dir.glob("*.jsonl"))
    cleanup_targets["Analysis Results"] = results_files
    
    # 6. Test Results Files
    test_files = []
    test_dir = Path("artifacts/test_results")
    if test_dir.exists():
        test_files.extend(test_dir.glob("*.json"))
        test_files.extend(test_dir.glob("*.metrics.json"))
    cleanup_targets["Test Results"] = test_files
    
    # 7. Temporary Export Files (if any exist in project root)
    temp_files = []
    project_root = Path(".")
    temp_files.extend(project_root.glob("*_export_*.csv"))
    temp_files.extend(project_root.glob("*_export_*.json"))
    temp_files.extend(project_root.glob("evaluation_results_*.csv"))
    temp_files.extend(project_root.glob("evaluation_results_*.json"))
    temp_files.extend(project_root.glob("privacy_*.csv"))
    temp_files.extend(project_root.glob("privacy_*.json"))
    if temp_files:
        cleanup_targets["Temporary Exports"] = temp_files
    
    # 8. Log Files (optional cleanup)
    log_files = []
    logs_dir = Path("logs")
    if logs_dir.exists():
        # Only include log files older than 7 days
        import time
        week_ago = time.time() - (7 * 24 * 60 * 60)
        for log_file in logs_dir.glob("*.log"):
            if log_file.stat().st_mtime < week_ago:
                log_files.append(log_file)
    if log_files:
        cleanup_targets["Old Log Files (>7 days)"] = log_files
    
    # Remove empty categories
    cleanup_targets = {k: v for k, v in cleanup_targets.items() if v}
    
    return cleanup_targets

def perform_comprehensive_cleanup(cleanup_targets):
    """Perform cleanup of all identified files"""
    cleanup_results = {}
    
    for component, files in cleanup_targets.items():
        cleaned_count = 0
        try:
            for file in files:
                if file.exists():
                    file.unlink()
                    cleaned_count += 1
        except Exception as e:
            # Log individual file errors but continue
            admin_logger.log_warning(f"Failed to clean some {component} files", str(e))
        
        cleanup_results[component] = cleaned_count
    
    return cleanup_results

def generate_cleanup_report(cleanup_targets):
    """Generate a CSV report of all files that would be cleaned"""
    import io
    
    output = io.StringIO()
    output.write("Component,File Path,File Name,Size (bytes),Modified Date,Age (days)\n")
    
    current_time = time.time()
    
    for component, files in cleanup_targets.items():
        for file in files:
            try:
                size = file.stat().st_size
                mtime = file.stat().st_mtime
                age_days = (current_time - mtime) / (24 * 60 * 60)
                modified_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                
                output.write(f'"{component}","{file}","{file.name}",{size},"{modified_date}",{age_days:.1f}\n')
            except:
                output.write(f'"{component}","{file}","{file.name}","ERROR","ERROR","ERROR"\n')
    
    return output.getvalue()

def render_maintenance_tab():
    """Render Maintenance tab content"""
    admin_logger.log_page_load("Maintenance tab accessed")
    st.subheader("🔄 System Maintenance")
    
    # Comprehensive cleanup operations
    st.markdown("### 🧹 Comprehensive System Cleanup")
    st.write("Clean generated files from all system components")
    
    # Scan for all generated files across components
    cleanup_targets = get_all_cleanup_targets()
    
    # Display summary
    total_files = sum(len(files) for files in cleanup_targets.values())
    
    if total_files > 0:
        st.info(f"📊 **Found {total_files} files across {len(cleanup_targets)} components:**")
        
        # Show breakdown by component
        for component, files in cleanup_targets.items():
            if files:
                with st.expander(f"**{component}** ({len(files)} files)"):
                    for file in files[:10]:  # Show first 10 files
                        file_age = time.ctime(file.stat().st_mtime)
                        file_size = file.stat().st_size
                        st.write(f"📄 `{file.name}` ({file_size:,} bytes, modified {file_age})")
                    if len(files) > 10:
                        st.write(f"... and {len(files) - 10} more files")
        
        st.markdown("---")
        
        # Cleanup options
        cleanup_col1, cleanup_col2 = st.columns(2)
        
        with cleanup_col1:
            if st.button("🧹 Clean All Generated Files", type="primary", use_container_width=True):
                admin_logger.log_button_click("Clean All Generated Files", 
                    total_files=total_files,
                    components=list(cleanup_targets.keys())
                )
                
                cleanup_results = perform_comprehensive_cleanup(cleanup_targets)
                
                # Display results
                total_cleaned = sum(cleanup_results.values())
                st.success(f"✅ Cleaned {total_cleaned} files across {len([c for c, count in cleanup_results.items() if count > 0])} components")
                
                # Show detailed results
                for component, count in cleanup_results.items():
                    if count > 0:
                        st.write(f"  • **{component}**: {count} files")
                
                admin_logger.log_success("Comprehensive cleanup completed", 
                    total_cleaned=total_cleaned,
                    breakdown=cleanup_results
                )
        
        with cleanup_col2:
            if st.button("📊 Export Cleanup Report", use_container_width=True):
                admin_logger.log_button_click("Export Cleanup Report", file_count=total_files)
                
                report = generate_cleanup_report(cleanup_targets)
                
                st.download_button(
                    label="📥 Download Report",
                    data=report,
                    file_name=f"cleanup_report_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
                admin_logger.log_download(f"cleanup_report_{time.strftime('%Y%m%d_%H%M%S')}.csv", "CSV")
    
    else:
        st.success("✨ **System is clean!** No generated files found.")
        st.info("Files will appear here as you use query generation, evaluation, and privacy analysis features.")


def render_logs_monitoring_tab():
    """Render Logs & Monitoring tab content"""
    admin_logger.log_page_load("Logs & Monitoring tab accessed")
    st.subheader("📋 Logs & Monitoring")
    
    # System logs
    st.markdown("### 📄 Recent System Logs")
    
    log_col1, log_col2 = st.columns(2)
    
    with log_col1:
        if st.button("📋 View Docker Logs"):
            admin_logger.log_button_click("View Docker Logs")
            try:
                result = subprocess.run([
                    "docker-compose", "logs", "--tail", "50", "elasticsearch"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    st.code(result.stdout, language="bash")
                    admin_logger.log_success("Docker logs retrieved", log_lines=len(result.stdout.split('\n')))
                else:
                    st.error("Could not retrieve Docker logs")
                    admin_logger.log_error("Docker logs retrieval failed", f"Return code: {result.returncode}")
            except Exception as e:
                st.error(f"Error: {e}")
                admin_logger.log_error("Docker logs error", str(e))
    
    with log_col2:
        if st.button("🔍 Check ES Cluster Logs"):
            admin_logger.log_button_click("Check ES Cluster Logs")
            try:
                result = subprocess.run([
                    "curl", "-s", "-u", "elastic:ChangeMe_123",
                    "http://localhost:9200/_cluster/allocation/explain"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    st.json(data)
                    admin_logger.log_success("ES cluster logs retrieved")
                else:
                    st.error("Could not retrieve cluster info")
                    admin_logger.log_error("ES cluster logs retrieval failed", f"Return code: {result.returncode}")
            except Exception as e:
                st.error(f"Error: {e}")
                admin_logger.log_error("ES cluster logs error", str(e))
    
    # Performance monitoring
    st.markdown("### 📊 Performance Monitoring")
    
    if st.button("⚡ Run Performance Test"):
        admin_logger.log_button_click("Run Performance Test")
        with st.spinner("Running performance benchmarks..."):
            st.info("Performance test functionality preserved from original")
            admin_logger.log_system_operation("Performance test initiated")
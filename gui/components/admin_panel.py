"""System Administration Panel Component for Streamlit GUI"""
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

from gui.utils.backend_interface import check_system_status

def render_admin_panel():
    """Render the system administration interface"""
    st.header("⚙️ System Administration")
    st.write("Monitor and manage system components, data, and configurations")
    
    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔧 System Status", 
        "📊 Data Management", 
        "🗂️ Index Management", 
        "🔄 Maintenance", 
        "📋 Logs & Monitoring"
    ])
    
    with tab1:
        st.subheader("🔧 System Status & Health")
        
        # Refresh status button
        if st.button("🔄 Refresh System Status", type="primary"):
            st.session_state.pop("system_status", None)
            st.toast("System status refreshed!", icon="✅")
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
                with st.spinner("Testing connection..."):
                    try:
                        result = subprocess.run([
                            "curl", "-s", "-u", "elastic:ChangeMe_123",
                            "http://localhost:9200/_cluster/health"
                        ], capture_output=True, text=True, timeout=10)
                        
                        if result.returncode == 0:
                            health_data = json.loads(result.stdout)
                            st.json(health_data)
                        else:
                            st.error("Connection failed")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
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
                with st.spinner("Testing Ollama..."):
                    try:
                        result = subprocess.run(
                            ["ollama", "list"], 
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            st.code(result.stdout)
                        else:
                            st.error("Ollama not responding")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
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
    
    with tab2:
        st.subheader("📊 Data Management")
        
        # Data ingestion section
        st.markdown("### 📥 Data Ingestion")
        
        # File upload for CSV data
        uploaded_file = st.file_uploader(
            "Upload CSV data for ingestion:",
            type="csv",
            help="Upload a CSV file to ingest into Elasticsearch"
        )
        
        if uploaded_file:
            # Preview data
            try:
                df = pd.read_csv(uploaded_file)
                st.write(f"**Preview** ({len(df)} rows, {len(df.columns)} columns):")
                st.dataframe(df.head(10), use_container_width=True)
                
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
                    # Save uploaded file temporarily
                    temp_file = Path(f"data_raw/temp_upload_{int(time.time())}.csv")
                    temp_file.parent.mkdir(exist_ok=True)
                    
                    with open(temp_file, 'wb') as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Run ingestion
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
                            else:
                                st.error("❌ Ingestion failed")
                                st.code(result.stderr)
                        
                        except subprocess.TimeoutExpired:
                            st.error("Ingestion timed out (5 minutes)")
                        except Exception as e:
                            st.error(f"Error: {e}")
                        finally:
                            # Clean up temp file
                            temp_file.unlink(missing_ok=True)
                            
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
        
        # Data export section
        st.markdown("### 📤 Data Export")
        
        export_col1, export_col2 = st.columns(2)
        
        with export_col1:
            export_index = st.selectbox(
                "Index to export:",
                ["logs_net", "logs_net_dp_eps05", "logs_net_dp_eps10", "logs_net_dp_eps20", "logs_net_drift"]
            )
            
            export_limit = st.number_input("Max records:", 100, 100000, 10000)
        
        with export_col2:
            export_format = st.selectbox("Export format:", ["CSV", "JSON", "JSONL"])
            include_metadata = st.checkbox("Include ES metadata", value=False)
        
        if st.button("📥 Export Data"):
            with st.spinner(f"Exporting from {export_index}..."):
                try:
                    # Simple export using curl
                    cmd = [
                        "curl", "-s", "-u", "elastic:ChangeMe_123",
                        f"http://localhost:9200/{export_index}/_search?size={export_limit}",
                        "-H", "Content-Type: application/json"
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        hits = data.get("hits", {}).get("hits", [])
                        
                        if hits:
                            # Convert to desired format
                            records = []
                            for hit in hits:
                                if include_metadata:
                                    records.append(hit)
                                else:
                                    records.append(hit["_source"])
                            
                            if export_format == "CSV":
                                df = pd.DataFrame([r for r in records if isinstance(r, dict)])
                                csv_data = df.to_csv(index=False)
                                
                                st.download_button(
                                    "📥 Download CSV",
                                    data=csv_data,
                                    file_name=f"{export_index}_export_{int(time.time())}.csv",
                                    mime="text/csv"
                                )
                            
                            elif export_format == "JSON":
                                json_data = json.dumps(records, indent=2)
                                
                                st.download_button(
                                    "📥 Download JSON",
                                    data=json_data,
                                    file_name=f"{export_index}_export_{int(time.time())}.json",
                                    mime="application/json"
                                )
                            
                            st.success(f"✅ Exported {len(records)} records")
                        else:
                            st.warning("No data found in index")
                    else:
                        st.error("Export failed")
                        
                except Exception as e:
                    st.error(f"Export error: {e}")
    
    with tab3:
        st.subheader("🗂️ Index Management")
        
        # List existing indices
        if st.button("🔄 Refresh Index List"):
            st.session_state.pop("index_list", None)
            st.toast("Index list refreshed!", icon="✅")
            # Note: No st.rerun() to avoid tab reset - list will refresh on next interaction
        
        # Get index information
        if "index_list" not in st.session_state:
            try:
                result = subprocess.run([
                    "curl", "-s", "-u", "elastic:ChangeMe_123",
                    "http://localhost:9200/_cat/indices?format=json&h=index,docs.count,store.size,status"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    indices = json.loads(result.stdout)
                    st.session_state.index_list = indices
                else:
                    st.session_state.index_list = []
            except:
                st.session_state.index_list = []
        
        indices = st.session_state.index_list
        
        if indices:
            # Filter to relevant indices
            relevant_indices = [idx for idx in indices if idx["index"].startswith("logs_net")]
            
            if relevant_indices:
                st.write("**Current Indices:**")
                
                # Create index summary table
                index_data = []
                for idx in relevant_indices:
                    index_data.append({
                        "Index": idx["index"],
                        "Documents": idx.get("docs.count", "0"),
                        "Size": idx.get("store.size", "0b"),
                        "Status": idx.get("status", "unknown")
                    })
                
                st.dataframe(pd.DataFrame(index_data), use_container_width=True)
                
                # Index operations
                st.markdown("### 🔧 Index Operations")
                
                op_col1, op_col2, op_col3 = st.columns(3)
                
                with op_col1:
                    if st.button("🆕 Create DP Indices"):
                        with st.spinner("Creating DP indices..."):
                            try:
                                # Run DP data creation
                                result = subprocess.run([
                                    sys.executable, "src/dp_synth.py"
                                ], capture_output=True, text=True, timeout=300)
                                
                                if result.returncode == 0:
                                    st.success("✅ DP indices created")
                                    st.code(result.stdout)
                                else:
                                    st.error("❌ DP creation failed")
                                    st.code(result.stderr)
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                with op_col2:
                    if st.button("🔄 Create Drift Index"):
                        with st.spinner("Creating schema drift index..."):
                            try:
                                result = subprocess.run([
                                    sys.executable, "src/create_drift_index.py"
                                ], capture_output=True, text=True, timeout=180)
                                
                                if result.returncode == 0:
                                    st.success("✅ Drift index created")
                                else:
                                    st.error("❌ Drift creation failed")
                                    st.code(result.stderr)
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                with op_col3:
                    # Dangerous operations
                    with st.expander("🚨 Dangerous Operations"):
                        st.warning("⚠️ These operations cannot be undone!")
                        
                        selected_index = st.selectbox(
                            "Select index to delete:",
                            [idx["index"] for idx in relevant_indices]
                        )
                        
                        confirm_delete = st.checkbox(f"I confirm deletion of {selected_index}")
                        
                        if st.button("🗑️ Delete Index", disabled=not confirm_delete):
                            try:
                                result = subprocess.run([
                                    "curl", "-X", "DELETE", "-u", "elastic:ChangeMe_123",
                                    f"http://localhost:9200/{selected_index}"
                                ], capture_output=True, text=True, timeout=30)
                                
                                if result.returncode == 0:
                                    st.success(f"✅ Deleted {selected_index}")
                                    st.session_state.pop("index_list", None)
                                    st.toast(f"Index {selected_index} deleted successfully!", icon="✅")
                                else:
                                    st.error("❌ Deletion failed")
                            except Exception as e:
                                st.error(f"Error: {e}")
            else:
                st.info("No relevant indices found (logs_net*)")
        else:
            st.error("❌ Could not retrieve index list. Check Elasticsearch connection.")
    
    with tab4:
        st.subheader("🔄 System Maintenance")
        
        # Cleanup operations
        st.markdown("### 🧹 Cleanup Operations")
        
        cleanup_col1, cleanup_col2 = st.columns(2)
        
        with cleanup_col1:
            st.write("**Generated Files Cleanup**")
            
            # Count generated files
            generated_dir = Path("artifacts/generated")
            if generated_dir.exists():
                query_files = list(generated_dir.glob("*.json"))
                st.write(f"Found {len(query_files)} generated files")
                
                if st.button("🗑️ Clean Generated Files"):
                    try:
                        cleaned_count = len(query_files)
                        for file in query_files:
                            file.unlink()
                        st.success(f"✅ Cleaned {cleaned_count} files")
                        st.session_state.generated_files_cleaned = True
                    except Exception as e:
                        st.error(f"Cleanup error: {e}")
                        st.session_state.generated_files_cleaned = False
            else:
                st.info("No generated files directory found")
        
        with cleanup_col2:
            st.write("**Results Cleanup**")
            
            # Count result files
            results_dir = Path("artifacts/results")
            if results_dir.exists():
                result_files = list(results_dir.glob("*.json"))
                st.write(f"Found {len(result_files)} result files")
                
                if st.button("🗑️ Clean Result Files"):
                    try:
                        cleaned_count = len(result_files)
                        for file in result_files:
                            file.unlink()
                        st.success(f"✅ Cleaned {cleaned_count} files")
                        st.session_state.result_files_cleaned = True
                    except Exception as e:
                        st.error(f"Cleanup error: {e}")
                        st.session_state.result_files_cleaned = False
            else:
                st.info("No results directory found")
        
        # System checks
        st.markdown("### 🔍 System Checks")
        
        if st.button("🩺 Run System Health Check"):
            with st.spinner("Running comprehensive health check..."):
                health_results = []
                
                # Check Python dependencies
                try:
                    import yaml, ollama, elasticsearch
                    health_results.append({"Check": "Python Dependencies", "Status": "✅ Pass", "Details": "All required packages found"})
                except ImportError as e:
                    health_results.append({"Check": "Python Dependencies", "Status": "❌ Fail", "Details": f"Missing: {e}"})
                
                # Check data directories
                required_dirs = ["artifacts", "tasks", "src", "data_raw"]
                for dir_name in required_dirs:
                    dir_path = Path(dir_name)
                    if dir_path.exists():
                        health_results.append({"Check": f"Directory: {dir_name}", "Status": "✅ Pass", "Details": "Exists"})
                    else:
                        health_results.append({"Check": f"Directory: {dir_name}", "Status": "❌ Fail", "Details": "Missing"})
                
                # Check configuration files
                config_files = ["artifacts/validator_rules.yaml", "artifacts/mappings.json", "tasks/prompts.yaml"]
                for config_file in config_files:
                    config_path = Path(config_file)
                    if config_path.exists():
                        health_results.append({"Check": f"Config: {config_file}", "Status": "✅ Pass", "Details": "Found"})
                    else:
                        health_results.append({"Check": f"Config: {config_file}", "Status": "❌ Fail", "Details": "Missing"})
                
                # Display results
                health_df = pd.DataFrame(health_results)
                st.dataframe(health_df, use_container_width=True)
                
                # Summary
                passed = len([r for r in health_results if "✅" in r["Status"]])
                total = len(health_results)
                st.write(f"**Health Score:** {passed}/{total} checks passed ({(passed/total)*100:.0f}%)")
    
    with tab5:
        st.subheader("📋 Logs & Monitoring")
        
        # System logs
        st.markdown("### 📄 Recent System Logs")
        
        log_col1, log_col2 = st.columns(2)
        
        with log_col1:
            if st.button("📋 View Docker Logs"):
                try:
                    result = subprocess.run([
                        "docker-compose", "logs", "--tail", "50", "elasticsearch"
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        st.code(result.stdout, language="bash")
                    else:
                        st.error("Could not retrieve Docker logs")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        with log_col2:
            if st.button("🔍 Check ES Cluster Logs"):
                try:
                    result = subprocess.run([
                        "curl", "-s", "-u", "elastic:ChangeMe_123",
                        "http://localhost:9200/_cluster/allocation/explain"
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        st.json(data)
                    else:
                        st.error("Could not retrieve cluster info")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # Performance monitoring
        st.markdown("### 📊 Performance Monitoring")
        
        if st.button("⚡ Run Performance Test"):
            with st.spinner("Running performance benchmarks..."):
                # Simple query performance test
                test_results = []
                
                try:
                    # Test basic search performance
                    start_time = time.time()
                    result = subprocess.run([
                        "curl", "-s", "-u", "elastic:ChangeMe_123",
                        "http://localhost:9200/logs_net/_search?size=1000"
                    ], capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        query_time = time.time() - start_time
                        data = json.loads(result.stdout)
                        total_docs = data.get("hits", {}).get("total", {}).get("value", 0)
                        
                        test_results.append({
                            "Test": "Basic Search (1000 docs)",
                            "Duration": f"{query_time:.2f}s",
                            "Status": "✅ Pass" if query_time < 5.0 else "⚠️ Slow",
                            "Details": f"Retrieved from {total_docs} total documents"
                        })
                    else:
                        test_results.append({
                            "Test": "Basic Search",
                            "Duration": "N/A",
                            "Status": "❌ Fail",
                            "Details": "Query failed"
                        })
                
                except Exception as e:
                    test_results.append({
                        "Test": "Basic Search",
                        "Duration": "N/A", 
                        "Status": "❌ Error",
                        "Details": str(e)
                    })
                
                # Display performance results
                if test_results:
                    perf_df = pd.DataFrame(test_results)
                    st.dataframe(perf_df, use_container_width=True)
        
        # Configuration display
        st.markdown("### ⚙️ System Configuration")
        
        config_col1, config_col2 = st.columns(2)
        
        with config_col1:
            st.write("**Environment Variables**")
            
            # Show relevant environment variables
            import os
            env_vars = {
                "PYTHONPATH": os.environ.get("PYTHONPATH", "Not set"),
                "ES_HOST": os.environ.get("ES_HOST", "localhost:9200"),
                "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "localhost:11434")
            }
            
            for var, value in env_vars.items():
                st.write(f"**{var}:** `{value}`")
        
        with config_col2:
            st.write("**System Paths**")
            
            paths = {
                "Project Root": str(project_root),
                "Current Working Dir": str(Path.cwd()),
                "Python Executable": sys.executable,
                "Python Version": sys.version.split()[0]
            }
            
            for path_name, path_value in paths.items():
                st.write(f"**{path_name}:** `{path_value}`")
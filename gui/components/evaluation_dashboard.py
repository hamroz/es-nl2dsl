"""Evaluation Dashboard Component for Streamlit GUI"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from gui.utils.backend_interface import (
    load_scenarios, run_scenario_evaluation, get_recent_results
)

def render_evaluation_dashboard():
    """Render the evaluation dashboard interface"""
    st.header("📊 Evaluation Dashboard")
    st.write("Run comprehensive evaluations across multiple scenarios and methods")
    
    # Load scenarios
    scenarios = load_scenarios()
    if not scenarios:
        st.error("❌ Could not load scenarios. Please check tasks/prompts.yaml")
        return
    
    # Create two columns for controls and results
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🎯 Scenario Selection")
        
        # Select all/none buttons
        select_col1, select_col2 = st.columns(2)
        with select_col1:
            if st.button("✅ Select All", use_container_width=True):
                for scenario in scenarios:
                    st.session_state[f"scenario_{scenario['id']}"] = True
                st.rerun()
        
        with select_col2:
            if st.button("❌ Clear All", use_container_width=True):
                for scenario in scenarios:
                    st.session_state[f"scenario_{scenario['id']}"] = False
                st.rerun()
        
        st.markdown("---")
        
        # Scenario checkboxes
        selected_scenarios = []
        for scenario in scenarios:
            key = f"scenario_{scenario['id']}"
            default_value = st.session_state.get(key, False)
            
            is_selected = st.checkbox(
                f"**{scenario['id']}** - {scenario['category']}",
                value=default_value,
                key=key,
                help=scenario['prompt']
            )
            
            if is_selected:
                selected_scenarios.append(scenario)
        
        st.markdown("---")
        st.subheader("🔧 Method Selection")
        
        # Method checkboxes
        methods = []
        constrained = st.checkbox("🤖 Constrained Generation", value=True)
        rules = st.checkbox("📋 Rules Baseline", value=False)
        zeroshot = st.checkbox("🎯 Zero-shot Baseline", value=False)
        
        if constrained:
            methods.append("constrained")
        if rules:
            methods.append("rules")
        if zeroshot:
            methods.append("zeroshot")
        
        st.markdown("---")
        st.subheader("⚙️ Execution Options")
        
        # Index selection
        index = st.selectbox(
            "Target Index:",
            ["logs_net", "logs_net_drift", "logs_net_dp_eps05", "logs_net_dp_eps10", "logs_net_dp_eps20"],
            help="Choose which Elasticsearch index to query against"
        )
        
        # Parallel execution
        parallel = st.checkbox("🚀 Parallel Execution", value=True, help="Run scenarios in parallel for faster execution")
        max_workers = st.slider("Max Workers:", 1, 8, 4) if parallel else 1
        
        # Run buttons
        st.markdown("---")
        run_selected = st.button("▶️ Run Selected", type="primary", use_container_width=True)
        run_all = st.button("🚀 Run All Scenarios", use_container_width=True)
        
        if run_all:
            # Select all scenarios
            selected_scenarios = scenarios
            for scenario in scenarios:
                st.session_state[f"scenario_{scenario['id']}"] = True
    
    with col2:
        st.subheader("📈 Results")
        
        # Run evaluation if requested
        if (run_selected or run_all) and selected_scenarios and methods:
            st.session_state.evaluation_running = True
            st.session_state.evaluation_results = {}
            
            # Create progress tracking
            total_runs = len(selected_scenarios) * len(methods)
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()
            
            # Create a table to show real-time results
            results_df = pd.DataFrame(columns=["Scenario", "Method", "F1", "Jaccard", "Precision", "Recall", "Status"])
            results_table = st.empty()
            
            completed_runs = 0
            
            def run_single_evaluation(scenario_id, method):
                """Run a single evaluation"""
                try:
                    success, metrics = run_scenario_evaluation(scenario_id, method, index)
                    return {
                        "scenario_id": scenario_id,
                        "method": method,
                        "success": success,
                        "metrics": metrics
                    }
                except Exception as e:
                    return {
                        "scenario_id": scenario_id,
                        "method": method,
                        "success": False,
                        "metrics": {"error": str(e)}
                    }
            
            # Execute evaluations
            if parallel and total_runs > 1:
                # Parallel execution
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # Submit all tasks
                    future_to_info = {}
                    for scenario in selected_scenarios:
                        for method in methods:
                            future = executor.submit(run_single_evaluation, scenario['id'], method)
                            future_to_info[future] = (scenario['id'], method)
                    
                    # Process results as they complete
                    for future in as_completed(future_to_info):
                        scenario_id, method = future_to_info[future]
                        result = future.result()
                        
                        completed_runs += 1
                        progress = completed_runs / total_runs
                        progress_bar.progress(progress)
                        status_text.text(f"Completed {completed_runs}/{total_runs}: {scenario_id} ({method})")
                        
                        # Update results
                        key = f"{scenario_id}_{method}"
                        st.session_state.evaluation_results[key] = result
                        
                        # Update results table
                        metrics = result["metrics"]
                        status = "✅ Pass" if result["success"] else "❌ Fail"
                        
                        new_row = pd.DataFrame([{
                            "Scenario": scenario_id,
                            "Method": method,
                            "F1": f"{metrics.get('f1', 0):.3f}" if result["success"] else "N/A",
                            "Jaccard": f"{metrics.get('jaccard', 0):.3f}" if result["success"] else "N/A",
                            "Precision": f"{metrics.get('precision', 0):.3f}" if result["success"] else "N/A",
                            "Recall": f"{metrics.get('recall', 0):.3f}" if result["success"] else "N/A",
                            "Status": status
                        }])
                        results_df = pd.concat([results_df, new_row], ignore_index=True)
                        results_table.dataframe(results_df, use_container_width=True)
            
            else:
                # Sequential execution
                for scenario in selected_scenarios:
                    for method in methods:
                        status_text.text(f"Running {scenario['id']} with {method}...")
                        
                        result = run_single_evaluation(scenario['id'], method)
                        
                        completed_runs += 1
                        progress = completed_runs / total_runs
                        progress_bar.progress(progress)
                        
                        # Update results
                        key = f"{scenario['id']}_{method}"
                        st.session_state.evaluation_results[key] = result
                        
                        # Update results table
                        metrics = result["metrics"]
                        status = "✅ Pass" if result["success"] else "❌ Fail"
                        
                        new_row = pd.DataFrame([{
                            "Scenario": scenario['id'],
                            "Method": method,
                            "F1": f"{metrics.get('f1', 0):.3f}" if result["success"] else "N/A",
                            "Jaccard": f"{metrics.get('jaccard', 0):.3f}" if result["success"] else "N/A",
                            "Precision": f"{metrics.get('precision', 0):.3f}" if result["success"] else "N/A",
                            "Recall": f"{metrics.get('recall', 0):.3f}" if result["success"] else "N/A",
                            "Status": status
                        }])
                        results_df = pd.concat([results_df, new_row], ignore_index=True)
                        results_table.dataframe(results_df, use_container_width=True)
            
            # Evaluation complete
            progress_bar.progress(1.0)
            status_text.text("✅ Evaluation complete!")
            st.session_state.evaluation_running = False
            
            # Summary statistics
            if not results_df.empty:
                st.markdown("---")
                st.subheader("📊 Summary Statistics")
                
                summary_cols = st.columns(4)
                
                with summary_cols[0]:
                    total_runs = len(results_df)
                    st.metric("Total Runs", total_runs)
                
                with summary_cols[1]:
                    passed_runs = len(results_df[results_df["Status"] == "✅ Pass"])
                    st.metric("Passed", passed_runs)
                
                with summary_cols[2]:
                    success_rate = (passed_runs / total_runs) * 100 if total_runs > 0 else 0
                    st.metric("Success Rate", f"{success_rate:.1f}%")
                
                with summary_cols[3]:
                    # Average F1 for successful runs
                    successful_runs = results_df[results_df["Status"] == "✅ Pass"]
                    if not successful_runs.empty:
                        avg_f1 = pd.to_numeric(successful_runs["F1"], errors='coerce').mean()
                        st.metric("Avg F1", f"{avg_f1:.3f}")
                    else:
                        st.metric("Avg F1", "N/A")
        
        # Display existing results if available
        elif "evaluation_results" in st.session_state and st.session_state.evaluation_results:
            st.info("📋 Showing results from previous evaluation run")
            
            # Recreate results table from session state
            results_data = []
            for key, result in st.session_state.evaluation_results.items():
                scenario_id, method = key.split('_', 1)
                metrics = result["metrics"]
                status = "✅ Pass" if result["success"] else "❌ Fail"
                
                results_data.append({
                    "Scenario": scenario_id,
                    "Method": method,
                    "F1": f"{metrics.get('f1', 0):.3f}" if result["success"] else "N/A",
                    "Jaccard": f"{metrics.get('jaccard', 0):.3f}" if result["success"] else "N/A",
                    "Precision": f"{metrics.get('precision', 0):.3f}" if result["success"] else "N/A",
                    "Recall": f"{metrics.get('recall', 0):.3f}" if result["success"] else "N/A",
                    "Status": status
                })
            
            if results_data:
                results_df = pd.DataFrame(results_data)
                st.dataframe(results_df, use_container_width=True)
        
        else:
            st.info("👆 Select scenarios and methods above, then click 'Run Selected' to start evaluation")
    
    # Visualization section
    if "evaluation_results" in st.session_state and st.session_state.evaluation_results:
        st.markdown("---")
        st.subheader("📈 Visualizations")
        
        # Prepare data for visualization
        viz_data = []
        for key, result in st.session_state.evaluation_results.items():
            scenario_id, method = key.split('_', 1)
            if result["success"]:
                metrics = result["metrics"]
                viz_data.append({
                    "Scenario": scenario_id,
                    "Method": method,
                    "F1": metrics.get('f1', 0),
                    "Jaccard": metrics.get('jaccard', 0),
                    "Precision": metrics.get('precision', 0),
                    "Recall": metrics.get('recall', 0)
                })
        
        if viz_data:
            viz_df = pd.DataFrame(viz_data)
            
            # Create visualizations
            viz_col1, viz_col2 = st.columns(2)
            
            with viz_col1:
                # F1 Score comparison by method
                fig_f1 = px.box(
                    viz_df, x="Method", y="F1", 
                    title="F1 Score Distribution by Method",
                    color="Method"
                )
                fig_f1.update_layout(showlegend=False)
                st.plotly_chart(fig_f1, use_container_width=True)
            
            with viz_col2:
                # Metrics heatmap
                pivot_df = viz_df.pivot_table(
                    index="Scenario", 
                    columns="Method", 
                    values="F1", 
                    aggfunc="mean"
                )
                
                fig_heatmap = px.imshow(
                    pivot_df.values,
                    x=pivot_df.columns,
                    y=pivot_df.index,
                    title="F1 Scores Heatmap",
                    color_continuous_scale="RdYlGn",
                    aspect="auto"
                )
                fig_heatmap.update_layout(
                    xaxis_title="Method",
                    yaxis_title="Scenario"
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)
    
    # Export functionality
    st.markdown("---")
    st.subheader("📁 Export Results")
    
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        if st.button("📊 Export CSV", use_container_width=True):
            if "evaluation_results" in st.session_state:
                # Create export data
                export_data = []
                for key, result in st.session_state.evaluation_results.items():
                    scenario_id, method = key.split('_', 1)
                    metrics = result["metrics"]
                    
                    export_data.append({
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "scenario_id": scenario_id,
                        "method": method,
                        "success": result["success"],
                        "f1": metrics.get('f1', 0) if result["success"] else None,
                        "jaccard": metrics.get('jaccard', 0) if result["success"] else None,
                        "precision": metrics.get('precision', 0) if result["success"] else None,
                        "recall": metrics.get('recall', 0) if result["success"] else None,
                        "validation": metrics.get('validation', False) if result["success"] else False,
                        "error": metrics.get('error', '') if not result["success"] else ''
                    })
                
                export_df = pd.DataFrame(export_data)
                csv = export_df.to_csv(index=False)
                
                st.download_button(
                    "📥 Download CSV",
                    data=csv,
                    file_name=f"evaluation_results_{int(time.time())}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No results to export")
    
    with export_col2:
        if st.button("📋 Export JSON", use_container_width=True):
            if "evaluation_results" in st.session_state:
                json_data = json.dumps(st.session_state.evaluation_results, indent=2)
                st.download_button(
                    "📥 Download JSON",
                    data=json_data,
                    file_name=f"evaluation_results_{int(time.time())}.json",
                    mime="application/json"
                )
            else:
                st.warning("No results to export")
    
    with export_col3:
        if st.button("🗑️ Clear Results", use_container_width=True):
            if "evaluation_results" in st.session_state:
                del st.session_state.evaluation_results
                st.success("Results cleared!")
                st.rerun()
    
    # Recent evaluations
    st.markdown("---")
    st.subheader("📋 Recent Evaluations")
    
    recent_results = get_recent_results()
    if recent_results:
        # Display recent results in a table
        recent_data = []
        for result in recent_results:
            metrics = result.get("metrics", {})
            recent_data.append({
                "Timestamp": result.get("timestamp", "Unknown")[:19],
                "Scenario": result.get("scenario_id", "Unknown"),
                "F1": f"{metrics.get('f1', 0):.3f}",
                "Validation": "✅" if result.get("validation_passed", False) else "❌"
            })
        
        recent_df = pd.DataFrame(recent_data)
        st.dataframe(recent_df, use_container_width=True)
    else:
        st.info("No recent evaluation results found.")
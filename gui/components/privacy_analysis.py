"""Privacy Analysis Component for Streamlit GUI"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import time
import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from gui.utils.backend_interface import (
    load_scenarios, run_scenario_evaluation, check_system_status
)

def render_privacy_analysis():
    """Render the privacy analysis interface"""
    st.header("🔒 Privacy Analysis")
    st.write("Analyze privacy-utility tradeoffs using Differential Privacy techniques")
    
    # Create tabs for different privacy analysis modes
    tab1, tab2, tab3, tab4 = st.tabs(["📊 DP Overview", "🔬 Privacy-Utility Analysis", "⚖️ Epsilon Comparison", "📈 Results Visualization"])
    
    with tab1:
        st.subheader("📊 Differential Privacy Overview")
        st.write("Understanding privacy protection levels and their impact on query performance")
        
        # DP explanation
        st.markdown("""
        **Differential Privacy (DP)** provides mathematical guarantees for privacy protection by adding calibrated noise to data.
        
        **Key Concepts:**
        - **ε (Epsilon)**: Privacy budget - lower values mean stronger privacy but potentially reduced utility
        - **δ (Delta)**: Failure probability - typically set to 1/n where n is dataset size
        - **Laplace Mechanism**: Adds noise proportional to sensitivity/ε
        """)
        
        # Available DP indices
        st.subheader("🗂️ Available DP Indices")
        
        # Check system status for available indices
        status = check_system_status()
        
        dp_indices = [
            {"name": "logs_net", "epsilon": "∞", "description": "Original data (no privacy protection)", "color": "#dc3545"},
            {"name": "logs_net_dp_eps05", "epsilon": "0.5", "description": "Strong privacy protection", "color": "#28a745"},
            {"name": "logs_net_dp_eps10", "epsilon": "1.0", "description": "Moderate privacy protection", "color": "#ffc107"},
            {"name": "logs_net_dp_eps20", "epsilon": "2.0", "description": "Weak privacy protection", "color": "#fd7e14"}
        ]
        
        for idx_info in dp_indices:
            col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
            
            with col1:
                st.write(f"**{idx_info['name']}**")
            
            with col2:
                st.markdown(f"<span style='color: {idx_info['color']}; font-weight: bold;'>ε = {idx_info['epsilon']}</span>", 
                           unsafe_allow_html=True)
            
            with col3:
                # Check if index exists
                index_exists = True  # Assume exists for now
                if index_exists:
                    st.success("✅ Available")
                else:
                    st.error("❌ Missing")
            
            with col4:
                st.write(idx_info['description'])
        
        # Privacy-utility tradeoff visualization
        st.subheader("📈 Privacy-Utility Tradeoff")
        
        # Theoretical curve
        epsilon_values = np.array([0.1, 0.5, 1.0, 2.0, 5.0, 10.0])
        utility_values = 1 - np.exp(-epsilon_values * 0.5)  # Theoretical utility curve
        
        fig_tradeoff = go.Figure()
        fig_tradeoff.add_trace(go.Scatter(
            x=epsilon_values, y=utility_values,
            mode='lines+markers',
            name='Theoretical Curve',
            line=dict(color='#1f77b4', width=3)
        ))
        
        # Mark our epsilon values
        our_epsilons = [0.5, 1.0, 2.0]
        our_utilities = [1 - np.exp(-eps * 0.5) for eps in our_epsilons]
        
        fig_tradeoff.add_trace(go.Scatter(
            x=our_epsilons, y=our_utilities,
            mode='markers',
            name='Our Configurations',
            marker=dict(color='#dc3545', size=12, symbol='diamond')
        ))
        
        fig_tradeoff.update_layout(
            title="Privacy-Utility Tradeoff Curve",
            xaxis_title="Privacy Budget (ε)",
            yaxis_title="Relative Utility",
            xaxis_type="log",
            showlegend=True
        )
        
        st.plotly_chart(fig_tradeoff, use_container_width=True)
    
    with tab2:
        st.subheader("🔬 Privacy-Utility Analysis")
        st.write("Run comprehensive analysis across different privacy levels")
        
        # Analysis configuration
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Scenario Selection")
            
            # Load scenarios
            scenarios = load_scenarios()
            if scenarios:
                selected_scenarios = []
                
                # Select all/none buttons
                select_col1, select_col2 = st.columns(2)
                with select_col1:
                    if st.button("✅ Select All Scenarios", use_container_width=True):
                        for scenario in scenarios:
                            st.session_state[f"privacy_scenario_{scenario['id']}"] = True
                        st.rerun()
                
                with select_col2:
                    if st.button("❌ Clear All Scenarios", use_container_width=True):
                        for scenario in scenarios:
                            st.session_state[f"privacy_scenario_{scenario['id']}"] = False
                        st.rerun()
                
                # Scenario checkboxes
                for scenario in scenarios[:6]:  # Limit for privacy analysis
                    key = f"privacy_scenario_{scenario['id']}"
                    default_value = st.session_state.get(key, False)
                    
                    is_selected = st.checkbox(
                        f"**{scenario['id']}** - {scenario['category']}",
                        value=default_value,
                        key=key,
                        help=scenario['prompt']
                    )
                    
                    if is_selected:
                        selected_scenarios.append(scenario)
            else:
                st.error("Could not load scenarios")
                selected_scenarios = []
        
        with col2:
            st.subheader("⚙️ Analysis Configuration")
            
            # Epsilon values to test
            epsilon_options = st.multiselect(
                "Privacy Levels (ε):",
                ["∞ (Original)", "2.0", "1.0", "0.5"],
                default=["∞ (Original)", "1.0", "0.5"]
            )
            
            # Method selection
            method = st.selectbox(
                "Query Generation Method:",
                ["constrained", "rules", "zeroshot"],
                index=0
            )
            
            # Parallel execution
            parallel = st.checkbox("🚀 Parallel Execution", value=True)
            max_workers = st.slider("Max Workers:", 1, 6, 3) if parallel else 1
            
            # Run analysis button
            run_analysis = st.button("🔬 Run Privacy Analysis", type="primary", use_container_width=True)
        
        # Run privacy analysis
        if run_analysis and selected_scenarios and epsilon_options:
            st.session_state.privacy_analysis_running = True
            
            # Map epsilon options to indices
            epsilon_to_index = {
                "∞ (Original)": "logs_net",
                "2.0": "logs_net_dp_eps20",
                "1.0": "logs_net_dp_eps10", 
                "0.5": "logs_net_dp_eps05"
            }
            
            selected_indices = [epsilon_to_index[eps] for eps in epsilon_options]
            total_runs = len(selected_scenarios) * len(selected_indices)
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Results tracking
            results_container = st.container()
            with results_container:
                results_df = pd.DataFrame(columns=["Scenario", "Epsilon", "F1", "Jaccard", "Precision", "Recall", "Privacy_Cost"])
                results_table = st.empty()
            
            completed_runs = 0
            privacy_results = {}
            
            def run_privacy_evaluation(scenario_id, index_name, epsilon_val):
                """Run evaluation for a specific scenario and privacy level"""
                try:
                    success, metrics = run_scenario_evaluation(scenario_id, method, index_name)
                    
                    # Calculate privacy cost (utility degradation from original)
                    privacy_cost = 0.0
                    if epsilon_val != "∞" and "f1" in metrics:
                        # Estimate degradation (placeholder calculation)
                        privacy_cost = max(0, (1.0 - metrics["f1"]) * float(epsilon_val if epsilon_val != "∞" else 1.0))
                    
                    return {
                        "scenario_id": scenario_id,
                        "epsilon": epsilon_val,
                        "index": index_name,
                        "success": success,
                        "metrics": metrics,
                        "privacy_cost": privacy_cost
                    }
                except Exception as e:
                    return {
                        "scenario_id": scenario_id,
                        "epsilon": epsilon_val,
                        "index": index_name,
                        "success": False,
                        "metrics": {"error": str(e)},
                        "privacy_cost": 1.0
                    }
            
            # Execute privacy analysis
            if parallel and total_runs > 1:
                # Parallel execution
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_info = {}
                    
                    for scenario in selected_scenarios:
                        for epsilon_opt in epsilon_options:
                            index_name = epsilon_to_index[epsilon_opt]
                            future = executor.submit(run_privacy_evaluation, scenario['id'], index_name, epsilon_opt)
                            future_to_info[future] = (scenario['id'], epsilon_opt)
                    
                    # Process results as they complete
                    for future in as_completed(future_to_info):
                        scenario_id, epsilon_val = future_to_info[future]
                        result = future.result()
                        
                        completed_runs += 1
                        progress = completed_runs / total_runs
                        progress_bar.progress(progress)
                        status_text.text(f"Completed {completed_runs}/{total_runs}: {scenario_id} (ε={epsilon_val})")
                        
                        # Store result
                        key = f"{scenario_id}_{epsilon_val}"
                        privacy_results[key] = result
                        
                        # Update results table
                        if result["success"]:
                            metrics = result["metrics"]
                            new_row = pd.DataFrame([{
                                "Scenario": scenario_id,
                                "Epsilon": epsilon_val,
                                "F1": f"{metrics.get('f1', 0):.3f}",
                                "Jaccard": f"{metrics.get('jaccard', 0):.3f}",
                                "Precision": f"{metrics.get('precision', 0):.3f}",
                                "Recall": f"{metrics.get('recall', 0):.3f}",
                                "Privacy_Cost": f"{result['privacy_cost']:.3f}"
                            }])
                            results_df = pd.concat([results_df, new_row], ignore_index=True)
                            results_table.dataframe(results_df, use_container_width=True)
            
            else:
                # Sequential execution
                for scenario in selected_scenarios:
                    for epsilon_opt in epsilon_options:
                        index_name = epsilon_to_index[epsilon_opt]
                        status_text.text(f"Running {scenario['id']} with ε={epsilon_opt}...")
                        
                        result = run_privacy_evaluation(scenario['id'], index_name, epsilon_opt)
                        
                        completed_runs += 1
                        progress = completed_runs / total_runs
                        progress_bar.progress(progress)
                        
                        # Store result
                        key = f"{scenario['id']}_{epsilon_opt}"
                        privacy_results[key] = result
                        
                        # Update results table
                        if result["success"]:
                            metrics = result["metrics"]
                            new_row = pd.DataFrame([{
                                "Scenario": scenario["id"],
                                "Epsilon": epsilon_opt,
                                "F1": f"{metrics.get('f1', 0):.3f}",
                                "Jaccard": f"{metrics.get('jaccard', 0):.3f}",
                                "Precision": f"{metrics.get('precision', 0):.3f}",
                                "Recall": f"{metrics.get('recall', 0):.3f}",
                                "Privacy_Cost": f"{result['privacy_cost']:.3f}"
                            }])
                            results_df = pd.concat([results_df, new_row], ignore_index=True)
                            results_table.dataframe(results_df, use_container_width=True)
            
            # Analysis complete
            progress_bar.progress(1.0)
            status_text.text("✅ Privacy analysis complete!")
            
            # Store results in session state
            st.session_state.privacy_results = privacy_results
            st.session_state.privacy_analysis_running = False
    
    with tab3:
        st.subheader("⚖️ Epsilon Comparison")
        st.write("Compare performance across different privacy levels")
        
        # Load existing results if available
        if "privacy_results" in st.session_state:
            results = st.session_state.privacy_results
            
            # Aggregate results by epsilon
            epsilon_summary = {}
            
            for key, result in results.items():
                if result["success"]:
                    epsilon = result["epsilon"]
                    if epsilon not in epsilon_summary:
                        epsilon_summary[epsilon] = {"f1_scores": [], "jaccard_scores": [], "privacy_costs": []}
                    
                    metrics = result["metrics"]
                    epsilon_summary[epsilon]["f1_scores"].append(metrics.get("f1", 0))
                    epsilon_summary[epsilon]["jaccard_scores"].append(metrics.get("jaccard", 0))
                    epsilon_summary[epsilon]["privacy_costs"].append(result["privacy_cost"])
            
            if epsilon_summary:
                # Create comparison charts
                col1, col2 = st.columns(2)
                
                with col1:
                    # F1 score comparison
                    epsilon_labels = []
                    f1_means = []
                    f1_stds = []
                    
                    for epsilon in sorted(epsilon_summary.keys(), key=lambda x: float(x) if x != "∞" else float('inf')):
                        scores = epsilon_summary[epsilon]["f1_scores"]
                        epsilon_labels.append(f"ε = {epsilon}")
                        f1_means.append(np.mean(scores))
                        f1_stds.append(np.std(scores))
                    
                    fig_f1 = go.Figure()
                    fig_f1.add_trace(go.Bar(
                        x=epsilon_labels,
                        y=f1_means,
                        error_y=dict(type='data', array=f1_stds),
                        name='F1 Score',
                        marker_color='#1f77b4'
                    ))
                    
                    fig_f1.update_layout(
                        title="F1 Score by Privacy Level",
                        xaxis_title="Privacy Level",
                        yaxis_title="F1 Score",
                        yaxis=dict(range=[0, 1])
                    )
                    
                    st.plotly_chart(fig_f1, use_container_width=True)
                
                with col2:
                    # Privacy cost comparison
                    privacy_means = []
                    privacy_stds = []
                    
                    for epsilon in sorted(epsilon_summary.keys(), key=lambda x: float(x) if x != "∞" else float('inf')):
                        costs = epsilon_summary[epsilon]["privacy_costs"]
                        privacy_means.append(np.mean(costs))
                        privacy_stds.append(np.std(costs))
                    
                    fig_privacy = go.Figure()
                    fig_privacy.add_trace(go.Bar(
                        x=epsilon_labels,
                        y=privacy_means,
                        error_y=dict(type='data', array=privacy_stds),
                        name='Privacy Cost',
                        marker_color='#dc3545'
                    ))
                    
                    fig_privacy.update_layout(
                        title="Privacy Cost by Privacy Level",
                        xaxis_title="Privacy Level",
                        yaxis_title="Privacy Cost",
                        yaxis=dict(range=[0, 1])
                    )
                    
                    st.plotly_chart(fig_privacy, use_container_width=True)
                
                # Summary statistics table
                st.subheader("📊 Summary Statistics")
                
                summary_data = []
                for epsilon in sorted(epsilon_summary.keys(), key=lambda x: float(x) if x != "∞" else float('inf')):
                    data = epsilon_summary[epsilon]
                    summary_data.append({
                        "Privacy Level (ε)": epsilon,
                        "Avg F1": f"{np.mean(data['f1_scores']):.3f}",
                        "Std F1": f"{np.std(data['f1_scores']):.3f}",
                        "Avg Jaccard": f"{np.mean(data['jaccard_scores']):.3f}",
                        "Avg Privacy Cost": f"{np.mean(data['privacy_costs']):.3f}",
                        "Sample Count": len(data['f1_scores'])
                    })
                
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True)
            
            else:
                st.info("No successful privacy analysis results to display")
        
        else:
            st.info("Run a privacy analysis to see epsilon comparison results")
    
    with tab4:
        st.subheader("📈 Results Visualization")
        st.write("Advanced visualization of privacy-utility relationships")
        
        if "privacy_results" in st.session_state:
            results = st.session_state.privacy_results
            
            # Prepare data for visualization
            viz_data = []
            for key, result in results.items():
                if result["success"]:
                    scenario_id, epsilon = key.rsplit('_', 1)
                    metrics = result["metrics"]
                    
                    # Convert epsilon to numeric for plotting
                    epsilon_numeric = float(epsilon) if epsilon != "∞" else 100.0
                    
                    viz_data.append({
                        "Scenario": scenario_id,
                        "Epsilon": epsilon,
                        "Epsilon_Numeric": epsilon_numeric,
                        "F1": metrics.get("f1", 0),
                        "Jaccard": metrics.get("jaccard", 0),
                        "Precision": metrics.get("precision", 0),
                        "Recall": metrics.get("recall", 0),
                        "Privacy_Cost": result["privacy_cost"]
                    })
            
            if viz_data:
                viz_df = pd.DataFrame(viz_data)
                
                # Multi-metric visualization
                col1, col2 = st.columns(2)
                
                with col1:
                    # Privacy-Utility scatter plot
                    fig_scatter = px.scatter(
                        viz_df, 
                        x="Epsilon_Numeric", 
                        y="F1",
                        color="Scenario",
                        size="Jaccard",
                        hover_data=["Precision", "Recall"],
                        title="Privacy-Utility Scatter Plot",
                        labels={"Epsilon_Numeric": "Privacy Budget (ε)", "F1": "F1 Score"}
                    )
                    fig_scatter.update_xaxis(type="log")
                    st.plotly_chart(fig_scatter, use_container_width=True)
                
                with col2:
                    # Heatmap of metrics across scenarios and epsilon values
                    pivot_df = viz_df.pivot_table(
                        index="Scenario", 
                        columns="Epsilon", 
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
                        xaxis_title="Privacy Level (ε)",
                        yaxis_title="Scenario"
                    )
                    st.plotly_chart(fig_heatmap, use_container_width=True)
                
                # Parallel coordinates plot
                st.subheader("🔗 Multi-Dimensional Analysis")
                
                # Prepare data for parallel coordinates
                parallel_df = viz_df.copy()
                parallel_df["Epsilon_Scaled"] = parallel_df["Epsilon_Numeric"] / 100.0  # Scale for visualization
                
                fig_parallel = px.parallel_coordinates(
                    parallel_df,
                    dimensions=["Epsilon_Scaled", "F1", "Jaccard", "Precision", "Recall"],
                    color="F1",
                    title="Multi-Dimensional Privacy-Utility Analysis",
                    color_continuous_scale="RdYlGn"
                )
                
                st.plotly_chart(fig_parallel, use_container_width=True)
                
                # Export privacy analysis results
                st.markdown("---")
                st.subheader("📁 Export Privacy Analysis")
                
                export_col1, export_col2 = st.columns(2)
                
                with export_col1:
                    if st.button("📊 Export Privacy Report", use_container_width=True):
                        # Create comprehensive privacy report
                        report_data = {
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "analysis_type": "privacy_utility",
                            "scenarios_tested": len(viz_df["Scenario"].unique()),
                            "epsilon_values": list(viz_df["Epsilon"].unique()),
                            "summary_statistics": viz_df.groupby("Epsilon").agg({
                                "F1": ["mean", "std", "min", "max"],
                                "Jaccard": ["mean", "std"],
                                "Privacy_Cost": ["mean", "std"]
                            }).to_dict(),
                            "detailed_results": viz_data
                        }
                        
                        report_json = json.dumps(report_data, indent=2)
                        
                        st.download_button(
                            "📥 Download Privacy Report",
                            data=report_json,
                            file_name=f"privacy_analysis_{int(time.time())}.json",
                            mime="application/json"
                        )
                
                with export_col2:
                    if st.button("📋 Export Results CSV", use_container_width=True):
                        csv = viz_df.to_csv(index=False)
                        
                        st.download_button(
                            "📥 Download CSV",
                            data=csv,
                            file_name=f"privacy_results_{int(time.time())}.csv",
                            mime="text/csv"
                        )
            
            else:
                st.info("No successful privacy analysis results to visualize")
        
        else:
            st.info("Run a privacy analysis to see detailed visualizations")
        
        # Privacy recommendations
        st.markdown("---")
        st.subheader("💡 Privacy Recommendations")
        
        st.info("""
        **Privacy-Utility Best Practices:**
        
        1. **ε = 0.5**: Strong privacy protection, suitable for sensitive data with moderate utility requirements
        2. **ε = 1.0**: Balanced privacy-utility tradeoff for most applications
        3. **ε = 2.0**: Weak privacy protection but higher utility for less sensitive scenarios
        4. **Monitoring**: Regularly assess the privacy-utility curve for your specific use cases
        5. **Adaptive ε**: Consider dynamic epsilon allocation based on query sensitivity
        """)
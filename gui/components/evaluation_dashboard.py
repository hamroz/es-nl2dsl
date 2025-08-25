"""Enhanced Evaluation Dashboard with CIC-IDS2017 Support and Model Selection"""
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

# Import logging utilities
from gui.utils.logging_utils import get_gui_logger

# Initialize component logger
eval_logger = get_gui_logger("evaluation_dashboard")

from src.core.enhanced_evaluation import EnhancedEvaluator
from src.external.llm_manager import get_external_llm_manager
from gui.utils.backend_interface import get_available_indices

def generate_summary_from_results(results):
    """Generate summary statistics from evaluation results"""
    if not results:
        return {}
    
    successful_results = [r for r in results if r.get('success', False)]
    total_results = len(results)
    
    # Overall statistics
    overall = {
        'total_evaluations': total_results,
        'successful_evaluations': len(successful_results),
        'success_rate': len(successful_results) / total_results if total_results > 0 else 0.0,
        'avg_generation_time': sum(r.get('generation_time', 0) for r in successful_results) / len(successful_results) if successful_results else 0.0
    }
    
    # Add metric averages if available
    f1_scores = []
    precisions = []
    recalls = []
    ast_similarities = []
    
    for r in successful_results:
        if r.get('execution_metrics'):
            metrics = r['execution_metrics']
            if isinstance(metrics, dict) and 'traditional' in metrics:
                f1_scores.append(metrics['traditional'].get('f1_score', 0))
                precisions.append(metrics['traditional'].get('precision', 0))
                recalls.append(metrics['traditional'].get('recall', 0))
        
        ast_similarities.append(r.get('ast_similarity', 0))
    
    if f1_scores:
        overall['avg_f1_score'] = sum(f1_scores) / len(f1_scores)
        overall['avg_precision'] = sum(precisions) / len(precisions)
        overall['avg_recall'] = sum(recalls) / len(recalls)
    
    if ast_similarities:
        overall['avg_ast_similarity'] = sum(ast_similarities) / len(ast_similarities)
    
    # By method statistics
    by_method = {}
    for method in set(r.get('method') for r in results if r.get('method')):
        method_results = [r for r in results if r.get('method') == method]
        method_successful = [r for r in method_results if r.get('success', False)]
        
        method_stats = {
            'count': len(method_results),
            'success_rate': len(method_successful) / len(method_results) if method_results else 0.0,
            'avg_generation_time': sum(r.get('generation_time', 0) for r in method_successful) / len(method_successful) if method_successful else 0.0
        }
        
        # Add method-specific metrics
        method_f1s = []
        for r in method_successful:
            if r.get('execution_metrics'):
                metrics = r['execution_metrics']
                if isinstance(metrics, dict) and 'traditional' in metrics:
                    method_f1s.append(metrics['traditional'].get('f1_score', 0))
        
        if method_f1s:
            method_stats['avg_f1_score'] = sum(method_f1s) / len(method_f1s)
        
        by_method[method] = method_stats
    
    # By model statistics
    by_model = {}
    for model in set(r.get('model') for r in results if r.get('model')):
        model_results = [r for r in results if r.get('model') == model]
        model_successful = [r for r in model_results if r.get('success', False)]
        
        model_stats = {
            'count': len(model_results),
            'success_rate': len(model_successful) / len(model_results) if model_results else 0.0,
            'avg_generation_time': sum(r.get('generation_time', 0) for r in model_successful) / len(model_successful) if model_successful else 0.0
        }
        
        # Add model-specific metrics
        model_f1s = []
        for r in model_successful:
            if r.get('execution_metrics'):
                metrics = r['execution_metrics']
                if isinstance(metrics, dict) and 'traditional' in metrics:
                    model_f1s.append(metrics['traditional'].get('f1_score', 0))
        
        if model_f1s:
            model_stats['avg_f1_score'] = sum(model_f1s) / len(model_f1s)
        
        by_model[model] = model_stats
    
    return {
        'overall': overall,
        'by_method': by_method,
        'by_model': by_model,
        'timestamp': time.time()
    }

def render_evaluation_dashboard():
    """Render the enhanced evaluation dashboard interface"""
    eval_logger.log_page_load("Evaluation Dashboard loaded")
    st.header("📊 Enhanced Evaluation Dashboard")
    st.write("Comprehensive evaluation across datasets, methods, and models")
    
    # Initialize evaluator
    evaluator = EnhancedEvaluator()
    llm_manager = get_external_llm_manager()
    
    # Create main layout
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🎯 Configuration")
        
        # Dataset Selection
        st.markdown("### 📁 Dataset Selection")
        dataset = st.selectbox(
            "Choose Dataset:",
            ["standard", "cic_ids2017"],
            format_func=lambda x: "Standard Test Scenarios" if x == "standard" else "CIC-IDS2017 Attack Scenarios",
            help="Select the dataset to evaluate against"
        )
        
        # Log dataset selection
        if "last_eval_dataset" not in st.session_state:
            st.session_state.last_eval_dataset = dataset
        elif st.session_state.last_eval_dataset != dataset:
            eval_logger.log_selection_change("dataset", st.session_state.last_eval_dataset, dataset)
            st.session_state.last_eval_dataset = dataset
        
        # Load scenarios for selected dataset
        scenarios = evaluator.load_scenarios(dataset)
        if not scenarios:
            st.error(f"❌ No scenarios found for {dataset}")
            return
        
        st.markdown("---")
        
        # Model Selection
        st.markdown("### 🤖 Model Selection")
        
        # Get available models (using same format as query generator)
        from gui.utils.backend_interface import get_available_models
        local_models = get_available_models()
        external_llms = llm_manager.list_llms(enabled_only=True)
        
        # Combine models with consistent prefixes
        available_models = []
        if local_models:
            available_models.extend([f"Local: {m}" for m in local_models])
        if external_llms:
            available_models.extend([f"External: {llm.name}" for llm in external_llms])
        
        # Set default selection
        default_models = []
        default_model = "Local: llama3.1:latest"
        if default_model in available_models:
            default_models.append(default_model)
        elif available_models:
            default_models.append(available_models[0])
        
        selected_models = st.multiselect(
            "Select Models to Evaluate:",
            available_models,
            default=default_models,
            help=f"Choose which models to use for generation. Available: {len(local_models)} local, {len(external_llms)} external"
        )
        
        # Keep model names with prefixes for the evaluator
        # Both local and external models are now supported
        if not selected_models:
            st.error("Please select at least one model for evaluation.")
        
        st.markdown("---")
        
        # Scenario Selection
        st.markdown("### 📋 Scenario Selection")
        
        # Select all/none buttons
        select_col1, select_col2 = st.columns(2)
        with select_col1:
            if st.button("✅ Select All", use_container_width=True):
                eval_logger.log_button_click("Select All Scenarios", dataset=dataset, scenario_count=len(scenarios))
                for scenario in scenarios:
                    st.session_state[f"eval_scenario_{scenario['id']}"] = True
                st.toast(f"All {len(scenarios)} scenarios selected!", icon="✅")
        
        with select_col2:
            if st.button("❌ Clear All", use_container_width=True):
                eval_logger.log_button_click("Clear All Scenarios", dataset=dataset, scenario_count=len(scenarios))
                for scenario in scenarios:
                    st.session_state[f"eval_scenario_{scenario['id']}"] = False
                st.toast("All scenarios cleared!", icon="❌")
        
        # Scenario checkboxes with categories
        selected_scenarios = []
        categories = {}
        
        for scenario in scenarios:
            category = scenario.get('category', 'General')
            if category not in categories:
                categories[category] = []
            categories[category].append(scenario)
        
        for category, cat_scenarios in categories.items():
            with st.expander(f"**{category}** ({len(cat_scenarios)} scenarios)", expanded=False):
                for scenario in cat_scenarios:
                    key = f"eval_scenario_{scenario['id']}"
                    default_value = st.session_state.get(key, False)
                    
                    is_selected = st.checkbox(
                        f"**{scenario['id']}**",
                        value=default_value,
                        key=key,
                        help=scenario['prompt']
                    )
                    
                    if is_selected:
                        selected_scenarios.append(scenario['id'])
        
        st.markdown("---")
        
        # Method Selection
        st.markdown("### 🔧 Method Selection")
        
        methods = []
        constrained = st.checkbox("🎯 Constrained Generation", value=True, 
                                 help="Use constrained generation with validation")
        rules = st.checkbox("📋 Rules Baseline", value=True,
                           help="Rule-based query generation")
        zeroshot = st.checkbox("🚀 Zero-shot Baseline", value=True,
                              help="Direct LLM generation without constraints")
        
        if constrained:
            methods.append("constrained")
        if rules:
            methods.append("rules")
        if zeroshot:
            methods.append("zeroshot")
        
        st.markdown("---")
        
        # Execution Options
        st.markdown("### ⚙️ Execution Options")
        
        # Get available indices
        indices = get_available_indices()
        
        # Filter indices based on dataset
        if dataset == "cic_ids2017":
            default_index = "logs_cic_ids2017"
            relevant_indices = [i for i in indices if "cic" in i.lower()]
        else:
            default_index = "logs_net"
            relevant_indices = [i for i in indices if "cic" not in i.lower()]
        
        # Ensure default exists
        if default_index not in relevant_indices and relevant_indices:
            default_index = relevant_indices[0]
        
        index = st.selectbox(
            "Target Index:",
            relevant_indices,
            index=relevant_indices.index(default_index) if default_index in relevant_indices else 0,
            help="Elasticsearch index to execute queries against"
        )
        
        save_results = st.checkbox("💾 Save Results", value=True,
                                  help="Save evaluation results to file")
        
        # Summary statistics
        st.markdown("---")
        st.info(f"""
        **Evaluation Configuration:**
        - Dataset: {dataset}
        - Scenarios: {len(selected_scenarios)}/{len(scenarios)}
        - Methods: {len(methods)}
        - Selected Models: {len(selected_models)}
        - Total Evaluations: {len(selected_scenarios) * len(methods) * len(selected_models)}
        """)
        
        # Run button
        if st.button("🚀 Run Evaluation", type="primary", use_container_width=True):
            eval_logger.log_button_click("Run Evaluation",
                dataset=dataset,
                scenario_count=len(selected_scenarios),
                method_count=len(methods),
                model_count=len(selected_models),
                total_evaluations=len(selected_scenarios) * len(methods) * len(selected_models)
            )
            
            if not selected_scenarios:
                st.error("Please select at least one scenario")
                eval_logger.log_warning("Evaluation start failed", "No scenarios selected")
            elif not methods:
                st.error("Please select at least one method")
                eval_logger.log_warning("Evaluation start failed", "No methods selected")
            elif not selected_models:
                st.error("Please select at least one model")
                eval_logger.log_warning("Evaluation start failed", "No models selected")
            else:
                eval_logger.log_system_operation("Evaluation batch started",
                    dataset=dataset,
                    scenarios=selected_scenarios,
                    methods=methods,
                    models=selected_models
                )
                
                # Log detailed model information
                print(f"🚀 Starting evaluation batch:")
                print(f"   📊 Dataset: {dataset}")
                print(f"   📋 Scenarios: {len(selected_scenarios)} selected")
                print(f"   🔧 Methods: {', '.join(methods)}")
                print(f"   🤖 Models: {', '.join(selected_models)}")
                print(f"   📈 Total evaluations: {len(selected_scenarios) * len(methods) * len(selected_models)}")
                print(f"   🎯 Individual tasks will be logged below...")
                
                with st.spinner(f"Running {len(selected_scenarios) * len(methods) * len(selected_models)} evaluations..."):
                    # Run evaluation
                    summary = evaluator.run_evaluation(
                        dataset=dataset,
                        scenarios=selected_scenarios,
                        methods=methods,
                        models=selected_models,
                        save_results=save_results
                    )
                    
                    # Store results in session state
                    st.session_state['eval_results'] = evaluator.results
                    st.session_state['eval_summary'] = summary
                    st.success("✅ Evaluation complete!")
                    st.balloons()
                    
                    eval_logger.log_success("Evaluation batch completed", 
                        dataset=dataset,
                        total_evaluations=len(selected_scenarios) * len(methods) * len(selected_models),
                        results_count=len(evaluator.results) if hasattr(evaluator, 'results') else 0
                    )
    
    with col2:
        st.subheader("📊 Results & Analysis")
        
        # Check if results exist
        if 'eval_results' not in st.session_state or not st.session_state['eval_results']:
            st.info("👈 Configure and run evaluation to see results")
            
            # Show recent results if available
            recent_files = list(Path("artifacts/evaluation_results").glob("eval_*.json"))
            if recent_files:
                st.markdown("### 📁 Recent Evaluations")
                recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                for file in recent_files[:5]:
                    file_info = file.stem.replace("eval_", "").replace("_", " ")
                    if st.button(f"📄 Load: {file_info}", key=f"load_{file.name}"):
                        with open(file, 'r') as f:
                            results_data = json.load(f)
                            st.session_state['eval_results'] = results_data
                            
                        # Also load the corresponding summary file
                        summary_file = file.parent / file.name.replace("eval_", "summary_")
                        if summary_file.exists():
                            with open(summary_file, 'r') as f:
                                summary_data = json.load(f)
                                st.session_state['eval_summary'] = summary_data
                                
                        # If no summary file exists, generate summary from results
                        elif results_data:
                            st.session_state['eval_summary'] = generate_summary_from_results(results_data)
                            
                        st.toast(f"Loaded {len(results_data)} results", icon="✅")
                        eval_logger.log_user_action("Loaded recent evaluation", filename=file.name)
                        st.rerun()  # Rerun to show the loaded results
            return
        
        results = st.session_state['eval_results']
        summary = st.session_state.get('eval_summary', {})
        
        # Display tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Overview", "🎯 By Method", "🤖 By Model", "📊 By Scenario", "📋 Detailed Results"
        ])
        
        # Log tab access for evaluation results
        eval_logger.log_page_load("Evaluation results viewed")
        
        with tab1:
            st.markdown("### 📊 Overall Performance")
            
            if summary and 'overall' in summary:
                overall = summary['overall']
                
                # Key metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Success Rate", f"{overall.get('success_rate', 0)*100:.1f}%")
                with col2:
                    st.metric("Avg F1 Score", f"{overall.get('avg_f1_score', 0):.3f}")
                with col3:
                    st.metric("Semantic Similarity", f"{overall.get('avg_semantic_similarity', 0):.3f}")
                with col4:
                    st.metric("AST Similarity", f"{overall.get('avg_ast_similarity', 0):.3f}")
                with col5:
                    st.metric("Avg Gen Time", f"{overall.get('avg_generation_time', 0):.2f}s")
                
                # Performance chart
                if 'by_method' in summary:
                    st.markdown("### Method Comparison")
                    method_data = []
                    for method, metrics in summary['by_method'].items():
                        method_data.append({
                            'Method': method,
                            'F1 Score': metrics.get('avg_f1_score', 0),
                            'Precision': metrics.get('avg_precision', 0),
                            'Recall': metrics.get('avg_recall', 0),
                            'Semantic Similarity': metrics.get('avg_semantic_similarity', 0),
                            'AST Similarity': metrics.get('avg_ast_similarity', 0)
                        })
                    
                    df_methods = pd.DataFrame(method_data)
                    fig = px.bar(df_methods, x='Method', 
                                y=['F1 Score', 'Precision', 'Recall', 'Semantic Similarity', 'AST Similarity'],
                                title="Performance by Method",
                                barmode='group')
                    st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.markdown("### 🎯 Method Analysis")
            
            if 'by_method' in summary:
                for method, metrics in summary['by_method'].items():
                    with st.expander(f"**{method.upper()}** Method", expanded=True):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Evaluations", metrics.get('count', 0))
                        with col2:
                            st.metric("Success Rate", f"{metrics.get('success_rate', 0)*100:.1f}%")
                        with col3:
                            st.metric("Avg F1", f"{metrics.get('avg_f1_score', 0):.3f}")
                        with col4:
                            st.metric("Avg Time", f"{metrics.get('avg_generation_time', 0):.2f}s")
                        
                        # Detailed metrics
                        st.markdown("**Detailed Metrics:**")
                        detailed = {
                            'Precision': metrics.get('avg_precision', 0),
                            'Recall': metrics.get('avg_recall', 0),
                            'F1 Score': metrics.get('avg_f1_score', 0),
                            'Jaccard': metrics.get('avg_jaccard', 0),
                            'AST Similarity': metrics.get('avg_ast_similarity', 0)
                        }
                        df_detailed = pd.DataFrame([detailed]).T
                        df_detailed.columns = ['Score']
                        st.dataframe(df_detailed, use_container_width=True)
        
        with tab3:
            st.markdown("### 🤖 Model Analysis")
            
            if 'by_model' in summary:
                model_comparison = []
                for model, metrics in summary['by_model'].items():
                    model_comparison.append({
                        'Model': model,
                        'Success Rate': metrics.get('success_rate', 0) * 100,
                        'F1 Score': metrics.get('avg_f1_score', 0),
                        'AST Similarity': metrics.get('avg_ast_similarity', 0),
                        'Gen Time (s)': metrics.get('avg_generation_time', 0)
                    })
                
                df_models = pd.DataFrame(model_comparison)
                
                # Model comparison chart
                fig = make_subplots(
                    rows=2, cols=2,
                    subplot_titles=('Success Rate (%)', 'F1 Score', 'AST Similarity', 'Generation Time (s)')
                )
                
                # Success Rate
                fig.add_trace(
                    go.Bar(x=df_models['Model'], y=df_models['Success Rate'], name='Success Rate'),
                    row=1, col=1
                )
                
                # F1 Score
                fig.add_trace(
                    go.Bar(x=df_models['Model'], y=df_models['F1 Score'], name='F1 Score'),
                    row=1, col=2
                )
                
                # AST Similarity
                fig.add_trace(
                    go.Bar(x=df_models['Model'], y=df_models['AST Similarity'], name='AST Similarity'),
                    row=2, col=1
                )
                
                # Generation Time
                fig.add_trace(
                    go.Bar(x=df_models['Model'], y=df_models['Gen Time (s)'], name='Gen Time'),
                    row=2, col=2
                )
                
                fig.update_layout(height=600, showlegend=False, title_text="Model Performance Comparison")
                st.plotly_chart(fig, use_container_width=True)
                
                # Detailed table
                st.markdown("### Detailed Model Metrics")
                st.dataframe(df_models, use_container_width=True)
        
        with tab4:
            st.markdown("### 📊 Scenario Analysis")
            
            # Group results by scenario
            scenario_metrics = {}
            for result in results:
                # Handle both dict and object results
                if isinstance(result, dict):
                    scenario_id = result.get('scenario_id')
                    f1_score = result.get('execution_metrics', {}).get('f1_score', 0) if result.get('execution_metrics') else 0
                    ast_sim = result.get('ast_similarity', 0)
                    error = result.get('error')
                else:
                    scenario_id = result.scenario_id
                    execution_metrics = getattr(result, 'execution_metrics', None)
                    f1_score = execution_metrics.get('f1_score', 0) if execution_metrics else 0
                    ast_sim = result.ast_similarity
                    error = result.error
                
                if scenario_id not in scenario_metrics:
                    scenario_metrics[scenario_id] = {
                        'f1_scores': [],
                        'ast_similarities': [],
                        'success_count': 0,
                        'total_count': 0
                    }
                
                scenario_metrics[scenario_id]['f1_scores'].append(f1_score)
                scenario_metrics[scenario_id]['ast_similarities'].append(ast_sim)
                scenario_metrics[scenario_id]['total_count'] += 1
                if not error:
                    scenario_metrics[scenario_id]['success_count'] += 1
            
            # Create scenario performance table
            scenario_data = []
            for scenario_id, metrics in scenario_metrics.items():
                scenario_data.append({
                    'Scenario': scenario_id,
                    'Success Rate': (metrics['success_count'] / metrics['total_count']) * 100,
                    'Avg F1': sum(metrics['f1_scores']) / len(metrics['f1_scores']) if metrics['f1_scores'] else 0,
                    'Avg AST Sim': sum(metrics['ast_similarities']) / len(metrics['ast_similarities']) if metrics['ast_similarities'] else 0,
                    'Evaluations': metrics['total_count']
                })
            
            df_scenarios = pd.DataFrame(scenario_data)
            df_scenarios = df_scenarios.sort_values('Avg F1', ascending=False)
            
            # Heatmap of scenario performance
            st.markdown("#### Scenario Performance Ranking")
            st.dataframe(
                df_scenarios.style.background_gradient(subset=['Success Rate', 'Avg F1', 'Avg AST Sim']),
                use_container_width=True
            )
            
            # Best and worst scenarios
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🏆 Top Performing Scenarios")
                st.dataframe(df_scenarios.head(5)[['Scenario', 'Avg F1', 'Success Rate']], use_container_width=True)
            
            with col2:
                st.markdown("#### ⚠️ Challenging Scenarios")
                st.dataframe(df_scenarios.tail(5)[['Scenario', 'Avg F1', 'Success Rate']], use_container_width=True)
        
        with tab5:
            st.markdown("### 📋 Detailed Results")
            
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_method = st.selectbox("Filter by Method:", ["All"] + methods)
            with col2:
                filter_model = st.selectbox("Filter by Model:", ["All"] + selected_models)
            with col3:
                show_errors = st.checkbox("Show Only Errors", value=False)
            
            # Filter results
            filtered_results = results
            if filter_method != "All":
                filtered_results = [r for r in filtered_results 
                                  if (r.get('method') if isinstance(r, dict) else r.method) == filter_method]
            if filter_model != "All":
                filtered_results = [r for r in filtered_results 
                                  if (r.get('model') if isinstance(r, dict) else r.model) == filter_model]
            if show_errors:
                filtered_results = [r for r in filtered_results 
                                  if (r.get('error') if isinstance(r, dict) else r.error)]
            
            st.info(f"Showing {len(filtered_results)} of {len(results)} results")
            
            # Display results
            for i, result in enumerate(filtered_results[:20]):  # Limit to 20 for performance
                # Handle both dict and object results
                if isinstance(result, dict):
                    scenario_id = result.get('scenario_id')
                    method = result.get('method')
                    model = result.get('model')
                    f1_score = result.get('execution_metrics', {}).get('f1_score', 0) if result.get('execution_metrics') else 0
                    error = result.get('error')
                    prompt = result.get('prompt')
                    generated_query = result.get('generated_query')
                else:
                    scenario_id = result.scenario_id
                    method = result.method
                    model = result.model
                    execution_metrics = getattr(result, 'execution_metrics', None)
                    f1_score = execution_metrics.get('f1_score', 0) if execution_metrics else 0
                    error = result.error
                    prompt = result.prompt
                    generated_query = getattr(result, 'generated_query', None)
                
                status = "❌" if error else "✅"
                
                with st.expander(f"{status} {scenario_id} | {method}/{model} | F1: {f1_score:.3f}"):
                    st.markdown(f"**Prompt:** {prompt}")
                    
                    if error:
                        st.error(f"**Error:** {error}")
                    
                    if generated_query:
                        st.markdown("**Generated Query:**")
                        st.json(generated_query)
                    
                    # Show metrics if available
                    if isinstance(result, dict) and result.get('execution_metrics'):
                        metrics = result['execution_metrics']
                    elif hasattr(result, 'execution_metrics') and result.execution_metrics:
                        metrics = result.execution_metrics
                    else:
                        metrics = None
                    
                    if metrics:
                        st.markdown("**Traditional Metrics:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Precision", f"{metrics.get('precision', 0):.3f}")
                        with col2:
                            st.metric("Recall", f"{metrics.get('recall', 0):.3f}")
                        with col3:
                            st.metric("F1 Score", f"{metrics.get('f1_score', 0):.3f}")
                        with col4:
                            st.metric("Jaccard", f"{metrics.get('jaccard', 0):.3f}")
                        
                        # Enhanced metrics if available
                        if any(k in metrics for k in ['semantic_similarity', 'comprehensiveness', 'efficiency', 'quality_level']):
                            st.markdown("**Enhanced Metrics:**")
                            col5, col6, col7, col8 = st.columns(4)
                            with col5:
                                st.metric("Semantic Similarity", f"{metrics.get('semantic_similarity', 0):.3f}")
                            with col6:
                                st.metric("Comprehensiveness", f"{metrics.get('comprehensiveness', 0):.3f}")
                            with col7:
                                st.metric("Efficiency", f"{metrics.get('efficiency', 0):.3f}")
                            with col8:
                                quality = metrics.get('quality_level', 'unknown')
                                st.metric("Quality Level", quality.upper())
        
        # Export options
        st.markdown("---")
        st.markdown("### 💾 Export Results")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Export to CSV", use_container_width=True):
                eval_logger.log_button_click("Export Evaluation Results to CSV",
                    dataset=dataset,
                    result_count=len(results)
                )
                
                # Convert results to DataFrame
                df_export = pd.DataFrame([
                    {
                        'scenario_id': r.get('scenario_id') if isinstance(r, dict) else getattr(r, 'scenario_id', 'unknown'),
                        'method': r.get('method') if isinstance(r, dict) else getattr(r, 'method', 'unknown'),
                        'model': r.get('model') if isinstance(r, dict) else getattr(r, 'model', 'unknown'),
                        'f1_score': (r.get('execution_metrics', {}).get('f1_score', 0) if r.get('execution_metrics') else 0) if isinstance(r, dict) else (getattr(r, 'execution_metrics', {}).get('f1_score', 0) if getattr(r, 'execution_metrics', None) else 0),
                        'ast_similarity': r.get('ast_similarity', 0) if isinstance(r, dict) else getattr(r, 'ast_similarity', 0),
                        'success': not (r.get('error') if isinstance(r, dict) else getattr(r, 'error', None))
                    }
                    for r in results
                ])
                
                csv = df_export.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"evaluation_results_{dataset}_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
                eval_logger.log_download(f"evaluation_results_{dataset}.csv", "CSV",
                                       record_count=len(results))
        
        with col2:
            if st.button("📋 Export to JSON", use_container_width=True):
                eval_logger.log_button_click("Export Evaluation Results to JSON",
                    dataset=dataset,
                    result_count=len(results)
                )
                
                json_data = json.dumps(results if isinstance(results[0], dict) else [r.__dict__ for r in results], indent=2, default=str)
                st.download_button(
                    label="Download JSON",
                    data=json_data,
                    file_name=f"evaluation_results_{dataset}_{time.strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
                
                eval_logger.log_download(f"evaluation_results_{dataset}.json", "JSON",
                                       record_count=len(results))
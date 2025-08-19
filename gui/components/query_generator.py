"""Query Generator Component for Streamlit GUI"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from gui.utils.backend_interface import (
    run_query_generation, validate_query, get_available_models,
    get_available_indices, execute_elasticsearch_query, 
    export_results_as_csv, export_results_as_json
)

def render_query_generator():
    """Render the query generator interface"""
    st.header("🤖 Query Generator")
    st.write("Generate Elasticsearch DSL queries from natural language descriptions")
    
    # Create two columns for input and output
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Input")
        
        # Check for example selection
        default_prompt = "Find events labeled malicious on 2017-07-04"
        if "example_prompt" in st.session_state:
            default_prompt = st.session_state.example_prompt
            st.session_state.pop("example_prompt")  # Remove after use
        
        # Query input
        prompt = st.text_area(
            "Natural Language Query:",
            value=default_prompt,
            height=100,
            help="Enter your query in natural language. Be specific about time ranges and conditions."
        )
        
        # Index and method selection in two columns
        method_col, index_col = st.columns(2)
        
        with method_col:
            method = st.selectbox(
                "Generation Method:",
                ["constrained", "rules", "zeroshot"],
                index=0,
                help="Choose the query generation method"
            )
        
        with index_col:
            # Get available indices
            available_indices = get_available_indices()
            default_index = "logs_net" if "logs_net" in available_indices else available_indices[0] if available_indices else "logs_net"
            
            selected_index = st.selectbox(
                "Target Index:",
                available_indices,
                index=available_indices.index(default_index) if default_index in available_indices else 0,
                help="Select the Elasticsearch index to query"
            )
        
        # Advanced options in expandable section
        with st.expander("⚙️ Advanced Options"):
            col1a, col1b = st.columns(2)
            
            with col1a:
                schema_validation = st.checkbox("Schema Validation", value=True)
                few_shot = st.checkbox("Few-shot Examples", value=True)
            
            with col1b:
                # Get available models dynamically
                available_models = get_available_models()
                
                # Set default model (prefer llama3.1 if available)
                default_model = "llama3.1:latest"
                if default_model not in available_models and available_models:
                    default_model = available_models[0]
                
                default_index = 0
                if default_model in available_models:
                    default_index = available_models.index(default_model)
                
                model = st.selectbox(
                    "Model:", 
                    available_models,
                    index=default_index,
                    help=f"Available offline LLMs ({len(available_models)} models found)"
                )
                max_retries = st.number_input("Max Retries:", min_value=1, max_value=5, value=2)
        
        # Generate button
        generate_button = st.button("🚀 Generate Query", type="primary", use_container_width=True)
        
        # Generation log section
        if generate_button or st.session_state.get("show_generation_log", False):
            st.subheader("Generation Log")
            log_container = st.container()
    
    with col2:
        st.subheader("Output")
        
        # Handle generation
        if generate_button:
            st.session_state.show_generation_log = True
            
            with log_container:
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Step 1: Validation
                status_text.text("🔍 Validating input...")
                progress_bar.progress(20)
                time.sleep(0.5)
                
                # Step 2: Generation
                status_text.text("🤖 Generating query...")
                progress_bar.progress(50)
                
                # Run generation
                success, output, data = run_query_generation(prompt, method)
                
                # Step 3: Validation
                status_text.text("✅ Validating output...")
                progress_bar.progress(80)
                time.sleep(0.5)
                
                progress_bar.progress(100)
                status_text.text("✅ Generation complete!")
                
                # Store results in session state
                st.session_state.generation_results = {
                    "success": success,
                    "output": output,
                    "data": data,
                    "prompt": prompt,
                    "method": method
                }
        
        # Display results
        if "generation_results" in st.session_state:
            results = st.session_state.generation_results
            
            if results["success"]:
                # Display generated query
                query = results["data"].get("query", {})
                
                if "abstain" in query:
                    st.error("🚫 Generation Abstained")
                    st.write(f"**Reason:** {query.get('reason', 'Unknown')}")
                else:
                    st.success("✅ Query Generated Successfully")
                    
                    # Format and display JSON
                    try:
                        formatted_query = json.dumps(query, indent=2)
                        st.code(formatted_query, language="json")
                        
                        # Buttons row
                        button_col1, button_col2 = st.columns(2)
                        
                        with button_col1:
                            st.download_button(
                                "📥 Download Query",
                                data=formatted_query,
                                file_name=f"query_{int(time.time())}.json",
                                mime="application/json"
                            )
                        
                        with button_col2:
                            execute_button = st.button("🚀 Execute Query", type="secondary")
                        
                        # Execute query if button pressed
                        if execute_button:
                            st.session_state.execute_query = True
                            st.session_state.query_to_execute = query
                            st.session_state.target_index = selected_index
                    except Exception as e:
                        st.error(f"Error formatting query: {e}")
                
                # Display metrics
                metrics = results["data"].get("metrics", {})
                if metrics:
                    st.subheader("📊 Generation Metrics")
                    
                    metric_cols = st.columns(3)
                    
                    with metric_cols[0]:
                        latency = metrics.get("latency_seconds", 0)
                        st.metric("Latency", f"{latency:.2f}s")
                    
                    with metric_cols[1]:
                        attempts = metrics.get("attempts", 0)
                        st.metric("Attempts", attempts)
                    
                    with metric_cols[2]:
                        success_rate = 100 if results["success"] else 0
                        st.metric("Success", f"{success_rate}%")
                    
                    # Show retry reasons if any
                    retry_reasons = metrics.get("retry_reasons", [])
                    if retry_reasons:
                        st.write("**Retry Reasons:**")
                        for i, reason in enumerate(retry_reasons, 1):
                            st.write(f"{i}. {reason}")
            
            else:
                st.error("❌ Generation Failed")
                st.write("**Error Details:**")
                st.code(results["output"])
    
    # Query Execution Section
    # Show execution results if we have them or if execution was requested
    show_execution = (st.session_state.get("execute_query", False) or 
                     "last_execution_results" in st.session_state)
    
    if show_execution:
        st.markdown("---")
        st.subheader("🔍 Query Execution Results")
        
        query_to_execute = st.session_state.get("query_to_execute", {})
        target_index = st.session_state.get("target_index", "logs_net")
        
        # Check if we need to execute a new query
        need_execution = st.session_state.get("execute_query", False)
        
        if need_execution:
            # Reset execution flag
            st.session_state.execute_query = False
        
        if query_to_execute or "last_execution_results" in st.session_state:
            # Execution controls
            exec_col1, exec_col2 = st.columns([3, 1])
            
            with exec_col1:
                # Get current size limit from session state or default
                current_size = st.session_state.get("execution_size_limit", 1000)
                size_limit = st.slider(
                    "Max Results to Return:", 
                    min_value=10, max_value=10000, value=current_size, step=50,
                    key="size_limit_slider",
                    help="Limit the number of results returned to avoid overwhelming the interface"
                )
                # Store size limit in session state
                st.session_state.execution_size_limit = size_limit
            
            with exec_col2:
                # Re-execute button
                if st.button("🔄 Re-execute Query", type="secondary"):
                    need_execution = True
                    st.session_state.execute_query = True
            
            # Execute query if needed (first time or re-execute)
            if need_execution and query_to_execute:
                with st.spinner(f"Executing query on index '{target_index}'..."):
                    success, execution_results = execute_elasticsearch_query(
                        query_to_execute, target_index, max_size=size_limit
                    )
                    # Store results in session state for persistence
                    if success:
                        st.session_state.last_execution_results = execution_results
                    else:
                        st.session_state.last_execution_error = execution_results
            
            # Use stored results for display
            execution_results = st.session_state.get("last_execution_results")
            execution_error = st.session_state.get("last_execution_error")
            
            # Display results or errors
            if execution_results:
                # Display query info
                st.info(f"📋 **Query executed on:** `{execution_results['index']}` | **Max results:** {st.session_state.get('execution_size_limit', 1000)}")
                
                # Display summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Hits", f"{execution_results['total_hits']:,}")
                with col2:
                    st.metric("Returned", f"{execution_results['returned_hits']:,}")
                with col3:
                    st.metric("Query Time", f"{execution_results['took']} ms")
                with col4:
                    st.metric("Index", execution_results['index'])
                
                # Display results
                if execution_results['results']:
                    st.subheader("📄 Query Results")
                    
                    # Results display options
                    display_cols = st.columns([3, 1, 1])
                    
                    with display_cols[0]:
                        # Get current display format from session state or default
                        current_format = st.session_state.get("execution_display_format", "Table")
                        format_options = ["Table", "JSON", "Raw Data"]
                        default_index = 0
                        if current_format in format_options:
                            default_index = format_options.index(current_format)
                        
                        display_format = st.selectbox(
                            "Display Format:",
                            format_options,
                            index=default_index,
                            key="display_format_selector",
                            help="Choose how to display the results"
                        )
                        # Store format in session state
                        st.session_state.execution_display_format = display_format
                    
                    with display_cols[1]:
                        # Export buttons
                        if execution_results['results']:
                            csv_data = export_results_as_csv(execution_results)
                            st.download_button(
                                "📊 Export CSV",
                                data=csv_data,
                                file_name=f"query_results_{int(time.time())}.csv",
                                mime="text/csv"
                            )
                    
                    with display_cols[2]:
                        if execution_results['results']:
                            json_data = export_results_as_json(execution_results)
                            st.download_button(
                                "📋 Export JSON",
                                data=json_data,
                                file_name=f"query_results_{int(time.time())}.json",
                                mime="application/json"
                            )
                    
                    # Display results based on format selection
                    if display_format == "Table":
                        # Convert to DataFrame for better display
                        try:
                            import pandas as pd
                            df = pd.DataFrame(execution_results['results'])
                            
                            # Truncate long text fields for better table display
                            for col in df.columns:
                                if df[col].dtype == 'object':
                                    df[col] = df[col].astype(str).apply(
                                        lambda x: (x[:100] + '...') if len(str(x)) > 100 else x
                                    )
                            
                            st.dataframe(df, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error displaying table: {e}")
                            st.json(execution_results['results'])
                    
                    elif display_format == "JSON":
                        # Pretty print JSON with syntax highlighting
                        st.json(execution_results['results'])
                    
                    else:  # Raw Data
                        # Display raw results with expandable sections
                        for i, result in enumerate(execution_results['results'][:100]):  # Limit to first 100
                            with st.expander(f"Document {i+1} (ID: {result.get('_id', 'Unknown')})", expanded=(i < 3)):
                                st.json(result)
                        
                        if len(execution_results['results']) > 100:
                            st.info(f"Showing first 100 results. Total: {len(execution_results['results'])} documents.")
                
                # Display aggregations if present
                if execution_results.get('aggregations'):
                    st.subheader("📊 Aggregations")
                    st.json(execution_results['aggregations'])
                
                # Clear results button
                st.markdown("---")
                if st.button("🗑️ Clear Execution Results", type="secondary"):
                    st.session_state.pop("last_execution_results", None)
                    st.session_state.pop("last_execution_error", None)
                    st.session_state.pop("execution_size_limit", None)
                    st.session_state.pop("execution_display_format", None)
                    st.rerun()
                
            elif execution_error:
                st.error("❌ Query Execution Failed")
                st.write("**Error Details:**")
                st.code(execution_error.get("error", "Unknown error"))
                
                # Show the query that failed for debugging
                query_to_show = execution_error.get("query", query_to_execute)
                if query_to_show:
                    st.write("**Failed Query:**")
                    st.code(json.dumps(query_to_show, indent=2), language="json")
                
                # Clear results button for errors
                if st.button("🗑️ Clear Error", type="secondary"):
                    st.session_state.pop("last_execution_error", None)
                    st.session_state.pop("last_execution_results", None)
                    st.rerun()
    
    # Quick examples section
    st.markdown("---")
    st.subheader("💡 Example Queries")
    
    example_cols = st.columns(3)
    
    examples = [
        "Find events labeled malicious on 2017-07-04",
        "Find TCP connections with more than 10000 bytes transferred from 10.42.42.1",
        "Find all traffic to destination port 445 or 3389 on July 4, 2017"
    ]
    
    for i, (col, example) in enumerate(zip(example_cols, examples)):
        with col:
            if st.button(f"📝 Example {i+1}", key=f"example_{i}", use_container_width=True):
                st.session_state.example_prompt = example
                st.toast(f"Example {i+1} selected!", icon="📝")
    
    # Note: Example handling is now done at the top of the component
    
    # Query validation section
    st.markdown("---")
    st.subheader("🔍 Query Validation")
    
    # File uploader for external queries
    uploaded_file = st.file_uploader(
        "Upload Query JSON for Validation:",
        type="json",
        help="Upload an Elasticsearch DSL query for validation"
    )
    
    if uploaded_file:
        try:
            query_content = json.load(uploaded_file)
            st.code(json.dumps(query_content, indent=2), language="json")
            
            # Save temporary file for validation
            temp_file = Path(f"artifacts/generated/temp_validation_{int(time.time())}.json")
            with open(temp_file, 'w') as f:
                json.dump(query_content, f)
            
            if st.button("🔍 Validate Query"):
                with st.spinner("Validating query..."):
                    is_valid, validation_output = validate_query(str(temp_file))
                
                if is_valid:
                    st.success("✅ Query is valid!")
                else:
                    st.error("❌ Query validation failed")
                    st.code(validation_output)
                
                # Clean up temp file
                temp_file.unlink(missing_ok=True)
        
        except json.JSONDecodeError:
            st.error("❌ Invalid JSON file")
        except Exception as e:
            st.error(f"❌ Error processing file: {e}")
    
    # Recent generations
    st.markdown("---")
    st.subheader("📝 Recent Generations")
    
    # List recent query files
    generated_dir = Path("artifacts/generated")
    if generated_dir.exists():
        query_files = sorted(
            [f for f in generated_dir.glob("*.json") if not f.name.endswith(".metrics.json")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:5]  # Show last 5
        
        if query_files:
            for query_file in query_files:
                with st.expander(f"📄 {query_file.name}"):
                    try:
                        with open(query_file) as f:
                            query_data = json.load(f)
                        st.code(json.dumps(query_data, indent=2), language="json")
                        
                        # Show metrics if available
                        metrics_file = query_file.with_suffix(".metrics.json")
                        if metrics_file.exists():
                            with open(metrics_file) as f:
                                metrics_data = json.load(f)
                            st.json(metrics_data)
                    except Exception as e:
                        st.error(f"Error loading {query_file.name}: {e}")
        else:
            st.info("No recent generations found. Generate a query to see results here.")
    else:
        st.info("Generated queries directory not found.")
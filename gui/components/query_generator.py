"""Query Generator Component for Streamlit GUI

User Experience Improvements:
- Fixed display format selectbox to respond reliably on first click
- Improved session state management for consistent UI behavior
- Eliminated race conditions in widget state updates
- Fixed slider value validation to prevent browser console errors
- Fixed example query buttons to work immediately on first click
"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.external.llm_manager import get_external_llm_manager
from gui.utils.backend_interface import (
    run_query_generation, validate_query, get_available_models,
    get_available_indices, execute_elasticsearch_query, 
    export_results_as_csv, export_results_as_json
)

def get_external_llm_models():
    """Get list of enabled external LLM models"""
    try:
        manager = get_external_llm_manager()
        llms = manager.list_llms(enabled_only=True)
        return [llm.name for llm in llms]
    except:
        return []

def render_query_generator():
    """Render the query generator interface"""
    st.header("🤖 Query Generator")
    st.write("Generate Elasticsearch DSL queries from natural language descriptions")
    
    # Create two columns for input and output
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Input")
        
        # Handle example selection with immediate text area update
        default_prompt = "Find events labeled malicious on 2017-07-04"
        
        # Check if an example was just selected
        if "selected_example" in st.session_state:
            default_prompt = st.session_state.selected_example
            # Keep the example in session state until user changes it
        
        # Query input
        prompt = st.text_area(
            "Natural Language Query:",
            value=default_prompt,
            height=100,
            key="query_text_input",
            help="Enter your query in natural language. Be specific about time ranges and conditions."
        )
        
        # Clear selected example if user modified the text
        if "selected_example" in st.session_state and prompt != st.session_state.selected_example:
            st.session_state.pop("selected_example", None)
        
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
                # Get available models dynamically (both local and external)
                available_models = get_available_models()
                external_models = get_external_llm_models()
                
                # Combine models with prefixes
                all_models = []
                if available_models:
                    all_models.extend([f"Local: {m}" for m in available_models])
                if external_models:
                    all_models.extend([f"External: {m}" for m in external_models])
                
                if not all_models:
                    st.warning("No models available. Please configure LLMs.")
                    model = None
                else:
                    # Set default model (prefer llama3.1 if available)
                    default_model = "Local: llama3.1:latest"
                    if default_model not in all_models and all_models:
                        default_model = all_models[0]
                    
                    default_index = 0
                    if default_model in all_models:
                        default_index = all_models.index(default_model)
                    
                    model = st.selectbox(
                        "Model:", 
                        all_models,
                        index=default_index,
                        help=f"Available LLMs: {len(available_models)} local, {len(external_models)} external"
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
                success, output, data = run_query_generation(
                    prompt, method, index=selected_index, model=model
                )
                
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
                full_query_data = results["data"].get("query", {})
                
                # Check if generation was abstained at the top level
                if "abstain" in full_query_data:
                    st.error("🚫 Generation Abstained")
                    st.write(f"**Reason:** {full_query_data.get('reason', 'Unknown')}")
                elif not full_query_data:
                    st.error("🚫 Empty Query Generated")
                    st.write("**Reason:** No query content returned")
                else:
                    st.success("✅ Query Generated Successfully")
                    
                    # Format and display JSON
                    try:
                        formatted_query = json.dumps(full_query_data, indent=2)
                        
                        # Create editable text area for query
                        st.subheader("📝 Generated Query (Editable)")
                        st.info("💡 You can edit the query below before executing")
                        
                        # Initialize edited query in session state if not exists
                        if 'edited_query' not in st.session_state or st.session_state.get('last_generated_query') != formatted_query:
                            st.session_state.edited_query = formatted_query
                            st.session_state.last_generated_query = formatted_query
                        
                        # Editable text area
                        edited_query_str = st.text_area(
                            "Edit Query:",
                            value=st.session_state.edited_query,
                            height=300,
                            key="query_editor",
                            help="Modify the query as needed. Must be valid JSON."
                        )
                        
                        # Update session state with edited query
                        st.session_state.edited_query = edited_query_str
                        
                        # Validate JSON
                        try:
                            parsed_query = json.loads(edited_query_str)
                            st.success("✅ Valid JSON")
                            
                            # Buttons row
                            button_col1, button_col2, button_col3 = st.columns(3)
                            
                            with button_col1:
                                st.download_button(
                                    "📥 Download Query",
                                    data=edited_query_str,
                                    file_name=f"query_{int(time.time())}.json",
                                    mime="application/json"
                                )
                            
                            with button_col2:
                                if st.button("🔄 Reset to Original", type="secondary"):
                                    st.session_state.edited_query = formatted_query
                                    st.rerun()
                            
                            with button_col3:
                                execute_button = st.button("🚀 Execute Query", type="primary")
                            
                            # Execute query if button pressed
                            if execute_button:
                                st.session_state.execute_query = True
                                st.session_state.query_to_execute = parsed_query
                                st.session_state.target_index = selected_index
                                
                        except json.JSONDecodeError as e:
                            st.error(f"❌ Invalid JSON: {str(e)}")
                            st.warning("Please fix the JSON syntax before executing")
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
                # Define slider constraints
                min_val, max_val, step_val = 10, 10000, 50
                default_val = 1000
                
                # Initialize and validate size limit in session state
                if "execution_size_limit" not in st.session_state:
                    st.session_state.execution_size_limit = default_val
                
                # Validate current session state value against slider constraints
                current_val = st.session_state.execution_size_limit
                
                # Ensure value is within bounds
                current_val = max(min_val, min(max_val, current_val))
                
                # Ensure value is compatible with step (round to nearest valid step)
                # Example: if current_val=1075, step=50, min=10, result=1060 (valid step)
                current_val = round((current_val - min_val) / step_val) * step_val + min_val
                
                # Update session state with validated value
                st.session_state.execution_size_limit = current_val
                
                size_limit = st.slider(
                    "Max Results to Return:", 
                    min_value=min_val, 
                    max_value=max_val, 
                    value=current_val, 
                    step=step_val,
                    key="size_limit_slider",
                    help="Limit the number of results returned to avoid overwhelming the interface"
                )
                
                # Update session state only when value actually changes
                if size_limit != st.session_state.execution_size_limit:
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
                        format_options = ["Table", "JSON", "Raw Data"]
                        
                        # Initialize display format if not set
                        if "execution_display_format" not in st.session_state:
                            st.session_state.execution_display_format = "Table"
                        
                        # Ensure current selection is valid
                        current_selection = st.session_state.execution_display_format
                        if current_selection not in format_options:
                            current_selection = "Table"
                            st.session_state.execution_display_format = current_selection
                        
                        # Use a stable key for the selectbox
                        display_format = st.selectbox(
                            "Display Format:",
                            format_options,
                            index=format_options.index(current_selection),
                            key="query_results_display_format",
                            help="Choose how to display the results"
                        )
                        
                        # Update session state when selection changes
                        if display_format != st.session_state.execution_display_format:
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
                
                else:
                    # No results found - show helpful information
                    st.warning("⚠️ No results found")
                    
                    # Try to provide helpful suggestions
                    st.subheader("💡 Suggestions")
                    
                    # Show the query that was executed
                    with st.expander("Query that was executed:", expanded=True):
                        st.code(json.dumps(query_to_execute, indent=2), language="json")
                    
                    # Provide helpful tips based on index
                    if "cic" in target_index.lower():
                        st.info("""
                        **Common issues with CIC-IDS2017 queries:**
                        
                        1. **Check IP addresses**: DDoS attacks come from `172.16.0.1`, not `192.168.x.x`
                        2. **Verify ports**: Common attack ports are 80, 21, 443, 22, 444
                        3. **Adjust thresholds**: 
                           - Packet rates: Average is ~2 pps, high is >10 pps
                           - Flow duration: In milliseconds (1000 = 1 second)
                        4. **Check attack types**: dos, scan, bruteforce (not DDoS, portscan, etc.)
                        
                        **Try these example queries that work:**
                        - Find DDoS attacks from 172.16.0.1
                        - Find port scans targeting port 80
                        - Find traffic with packet rate over 5
                        """)
                    else:
                        st.info("""
                        **Possible reasons for no results:**
                        
                        1. The combination of filters is too restrictive
                        2. Check field values match actual data
                        3. Verify date ranges include your data
                        4. Try removing some conditions
                        """)
                    
                    # Suggest editing the query
                    st.success("✨ **Tip**: Edit the query above and try different values!")
                
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
                # Store selected example for immediate text area update
                st.session_state.selected_example = example
                st.toast(f"Example {i+1} selected!", icon="📝")
                # Force rerun to immediately update text area with new value
                st.rerun()
    
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
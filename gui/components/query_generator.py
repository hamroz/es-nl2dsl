"""
Query Generator Component: Interactive Streamlit interface for query generation

This module provides the primary user interface for the ES-NL2DSL system, enabling
natural language to Elasticsearch DSL query generation through an intuitive web-based
interface. It combines real-time query generation with advanced features including
multi-index support, query execution, result visualization, and data export capabilities.

Key features:
- Interactive natural language query input with intelligent examples
- Dynamic index selection with real-time schema discovery
- Multiple generation methods (enhanced constrained, rules-based, zero-shot)
- Real-time query execution with configurable result limits
- Multiple result display formats (table, JSON, raw data) with syntax highlighting
- One-click data export (CSV, JSON) with proper formatting
- Performance monitoring with execution metrics and timing
- External LLM integration with provider selection
- Comprehensive error handling and user feedback

This component serves as the main entry point for end users and integrates with
the backend processing pipeline to deliver a complete query generation experience.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import logging utilities
from gui.utils.logging_utils import get_gui_logger

# Initialize component logger
query_logger = get_gui_logger("query_generator")

from src.external.llm_manager import get_external_llm_manager
from gui.utils.backend_interface import (
    run_query_generation, validate_query, get_available_models,
    get_available_indices, execute_elasticsearch_query, 
    export_results_as_csv, export_results_as_json
)

def get_external_llm_models():
    """
    Retrieve list of configured and enabled external LLM providers.
    
    Queries the external LLM manager to obtain a list of all configured
    language model providers that are currently enabled and available
    for query generation.
    
    Returns:
        List[str]: Names of enabled external LLM providers (OpenAI, Anthropic, 
                  Google, etc.), empty list if none configured or on error
                  
    Used for populating the LLM selection dropdown in the advanced options
    section of the query generator interface.
    """
    try:
        manager = get_external_llm_manager()
        llms = manager.list_llms(enabled_only=True)
        return [llm.name for llm in llms]
    except:
        return []

def render_query_generator():
    """
    Render the main query generator interface with full interactive capabilities.
    
    This function creates and manages the complete user interface for natural language
    to Elasticsearch DSL query generation, including input forms, configuration options,
    result display, and export functionality. It handles user interactions, state management,
    and integration with backend processing systems.
    
    Interface Components:
        - Natural language input with example queries and smart suggestions
        - Index selection dropdown with real-time availability checking
        - Generation method selection (enhanced constrained, rules, zero-shot)
        - Advanced configuration options (models, validation, examples)
        - Query execution controls with configurable result limits
        - Multi-format result display (table, JSON, raw data)
        - Export functionality (CSV, JSON) with one-click downloads
        - Performance metrics and execution timing
        - Error handling and user feedback systems
        
    Features:
        - Session state management for consistent user experience
        - Real-time validation and feedback
        - Intelligent example query suggestions
        - External LLM provider integration
        - Comprehensive logging for debugging and analytics
    """
    query_logger.log_page_load("Query Generator component loaded")
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
        
        # Log input changes (without storing the actual prompt for privacy)
        if prompt and prompt != default_prompt:
            query_logger.log_input_change("text_area", "natural_language_query", len(prompt))
        
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
            # Log method selection
            if "last_selected_method" not in st.session_state:
                st.session_state.last_selected_method = method
            elif st.session_state.last_selected_method != method:
                query_logger.log_selection_change("method", st.session_state.last_selected_method, method)
                st.session_state.last_selected_method = method
        
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
            # Log index selection
            if "last_selected_index" not in st.session_state:
                st.session_state.last_selected_index = selected_index
            elif st.session_state.last_selected_index != selected_index:
                query_logger.log_selection_change("index", st.session_state.last_selected_index, selected_index)
                st.session_state.last_selected_index = selected_index
        
        # Index Information Panel
        if selected_index:
            with st.expander(f"📊 Index Information: {selected_index}", expanded=False):
                try:
                    from gui.utils.backend_interface import get_index_profile_info, refresh_index_profile
                    
                    # Refresh button at the top
                    if st.button("🔄 Refresh Profile", help="Refresh index profile", key=f"refresh_{selected_index}"):
                        with st.spinner("Refreshing index profile..."):
                            success = refresh_index_profile(selected_index)
                            if success:
                                st.success("Profile refreshed!")
                                st.rerun()
                            else:
                                st.error("Failed to refresh profile")
                    
                    # Get index profile
                    profile_info = get_index_profile_info(selected_index)
                    
                    if profile_info.get("has_profile"):
                        # Display key metrics in a simple row
                        info_col1, info_col2, info_col3 = st.columns(3)
                        
                        with info_col1:
                            st.metric("Documents", f"{profile_info.get('document_count', 0):,}")
                        
                        with info_col2:
                            st.metric("Fields", profile_info.get('field_count', 0))
                        
                        with info_col3:
                            system_type = profile_info.get('system_type', 'Unknown')
                            st.metric("System Type", system_type)
                        
                        # Date range information
                        date_range = profile_info.get('date_range', {})
                        if date_range.get('min_date') and date_range.get('max_date'):
                            st.info(f"📅 **Data Range:** {date_range['min_date'][:10]} to {date_range['max_date'][:10]}")
                        
                        # Key fields
                        key_fields = profile_info.get('key_fields', {})
                        if any(key_fields.values()):
                            st.write("**Key Fields:**")
                            for field_type, fields in key_fields.items():
                                if fields:
                                    field_type_display = field_type.replace('_', ' ').title()
                                    st.write(f"• **{field_type_display}:** {', '.join(fields[:3])}")
                        
                        # Sample fields
                        sample_fields = profile_info.get('sample_fields', [])
                        if sample_fields:
                            st.write(f"**Available Fields:** {', '.join(sample_fields)}")
                            if len(sample_fields) >= 10:
                                st.write("*...and more*")
                    else:
                        st.warning(f"⚠️ Could not load profile for {selected_index}")
                        if profile_info.get('error'):
                            st.error(f"Error: {profile_info['error']}")
                
                except Exception as e:
                    st.error(f"Error loading index information: {e}")
        
        # Advanced options in expandable section
        with st.expander("⚙️ Advanced Options"):
            adv_col1, adv_col2 = st.columns(2)
            
            with adv_col1:
                schema_validation = st.checkbox("Schema Validation", value=True)
                few_shot = st.checkbox("Few-shot Examples", value=True)
            
            with adv_col2:
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
                    # Log model selection
                    if "last_selected_model" not in st.session_state:
                        st.session_state.last_selected_model = model
                    elif st.session_state.last_selected_model != model:
                        query_logger.log_selection_change("model", st.session_state.last_selected_model, model)
                        st.session_state.last_selected_model = model
                        
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
            query_logger.log_button_click("Generate Query", method=method, model=model, index=selected_index, prompt_length=len(prompt))
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
                
                # Log generation start
                query_logger.log_query_generation(method, model, len(prompt), index=selected_index)
                
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
                
                # Log generation result
                if success:
                    query_logger.log_success("Query generation completed", 
                        method=method, 
                        model=model,
                        prompt_length=len(prompt),
                        has_query=bool(data.get("query"))
                    )
                else:
                    query_logger.log_error("Query generation failed", output, 
                                         method=method, model=model, prompt_length=len(prompt))
                
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
                        
                        # Add query validation
                        try:
                            from gui.utils.backend_interface import validate_query_with_feedback
                            validation_result = validate_query_with_feedback(full_query_data, selected_index)
                            
                            # Show validation status and score (simple layout to avoid column nesting)
                            if validation_result["is_valid"]:
                                st.success(f"{validation_result['status_emoji']} Query is valid")
                            else:
                                st.error(f"{validation_result['status_emoji']} Query has issues")
                            
                            score = validation_result.get("score", 0)
                            st.info(f"📊 **Quality Score:** {score:.0f}/100")
                            
                            # Show execution info if available (no nested columns)
                            if validation_result.get("result_count") is not None:
                                result_count = validation_result["result_count"]
                                exec_info = f"📊 **Results:** {result_count:,} documents"
                                
                                if validation_result.get("execution_time_ms"):
                                    exec_time = validation_result["execution_time_ms"]
                                    exec_info += f" | ⏱️ **Speed:** {exec_time:.0f}ms"
                                
                                st.info(exec_info)
                            
                            # Show validation feedback
                            if validation_result.get("issues"):
                                with st.expander("❌ Issues Found", expanded=True):
                                    for issue in validation_result["issues"]:
                                        st.error(f"• {issue}")
                            
                            if validation_result.get("warnings"):
                                with st.expander("⚠️ Warnings"):
                                    for warning in validation_result["warnings"]:
                                        st.warning(f"• {warning}")
                            
                            if validation_result.get("suggestions"):
                                with st.expander("💡 Optimization Suggestions"):
                                    for suggestion in validation_result["suggestions"]:
                                        st.info(f"• {suggestion}")
                        
                        except Exception as e:
                            st.warning(f"⚠️ Could not validate query: {e}")
                        
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
                            
                            # Action buttons (stacked to avoid column nesting)
                            st.download_button(
                                "📥 Download Query",
                                data=edited_query_str,
                                file_name=f"query_{int(time.time())}.json",
                                mime="application/json",
                                key="download_query_btn"
                            )
                            
                            if st.button("🔄 Reset to Original", type="secondary", key="reset_query_btn"):
                                st.session_state.edited_query = formatted_query
                                st.rerun()
                            
                            execute_button = st.button("🚀 Execute Query", type="primary", key="execute_query_btn")
                            
                            # Execute query if button pressed
                            if execute_button:
                                query_logger.log_button_click("Execute Query", index=selected_index, 
                                                            query_size=len(json.dumps(parsed_query)))
                                st.session_state.execute_query = True
                                st.session_state.query_to_execute = parsed_query
                                st.session_state.target_index = selected_index
                                
                        except json.JSONDecodeError as e:
                            st.error(f"❌ Invalid JSON: {str(e)}")
                            st.warning("Please fix the JSON syntax before executing")
                    except Exception as e:
                        st.error(f"Error formatting query: {e}")
                
                # Display metrics (using simple layout to avoid column nesting)
                metrics = results["data"].get("metrics", {})
                if metrics:
                    st.subheader("📊 Generation Metrics")
                    
                    latency = metrics.get("latency_seconds", 0)
                    attempts = metrics.get("attempts", 0)
                    success_rate = 100 if results["success"] else 0
                    
                    # Display metrics in a single info box to avoid nested columns
                    metrics_text = f"⏱️ **Latency:** {latency:.2f}s | 🔄 **Attempts:** {attempts} | ✅ **Success:** {success_rate}%"
                    st.info(metrics_text)
                    
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
            # Execution controls (simplified to avoid column nesting)
            st.write("**Execution Options:**")
            
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
            
            # Re-execute button
            if st.button("🔄 Re-execute Query", type="secondary", key="re_execute_query_btn"):
                need_execution = True
                st.session_state.execute_query = True
            
            # Execute query if needed (first time or re-execute)
            if need_execution and query_to_execute:
                query_logger.log_query_execution(target_index, "generated_query")
                with st.spinner(f"Executing query on index '{target_index}'..."):
                    success, execution_results = execute_elasticsearch_query(
                        query_to_execute, target_index, max_size=size_limit
                    )
                    # Store results in session state for persistence
                    if success:
                        st.session_state.last_execution_results = execution_results
                        query_logger.log_success("Query executed successfully", 
                            index=target_index,
                            result_count=execution_results.get("returned_hits", 0),
                            total_hits=execution_results.get("total_hits", 0),
                            execution_time_ms=execution_results.get("took", 0)
                        )
                    else:
                        st.session_state.last_execution_error = execution_results
                        query_logger.log_error("Query execution failed", str(execution_results.get("error", "Unknown error")),
                                             index=target_index)
            
            # Use stored results for display
            execution_results = st.session_state.get("last_execution_results")
            execution_error = st.session_state.get("last_execution_error")
            
            # Display results or errors
            if execution_results:
                # Display query info
                st.info(f"📋 **Query executed on:** `{execution_results['index']}` | **Max results:** {st.session_state.get('execution_size_limit', 1000)}")
                
                # Display summary metrics (using simple layout to avoid column nesting)
                total_hits = execution_results['total_hits']
                returned_hits = execution_results['returned_hits']
                query_time = execution_results['took']
                index_name = execution_results['index']
                
                metrics_summary = f"📊 **Total Hits:** {total_hits:,} | 📄 **Returned:** {returned_hits:,} | ⏱️ **Query Time:** {query_time} ms | 🗂️ **Index:** {index_name}"
                st.info(metrics_summary)
                
                # Display results
                if execution_results['results']:
                    st.subheader("📄 Query Results")
                    
                    # Results display options (simplified layout to avoid column nesting)
                    st.write("**Display Options:**")
                    
                    # Display format selection
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
                    
                    # Export buttons (stacked to avoid column nesting)
                    if execution_results['results']:
                        st.write("**Export Options:**")
                        
                        csv_data = export_results_as_csv(execution_results)
                        if st.download_button(
                            "📊 Export CSV",
                            data=csv_data,
                            file_name=f"query_results_{int(time.time())}.csv",
                            mime="text/csv",
                            key="export_csv_btn"
                        ):
                            query_logger.log_download(f"query_results_{int(time.time())}.csv", "CSV",
                                                    record_count=len(execution_results['results']))
                        
                        json_data = export_results_as_json(execution_results)
                        if st.download_button(
                            "📋 Export JSON",
                            data=json_data,
                            file_name=f"query_results_{int(time.time())}.json",
                            mime="application/json",
                            key="export_json_btn"
                        ):
                            query_logger.log_download(f"query_results_{int(time.time())}.json", "JSON",
                                                    record_count=len(execution_results['results']))
                    
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
                query_logger.log_button_click(f"Example {i+1}", example_length=len(example))
                # Store selected example for immediate text area update
                st.session_state.selected_example = example
                st.toast(f"Example {i+1} selected!", icon="📝")
                query_logger.log_user_action("Example query selected", example_number=i+1)
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
        query_logger.log_file_upload(uploaded_file.name, uploaded_file.size, uploaded_file.type)
        try:
            query_content = json.load(uploaded_file)
            st.code(json.dumps(query_content, indent=2), language="json")
            
            # Save temporary file for validation
            temp_file = Path(f"artifacts/generated/temp_validation_{int(time.time())}.json")
            with open(temp_file, 'w') as f:
                json.dump(query_content, f)
            
            if st.button("🔍 Validate Query"):
                query_logger.log_button_click("Validate Uploaded Query", filename=uploaded_file.name)
                with st.spinner("Validating query..."):
                    is_valid, validation_output = validate_query(str(temp_file))
                
                if is_valid:
                    st.success("✅ Query is valid!")
                    query_logger.log_success("Query validation passed", filename=uploaded_file.name)
                else:
                    st.error("❌ Query validation failed")
                    st.code(validation_output)
                    query_logger.log_error("Query validation failed", validation_output, filename=uploaded_file.name)
                
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
    
    # Query Explanation Section (moved from interpretability dashboard)
    st.markdown("---")
    st.subheader("🧠 Query Generation Explanation")
    st.markdown("Understand how and why specific DSL queries were generated")
    
    # Query explanation section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Option to load existing query or create new one
        explanation_mode = st.radio(
            "Explanation Mode",
            ["Load Existing Query", "Generate & Explain New Query"],
            horizontal=True
        )
    
    with col2:
        explanation_level = st.selectbox(
            "Detail Level",
            ["Basic", "Detailed", "Technical", "Research"],
            index=1
        )
    
    if explanation_mode == "Load Existing Query":
        # File upload for existing query
        uploaded_file = st.file_uploader(
            "Upload Query JSON",
            type=['json'],
            help="Upload a generated query file to analyze",
            key="explanation_uploader"
        )
        
        prompt_text = st.text_area(
            "Original Prompt",
            placeholder="Enter the original natural language prompt...",
            help="The natural language prompt that generated this query",
            key="explanation_prompt"
        )
        
        if uploaded_file and prompt_text:
            try:
                query_data = json.load(uploaded_file)
                
                if st.button("🔍 Explain Query", type="primary", key="explain_uploaded"):
                    with st.spinner("Generating explanation..."):
                        explanation = explain_uploaded_query(query_data, prompt_text, explanation_level)
                        display_query_explanation(explanation)
                        
            except Exception as e:
                st.error(f"Error loading query file: {e}")
    
    else:
        # Generate new query and explain
        prompt_text = st.text_area(
            "Natural Language Prompt",
            placeholder="Enter your query description...",
            help="Describe what you want to find in natural language",
            key="explanation_new_prompt"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            # Get all available models (local + external)
            from gui.utils.backend_interface import get_all_available_models
            all_models = get_all_available_models()
            
            model = st.selectbox(
                "Model",
                all_models,
                index=0,
                help="🖥️=Local models, ☁️=External models",
                key="explanation_model"
            )
        
        with col2:
            method = st.selectbox(
                "Method",
                ["constrained", "zero_shot"],
                index=0,
                key="explanation_method"
            )
        
        if st.button("🚀 Generate & Explain", type="primary", key="generate_and_explain"):
            if prompt_text:
                # Show which model is being used
                st.info(f"🤖 Using model: **{model}** with method: **{method}**")
                
                with st.spinner(f"Generating query with {model} and creating explanation..."):
                    result = generate_and_explain_query(prompt_text, model, method, explanation_level)
                    
                    if result["success"]:
                        # Show generation details
                        st.success(f"✅ Query generated successfully using {model}")
                        
                        # Show the generated query first
                        st.subheader("Generated Query")
                        st.json(result["query"])
                        
                        # Show generation output if available
                        if "generation_output" in result and result["generation_output"]:
                            with st.expander("📋 Generation Log"):
                                st.text(result["generation_output"])
                        
                        # Then show the explanation
                        display_query_explanation(result["explanation"])
                    else:
                        st.error(f"Generation failed with {model}: {result['error']}")
            else:
                st.warning("Please enter a prompt")


def explain_uploaded_query(query_data: dict, prompt: str, level: str) -> dict:
    """Explain an uploaded query"""
    try:
        from src.explainability.query_explainer import QueryExplainer, ExplanationLevel
        
        explainer = QueryExplainer()
        explanation_level = ExplanationLevel(level.lower())
        
        explanation = explainer.explain_query(prompt, query_data, explanation_level)
        return explanation.to_dict()
    
    except Exception as e:
        return {"error": str(e)}


def generate_and_explain_query(prompt: str, model: str, method: str, level: str) -> dict:
    """Generate a new query and explain it"""
    try:
        import uuid
        from gui.utils.backend_interface import run_query_generation
        
        # Generate unique task ID
        task_id = f"explain_{uuid.uuid4().hex[:8]}"
        
        # Use the proper backend interface that handles both local and external models
        success, output, query_data = run_query_generation(
            prompt=prompt,
            method=method,
            task_id=task_id,
            model=model  # Pass model with emoji prefix - backend will handle it
        )
        
        if success and query_data:
            # Generate explanation
            explanation = explain_uploaded_query(query_data, prompt, level)
            
            return {
                "success": True,
                "query": query_data,
                "explanation": explanation,
                "generation_output": output
            }
        else:
            return {"success": False, "error": output or "Query generation failed"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def display_query_explanation(explanation: dict) -> None:
    """Display comprehensive query explanation"""
    
    if "error" in explanation:
        st.error(f"Explanation error: {explanation['error']}")
        return
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        confidence = explanation.get("confidence_score", 0)
        st.metric("Confidence", f"{confidence:.2f}", help="Overall confidence in the explanation")
    
    with col2:
        complexity = explanation.get("complexity_score", 0)
        st.metric("Complexity", f"{complexity:.2f}", help="Query complexity score")
    
    with col3:
        decision_count = len(explanation.get("decisions", []))
        st.metric("Decisions", decision_count, help="Number of decisions analyzed")
    
    with col4:
        risk_level = explanation.get("risk_assessment", {}).get("overall_risk_level", "unknown")
        risk_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk_level, "⚪")
        st.metric("Risk Level", f"{risk_color} {risk_level.title()}")
    
    # Query summary
    st.markdown("### 📋 Query Summary")
    st.info(explanation.get("query_summary", "No summary available"))
    
    # Decision explanations
    st.markdown("### 🧠 Decision Analysis")
    
    decisions = explanation.get("decisions", [])
    if decisions:
        for i, decision in enumerate(decisions, 1):
            with st.expander(f"Decision {i}: {decision.get('decision_type', 'Unknown').replace('_', ' ').title()}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Rationale:** {decision.get('rationale', 'No rationale provided')}")
                    
                    if decision.get("prompt_evidence"):
                        st.markdown(f"**Evidence from prompt:** {', '.join(decision['prompt_evidence'])}")
                    
                    if decision.get("alternatives"):
                        alternatives_text = ", ".join([alt.get("field", alt.get("operator", str(alt))) for alt in decision["alternatives"][:3]])
                        st.markdown(f"**Alternatives considered:** {alternatives_text}")
                
                with col2:
                    confidence = decision.get("confidence", 0)
                    st.metric("Confidence", f"{confidence:.2f}")
                    
                    if decision.get("field_name"):
                        st.markdown(f"**Field:** `{decision['field_name']}`")
    
    # Attention weights visualization
    st.markdown("### 🎯 Attention Analysis")
    attention_weights = explanation.get("attention_weights", {})
    
    if attention_weights:
        import plotly.express as px
        # Create attention visualization
        tokens = list(attention_weights.keys())
        weights = list(attention_weights.values())
        
        fig = px.bar(
            x=tokens,
            y=weights,
            title="Token Attention Weights",
            labels={"x": "Tokens", "y": "Attention Weight"}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Risk assessment
    st.markdown("### ⚠️ Risk Assessment")
    risk_assessment = explanation.get("risk_assessment", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        perf_risks = risk_assessment.get("performance_risks", [])
        if perf_risks:
            st.markdown("**Performance Risks:**")
            for risk in perf_risks:
                st.warning(f"• {risk}")
        else:
            st.success("✅ No performance risks identified")
    
    with col2:
        security_risks = risk_assessment.get("security_risks", [])
        if security_risks:
            st.markdown("**Security Risks:**")
            for risk in security_risks:
                st.error(f"• {risk}")
        else:
            st.success("✅ No security risks identified")
    
    with col3:
        accuracy_risks = risk_assessment.get("accuracy_risks", [])
        if accuracy_risks:
            st.markdown("**Accuracy Risks:**")
            for risk in accuracy_risks:
                st.warning(f"• {risk}")
        else:
            st.success("✅ No accuracy risks identified")
    
    # Optimization suggestions
    st.markdown("### 💡 Optimization Suggestions")
    optimizations = explanation.get("optimization_suggestions", [])
    
    if optimizations:
        for i, suggestion in enumerate(optimizations, 1):
            st.info(f"{i}. {suggestion}")
    else:
        st.success("No optimizations suggested - query looks good!")
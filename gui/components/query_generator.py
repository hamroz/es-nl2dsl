"""Query Generator Component for Streamlit GUI"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from gui.utils.backend_interface import run_query_generation, validate_query, get_available_models

def render_query_generator():
    """Render the query generator interface"""
    st.header("🤖 Query Generator")
    st.write("Generate Elasticsearch DSL queries from natural language descriptions")
    
    # Create two columns for input and output
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Input")
        
        # Query input
        prompt = st.text_area(
            "Natural Language Query:",
            value="Find events labeled malicious on 2017-07-04",
            height=100,
            help="Enter your query in natural language. Be specific about time ranges and conditions."
        )
        
        # Method selection
        method = st.selectbox(
            "Generation Method:",
            ["constrained", "rules", "zeroshot"],
            index=0,
            help="Choose the query generation method"
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
                        
                        # Download button
                        st.download_button(
                            "📥 Download Query",
                            data=formatted_query,
                            file_name=f"query_{int(time.time())}.json",
                            mime="application/json"
                        )
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
                st.rerun()
    
    # Apply example if selected
    if "example_prompt" in st.session_state:
        st.session_state.pop("example_prompt")  # Remove after use
    
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
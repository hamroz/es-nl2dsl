"""
External LLM Management Panel for System Administration
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.external_llm_manager import ExternalLLM, get_external_llm_manager

def render_external_llm_panel():
    """Render the External LLM management interface"""
    st.title("🤖 External LLM Management")
    st.markdown("Configure and manage external AI models (OpenAI, Anthropic, Cohere, etc.)")
    
    manager = get_external_llm_manager()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["➕ Add New LLM", "📋 Manage LLMs", "🧪 Test LLMs"])
    
    with tab1:
        render_add_llm_tab(manager)
    
    with tab2:
        render_manage_llms_tab(manager)
    
    with tab3:
        render_test_llms_tab(manager)

def render_add_llm_tab(manager):
    """Render the Add New LLM tab"""
    st.markdown("### Add New External LLM")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # LLM Name
        llm_name = st.text_input(
            "LLM Configuration Name",
            placeholder="e.g., GPT-4 Production",
            help="A unique name to identify this LLM configuration"
        )
        
        # Provider selection
        provider = st.selectbox(
            "Provider",
            ["openai", "google", "deepseek"],
            help="Select the LLM provider"
        )
        
        # Model selection based on provider
        available_models = manager.get_available_models()
        model_id = st.selectbox(
            "Model",
            available_models.get(provider, []),
            help="Select the specific model to use"
        )
    
    with col2:
        # API Key
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="Enter your API key",
            help="Your API key for the selected provider"
        )
        
        # Advanced settings
        with st.expander("Advanced Settings"):
            max_tokens = st.number_input(
                "Max Tokens",
                min_value=100,
                max_value=8000,
                value=2000,
                help="Maximum tokens in the response"
            )
            
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=0.7,
                step=0.1,
                help="Controls randomness (0=deterministic, 2=very random)"
            )
            
            custom_endpoint = st.text_input(
                "Custom Endpoint (Optional)",
                placeholder="Leave empty for default",
                help="Custom API endpoint if using a proxy or custom deployment"
            )
    
    # Add button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🚀 Add LLM", type="primary", use_container_width=True):
            if not llm_name:
                st.error("Please provide a configuration name")
            elif not api_key:
                st.error("Please provide an API key")
            elif llm_name in [llm.name for llm in manager.list_llms()]:
                st.error(f"Configuration '{llm_name}' already exists")
            else:
                # Create LLM configuration
                llm = ExternalLLM(
                    name=llm_name,
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    endpoint=custom_endpoint if custom_endpoint else None,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                with st.spinner(f"Validating {provider} API key..."):
                    if manager.add_llm(llm):
                        st.success(f"✅ Successfully added '{llm_name}'!")
                        st.balloons()
                        # Clear form
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to validate API key. Please check your credentials.")
    
    # Show provider-specific instructions
    st.markdown("---")
    st.markdown("### 📚 Provider Setup Instructions")
    
    setup_tab1, setup_tab2, setup_tab3 = st.tabs(["OpenAI (GPT-5)", "Google Gemini", "DeepSeek"])
    
    with setup_tab1:
        st.markdown("""
        **OpenAI (GPT-5 Series)**
        1. Go to [platform.openai.com](https://platform.openai.com)
        2. Sign in or create an account
        3. Navigate to API Keys section
        4. Click "Create new secret key"
        5. Copy the key (starts with `sk-`)
        6. Choose model:
           - `gpt-5`: Flagship reasoning model ($1.25/1M input, $10/1M output)
           - `gpt-5-mini`: Lightweight version ($0.25/1M input, $2/1M output)
           - `gpt-5-nano`: Fastest, lowest latency ($0.05/1M input, $0.40/1M output)
        
        **Note**: GPT-5 models support reasoning_effort and verbosity parameters for enhanced control.
        """)
    
    with setup_tab2:
        st.markdown("""
        **Google Gemini (2.5 Series)**
        1. Go to [aistudio.google.com](https://aistudio.google.com)
        2. Sign in with your Google account
        3. Navigate to "Get API key" in the left menu
        4. Click "Create API key"
        5. Copy the generated API key
        6. Choose model:
           - `gemini-2.5-pro`: Most powerful with adaptive thinking
           - `gemini-2.5-flash`: Optimized for speed and high throughput
        
        **Note**: Both models have thinking enabled by default and support multimodal inputs.
        """)
    
    with setup_tab3:
        st.markdown("""
        **DeepSeek (Reasoner)**
        1. Go to [platform.deepseek.com](https://platform.deepseek.com)
        2. Sign in or create an account
        3. Navigate to API Keys
        4. Create and copy your API key
        5. Model:
           - `deepseek-reasoner`: R1 reasoning model with Chain of Thought
        
        **Note**: DeepSeek R1 achieves performance comparable to OpenAI o1 on reasoning tasks.
        """)

def render_manage_llms_tab(manager):
    """Render the Manage LLMs tab"""
    st.markdown("### Configured LLMs")
    
    llms = manager.list_llms()
    
    if not llms:
        st.info("No external LLMs configured yet. Add one in the 'Add New LLM' tab.")
        return
    
    # Display LLMs in a table-like format
    for llm in llms:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 1, 1])
            
            with col1:
                status_icon = "🟢" if llm.enabled else "🔴"
                st.markdown(f"**{status_icon} {llm.name}**")
                st.caption(f"Added: {llm.added_date[:10]}")
            
            with col2:
                st.markdown(f"**Provider:** {llm.provider}")
                st.caption(f"Model: {llm.model_id}")
            
            with col3:
                st.markdown(f"**Settings:**")
                st.caption(f"Tokens: {llm.max_tokens}, Temp: {llm.temperature}")
            
            with col4:
                # Enable/Disable toggle
                new_status = st.checkbox(
                    "Enabled",
                    value=llm.enabled,
                    key=f"enable_{llm.name}"
                )
                if new_status != llm.enabled:
                    manager.update_llm_status(llm.name, new_status)
                    st.rerun()
            
            with col5:
                # Delete button
                if st.button("🗑️", key=f"delete_{llm.name}", help="Delete this LLM"):
                    if st.session_state.get(f"confirm_delete_{llm.name}", False):
                        manager.remove_llm(llm.name)
                        st.success(f"Deleted '{llm.name}'")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{llm.name}"] = True
                        st.warning("Click again to confirm deletion")
            
            st.markdown("---")
    
    # Summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total LLMs", len(llms))
    with col2:
        enabled_count = sum(1 for llm in llms if llm.enabled)
        st.metric("Enabled", enabled_count)
    with col3:
        providers = set(llm.provider for llm in llms)
        st.metric("Providers", len(providers))

def render_test_llms_tab(manager):
    """Render the Test LLMs tab"""
    st.markdown("### Test External LLMs")
    st.markdown("Send a test query to verify your LLM configurations are working correctly.")
    
    # Get enabled LLMs
    llms = manager.list_llms(enabled_only=True)
    
    if not llms:
        st.warning("No enabled LLMs found. Please add and enable an LLM first.")
        return
    
    # LLM selection
    llm_names = [llm.name for llm in llms]
    selected_llm = st.selectbox(
        "Select LLM to Test",
        llm_names,
        help="Choose which LLM configuration to test"
    )
    
    # Test prompt
    test_prompt = st.text_area(
        "Test Prompt",
        value="Generate an Elasticsearch DSL query to find all documents with src_ip='192.168.1.1' from the last 24 hours. Return only the JSON query.",
        height=100,
        help="Enter a test prompt to send to the LLM"
    )
    
    # Test button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🧪 Run Test", type="primary", use_container_width=True):
            with st.spinner(f"Testing {selected_llm}..."):
                start_time = datetime.now()
                
                # Call the LLM
                response = manager.call_llm(
                    selected_llm,
                    test_prompt,
                    system_prompt="You are an Elasticsearch DSL query generator. Return only valid JSON."
                )
                
                end_time = datetime.now()
                response_time = (end_time - start_time).total_seconds()
                
                if response:
                    st.success(f"✅ Test successful! Response time: {response_time:.2f}s")
                    
                    # Display response
                    st.markdown("#### Response:")
                    
                    # Try to parse as JSON for better display
                    try:
                        import json
                        # Extract JSON from response if wrapped in markdown
                        if "```json" in response:
                            response = response.split("```json")[1].split("```")[0]
                        elif "```" in response:
                            response = response.split("```")[1].split("```")[0]
                        
                        parsed = json.loads(response)
                        st.json(parsed)
                    except:
                        # Display as code if not valid JSON
                        st.code(response, language="json")
                    
                    # Show metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Response Time", f"{response_time:.2f}s")
                    with col2:
                        st.metric("Response Length", f"{len(response)} chars")
                    with col3:
                        llm_config = manager.get_llm(selected_llm)
                        st.metric("Model", llm_config.model_id)
                else:
                    st.error(f"❌ Test failed! Check your API key and configuration.")
    
    with col2:
        # Quick validation button
        if st.button("🔍 Validate All", use_container_width=True):
            st.markdown("#### Validation Results:")
            for llm in llms:
                with st.spinner(f"Validating {llm.name}..."):
                    if manager.validate_llm(llm):
                        st.success(f"✅ {llm.name}: Valid")
                    else:
                        st.error(f"❌ {llm.name}: Invalid")
    
    # Show example queries
    with st.expander("📖 Example Test Prompts"):
        st.markdown("""
        **Simple Query:**
        ```
        Find all malicious events from the last hour
        ```
        
        **Complex Query:**
        ```
        Generate an Elasticsearch query to find port scans on port 443 
        from IP 192.168.1.1 with more than 100 connections in the last 24 hours
        ```
        
        **Aggregation Query:**
        ```
        Create a query to get the top 10 source IPs by traffic volume
        ```
        """)
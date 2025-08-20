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
    st.markdown("Configure and manage external AI models (OpenAI, Google, DeepSeek, Qwen).")

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
            placeholder="e.g., GPT-5 Production",
            help="A unique name to identify this LLM configuration",
        )

        # Provider selection (keep in sync with manager.get_available_models())
        provider = st.selectbox(
            "Provider",
            ["openai", "google", "deepseek", "qwen"],
            help="Select the LLM provider",
        )

        # Model selection based on provider
        available_models = manager.get_available_models()
        provider_models = available_models.get(provider, [])

        # If we ever need a manual model id, we could allow a custom input.
        # For now, stick with selectbox since we ship curated options.
        model_id = st.selectbox(
            "Model",
            provider_models,
            help="Select the specific model to use",
        )

    with col2:
        # API Key
        api_key = st.text_input(
            "API Key",
            type="password",
            placeholder="Enter your API key",
            help="Your API key for the selected provider",
        )

        # Advanced settings
        with st.expander("Advanced Settings"):
            max_tokens = st.number_input(
                "Max Tokens",
                min_value=100,
                max_value=8000,
                value=2000,
                help="Maximum tokens in the response",
            )

            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=2.0,
                value=0.7,
                step=0.1,
                help="Controls randomness (0=deterministic, 2=very random)",
            )

            # Set default endpoints based on provider
            default_endpoints = {
                "deepseek": "https://api.deepseek.com/v1",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1"
            }
            placeholder = default_endpoints.get(provider, "Leave empty for default")
            
            custom_endpoint = st.text_input(
                "Custom Endpoint (Optional)",
                placeholder=placeholder,
                help="Custom API base URL. Some providers require specific endpoints.",
            )

    # Add button
    col1b, col2b, col3b = st.columns([1, 1, 2])
    with col1b:
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
                    temperature=temperature,
                )

                with st.spinner(f"Validating {provider} credentials..."):
                    ok = manager.add_llm(llm)
                    if ok:
                        st.success(f"✅ Successfully added '{llm_name}'!")
                        st.balloons()
                        st.rerun()
                    else:
                        err = manager.last_error or "Failed to validate API key."
                        st.error(f"❌ {err}")

    # Show provider-specific instructions
    st.markdown("---")
    st.markdown("### 📚 Provider Setup Instructions")

    setup_tab1, setup_tab2, setup_tab3, setup_tab4 = st.tabs(
        ["OpenAI", "Google Gemini", "DeepSeek", "Qwen AI"]
    )

    with setup_tab1:
        st.markdown(
            """
**OpenAI**
1. Create an API key at [platform.openai.com](https://platform.openai.com/api-keys)
2. Available models:
   - **gpt-4o**: Latest and most capable model
   - **gpt-4o-mini**: Faster, more affordable variant
   - **gpt-4-turbo**: Previous generation turbo model
   - **o1**: Advanced reasoning model
   - **o1-mini**: Smaller reasoning model
   - **o3-mini**: Latest mini model
3. Paste your API key and click **Add LLM**

**Notes**
- The app automatically handles both Chat Completions and Responses API
- For proxies/self-hosted gateways, set a **Custom Endpoint**
"""
        )

    with setup_tab2:
        st.markdown(
            """
**Google Gemini**
1. Create an API key at [Google AI Studio](https://aistudio.google.com/apikey)
2. Available models:
   - **gemini-2.5-pro**: Most capable Gemini model
   - **gemini-2.5-flash**: Fast and efficient
   - **gemini-2.0-flash-thinking-exp**: Experimental thinking model
   - **gemini-1.5-pro**: Previous generation pro model
   - **gemini-1.5-flash**: Previous generation flash model
3. Paste your API key and click **Add LLM**
"""
        )

    with setup_tab3:
        st.markdown(
            """
**DeepSeek (OpenAI-compatible)**
1. Create an API key at [DeepSeek Platform](https://platform.deepseek.com)
2. Available models:
   - **deepseek-reasoner**: R1-style reasoning model
   - **deepseek-chat**: Standard chat model
   - **deepseek-coder**: Specialized for code generation
3. Endpoint: `https://api.deepseek.com/v1` (auto-filled)
4. Paste your API key and click **Add LLM**
"""
        )

    with setup_tab4:
        st.markdown(
            """
**Qwen AI (Alibaba Cloud)**
1. Create an API key at [Alibaba Cloud DashScope](https://dashscope.console.aliyun.com)
2. Available models:
   - **qwen-max**: Most capable Qwen model
   - **qwen-plus**: Balanced performance and cost
   - **qwen-turbo**: Fast and efficient
   - **qwen-long**: Extended context window
   - **qwen2.5-coder-32b-instruct**: Specialized for coding
3. Endpoint: `https://dashscope.aliyuncs.com/compatible-mode/v1` (auto-filled)
4. Paste your API key and click **Add LLM**

**Note**: Qwen uses OpenAI-compatible API format
"""
        )


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
            col1, col2, col3, col4, col5 = st.columns([3, 2, 3, 1, 1])

            with col1:
                status_icon = "🟢" if llm.enabled else "🔴"
                st.markdown(f"**{status_icon} {llm.name}**")
                st.caption(f"Added: {llm.added_date[:10]}")

            with col2:
                st.markdown(f"**Provider:** {llm.provider}")
                st.caption(f"Model: `{llm.model_id}`")

            with col3:
                st.markdown("**Settings:**")
                st.caption(f"Tokens: {llm.max_tokens}, Temp: {llm.temperature}")
                if llm.endpoint:
                    st.caption(f"Endpoint: `{llm.endpoint}`")

            with col4:
                # Enable/Disable toggle
                new_status = st.checkbox(
                    "Enabled", value=llm.enabled, key=f"enable_{llm.name}"
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
    st.markdown(
        "Send a test query to verify your LLM configurations are working correctly."
    )

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
        help="Choose which LLM configuration to test",
    )

    # Test prompt
    test_prompt = st.text_area(
        "Test Prompt",
        value="Generate an Elasticsearch DSL query to find all documents with src_ip='192.168.1.1' from the last 24 hours. Return only the JSON query.",
        height=120,
        help="Enter a test prompt to send to the LLM",
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
                    system_prompt="You are an Elasticsearch DSL query generator. Return only valid JSON.",
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
                        resp = response
                        if "```json" in resp:
                            resp = resp.split("```json")[1].split("```")[0]
                        elif "```" in resp:
                            resp = resp.split("```")[1].split("```")[0]

                        parsed = json.loads(resp)
                        st.json(parsed)
                    except Exception:
                        # Display as code if not valid JSON
                        st.code(response, language="json")

                    # Show metrics
                    colm1, colm2, colm3 = st.columns(3)
                    with colm1:
                        st.metric("Response Time", f"{response_time:.2f}s")
                    with colm2:
                        st.metric("Response Length", f"{len(response)} chars")
                    with colm3:
                        llm_config = manager.get_llm(selected_llm)
                        st.metric("Model", llm_config.model_id)
                else:
                    err = manager.last_error or "Check your API key, model, and endpoint."
                    st.error(f"❌ Test failed: {err}")

    with col2:
        # Quick validation button
        if st.button("🔍 Validate All", use_container_width=True):
            st.markdown("#### Validation Results:")
            for llm in llms:
                with st.spinner(f"Validating {llm.name}..."):
                    ok = manager.validate_llm(llm)
                    if ok:
                        st.success(f"✅ {llm.name}: Valid")
                    else:
                        err = manager.last_error or "Invalid configuration"
                        st.error(f"❌ {llm.name}: {err}")

    # Show example queries
    with st.expander("📖 Example Test Prompts"):
        st.markdown(
            """
            **Simple Query:**
            Find all malicious events from the last hour
            **Complex Query:**
            Generate an Elasticsearch query to find port scans on port 443
            from IP 192.168.1.1 with more than 100 connections in the last 24 hours
            **Aggregation Query:**
            Create a query to get the top 10 source IPs by traffic volume
            """
        )
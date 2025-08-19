"""ES-NL2DSL Streamlit GUI Application"""
import streamlit as st
import sys
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import components
from gui.utils.backend_interface import check_system_status
from gui.components.query_generator import render_query_generator
from gui.components.evaluation_dashboard import render_evaluation_dashboard
from gui.components.security_panel import render_security_panel
from gui.components.privacy_analysis import render_privacy_analysis
from gui.components.admin_panel import render_admin_panel

# Page configuration
st.set_page_config(
    page_title="ES-NL2DSL: Natural Language to Elasticsearch DSL",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-good { background-color: #28a745; }
    .status-bad { background-color: #dc3545; }
    .status-warning { background-color: #ffc107; }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    /* Improve sidebar navigation */
    .stSidebar .stButton > button {
        width: 100%;
        text-align: left;
        border-radius: 8px;
        margin-bottom: 4px;
        transition: all 0.2s ease;
    }
    .stSidebar .stButton > button:hover {
        background-color: #f0f2f6;
        border-color: #1f77b4;
    }
    /* Active navigation button styling */
    .stSidebar .stButton > button[kind="primary"] {
        background-color: #1f77b4 !important;
        color: white !important;
        border-color: #1f77b4 !important;
    }
</style>
""", unsafe_allow_html=True)

def render_header():
    """Render the main header"""
    st.markdown(
        '<h1 class="main-header">🔍 ES-NL2DSL: Natural Language to Elasticsearch DSL</h1>', 
        unsafe_allow_html=True
    )
    st.markdown("---")

def render_status_bar():
    """Render system status bar"""
    # Check if status is in session state and not too old
    if "system_status" not in st.session_state or \
       time.time() - st.session_state.get("last_status_check", 0) > 30:
        
        with st.spinner("Checking system status..."):
            st.session_state.system_status = check_system_status()
            st.session_state.last_status_check = time.time()
    
    status = st.session_state.system_status
    
    # Create status indicators
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
    
    with col1:
        es_status = "🟢" if status["elasticsearch"] else "🔴"
        st.write(f"{es_status} **Elasticsearch:** {'Running' if status['elasticsearch'] else 'Offline'}")
    
    with col2:
        ollama_status = "🟢" if status["ollama"] else "🔴"
        st.write(f"{ollama_status} **Ollama:** {'Ready' if status['ollama'] else 'Offline'}")
    
    with col3:
        indices_status = "🟢" if status["indices"] > 0 else "🔴"
        st.write(f"{indices_status} **Indices:** {status['indices']} available")
    
    with col4:
        models_count = len(status["models"])
        models_status = "🟢" if models_count > 0 else "🔴"
        st.write(f"{models_status} **Models:** {models_count} loaded")
    
    with col5:
        last_check = int(time.time() - status["last_check"])
        st.write(f"🕐 **Last Check:** {last_check}s ago")
    
    # Show detailed model info if available
    if status["models"]:
        st.caption(f"Available models: {', '.join(status['models'])}")
    
    st.markdown("---")

def main():
    """Main application"""
    render_header()
    render_status_bar()
    
    # Initialize current page in session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "🤖 Query Generator"
    
    # Sidebar navigation with persistent buttons
    st.sidebar.title("🧭 Navigation")
    
    # Show current page indicator
    st.sidebar.markdown(f"**Current:** {st.session_state.current_page}")
    st.sidebar.markdown("---")
    
    # Navigation buttons
    nav_options = [
        "🤖 Query Generator",
        "📊 Evaluation Dashboard", 
        "🛡️ Security Testing",
        "🔒 Privacy Analysis",
        "⚙️ System Administration"
    ]
    
    # Create navigation buttons
    for option in nav_options:
        is_current = st.session_state.current_page == option
        button_type = "primary" if is_current else "secondary"
        
        # Don't disable buttons - just style them differently
        if st.sidebar.button(
            option, 
            key=f"nav_{option}",
            use_container_width=True,
            type=button_type
        ):
            # Only change page if it's different from current
            if not is_current:
                st.session_state.current_page = option
                st.rerun()  # Rerun only for navigation changes
    
    st.sidebar.markdown("---")
    
    # Add refresh button in sidebar
    if st.sidebar.button("🔄 Refresh Status", use_container_width=True):
        st.session_state.pop("system_status", None)
        # Don't call st.rerun() here to avoid navigation reset
        st.toast("Status refreshed!", icon="✅")
    
    # Render selected page based on session state
    page = st.session_state.current_page
    if page == "🤖 Query Generator":
        render_query_generator()
    elif page == "📊 Evaluation Dashboard":
        render_evaluation_dashboard()
    elif page == "🛡️ Security Testing":
        render_security_panel()
    elif page == "🔒 Privacy Analysis":
        render_privacy_analysis()
    elif page == "⚙️ System Administration":
        render_admin_panel()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "**ES-NL2DSL** - Secure Natural Language to Elasticsearch DSL Translation | "
        "[Documentation](README.md) | [GitHub](https://github.com/hamroz/es-nl2dsl)"
    )

if __name__ == "__main__":
    main()
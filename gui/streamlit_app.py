"""
ES-NL2DSL Streamlit Application: Main web interface entry point

This module serves as the primary entry point for the ES-NL2DSL web-based graphical
user interface, providing a comprehensive Streamlit application that integrates all
system components into a unified platform for natural language to Elasticsearch DSL
query generation, evaluation, and system management.

Key capabilities:
- Multi-component navigation with organized sidebar interface
- Real-time system status monitoring with health indicators
- Interactive query generation with advanced configuration options
- Comprehensive evaluation dashboard with statistical analysis
- Security testing panel with red team capabilities
- Privacy analysis tools with differential privacy support
- System administration interface with full management capabilities
- Data exploration tools with interactive visualization
- Multi-modal data adaptation with AI-powered assistance
- Responsive web design with professional styling and UX

The application serves as the central hub for all ES-NL2DSL functionality,
providing both end-users and administrators with intuitive access to the
complete system capabilities through a modern web interface.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import streamlit as st
import sys
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import logging utilities
from gui.utils.logging_utils import get_gui_logger

# Initialize main app logger
app_logger = get_gui_logger("main_app")

# Import components
from gui.utils.backend_interface import check_system_status
from gui.components.query_generator import render_query_generator
from gui.components.evaluation_dashboard import render_evaluation_dashboard
from gui.components.security_panel import render_security_panel
from gui.components.privacy_analysis import render_privacy_analysis
from gui.components.admin_panel import render_admin_panel
from gui.components.data_explorer import render_data_explorer


# Import simplified data adaptation dashboard
from gui.components.multimodal_dashboard import render_multimodal_dashboard

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
    app_logger.log_page_load("Application header rendered")
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
        
        app_logger.log_system_operation("System status check initiated")
        with st.spinner("Checking system status..."):
            st.session_state.system_status = check_system_status()
            st.session_state.last_status_check = time.time()
            app_logger.log_success("System status updated")
    
    status = st.session_state.system_status
    
    # Log status metrics for monitoring
    app_logger.log_status("System status", "Status bar rendered", 
                         elasticsearch=status["elasticsearch"],
                         ollama=status["ollama"],
                         indices=status["indices"],
                         models=len(status["models"]))
    
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
    app_logger.log_system_operation("Main application started")
    
    render_header()
    render_status_bar()
    
    # Initialize current page in session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "🤖 Query Generator"
        app_logger.log_state_change("current_page", None, st.session_state.current_page)
    
    # Sidebar navigation with persistent buttons
    st.sidebar.title("🧭 Navigation")
    app_logger.log_page_load("Sidebar navigation rendered")
    
    # Show current page indicator
    st.sidebar.markdown(f"**Current:** {st.session_state.current_page}")
    st.sidebar.markdown("---")
    
    # Navigation buttons
    nav_options = [
        "🤖 Query Generator",
        "🔍 Data Explorer",
        "📊 Evaluation Dashboard",
        "🛡️ Security Testing",
        "🔒 Privacy Analysis",
        # Data Adaptation
        "🎭 Multi-Modal Data Adaptation",
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
                app_logger.log_navigation(st.session_state.current_page, option)
                app_logger.log_user_action("Navigation button clicked", destination=option)
                st.session_state.current_page = option
                st.rerun()  # Rerun only for navigation changes
    
    st.sidebar.markdown("---")
    
    # Add refresh button in sidebar
    if st.sidebar.button("🔄 Refresh Status", use_container_width=True):
        app_logger.log_user_action("Status refresh button clicked")
        st.session_state.pop("system_status", None)
        # Don't call st.rerun() here to avoid navigation reset and maintain user's current tab
        st.toast("Status refreshed!", icon="✅")
        app_logger.log_success("System status manually refreshed")
    
    # Render selected page based on session state
    page = st.session_state.current_page
    app_logger.log_page_load(page)
    if page == "🤖 Query Generator":
        render_query_generator()
    elif page == "🔍 Data Explorer":
        render_data_explorer()
    elif page == "📊 Evaluation Dashboard":
        render_evaluation_dashboard()
    elif page == "🛡️ Security Testing":
        render_security_panel()
    elif page == "🔒 Privacy Analysis":
        render_privacy_analysis()
    # Data Adaptation
    elif page == "🎭 Multi-Modal Data Adaptation":
        render_multimodal_dashboard()
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
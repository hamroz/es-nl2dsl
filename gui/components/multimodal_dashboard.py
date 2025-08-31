#!/usr/bin/env python3
"""
Multi-Modal Data Adaptation Dashboard: AI-powered data integration interface

This module provides advanced multi-modal data adaptation capabilities for the ES-NL2DSL
system through an intelligent Streamlit interface. It enables automatic adaptation to new
log formats and data sources using AI-powered schema analysis, field mapping, and ingestion
workflows to extend system capabilities beyond predefined datasets.

Key capabilities:
- AI-powered data source analysis with automatic schema discovery
- Multi-format data ingestion (CSV, JSON, Syslog, custom formats)
- Intelligent field mapping with semantic analysis and suggestions
- Real-time data profiling with statistical analysis and validation
- Custom index creation with optimized mappings for new data sources
- Interactive data preview with quality assessment and anomaly detection
- Automated ingestion pipelines with progress monitoring and error handling
- Historical adaptation tracking with configuration management
- Integration testing with existing query generation pipelines
- Documentation generation for new data sources and field mappings

The dashboard serves as the primary tool for system administrators and data engineers
to rapidly integrate new data sources into the ES-NL2DSL system, enabling seamless
expansion of cybersecurity analysis capabilities across diverse log formats.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import streamlit as st
import json
import sys
from pathlib import Path
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def render_multimodal_dashboard():
    """Render the multi-modal queries dashboard focused on data adaptation"""
    
    st.header("🎭 Multi-Modal Data Adaptation")
    st.markdown("Adapt the system to new log data from any source with AI assistance")
    
    # Main workflow tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📁 Data Analysis", 
        "🔄 Data Ingestion", 
        "📚 History",
        "🔍 Diagnostics"
    ])
    
    with tab1:
        render_data_analysis_tab()
    
    with tab2:
        render_data_ingestion_tab()
    
    with tab3:
        render_history_tab()
    
    with tab4:
        render_diagnostics_tab()


def render_data_analysis_tab():
    """Render data analysis and schema detection tab"""
    st.subheader("📊 Analyze New Log Data")
    st.markdown("Upload and analyze new log files to understand their structure")
    
    # Show current session status if available
    if hasattr(st.session_state, 'current_adaptation_id'):
        from src.data_adaptation.adaptation_history import get_adaptation_history
        history = get_adaptation_history()
        record = history.get_record(st.session_state.current_adaptation_id)
        if record:
            st.info(f"📋 Current session: {record.get_status_emoji()} {record.get_display_name()} ({record.status})")
    
    # File upload options
    upload_method = st.radio(
        "Choose upload method:",
        ["Upload File", "Use Local File Path"],
        help="Choose how to provide your data file"
    )
    
    uploaded_file = None
    local_file_path = None
    
    if upload_method == "Upload File":
        uploaded_file = st.file_uploader(
            "Upload Log Data File",
            type=['csv', 'json', 'jsonl', 'ndjson'],
            help="Upload CSV, JSON, or JSONL log files"
        )
    else:
        local_file_path = st.text_input(
            "Enter file path:",
            placeholder="e.g., data_raw/sample_cybersecurity_logs.csv",
            help="Enter the path to your local file"
        )
        
        if local_file_path and not Path(local_file_path).exists():
            st.error(f"❌ File not found: {local_file_path}")
            local_file_path = None
    
    if uploaded_file or local_file_path:
        # Handle file path based on upload method
        if uploaded_file:
            # Save uploaded file temporarily with better error handling
            try:
                # Create a unique temp file
                import uuid
                temp_dir = Path("/tmp")
                temp_dir.mkdir(exist_ok=True)
                
                file_extension = uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else 'csv'
                temp_filename = f"uploaded_data_{uuid.uuid4().hex[:8]}.{file_extension}"
                temp_path = temp_dir / temp_filename
                
                # Write file content
                with open(temp_path, 'wb') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                
                temp_path = str(temp_path)
                file_name = uploaded_file.name
                
            except Exception as upload_error:
                st.error(f"❌ File upload failed: {upload_error}")
                return
        else:
            # Use local file path directly
            temp_path = local_file_path
            file_name = Path(local_file_path).name
        
        col1, col2 = st.columns([2, 1])
        
        with col2:
            # AI Model selection
            from gui.utils.backend_interface import get_all_available_models
            all_models = get_all_available_models()
            
            ai_model = st.selectbox(
                "AI Assistant Model",
                all_models,
                index=0,
                help="Choose AI model for analysis assistance"
            )
            
            analyze_with_ai = st.checkbox("Use AI Analysis", value=True)
        
        with col1:
            if st.button("🔍 Analyze Data Structure", type="primary"):
                with st.spinner("Analyzing data structure..."):
                    # Analyze schema
                    from src.data_adaptation.schema_analyzer import SchemaAnalyzer
                    analyzer = SchemaAnalyzer()
                    schema = analyzer.analyze_data_file(temp_path)
                    
                    if "error" not in schema:
                        st.session_state.analyzed_schema = schema
                        st.session_state.uploaded_file_name = file_name
                        
                        # Create history record
                        from src.data_adaptation.adaptation_history import get_adaptation_history
                        history = get_adaptation_history()
                        record_id = history.create_record(file_name, schema, ai_model)
                        st.session_state.current_adaptation_id = record_id
                        
                        # Display schema analysis
                        display_schema_analysis(schema)
                        
                        # AI Analysis if enabled
                        if analyze_with_ai:
                            # Pass the full model name with emoji prefix so AI assistant can determine type
                            model_name = ai_model
                            
                            with st.spinner("Getting AI insights..."):
                                from src.data_adaptation.ai_assistant import AIAssistant
                                ai_assistant = AIAssistant()
                                ai_analysis = ai_assistant.analyze_data_with_ai(schema, model_name)
                                
                                if ai_analysis["success"]:
                                    st.session_state.ai_analysis = ai_analysis
                                    display_ai_analysis(ai_analysis)
                                    
                                    # Update history record with AI analysis
                                    if hasattr(st.session_state, 'current_adaptation_id'):
                                        history.update_record(
                                            st.session_state.current_adaptation_id,
                                            ai_analysis=ai_analysis,
                                            model_used=ai_model
                                        )
                                else:
                                    st.error(f"AI analysis failed: {ai_analysis.get('error', 'Unknown error')}")
                    else:
                        st.error(f"Analysis failed: {schema['error']}")
        
        # Clean up temp file
        Path(temp_path).unlink(missing_ok=True)
    
    # Display previous analysis if available
    if hasattr(st.session_state, 'analyzed_schema'):
        st.markdown("---")
        st.markdown("### 📋 Previous Analysis Results")
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**File:** {getattr(st.session_state, 'uploaded_file_name', 'Unknown')}")
            st.info(f"**Format:** {st.session_state.analyzed_schema.get('format', 'Unknown')}")
        
        with col2:
            st.info(f"**Fields:** {len(st.session_state.analyzed_schema.get('fields', {}))}")
            st.info(f"**Records:** {st.session_state.analyzed_schema.get('sample_records', 0)}")
        
        if st.button("📋 Show Detailed Analysis"):
            display_schema_analysis(st.session_state.analyzed_schema)
            if hasattr(st.session_state, 'ai_analysis'):
                display_ai_analysis(st.session_state.ai_analysis)


def render_data_ingestion_tab():
    """Render data ingestion tab"""
    st.subheader("🔄 Ingest Data into Elasticsearch")
    st.markdown("Load analyzed data into Elasticsearch for querying")
    
    # Show current session status if available
    if hasattr(st.session_state, 'current_adaptation_id'):
        from src.data_adaptation.adaptation_history import get_adaptation_history
        history = get_adaptation_history()
        record = history.get_record(st.session_state.current_adaptation_id)
        if record:
            st.info(f"📋 Current session: {record.get_status_emoji()} {record.get_display_name()} ({record.status})")
    
    # Check if schema has been analyzed
    if not hasattr(st.session_state, 'analyzed_schema'):
        st.warning("⚠️ Please analyze data in the **Data Analysis** tab first")
        return
    
    schema = st.session_state.analyzed_schema
    
    # Display data summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Data Format", schema.get('format', 'Unknown'))
    with col2:
        st.metric("Total Fields", len(schema.get('fields', {})))
    with col3:
        st.metric("Sample Records", schema.get('sample_records', 0))
    
    # Index configuration
    st.markdown("### ⚙️ Elasticsearch Configuration")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        index_name = st.text_input(
            "Index Name",
            value=f"logs_{getattr(st.session_state, 'uploaded_file_name', 'data').split('.')[0].lower()}",
            help="Name for the Elasticsearch index"
        )
    
    with col2:
        # Test ES connection
        if st.button("🔗 Test Connection"):
            from src.data_adaptation.data_adapter import DataAdapter
            adapter = DataAdapter()
            connection = adapter.test_elasticsearch_connection()
            
            if connection["connected"]:
                st.success(f"✅ Connected to {connection.get('cluster_name', 'Elasticsearch')}")
            else:
                st.error(f"❌ Connection failed: {connection.get('error', 'Unknown error')}")
    
    # Auto-generate Elasticsearch mapping
    from src.data_adaptation.schema_analyzer import SchemaAnalyzer
    analyzer = SchemaAnalyzer()
    es_mapping = analyzer.suggest_elasticsearch_mapping(schema)
    
    st.markdown("### 📝 Elasticsearch Mapping")
    with st.expander("View Generated Mapping"):
        st.json(es_mapping)
    
    # Ingestion
    st.markdown("### 📤 Data Ingestion")
    
    # File input for ingestion
    ingest_method = st.radio(
        "Choose ingestion method:",
        ["Upload File", "Use Local File Path"],
        key="ingest_method",
        help="Choose how to provide your data file for ingestion"
    )
    
    ingest_file = None
    ingest_local_path = None
    
    if ingest_method == "Upload File":
        ingest_file = st.file_uploader(
            "Upload Data File for Ingestion",
            type=['csv', 'json', 'jsonl', 'ndjson'],
            key="ingest_file",
            help="Upload your data file for ingestion"
        )
    else:
        ingest_local_path = st.text_input(
            "Enter file path for ingestion:",
            placeholder="e.g., data_raw/sample_cybersecurity_logs.csv",
            key="ingest_local_path",
            help="Enter the path to your local file for ingestion"
        )
        
        if ingest_local_path and not Path(ingest_local_path).exists():
            st.error(f"❌ File not found: {ingest_local_path}")
            ingest_local_path = None
    
    if st.button("🚀 Ingest Data", type="primary") and (ingest_file or ingest_local_path):
        # Handle file path based on ingestion method
        if ingest_file:
            # Save uploaded file temporarily with better error handling
            try:
                import uuid
                temp_dir = Path("/tmp")
                temp_dir.mkdir(exist_ok=True)
                
                file_extension = ingest_file.name.split('.')[-1] if '.' in ingest_file.name else 'csv'
                temp_filename = f"ingest_data_{uuid.uuid4().hex[:8]}.{file_extension}"
                temp_path = temp_dir / temp_filename
                
                # Write file content
                with open(temp_path, 'wb') as tmp_file:
                    tmp_file.write(ingest_file.getvalue())
                
                temp_path = str(temp_path)
                
            except Exception as upload_error:
                st.error(f"❌ File upload failed: {upload_error}")
                return
        else:
            # Use local file path directly
            temp_path = ingest_local_path
        
        with st.spinner(f"Ingesting data into index '{index_name}'..."):
            from src.data_adaptation.data_adapter import DataAdapter
            adapter = DataAdapter()
            
            # Ingest with mapping
            result = adapter.ingest_data_file(temp_path, index_name, es_mapping)
            
            if result.get("success"):
                st.success(f"✅ Successfully ingested {result['successful']} documents!")
                st.info(f"Total: {result['total_docs']}, Successful: {result['successful']}, Errors: {result['errors']}")
                
                # Store index info for query generation
                st.session_state.ingested_index = index_name
                st.session_state.ingestion_result = result
                
                # Wait a moment for Elasticsearch to process the bulk ingestion
                import time
                time.sleep(2)  # Allow time for documents to be indexed
                
                # Quick verification using get_index_info instead
                try:
                    index_info = adapter.get_index_info(index_name)
                    if "error" not in index_info:
                        st.success("✅ Ingestion completed successfully!")
                        st.info(f"📊 Index created: {index_info['document_count']} documents, {index_info['field_count']} fields")
                        st.info(f"🔍 Fields: {', '.join(index_info['fields'][:5])}{'...' if len(index_info['fields']) > 5 else ''}")
                        
                        # Check if we got all expected fields
                        expected_fields = list(schema.get('fields', {}).keys())
                        if len(index_info['fields']) >= len(expected_fields):
                            st.success("✅ All CSV columns appear to be properly indexed!")
                        else:
                            st.warning(f"⚠️ Expected {len(expected_fields)} fields but got {len(index_info['fields'])}")
                    else:
                        st.warning("⚠️ Could not verify index creation")
                except Exception as e:
                    st.warning(f"⚠️ Verification unavailable: {e}")
                    st.info("Index created but verification skipped")
                
                # Store mapping information for future query generation
                from src.data_adaptation.mapping_storage import MappingStorage
                mapping_storage = MappingStorage()
                
                mapping_info = {
                    "schema": schema,
                    "field_patterns": schema.get('detected_patterns', {}),
                    "ai_analysis": getattr(st.session_state, 'ai_analysis', {}),
                    "elasticsearch_mapping": es_mapping
                }
                
                mapping_storage.store_index_mapping(index_name, mapping_info)
                st.info(f"📝 Stored field mapping for {index_name} - it will now appear in Query Generator!")
                
                # Update history record with ingestion results
                if hasattr(st.session_state, 'current_adaptation_id'):
                    from src.data_adaptation.adaptation_history import get_adaptation_history
                    history = get_adaptation_history()
                    history.update_record(
                        st.session_state.current_adaptation_id,
                        index_name=index_name,
                        status="ingested",
                        elasticsearch_mapping=es_mapping,
                        document_count=result.get('successful', 0)
                    )
                
            else:
                st.error(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")
                
                # Enhanced error reporting
                if 'missing_fields' in result and result['missing_fields']:
                    st.error(f"🔍 Missing field mappings: {result['missing_fields']}")
                    st.info("💡 These CSV columns were not included in the generated mapping. Please regenerate the mapping or check your schema analysis.")
                
                if 'error_details' in result:
                    error_details = result['error_details']
                    
                    # Field rejection errors
                    if error_details.get('field_rejections'):
                        st.error("🚫 Field Rejection Errors:")
                        for error in error_details['field_rejections'][:3]:  # Show first 3
                            st.code(f"Field '{error['field']}' was rejected: {error['reason']}")
                        
                        if len(error_details['field_rejections']) > 3:
                            st.info(f"Showing 3 of {len(error_details['field_rejections'])} field rejection errors")
                    
                    # Mapping errors
                    if error_details.get('mapping_errors'):
                        st.error("📝 Mapping Errors:")
                        for error in error_details['mapping_errors'][:3]:  # Show first 3
                            st.code(f"Mapping error: {error['reason']}")
                        
                        if len(error_details['mapping_errors']) > 3:
                            st.info(f"Showing 3 of {len(error_details['mapping_errors'])} mapping errors")
                    
                    # Other errors
                    if error_details.get('other_errors'):
                        with st.expander("Other Error Details"):
                            st.json(error_details['other_errors'][:3])  # Show first 3
                    
                    # Link to diagnostics tab for detailed analysis
                    total_errors = len(error_details.get('all_errors', []))
                    if total_errors > 0:
                        st.info(f"💡 **{total_errors} total errors detected.** Go to the **🔍 Diagnostics** tab for detailed error analysis and troubleshooting recommendations.")
                        
                        # Quick diagnostic button
                        if st.button("🚀 Run Quick Diagnosis", key="quick_diagnosis"):
                            # Store the error details for diagnostics
                            st.session_state.last_ingestion_errors = error_details
                            st.info("✅ Error data stored. Switch to the **🔍 Diagnostics** tab to view the analysis.")
        
        # Clean up
        Path(temp_path).unlink(missing_ok=True)





def render_history_tab():
    """Render the adaptation history tab"""
    st.subheader("📚 Adaptation History")
    st.markdown("View and manage your data adaptation sessions")
    
    from src.data_adaptation.adaptation_history import get_adaptation_history
    
    # Add refresh button to force reload
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh History"):
            history = get_adaptation_history(force_refresh=True)
            st.success(f"History refreshed! Found {len(history.records)} sessions")
        else:
            history = get_adaptation_history(force_refresh=True)  # Always force refresh on tab load
    
    # Add debug info
    with col1:
        st.info(f"📂 History file: `artifacts/adaptation_history.json` | Records loaded: {len(history.records)}")
    
    # Get summary stats
    stats = history.get_summary_stats()
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions", stats["total_records"])
    with col2:
        st.metric("Total Documents", f"{stats['total_documents']:,}")
    with col3:
        completed_count = stats["status_counts"].get("completed", 0)
        st.metric("Completed", completed_count)
    with col4:
        failed_count = stats["status_counts"].get("failed", 0)
        st.metric("Failed", failed_count)
    
    # Search and filter
    col1, col2 = st.columns([2, 1])
    with col1:
        search_query = st.text_input("🔍 Search by file or index name", placeholder="e.g., cybersecurity")
    with col2:
        status_filter = st.selectbox("Filter by status", ["All", "analyzed", "ingested", "completed", "failed"])
    
    # Get records
    if search_query:
        records = history.search_records(search_query)
    elif status_filter != "All":
        records = history.get_records_by_status(status_filter)
    else:
        records = history.list_records()
    
    if not records:
        st.info("No adaptation sessions found. Start by analyzing new data in the 'Data Analysis' tab!")
        return
    
    # Display records
    st.markdown(f"### 📋 Sessions ({len(records)} found)")
    
    for record in records:
        with st.expander(f"{record.get_status_emoji()} {record.get_display_name()} - {record.get_time_ago()}"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**File:** {record.file_name}")
                st.markdown(f"**Format:** {record.file_format}")
                st.markdown(f"**Status:** {record.status}")
                st.markdown(f"**Model Used:** {record.model_used}")
                
                if record.index_name:
                    st.markdown(f"**Index:** `{record.index_name}`")
                if record.document_count > 0:
                    st.markdown(f"**Documents:** {record.document_count:,}")
                
                # Show AI analysis summary
                if record.ai_analysis and record.ai_analysis.get("success"):
                    analysis = record.ai_analysis.get("analysis", {})
                    if analysis.get("system_type"):
                        st.markdown(f"**System Type:** {analysis['system_type']}")
            
            with col2:
                st.markdown(f"**Created:** {datetime.fromtimestamp(record.timestamp).strftime('%Y-%m-%d %H:%M')}")
                
                # Action buttons
                # Show load button for different session states
                if record.status == "analyzed":
                    if st.button(f"🔄 Load Schema", key=f"load_{record.id}"):
                        load_session_to_current(record)
                        st.success("Schema loaded! You can now proceed to ingestion.")
                        st.rerun()
                elif record.status in ["ingested", "completed"] and record.index_name:
                    if st.button(f"🔄 Load Session", key=f"load_{record.id}"):
                        load_session_to_current(record)
                        st.success("Session loaded! You can now work with this data.")
                        st.rerun()
                
                if st.button(f"🗑️ Delete", key=f"delete_{record.id}"):
                    if history.delete_record(record.id):
                        st.success("Session deleted!")
                        st.rerun()
                    else:
                        st.error("Failed to delete session")
            
            # Show field details
            if record.schema.get("fields"):
                st.markdown("**📋 Fields:**")
                fields = record.schema["fields"]
                field_list = []
                for field_name, field_info in list(fields.items())[:10]:  # Show first 10
                    field_list.append(f"• {field_name} ({field_info.get('type', 'unknown')})")
                if len(fields) > 10:
                    field_list.append(f"• ... and {len(fields) - 10} more fields")
                st.markdown("\n".join(field_list))
            



def load_session_to_current(record):
    """Load a historical session into current session state"""
    st.session_state.analyzed_schema = record.schema
    st.session_state.uploaded_file_name = record.file_name
    st.session_state.current_adaptation_id = record.id
    
    # Load AI analysis if available
    if record.ai_analysis:
        st.session_state.ai_analysis = record.ai_analysis
    
    # Load ingestion data if available
    if record.index_name:
        st.session_state.ingested_index = record.index_name
        
        # Simulate ingestion result for consistency
        st.session_state.ingestion_result = {
            "success": True,
            "successful": record.document_count,
            "total_docs": record.document_count,
            "errors": 0
        }
    



def display_schema_analysis(schema):
    """Display schema analysis results"""
    st.markdown("### 📊 Schema Analysis Results")
    
    # Overview
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Format", schema.get('format', 'Unknown'))
    with col2:
        st.metric("Total Fields", len(schema.get('fields', {})))
    with col3:
        st.metric("Sample Records", schema.get('sample_records', 0))
    with col4:
        patterns_count = len(schema.get('detected_patterns', {}))
        st.metric("Detected Patterns", patterns_count)
    
    # Field details
    with st.expander("📋 Field Details"):
        fields = schema.get('fields', {})
        for field_name, field_info in list(fields.items())[:20]:  # Show first 20 fields
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown(f"**{field_name}**")
            with col2:
                st.markdown(f"`{field_info.get('type', 'unknown')}`")
            with col3:
                samples = field_info.get('sample_values', [])
                if samples:
                    st.markdown(f"*{samples[0]}*")
    
    # Detected patterns
    patterns = schema.get('detected_patterns', {})
    if patterns:
        st.markdown("### 🔍 Detected Patterns")
        for pattern_name, fields in patterns.items():
            st.markdown(f"**{pattern_name.replace('_', ' ').title()}:** {', '.join(fields)}")


def display_ai_analysis(ai_analysis):
    """Display AI analysis results"""
    st.markdown("### 🤖 AI Analysis Results")
    
    analysis = ai_analysis.get('analysis', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🏢 System Type")
        st.info(analysis.get('system_type', 'Unknown'))
        
        st.markdown("#### 🔑 Important Fields")
        important_fields = analysis.get('important_fields', [])
        if important_fields:
            for field in important_fields[:10]:
                st.markdown(f"• {field}")
        else:
            st.markdown("*No important fields identified*")
    
    with col2:
        st.markdown("#### 💡 Recommended Queries")
        recommended_queries = analysis.get('recommended_queries', [])
        if recommended_queries:
            for query in recommended_queries[:5]:
                st.markdown(f"• {query}")
        else:
            st.markdown("*No query recommendations*")
        
        st.markdown("#### 🔍 Insights")
        insights = analysis.get('insights', [])
        if insights:
            for insight in insights[:3]:
                st.markdown(f"• {insight}")
        else:
            st.markdown("*No additional insights*")


def test_query_on_index(query, index_name):
    """Test a query on the ingested index"""
    try:
        from gui.utils.backend_interface import execute_elasticsearch_query
        
        with st.spinner("Testing query..."):
            # Execute query - pass the query dict directly, not as JSON string
            is_valid, result = execute_elasticsearch_query(query, index_name)
            
            if is_valid:
                if isinstance(result, dict) and 'hits' in result:
                    total_hits = result['hits']['total']['value'] if isinstance(result['hits']['total'], dict) else result['hits']['total']
                    st.success(f"✅ Query executed successfully! Found {total_hits} results")
                    
                    # Show sample results
                    hits = result['hits']['hits'][:3]  # First 3 results
                    if hits:
                        st.markdown("#### Sample Results:")
                        for i, hit in enumerate(hits):
                            with st.expander(f"Result {i+1}"):
                                st.json(hit['_source'])
                else:
                    st.success("✅ Query executed successfully!")
                    st.json(result)
            else:
                st.error(f"❌ Query failed: {result}")
                
    except Exception as e:
        st.error(f"❌ Error testing query: {e}")


def render_diagnostics_tab():
    """Render diagnostics tab for ingestion error analysis"""
    st.subheader("🔍 Ingestion Diagnostics")
    st.markdown("Analyze and troubleshoot data ingestion issues")
    
    # Check for last ingestion errors from current session
    if 'last_ingestion_errors' in st.session_state:
        st.warning("⚠️ **Recent ingestion errors detected from current session!**")
        if st.button("🔍 Analyze Current Session Errors", type="primary"):
            analyze_session_errors()
        st.divider()
    
    # Quick diagnostic buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚀 Run Full Diagnosis", type="primary", use_container_width=True):
            run_full_diagnosis()
    
    with col2:
        if st.button("📊 View Recent Errors", use_container_width=True):
            show_recent_errors()
    
    with col3:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
    
    # Display session error analysis if available
    if 'session_error_analysis' in st.session_state:
        display_session_error_analysis(st.session_state.session_error_analysis)
    
    # Display diagnosis results if available
    if 'diagnosis_results' in st.session_state:
        display_diagnosis_results(st.session_state.diagnosis_results)
    
    # Display recent errors if available
    if 'recent_errors_data' in st.session_state:
        display_recent_errors(st.session_state.recent_errors_data)


def analyze_session_errors():
    """Analyze errors from the current session"""
    with st.spinner("Analyzing current session errors..."):
        try:
            from src.data_adaptation.data_adapter import DataAdapter
            adapter = DataAdapter()
            
            error_details = st.session_state.last_ingestion_errors
            all_errors = error_details.get('all_errors', [])
            
            if all_errors:
                analysis = adapter._analyze_error_patterns(all_errors)
                recommendations = adapter._generate_error_recommendations(analysis)
                
                session_analysis = {
                    "error_analysis": analysis,
                    "recommendations": recommendations,
                    "error_details": error_details,
                    "timestamp": datetime.now().isoformat()
                }
                
                st.session_state.session_error_analysis = session_analysis
                st.success(f"✅ Analyzed {len(all_errors)} errors from current session!")
            else:
                st.warning("No detailed error information available")
                
        except Exception as e:
            st.error(f"❌ Session error analysis failed: {e}")


def run_full_diagnosis():
    """Run comprehensive ingestion diagnosis"""
    with st.spinner("Running comprehensive diagnosis..."):
        try:
            # Clear module cache to ensure we get the latest version
            import importlib
            import sys
            if 'src.data_adaptation.data_adapter' in sys.modules:
                importlib.reload(sys.modules['src.data_adaptation.data_adapter'])
            
            from src.data_adaptation.data_adapter import DataAdapter
            adapter = DataAdapter()
            
            # Verify methods exist
            if not hasattr(adapter, 'diagnose_ingestion_issues'):
                st.error("❌ Method 'diagnose_ingestion_issues' not found. Please restart Streamlit.")
                return
            
            # Get index name from session if available
            index_name = getattr(st.session_state, 'ingested_index', None)
            
            diagnosis = adapter.diagnose_ingestion_issues(index_name)
            st.session_state.diagnosis_results = diagnosis
            
            st.success("✅ Diagnosis completed!")
            
        except Exception as e:
            st.error(f"❌ Diagnosis failed: {e}")
            st.error(f"Error details: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


def show_recent_errors():
    """Show recent ingestion errors"""
    with st.spinner("Loading recent errors..."):
        try:
            # Clear module cache to ensure we get the latest version
            import importlib
            import sys
            if 'src.data_adaptation.data_adapter' in sys.modules:
                importlib.reload(sys.modules['src.data_adaptation.data_adapter'])
            
            from src.data_adaptation.data_adapter import DataAdapter
            adapter = DataAdapter()
            
            # Verify methods exist
            if not hasattr(adapter, 'get_recent_ingestion_errors'):
                st.error("❌ Method 'get_recent_ingestion_errors' not found. Please restart Streamlit.")
                return
            
            recent_errors = adapter.get_recent_ingestion_errors(10)
            st.session_state.recent_errors_data = recent_errors
            
            if recent_errors:
                st.success(f"✅ Found {len(recent_errors)} recent error logs")
            else:
                st.info("ℹ️ No recent error logs found")
                
        except Exception as e:
            st.error(f"❌ Failed to load errors: {e}")
            st.error(f"Error details: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


def display_session_error_analysis(session_analysis: Dict[str, Any]):
    """Display analysis results for current session errors"""
    st.markdown("### 🎯 Current Session Error Analysis")
    
    error_analysis = session_analysis.get("error_analysis", {})
    error_details = session_analysis.get("error_details", {})
    
    # Quick summary
    total_errors = error_analysis.get("total_errors", 0)
    st.info(f"📊 Analyzing **{total_errors} errors** from your recent ingestion attempt")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        field_rejections = error_analysis.get("field_rejection_analysis", {})
        st.metric("Field Rejections", f"{field_rejections.get('count', 0)} ({field_rejections.get('percentage', 0):.1f}%)")
    
    with col2:
        mapping_issues = error_analysis.get("mapping_issues", {})
        st.metric("Mapping Issues", f"{mapping_issues.get('count', 0)} ({mapping_issues.get('percentage', 0):.1f}%)")
    
    with col3:
        problematic_fields = error_analysis.get("most_problematic_fields", {})
        st.metric("Problematic Fields", len(problematic_fields))
    
    # Most problematic fields
    if problematic_fields:
        st.markdown("#### ⚠️ Fields Causing Issues")
        for field, count in sorted(problematic_fields.items(), key=lambda x: x[1], reverse=True)[:5]:
            st.write(f"• **{field}**: {count} errors")
    
    # Recommendations
    recommendations = session_analysis.get("recommendations", [])
    if recommendations:
        st.markdown("#### 💡 Immediate Action Items")
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
    
    # Show sample errors
    all_errors = error_details.get('all_errors', [])
    if all_errors:
        with st.expander(f"🔍 Sample Error Details ({len(all_errors)} total errors)"):
            # Group by error type and show samples
            errors_by_type = {}
            for error in all_errors:
                error_type = error.get('type', 'unknown')
                if error_type not in errors_by_type:
                    errors_by_type[error_type] = []
                errors_by_type[error_type].append(error)
            
            for error_type, type_errors in errors_by_type.items():
                st.markdown(f"**{error_type}** ({len(type_errors)} errors):")
                for error in type_errors[:2]:  # Show first 2 of each type
                    st.code(f"Document {error.get('document_id', 'unknown')}: {error.get('reason', 'No reason')}")
                if len(type_errors) > 2:
                    st.caption(f"... and {len(type_errors) - 2} more {error_type} errors")


def display_diagnosis_results(diagnosis: Dict[str, Any]):
    """Display comprehensive diagnosis results"""
    st.markdown("### 📋 Diagnosis Results")
    
    # Elasticsearch status
    es_status = diagnosis.get("elasticsearch_status", {})
    if es_status.get("connected"):
        st.success(f"✅ Elasticsearch Connected - Cluster: {es_status.get('cluster_name', 'unknown')}")
    else:
        st.error(f"❌ Elasticsearch Connection Failed: {es_status.get('error', 'Unknown error')}")
    
    # Error analysis
    error_analysis = diagnosis.get("error_analysis", {})
    if error_analysis:
        st.markdown("### 📊 Error Analysis")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Errors", error_analysis.get("total_errors", 0))
        
        with col2:
            field_rejections = error_analysis.get("field_rejection_analysis", {})
            st.metric("Field Rejections", f"{field_rejections.get('count', 0)} ({field_rejections.get('percentage', 0):.1f}%)")
        
        with col3:
            mapping_issues = error_analysis.get("mapping_issues", {})
            st.metric("Mapping Issues", f"{mapping_issues.get('count', 0)} ({mapping_issues.get('percentage', 0):.1f}%)")
        
        with col4:
            problematic_fields = error_analysis.get("most_problematic_fields", {})
            st.metric("Problematic Fields", len(problematic_fields))
        
        # Error type distribution
        if error_analysis.get("error_type_distribution"):
            st.markdown("#### 📈 Error Type Distribution")
            error_types = error_analysis["error_type_distribution"]
            
            # Create a simple bar chart using columns
            for error_type, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / error_analysis["total_errors"]) * 100
                st.write(f"**{error_type}**: {count} errors ({percentage:.1f}%)")
                st.progress(percentage / 100)
        
        # Most problematic fields
        if problematic_fields:
            st.markdown("#### ⚠️ Most Problematic Fields")
            for field, count in sorted(problematic_fields.items(), key=lambda x: x[1], reverse=True)[:10]:
                st.write(f"• **{field}**: {count} errors")
    
    # Recommendations
    recommendations = diagnosis.get("recommendations", [])
    if recommendations:
        st.markdown("### 💡 Recommendations")
        for i, rec in enumerate(recommendations, 1):
            st.markdown(f"{i}. {rec}")
    
    # Index information if available
    index_info = diagnosis.get("index_info", {})
    if index_info and "error" not in index_info:
        st.markdown("### 📊 Current Index Status")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Documents", index_info.get("document_count", 0))
        with col2:
            st.metric("Fields", index_info.get("field_count", 0))
        with col3:
            size_mb = index_info.get("size_bytes", 0) / (1024 * 1024)
            st.metric("Size (MB)", f"{size_mb:.2f}")


def display_recent_errors(recent_errors: List[Dict[str, Any]]):
    """Display recent error logs with detailed breakdown"""
    st.markdown("### 📝 Recent Error Logs")
    
    if not recent_errors:
        st.info("No recent error logs found")
        return
    
    # Summary of all recent errors
    total_errors = sum(error_data.get("total_errors", 0) for error_data in recent_errors)
    st.info(f"Found {len(recent_errors)} error log files with {total_errors} total errors")
    
    # Display each error log
    for i, error_data in enumerate(recent_errors):
        timestamp = error_data.get("timestamp", "Unknown")
        source_file = error_data.get("source_file", "Unknown")
        total_errors_in_file = error_data.get("total_errors", 0)
        
        with st.expander(f"📄 Error Log {i+1}: {total_errors_in_file} errors from {Path(source_file).name if source_file != 'Unknown' else 'Unknown'} ({timestamp[:19]})"):
            
            # Error summary
            error_summary = error_data.get("error_summary", {})
            if error_summary:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Error Types:**")
                    for error_type, count in error_summary.get("error_types", {}).items():
                        st.write(f"• {error_type}: {count}")
                
                with col2:
                    st.markdown("**Field Issues:**")
                    field_issues = error_summary.get("field_issues", {})
                    if field_issues:
                        for field, count in sorted(field_issues.items(), key=lambda x: x[1], reverse=True)[:5]:
                            st.write(f"• {field}: {count} errors")
                    else:
                        st.write("No field-specific issues detected")
                
                # Top errors
                top_errors = error_summary.get("top_errors", [])
                if top_errors:
                    st.markdown("**Most Common Errors:**")
                    for error_reason, count in top_errors[:3]:
                        st.code(f"{error_reason} ({count} occurrences)")
            
            # Show detailed errors button
            if st.button(f"🔍 Show All {total_errors_in_file} Errors", key=f"show_errors_{i}"):
                st.session_state[f"show_detailed_errors_{i}"] = True
                st.rerun()
            
            # Display detailed errors if requested (outside of expander to avoid nesting)
            if st.session_state.get(f"show_detailed_errors_{i}", False):
                show_detailed_errors_inline(error_data, i)


def show_detailed_errors_inline(error_data: Dict[str, Any], file_index: int):
    """Show detailed error breakdown inline (no nested expanders)"""
    errors = error_data.get("errors", [])
    
    st.markdown(f"### 🔍 Detailed Error Breakdown ({len(errors)} errors)")
    
    # Add a close button
    if st.button(f"❌ Hide Details", key=f"hide_errors_{file_index}"):
        st.session_state[f"show_detailed_errors_{file_index}"] = False
        st.rerun()
    
    # Group errors by type for better organization
    errors_by_type = {}
    for error in errors:
        error_type = error.get('type', 'unknown')
        if error_type not in errors_by_type:
            errors_by_type[error_type] = []
        errors_by_type[error_type].append(error)
    
    # Display errors by type using containers instead of expanders
    for error_type, type_errors in errors_by_type.items():
        st.markdown(f"#### 📋 {error_type} ({len(type_errors)} errors)")
        
        # Show first 5 errors of this type
        for i, error in enumerate(type_errors[:5]):
            with st.container():
                st.markdown(f"**Error {i+1}:**")
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.write(f"**Document ID:** {error.get('document_id', 'unknown')}")
                    st.write(f"**Status:** {error.get('status', 'unknown')}")
                
                with col2:
                    st.code(error.get('reason', 'No reason provided'))
                
                if i < len(type_errors[:5]) - 1:  # Don't add divider after last item
                    st.divider()
        
        if len(type_errors) > 5:
            st.info(f"Showing first 5 of {len(type_errors)} {error_type} errors")
        
        st.markdown("---")  # Separator between error types


def show_detailed_errors(error_data: Dict[str, Any]):
    """Legacy function - kept for compatibility"""
    errors = error_data.get("errors", [])
    st.markdown(f"### 🔍 Detailed Error Breakdown ({len(errors)} errors)")
    
    # Group errors by type
    errors_by_type = {}
    for error in errors:
        error_type = error.get('type', 'unknown')
        if error_type not in errors_by_type:
            errors_by_type[error_type] = []
        errors_by_type[error_type].append(error)
    
    # Display errors by type using simple containers
    for error_type, type_errors in errors_by_type.items():
        st.markdown(f"#### 📋 {error_type} ({len(type_errors)} errors)")
        
        # Show first 5 errors of this type
        for i, error in enumerate(type_errors[:5]):
            st.markdown(f"**Error {i+1}:** {error.get('reason', 'No reason provided')}")
        
        if len(type_errors) > 5:
            st.info(f"Showing first 5 of {len(type_errors)} {error_type} errors")


# Helper function to import required modules
def get_path_module():
    """Get Path module for file operations"""
    from pathlib import Path
    return Path

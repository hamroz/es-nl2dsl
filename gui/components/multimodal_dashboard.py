#!/usr/bin/env python3
"""Simplified Multi-Modal Queries Dashboard for Data Adaptation"""
import streamlit as st
import json
import sys
from pathlib import Path
import tempfile
from datetime import datetime

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
        "🎯 Query Generation",
        "📚 History"
    ])
    
    with tab1:
        render_data_analysis_tab()
    
    with tab2:
        render_data_ingestion_tab()
    
    with tab3:
        render_query_generation_tab()
    
    with tab4:
        render_history_tab()


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
                    "elasticsearch_mapping": es_mapping,
                    "query_suggestions": []
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
                        for error in error_details['field_rejections']:
                            st.code(f"Field '{error['field']}' was rejected: {error['reason']}")
                    
                    # Mapping errors
                    if error_details.get('mapping_errors'):
                        st.error("📝 Mapping Errors:")
                        for error in error_details['mapping_errors']:
                            st.code(f"Mapping error: {error['reason']}")
                    
                    # Other errors
                    if error_details.get('other_errors'):
                        with st.expander("Other Error Details"):
                            st.json(error_details['other_errors'])
        
        # Clean up
        Path(temp_path).unlink(missing_ok=True)


def render_query_generation_tab():
    """Render AI-assisted query generation tab"""
    st.subheader("🎯 Generate Queries for New Data")
    st.markdown("Use AI to generate useful queries for your newly ingested data")
    
    # Show current session status if available
    if hasattr(st.session_state, 'current_adaptation_id'):
        from src.data_adaptation.adaptation_history import get_adaptation_history
        history = get_adaptation_history()
        record = history.get_record(st.session_state.current_adaptation_id)
        if record:
            st.info(f"📋 Current session: {record.get_status_emoji()} {record.get_display_name()} ({record.status})")
    
    # Check if data has been ingested
    if not hasattr(st.session_state, 'ingested_index'):
        st.warning("⚠️ Please ingest data in the **Data Ingestion** tab first")
        return
    
    index_name = st.session_state.ingested_index
    schema = st.session_state.analyzed_schema
    
    # Display index info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Index Name", index_name)
    with col2:
        if hasattr(st.session_state, 'ingestion_result'):
            st.metric("Documents", st.session_state.ingestion_result.get('successful', 0))
    with col3:
        st.metric("Fields", len(schema.get('fields', {})))
    
    # AI-assisted query generation
    st.markdown("### 🤖 AI-Assisted Query Generation")
    
    user_request = st.text_area(
        "Describe what you want to find",
        placeholder="e.g., 'Show me failed login attempts from the last 24 hours'",
        help="Describe in natural language what kind of queries you need"
    )
    
    # AI Model selection
    from gui.utils.backend_interface import get_all_available_models
    all_models = get_all_available_models()
    
    ai_model = st.selectbox(
        "AI Model",
        all_models,
        key="query_gen_model"
    )
    
    if st.button("🚀 Generate Queries", type="primary") and user_request:
        model_name = ai_model  # Keep the full model name with emoji prefix
        
        with st.spinner("Generating queries with AI..."):
            from src.data_adaptation.ai_assistant import AIAssistant
            ai_assistant = AIAssistant()
            query_result = ai_assistant.generate_sample_queries(schema, user_request, model_name)
            
            if query_result["success"]:
                st.session_state.generated_queries = query_result["generated_queries"]
                st.success(f"✅ Generated {len(query_result['generated_queries'])} queries!")
                
                # Update history record with generated queries
                if hasattr(st.session_state, 'current_adaptation_id'):
                    from src.data_adaptation.adaptation_history import get_adaptation_history
                    history = get_adaptation_history()
                    history.update_record(
                        st.session_state.current_adaptation_id,
                        generated_queries=query_result["generated_queries"],
                        status="completed"
                    )
            else:
                st.error(f"Query generation failed: {query_result.get('error', 'Unknown error')}")
    
    # Display generated queries
    if hasattr(st.session_state, 'generated_queries'):
        st.markdown("---")
        st.markdown("### 📝 Generated Queries")
        
        for i, query in enumerate(st.session_state.generated_queries):
            with st.expander(f"Query {i+1}: {query.get('name', 'Unnamed')}"):
                st.markdown(f"**Description:** {query.get('description', 'No description')}")
                st.code(json.dumps(query.get('dsl', {}), indent=2), language="json")
                
                if st.button(f"🧪 Test Query {i+1}", key=f"test_{i}"):
                    test_query_on_index(query.get('dsl', {}), index_name)


def render_history_tab():
    """Render the adaptation history tab"""
    st.subheader("📚 Adaptation History")
    st.markdown("View and manage your data adaptation sessions")
    
    from src.data_adaptation.adaptation_history import get_adaptation_history
    history = get_adaptation_history()
    
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
                if record.status == "completed" and record.index_name:
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
            
            # Show generated queries
            if record.generated_queries:
                st.markdown(f"**🎯 Generated Queries ({len(record.generated_queries)}):**")
                for i, query in enumerate(record.generated_queries):
                    st.markdown(f"  {i+1}. **{query.get('name', 'Unnamed')}** - *{query.get('description', 'No description')}*")
                    if st.button(f"Test Query {i+1}", key=f"test_{record.id}_{i}"):
                        if record.index_name:
                            test_query_on_index(query.get('dsl', {}), record.index_name)


def load_session_to_current(record):
    """Load a historical session into current session state"""
    st.session_state.analyzed_schema = record.schema
    st.session_state.uploaded_file_name = record.file_name
    st.session_state.ai_analysis = record.ai_analysis
    st.session_state.ingested_index = record.index_name
    st.session_state.generated_queries = record.generated_queries
    st.session_state.current_adaptation_id = record.id
    
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
            # Execute query
            is_valid, result = execute_elasticsearch_query(json.dumps(query), index_name)
            
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

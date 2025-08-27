#!/usr/bin/env python3
"""Simplified Multi-Modal Queries Dashboard for Data Adaptation"""
import streamlit as st
import json
import sys
from pathlib import Path
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def render_multimodal_dashboard():
    """Render the multi-modal queries dashboard focused on data adaptation"""
    
    st.header("🎭 Multi-Modal Data Adaptation")
    st.markdown("Adapt the system to new log data from any source with AI assistance")
    
    # Main workflow tabs
    tab1, tab2, tab3 = st.tabs([
        "📁 Data Analysis", 
        "🔄 Data Ingestion", 
        "🎯 Query Generation"
    ])
    
    with tab1:
        render_data_analysis_tab()
    
    with tab2:
        render_data_ingestion_tab()
    
    with tab3:
        render_query_generation_tab()


def render_data_analysis_tab():
    """Render data analysis and schema detection tab"""
    st.subheader("📊 Analyze New Log Data")
    st.markdown("Upload and analyze new log files to understand their structure")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload Log Data File",
        type=['csv', 'json', 'jsonl', 'ndjson'],
        help="Upload CSV, JSON, or JSONL log files"
    )
    
    if uploaded_file:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
        
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
                        st.session_state.uploaded_file_name = uploaded_file.name
                        
                        # Display schema analysis
                        display_schema_analysis(schema)
                        
                        # AI Analysis if enabled
                        if analyze_with_ai:
                            # Extract model name (remove emoji prefix)
                            model_name = ai_model.replace("🖥️ ", "").replace("☁️ ", "")
                            
                            with st.spinner("Getting AI insights..."):
                                from src.data_adaptation.ai_assistant import AIAssistant
                                ai_assistant = AIAssistant()
                                ai_analysis = ai_assistant.analyze_data_with_ai(schema, model_name)
                                
                                if ai_analysis["success"]:
                                    st.session_state.ai_analysis = ai_analysis
                                    display_ai_analysis(ai_analysis)
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
    
    # File re-upload for ingestion
    ingest_file = st.file_uploader(
        "Re-upload Data File for Ingestion",
        type=['csv', 'json', 'jsonl', 'ndjson'],
        key="ingest_file",
        help="Upload the same file again for ingestion"
    )
    
    if st.button("🚀 Ingest Data", type="primary") and ingest_file:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ingest_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(ingest_file.getvalue())
            temp_path = tmp_file.name
        
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
                
            else:
                st.error(f"❌ Ingestion failed: {result.get('error', 'Unknown error')}")
        
        # Clean up
        Path(temp_path).unlink(missing_ok=True)


def render_query_generation_tab():
    """Render AI-assisted query generation tab"""
    st.subheader("🎯 Generate Queries for New Data")
    st.markdown("Use AI to generate useful queries for your newly ingested data")
    
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
        model_name = ai_model.replace("🖥️ ", "").replace("☁️ ", "")
        
        with st.spinner("Generating queries with AI..."):
            from src.data_adaptation.ai_assistant import AIAssistant
            ai_assistant = AIAssistant()
            query_result = ai_assistant.generate_sample_queries(schema, user_request, model_name)
            
            if query_result["success"]:
                st.session_state.generated_queries = query_result["generated_queries"]
                st.success(f"✅ Generated {len(query_result['generated_queries'])} queries!")
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

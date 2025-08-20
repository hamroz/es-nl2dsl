"""
Data Explorer component for viewing raw Elasticsearch data
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from gui.utils.backend_interface import (
    get_elasticsearch_client,
    get_available_indices,
    export_results_as_csv,
    export_results_as_json
)

def render_data_explorer():
    """Render the Data Explorer interface"""
    st.title("🔍 Data Explorer")
    st.markdown("Browse and explore raw data from Elasticsearch indices without writing queries.")
    
    # Get available indices
    indices = get_available_indices()
    if not indices:
        st.error("No indices available. Please ingest data first.")
        return
    
    # Index selection
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_index = st.selectbox(
            "Select Index",
            options=indices,
            help="Choose which Elasticsearch index to explore"
        )
    
    with col2:
        # Get document count for selected index
        try:
            es = get_elasticsearch_client()
            count_result = es.count(index=selected_index)
            total_docs = count_result['count']
            st.metric("Total Documents", f"{total_docs:,}")
        except Exception as e:
            st.error(f"Error getting document count: {e}")
            total_docs = 0
    
    # Data browsing options
    st.markdown("### 🎯 Browse Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Result limit
        result_limit = st.number_input(
            "Documents to Display",
            min_value=10,
            max_value=1000,
            value=100,
            step=10,
            help="Number of documents to retrieve"
        )
    
    with col2:
        # Sort field
        sort_field = st.selectbox(
            "Sort By",
            options=["@timestamp", "_doc", "src_ip", "dst_ip", "attack_type", "label"],
            help="Field to sort results by"
        )
    
    with col3:
        # Sort order
        sort_order = st.selectbox(
            "Sort Order",
            options=["desc", "asc"],
            help="Descending (newest first) or Ascending (oldest first)"
        )
    
    # Advanced filters
    with st.expander("🔧 Advanced Filters", expanded=False):
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            # Time range filter
            use_time_filter = st.checkbox("Enable Time Filter", value=False)
            if use_time_filter:
                time_range = st.selectbox(
                    "Time Range",
                    options=[
                        "Last 1 hour",
                        "Last 24 hours",
                        "Last 7 days",
                        "Last 30 days",
                        "All time"
                    ],
                    index=4
                )
            else:
                time_range = "All time"
            
            # Field value filter
            use_field_filter = st.checkbox("Enable Field Filter", value=False)
            if use_field_filter:
                filter_field = st.text_input(
                    "Field Name",
                    placeholder="e.g., attack_type",
                    help="Field to filter on"
                )
                filter_value = st.text_input(
                    "Field Value",
                    placeholder="e.g., dos",
                    help="Value to filter for"
                )
        
        with filter_col2:
            # Attack type filter for CIC data
            if "cic" in selected_index.lower():
                use_attack_filter = st.checkbox("Filter by Attack Type", value=False)
                if use_attack_filter:
                    attack_types = ["normal", "dos", "scan", "bruteforce", "web_attack"]
                    selected_attack = st.selectbox("Attack Type", attack_types)
                else:
                    selected_attack = None
            else:
                use_attack_filter = False
                selected_attack = None
            
            # Search text
            use_text_search = st.checkbox("Enable Text Search", value=False)
            if use_text_search:
                search_text = st.text_input(
                    "Search Text",
                    placeholder="Enter search terms",
                    help="Search across all text fields"
                )
            else:
                search_text = None
    
    # Sample data option
    st.markdown("### 📊 Sampling Options")
    sample_col1, sample_col2 = st.columns(2)
    
    with sample_col1:
        use_sampling = st.checkbox(
            "Use Random Sampling",
            value=False,
            help="Get a random sample instead of the most recent documents"
        )
    
    with sample_col2:
        if use_sampling:
            sample_seed = st.number_input(
                "Random Seed",
                min_value=0,
                value=42,
                help="Seed for reproducible random sampling"
            )
        else:
            sample_seed = None
    
    # Build the query
    query = build_exploration_query(
        use_time_filter=use_time_filter,
        time_range=time_range if use_time_filter else None,
        use_field_filter=use_field_filter,
        filter_field=filter_field if use_field_filter else None,
        filter_value=filter_value if use_field_filter else None,
        use_attack_filter=use_attack_filter,
        selected_attack=selected_attack,
        use_text_search=use_text_search,
        search_text=search_text,
        use_sampling=use_sampling,
        sample_seed=sample_seed
    )
    
    # Load Data button
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        load_button = st.button("🚀 Load Data", type="primary", use_container_width=True)
    with col2:
        clear_button = st.button("🔄 Clear Results", use_container_width=True)
    
    if clear_button:
        if 'explorer_results' in st.session_state:
            del st.session_state.explorer_results
            st.toast("Results cleared successfully!", icon="🔄")
        else:
            st.info("No results to clear")
    
    if load_button:
        with st.spinner("Loading data..."):
            try:
                es = get_elasticsearch_client()
                
                # Build sort parameter
                sort_param = [{sort_field: {"order": sort_order}}] if sort_field != "_doc" else None
                
                # Execute search
                response = es.search(
                    index=selected_index,
                    body=query,
                    size=result_limit,
                    sort=sort_param
                )
                
                # Store results in session state
                st.session_state.explorer_results = response
                st.session_state.explorer_index = selected_index
                st.session_state.explorer_query = query
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
                return
    
    # Display results
    if 'explorer_results' in st.session_state:
        response = st.session_state.explorer_results
        hits = response.get('hits', {}).get('hits', [])
        total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
        
        # Results summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Documents Found", f"{total_hits:,}")
        with col2:
            st.metric("Documents Displayed", f"{len(hits):,}")
        with col3:
            execution_time = response.get('took', 0)
            st.metric("Query Time", f"{execution_time}ms")
        
        if hits:
            # Display format selection
            display_format = st.radio(
                "Display Format",
                ["📊 Table View", "📋 JSON View", "📄 Document Cards"],
                horizontal=True
            )
            
            # Export buttons
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                csv_data = export_results_as_csv(hits)
                st.download_button(
                    label="📊 Export CSV",
                    data=csv_data,
                    file_name=f"data_export_{selected_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                json_data = export_results_as_json(hits)
                st.download_button(
                    label="📋 Export JSON",
                    data=json_data,
                    file_name=f"data_export_{selected_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            
            # Display data based on selected format
            if "Table View" in display_format:
                display_table_view(hits, selected_index)
            elif "JSON View" in display_format:
                display_json_view(hits)
            else:
                display_document_cards(hits, selected_index)
        else:
            st.info("No documents found matching the criteria.")
    
    # Query inspector
    if st.checkbox("🔍 Show Query Details", value=False):
        if 'explorer_query' in st.session_state:
            st.markdown("### Generated Elasticsearch Query")
            st.json(st.session_state.explorer_query)

def build_exploration_query(use_time_filter=False, time_range=None,
                           use_field_filter=False, filter_field=None, filter_value=None,
                           use_attack_filter=False, selected_attack=None,
                           use_text_search=False, search_text=None,
                           use_sampling=False, sample_seed=None):
    """Build Elasticsearch query based on exploration options"""
    
    # Start with base query
    query = {"query": {"bool": {"filter": []}}}
    
    # Add time filter
    if use_time_filter and time_range != "All time":
        now = datetime.now()
        if time_range == "Last 1 hour":
            start_time = now - timedelta(hours=1)
        elif time_range == "Last 24 hours":
            start_time = now - timedelta(days=1)
        elif time_range == "Last 7 days":
            start_time = now - timedelta(days=7)
        elif time_range == "Last 30 days":
            start_time = now - timedelta(days=30)
        else:
            start_time = None
        
        if start_time:
            query["query"]["bool"]["filter"].append({
                "range": {
                    "@timestamp": {
                        "gte": start_time.isoformat()
                    }
                }
            })
    
    # Add field filter
    if use_field_filter and filter_field and filter_value:
        query["query"]["bool"]["filter"].append({
            "term": {filter_field: filter_value}
        })
    
    # Add attack type filter
    if use_attack_filter and selected_attack:
        query["query"]["bool"]["filter"].append({
            "term": {"attack_type": selected_attack}
        })
    
    # Add text search
    if use_text_search and search_text:
        query["query"]["bool"]["must"] = [{
            "query_string": {
                "query": search_text,
                "default_field": "*"
            }
        }]
    
    # Add random sampling
    if use_sampling and sample_seed is not None:
        query["query"] = {
            "function_score": {
                "query": query["query"],
                "random_score": {
                    "seed": sample_seed
                }
            }
        }
    
    # If no filters, use match_all
    if not query["query"]["bool"]["filter"] and "must" not in query["query"]["bool"]:
        query = {"query": {"match_all": {}}}
    
    return query

def display_table_view(hits, index_name):
    """Display results in table format"""
    # Extract data for DataFrame
    data_rows = []
    for hit in hits:
        source = hit['_source']
        row = {'_id': hit['_id']}
        
        # Add common fields first
        common_fields = ['@timestamp', 'src_ip', 'dst_ip', 'src_port', 'dst_port', 
                        'protocol', 'attack_type', 'label']
        for field in common_fields:
            if field in source:
                row[field] = source[field]
        
        # Add numeric fields for CIC data
        if "cic" in index_name.lower():
            numeric_fields = ['flow_packets_s', 'flow_bytes_s', 'flow_duration',
                            'total_fwd_packets', 'total_bwd_packets']
            for field in numeric_fields:
                if field in source:
                    value = source[field]
                    # Format large numbers
                    if isinstance(value, (int, float)):
                        if field == 'flow_bytes_s':
                            row[field] = f"{value:,.0f}"
                        elif field == 'flow_packets_s':
                            row[field] = f"{value:.2f}"
                        else:
                            row[field] = value
                    else:
                        row[field] = value
        
        data_rows.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(data_rows)
    
    # Format timestamp if present
    if '@timestamp' in df.columns:
        df['@timestamp'] = pd.to_datetime(df['@timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Display with column configuration
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "_id": st.column_config.TextColumn("Document ID", width="small"),
            "@timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
            "src_ip": st.column_config.TextColumn("Source IP", width="medium"),
            "dst_ip": st.column_config.TextColumn("Dest IP", width="medium"),
            "attack_type": st.column_config.TextColumn("Attack Type", width="small"),
        }
    )

def display_json_view(hits):
    """Display results in JSON format"""
    # Use selectbox instead of tabs for JSON view options
    json_view_option = st.selectbox(
        "JSON View Type:",
        ["Pretty JSON", "Raw JSON", "Source Only"],
        index=0,
        help="Choose how to display the JSON data"
    )
    
    if json_view_option == "Pretty JSON":
        # Pretty printed JSON
        for i, hit in enumerate(hits):
            with st.expander(f"Document {i+1} - ID: {hit['_id']}", expanded=(i==0)):
                st.json(hit['_source'])
    elif json_view_option == "Raw JSON":
        # Raw JSON including metadata
        st.json([hit for hit in hits])
    else:  # "Source Only"
        # Source data only
        sources = [hit['_source'] for hit in hits]
        st.json(sources)

def display_document_cards(hits, index_name):
    """Display results as document cards"""
    for i, hit in enumerate(hits):
        source = hit['_source']
        
        # Create card container
        with st.container():
            # Card header
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"### Document {i+1}")
            with col2:
                st.caption(f"ID: {hit['_id'][:8]}...")
            
            # Card content in columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if '@timestamp' in source:
                    st.markdown(f"**Time:** {source['@timestamp']}")
                if 'src_ip' in source:
                    st.markdown(f"**Source:** {source.get('src_ip', 'N/A')}:{source.get('src_port', 'N/A')}")
                if 'dst_ip' in source:
                    st.markdown(f"**Dest:** {source.get('dst_ip', 'N/A')}:{source.get('dst_port', 'N/A')}")
            
            with col2:
                if 'protocol' in source:
                    st.markdown(f"**Protocol:** {source['protocol']}")
                if 'attack_type' in source:
                    attack = source['attack_type']
                    color = "🔴" if attack != "normal" else "🟢"
                    st.markdown(f"**Attack:** {color} {attack}")
                if 'label' in source:
                    st.markdown(f"**Label:** {source['label']}")
            
            with col3:
                # Show metrics for CIC data
                if "cic" in index_name.lower():
                    if 'flow_packets_s' in source:
                        st.metric("Packets/s", f"{source['flow_packets_s']:.2f}")
                    if 'flow_bytes_s' in source:
                        st.metric("Bytes/s", f"{source['flow_bytes_s']:,.0f}")
                else:
                    if 'bytes_in' in source:
                        st.metric("Bytes In", f"{source['bytes_in']:,}")
                    if 'bytes_out' in source:
                        st.metric("Bytes Out", f"{source['bytes_out']:,}")
            
            # Expandable section for all fields
            with st.expander("View All Fields"):
                # Display all fields in a formatted way
                for key, value in source.items():
                    if key not in ['@timestamp', 'src_ip', 'dst_ip', 'src_port', 
                                  'dst_port', 'protocol', 'attack_type', 'label']:
                        st.text(f"{key}: {value}")
            
            st.markdown("---")
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
    export_results_as_json,
    get_index_profile_info
)

# Import logging utilities
from gui.utils.logging_utils import get_gui_logger

# Initialize component logger
explorer_logger = get_gui_logger("data_explorer")

def get_index_fields(index_name):
    """Get available fields for an index"""
    try:
        es = get_elasticsearch_client()
        mapping = es.indices.get_mapping(index=index_name)
        fields = []
        
        # Extract fields from mapping
        index_mapping = mapping[index_name]['mappings']
        if 'properties' in index_mapping:
            for field_name, field_props in index_mapping['properties'].items():
                # Skip complex nested fields for sorting
                if field_props.get('type') in ['keyword', 'date', 'long', 'integer', 'float', 'double']:
                    fields.append(field_name)
                elif field_props.get('type') == 'text' and 'keyword' in field_props.get('fields', {}):
                    # Add .keyword subfield for text fields that have it
                    fields.append(f"{field_name}.keyword")
        
        # Add some common fallback fields
        common_fields = ['@timestamp', '_doc', '_score']
        for field in common_fields:
            if field not in fields:
                fields.append(field)
        
        return fields
    except Exception as e:
        # Fallback to common fields if mapping retrieval fails
        return ['@timestamp', '_doc', 'src_ip', 'dst_ip', 'attack_type', 'label']

def get_common_fields_across_indices(indices):
    """Get fields that are common across multiple selected indices"""
    if not indices:
        return ['@timestamp', '_doc']
    
    if len(indices) == 1:
        return get_index_fields(indices[0])
    
    # Get intersection of fields across all indices
    all_fields = [set(get_index_fields(idx)) for idx in indices]
    common_fields = set.intersection(*all_fields) if all_fields else set()
    
    # Always include basic fields
    basic_fields = ['@timestamp', '_doc', '_score']
    for field in basic_fields:
        common_fields.add(field)
    
    return sorted(list(common_fields))

def render_data_explorer():
    """Render the Data Explorer interface"""
    explorer_logger.log_page_load("Data Explorer component loaded")
    st.title("🔍 Data Explorer")
    st.markdown("Browse and explore raw data from Elasticsearch indices without writing queries.")
    
    # Get available indices
    indices = get_available_indices()
    if not indices:
        st.error("No indices available. Please ingest data first.")
        explorer_logger.log_warning("Data Explorer access", "No indices available")
        return
    
    # Index selection
    col1, col2 = st.columns([2, 1])
    with col1:
        # Allow multiple index selection
        selected_indices = st.multiselect(
            "Select Index(es)",
            options=indices,
            default=[indices[0]] if indices else [],
            help="Choose which Elasticsearch indices to explore. Select multiple to search across them."
        )
        
        # Backward compatibility - convert to single index if only one selected
        selected_index = selected_indices[0] if len(selected_indices) == 1 else ','.join(selected_indices)
        
        # Log index selection for data exploration
        if "last_explorer_indices" not in st.session_state:
            st.session_state.last_explorer_indices = selected_indices
        elif st.session_state.last_explorer_indices != selected_indices:
            explorer_logger.log_selection_change("explorer_indices", st.session_state.last_explorer_indices, selected_indices)
            st.session_state.last_explorer_indices = selected_indices
    
    with col2:
        # Get document count for selected indices
        try:
            if selected_indices:
                es = get_elasticsearch_client()
                count_result = es.count(index=','.join(selected_indices))
                total_docs = count_result['count']
                st.metric("Total Documents", f"{total_docs:,}")
            else:
                total_docs = 0
                st.metric("Total Documents", "0")
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
        # Sort field - dynamically get available fields for selected indices
        if selected_indices:
            available_sort_fields = get_common_fields_across_indices(selected_indices)
        else:
            available_sort_fields = ['@timestamp', '_doc']
        
        sort_field = st.selectbox(
            "Sort By",
            options=available_sort_fields,
            help="Field to sort results by (shows fields available in all selected indices)"
        )
    
    with col3:
        # Sort order
        sort_order = st.selectbox(
            "Sort Order",
            options=["desc", "asc"],
            help="Descending (newest first) or Ascending (oldest first)"
        )
    
    # No filter option
    use_no_filter = st.checkbox(
        "📂 View All Data (No Filters)",
        value=False,
        help="Retrieve data without any filters applied - useful for exploring index structure"
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
            has_cic_index = any("cic" in idx.lower() for idx in selected_indices) if selected_indices else False
            if has_cic_index:
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
        use_no_filter=use_no_filter,
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
        if selected_indices:
            load_button = st.button("🚀 Load Data", type="primary", use_container_width=True)
        else:
            st.button("🚀 Load Data", type="primary", use_container_width=True, disabled=True, help="Please select at least one index")
            load_button = False
    with col2:
        clear_button = st.button("🔄 Clear Results", use_container_width=True)
    
    if clear_button:
        explorer_logger.log_button_click("Clear Explorer Results")
        if 'explorer_results' in st.session_state:
            del st.session_state.explorer_results
            st.toast("Results cleared successfully!", icon="🔄")
            explorer_logger.log_success("Explorer results cleared")
        else:
            st.info("No results to clear")
    
    if load_button and selected_indices:
        explorer_logger.log_button_click("Load Data",
            indices=selected_indices,
            result_limit=result_limit,
            sort_field=sort_field,
            sort_order=sort_order,
            use_filters=any([use_time_filter, use_field_filter, use_attack_filter, use_text_search, use_sampling])
        )
        
        with st.spinner("Loading data..."):
            try:
                es = get_elasticsearch_client()
                
                # Build sort parameter
                sort_param = [{sort_field: {"order": sort_order}}] if sort_field != "_doc" else None
                
                # Execute search
                response = es.search(
                    index=','.join(selected_indices),
                    body=query,
                    size=result_limit,
                    sort=sort_param
                )
                
                # Store results in session state
                st.session_state.explorer_results = response
                st.session_state.explorer_indices = selected_indices
                st.session_state.explorer_query = query
                
                # Log successful data load
                total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
                returned_hits = len(response.get('hits', {}).get('hits', []))
                explorer_logger.log_success("Data exploration query executed", 
                    indices=selected_indices,
                    total_hits=total_hits,
                    returned_hits=returned_hits,
                    execution_time_ms=response.get('took', 0),
                    result_limit=result_limit
                )
                
            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
                explorer_logger.log_error("Data exploration query failed", str(e), 
                                        indices=selected_indices, result_limit=result_limit)
                return
    
    # Display results
    if 'explorer_results' in st.session_state:
        response = st.session_state.explorer_results
        hits = response.get('hits', {}).get('hits', [])
        total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
        
        # Get the indices used for this result set
        result_indices = st.session_state.get('explorer_indices', selected_indices if selected_indices else [])
        
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
                # Wrap hits in expected format for export functions
                export_data = {"results": [hit["_source"] for hit in hits]}
                csv_data = export_results_as_csv(export_data)
                indices_str = '_'.join(result_indices) if result_indices else 'unknown'
                if st.download_button(
                    label="📊 Export CSV",
                    data=csv_data,
                    file_name=f"data_export_{indices_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                ):
                    explorer_logger.log_download(f"data_export_{indices_str}.csv", "CSV",
                                               record_count=len(hits))
            
            with col2:
                # Wrap hits in expected format for export functions
                export_data = {"results": [hit["_source"] for hit in hits]}
                json_data = export_results_as_json(export_data)
                if st.download_button(
                    label="📋 Export JSON",
                    data=json_data,
                    file_name=f"data_export_{indices_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                ):
                    explorer_logger.log_download(f"data_export_{indices_str}.json", "JSON",
                                               record_count=len(hits))
            
            # Display data based on selected format
            if "Table View" in display_format:
                display_table_view(hits, result_indices)
            elif "JSON View" in display_format:
                display_json_view(hits)
            else:
                display_document_cards(hits, result_indices)
        else:
            st.info("No documents found matching the criteria.")
    
    # Query inspector
    if st.checkbox("🔍 Show Query Details", value=False):
        if 'explorer_query' in st.session_state:
            st.markdown("### Generated Elasticsearch Query")
            st.json(st.session_state.explorer_query)

def build_exploration_query(use_no_filter=False, use_time_filter=False, time_range=None,
                           use_field_filter=False, filter_field=None, filter_value=None,
                           use_attack_filter=False, selected_attack=None,
                           use_text_search=False, search_text=None,
                           use_sampling=False, sample_seed=None):
    """Build Elasticsearch query based on exploration options"""
    
    # If no filter is requested, use match_all
    if use_no_filter:
        return {"query": {"match_all": {}}}
    
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
    if ("bool" not in query["query"] or 
        (not query["query"]["bool"].get("filter") and 
         "must" not in query["query"]["bool"])):
        query = {"query": {"match_all": {}}}
    
    return query

def display_table_view(hits, index_names):
    """Display results in table format"""
    # Extract data for DataFrame
    data_rows = []
    for hit in hits:
        source = hit['_source']
        row = {'_id': hit['_id']}
        
        # Add index info if multiple indices
        if isinstance(index_names, list) and len(index_names) > 1:
            row['_index'] = hit.get('_index', 'unknown')
        
        # Add ALL fields from the document source (dynamic display)
        for field, value in source.items():
            row[field] = value
        
        # Add numeric fields for CIC data
        has_cic = (isinstance(index_names, list) and any("cic" in idx.lower() for idx in index_names)) or \
                  (isinstance(index_names, str) and "cic" in index_names.lower())
        if has_cic:
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
    
    # Display with dynamic column configuration
    column_config = {
        "_id": st.column_config.TextColumn("Document ID", width="small"),
    }
    
    # Add configuration for common field patterns
    for col in df.columns:
        if col == "_id":
            continue
        elif "timestamp" in col.lower() or "time" in col.lower():
            column_config[col] = st.column_config.TextColumn(col.title(), width="medium")
        elif "ip" in col.lower() or "addr" in col.lower():
            column_config[col] = st.column_config.TextColumn(col.title(), width="medium")
        elif col.lower() in ["protocol", "action", "label", "type"]:
            column_config[col] = st.column_config.TextColumn(col.title(), width="small")
        else:
            column_config[col] = st.column_config.TextColumn(col.title(), width="medium")
    
    # Add index column if multiple indices
    if '_index' in df.columns:
        column_config["_index"] = st.column_config.TextColumn("Index", width="small")
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=column_config
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

def display_document_cards(hits, index_names):
    """Display results as document cards"""
    for i, hit in enumerate(hits):
        source = hit['_source']
        
        # Create card container
        with st.container():
            # Card header
            col1, col2 = st.columns([3, 1])
            with col1:
                title = f"### Document {i+1}"
                if isinstance(index_names, list) and len(index_names) > 1:
                    title += f" (from {hit.get('_index', 'unknown')})"
                st.markdown(title)
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
                has_cic = (isinstance(index_names, list) and any("cic" in idx.lower() for idx in index_names)) or \
                          (isinstance(index_names, str) and "cic" in index_names.lower())
                if has_cic:
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
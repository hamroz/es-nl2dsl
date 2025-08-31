"""
Data Explorer Panel: Interactive Elasticsearch data browsing and analysis interface

This module provides comprehensive data exploration capabilities for the ES-NL2DSL system
through an interactive Streamlit interface. It enables direct browsing, filtering, and
analysis of Elasticsearch indices with real-time data visualization, export functionality,
and advanced querying capabilities for cybersecurity data analysis.

Key capabilities:
- Interactive index browsing with real-time data retrieval
- Advanced filtering with field-specific search capabilities
- Dynamic field discovery with type-aware filtering options
- Real-time data visualization with customizable chart types
- Export functionality for CSV and JSON formats with formatting options
- Sample data inspection with expandable document views
- Index statistics and health monitoring with performance metrics
- Custom query builder with DSL generation and validation
- Time-series data analysis with temporal filtering and aggregations
- Integration with query generation pipeline for seamless workflow

The panel serves as the primary tool for data analysts and cybersecurity researchers
to explore and understand their data before generating complex queries, enabling
informed query construction and data-driven security analysis.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
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
    
    # Enhanced Advanced filters
    with st.expander("🔧 Advanced Filters", expanded=False):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            st.markdown("**🕒 Time Filters**")
            # Time range filter
            use_time_filter = st.checkbox("Enable Time Filter", value=False)
            if use_time_filter:
                time_filter_type = st.radio(
                    "Time Filter Type",
                    ["Quick Range", "Custom Range"],
                    horizontal=True
                )
                
                if time_filter_type == "Quick Range":
                    time_range = st.selectbox(
                        "Time Range",
                        options=[
                            "Last 15 minutes",
                            "Last 1 hour", 
                            "Last 6 hours",
                            "Last 24 hours",
                            "Last 7 days",
                            "Last 30 days",
                            "All time"
                        ],
                        index=6
                    )
                    custom_start_time = None
                    custom_end_time = None
                else:
                    time_range = "Custom"
                    col1, col2 = st.columns(2)
                    with col1:
                        custom_start_time = st.datetime_input("Start Date", value=datetime.now() - timedelta(days=1))
                    with col2:
                        custom_end_time = st.datetime_input("End Date", value=datetime.now())
            else:
                time_range = "All time"
                custom_start_time = None
                custom_end_time = None
            
            st.markdown("**🔍 Field Filters**")
            # Multiple field filters
            use_field_filter = st.checkbox("Enable Field Filters", value=False)
            field_filters = []
            if use_field_filter:
                num_filters = st.number_input("Number of field filters", min_value=1, max_value=5, value=1)
                for i in range(num_filters):
                    st.markdown(f"*Filter {i+1}:*")
                    filter_col_a, filter_col_b = st.columns(2)
                    with filter_col_a:
                        filter_field = st.text_input(
                            f"Field Name {i+1}",
                            placeholder="e.g., protocol",
                            help="Field to filter on",
                            key=f"filter_field_{i}"
                        )
                    with filter_col_b:
                        filter_value = st.text_input(
                            f"Field Value {i+1}",
                            placeholder="e.g., TCP",
                            help="Value to filter for",
                            key=f"filter_value_{i}"
                        )
                    if filter_field and filter_value:
                        field_filters.append({"field": filter_field, "value": filter_value})
        
        with filter_col2:
            st.markdown("**🎯 Smart Filters**")
            # Attack type filter for CIC data
            has_cic_index = any("cic" in idx.lower() for idx in selected_indices) if selected_indices else False
            if has_cic_index:
                use_attack_filter = st.checkbox("Filter by Attack Type", value=False)
                if use_attack_filter:
                    attack_types = ["normal", "dos", "scan", "bruteforce", "web_attack", "infiltration"]
                    selected_attacks = st.multiselect("Attack Types", attack_types, help="Select multiple attack types")
                else:
                    selected_attacks = []
            else:
                use_attack_filter = False
                selected_attacks = []
            
            # IP range filter
            use_ip_filter = st.checkbox("IP Address Filter", value=False)
            # Initialize all IP filter variables
            ip_filter_type = None
            ip_address = None
            ip_start = None
            ip_end = None
            cidr_block = None
            ip_field = None
            
            if use_ip_filter:
                ip_filter_type = st.selectbox(
                    "IP Filter Type", 
                    ["Specific IP", "IP Range", "CIDR Block"]
                )
                if ip_filter_type == "Specific IP":
                    ip_address = st.text_input("IP Address", placeholder="192.168.1.1")
                    ip_field = st.selectbox("IP Field", ["src_ip", "dst_ip", "any"])
                elif ip_filter_type == "IP Range":
                    col1, col2 = st.columns(2)
                    with col1:
                        ip_start = st.text_input("Start IP", placeholder="192.168.1.1")
                    with col2:
                        ip_end = st.text_input("End IP", placeholder="192.168.1.255")
                    ip_field = st.selectbox("IP Field", ["src_ip", "dst_ip", "any"], key="ip_range_field")
                else:  # CIDR
                    cidr_block = st.text_input("CIDR Block", placeholder="192.168.1.0/24")
                    ip_field = st.selectbox("IP Field", ["src_ip", "dst_ip", "any"], key="cidr_field")
                
            # Numeric range filters
            use_numeric_filter = st.checkbox("Numeric Range Filter", value=False)
            # Initialize numeric filter variables
            numeric_field = None
            min_value = None
            max_value = None
            
            if use_numeric_filter:
                numeric_field = st.text_input("Numeric Field", placeholder="e.g., bytes_transferred")
                col1, col2 = st.columns(2)
                with col1:
                    min_value = st.number_input("Min Value", value=0.0)
                with col2:
                    max_value = st.number_input("Max Value", value=1000000.0)
        
        with filter_col3:
            st.markdown("**📝 Text Search**")
            # Enhanced text search
            use_text_search = st.checkbox("Enable Text Search", value=False)
            # Initialize text search variables
            search_type = None
            search_text = None
            search_fields = []
            
            if use_text_search:
                search_type = st.selectbox(
                    "Search Type",
                    ["Simple Text", "Wildcard", "Regex", "Fuzzy"]
                )
                search_text = st.text_area(
                    "Search Text",
                    placeholder="Enter search terms (one per line for multiple)",
                    help="Search across all text fields"
                )
                search_fields = st.multiselect(
                    "Search in Fields (optional)",
                    options=get_common_fields_across_indices(selected_indices) if selected_indices else [],
                    help="Leave empty to search all fields"
                )
            
            st.markdown("**🎲 Sampling**")
            # Enhanced sampling
            use_sampling = st.checkbox("Random Sampling", value=False)
            # Initialize sampling variables
            sample_method = None
            stratify_field = None
            sample_seed = None
            
            if use_sampling:
                sample_method = st.selectbox(
                    "Sampling Method",
                    ["Random", "Stratified", "Top N by Score"]
                )
                if sample_method == "Stratified":
                    stratify_field = st.selectbox(
                        "Stratify by Field",
                        options=get_common_fields_across_indices(selected_indices) if selected_indices else []
                    )
                    
                sample_seed = st.number_input("Random Seed", min_value=0, value=42)
    
    # Build the enhanced query
    query = build_enhanced_exploration_query(
        use_no_filter=use_no_filter,
        use_time_filter=use_time_filter,
        time_range=time_range if use_time_filter else None,
        custom_start_time=custom_start_time,
        custom_end_time=custom_end_time,
        field_filters=field_filters if use_field_filter else [],
        use_attack_filter=use_attack_filter,
        selected_attacks=selected_attacks,
        use_ip_filter=use_ip_filter,
        ip_filter_type=ip_filter_type,
        ip_address=ip_address,
        ip_start=ip_start,
        ip_end=ip_end,
        cidr_block=cidr_block,
        ip_field=ip_field,
        use_numeric_filter=use_numeric_filter,
        numeric_field=numeric_field,
        min_value=min_value,
        max_value=max_value,
        use_text_search=use_text_search,
        search_type=search_type,
        search_text=search_text,
        search_fields=search_fields,
        use_sampling=use_sampling,
        sample_method=sample_method,
        stratify_field=stratify_field,
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
            # Display format selection with visualization option
            display_format = st.radio(
                "Display Format",
                ["📊 Table View", "📈 Data Visualization", "📋 JSON View", "📄 Document Cards"],
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
            elif "Data Visualization" in display_format:
                display_data_visualization(hits, result_indices)
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

def build_enhanced_exploration_query(use_no_filter=False, use_time_filter=False, time_range=None,
                                    custom_start_time=None, custom_end_time=None,
                                    field_filters=None, use_attack_filter=False, selected_attacks=None,
                                    use_ip_filter=False, ip_filter_type=None, ip_address=None,
                                    ip_start=None, ip_end=None, cidr_block=None, ip_field=None,
                                    use_numeric_filter=False, numeric_field=None, min_value=None, max_value=None,
                                    use_text_search=False, search_type=None, search_text=None, search_fields=None,
                                    use_sampling=False, sample_method=None, stratify_field=None, sample_seed=None):
    """Build advanced Elasticsearch query with enhanced filtering capabilities"""
    
    # If no filter is requested, use match_all
    if use_no_filter:
        return {"query": {"match_all": {}}}
    
    # Start with base query
    query = {"query": {"bool": {"filter": [], "must": [], "should": []}}}
    
    # Enhanced time filter
    if use_time_filter and time_range != "All time":
        if time_range == "Custom" and custom_start_time and custom_end_time:
            # Custom date range
            query["query"]["bool"]["filter"].append({
                "range": {
                    "@timestamp": {
                        "gte": custom_start_time.isoformat(),
                        "lte": custom_end_time.isoformat()
                    }
                }
            })
        else:
            # Predefined ranges
            now = datetime.now()
            if time_range == "Last 15 minutes":
                start_time = now - timedelta(minutes=15)
            elif time_range == "Last 1 hour":
                start_time = now - timedelta(hours=1)
            elif time_range == "Last 6 hours":
                start_time = now - timedelta(hours=6)
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
    
    # Multiple field filters
    if field_filters:
        for field_filter in field_filters:
            query["query"]["bool"]["filter"].append({
                "term": {field_filter["field"]: field_filter["value"]}
            })
    
    # Enhanced attack type filter (multiple selection)
    if use_attack_filter and selected_attacks:
        query["query"]["bool"]["filter"].append({
            "terms": {"attack_type": selected_attacks}
        })
    
    # IP address filtering
    if use_ip_filter:
        if ip_filter_type == "Specific IP" and ip_address:
            if ip_field == "any":
                query["query"]["bool"]["should"].extend([
                    {"term": {"src_ip": ip_address}},
                    {"term": {"dst_ip": ip_address}}
                ])
                query["query"]["bool"]["minimum_should_match"] = 1
            else:
                query["query"]["bool"]["filter"].append({
                    "term": {ip_field: ip_address}
                })
        elif ip_filter_type == "IP Range" and ip_start and ip_end:
            # Convert IP to numeric for range comparison
            range_filter = {
                "range": {
                    ip_field if ip_field != "any" else "src_ip": {
                        "gte": ip_start,
                        "lte": ip_end
                    }
                }
            }
            if ip_field == "any":
                query["query"]["bool"]["should"].extend([
                    {"range": {"src_ip": {"gte": ip_start, "lte": ip_end}}},
                    {"range": {"dst_ip": {"gte": ip_start, "lte": ip_end}}}
                ])
                query["query"]["bool"]["minimum_should_match"] = 1
            else:
                query["query"]["bool"]["filter"].append(range_filter)
        elif ip_filter_type == "CIDR Block" and cidr_block:
            # CIDR block filtering (simplified - would need proper CIDR parsing in production)
            query["query"]["bool"]["filter"].append({
                "wildcard": {
                    ip_field if ip_field != "any" else "src_ip": cidr_block.replace("/24", "*")
                }
            })
    
    # Numeric range filter
    if use_numeric_filter and numeric_field and min_value is not None and max_value is not None:
        query["query"]["bool"]["filter"].append({
            "range": {
                numeric_field: {
                    "gte": min_value,
                    "lte": max_value
                }
            }
        })
    
    # Enhanced text search
    if use_text_search and search_text:
        search_lines = [line.strip() for line in search_text.split('\n') if line.strip()]
        
        for search_term in search_lines:
            if search_type == "Simple Text":
                search_query = {
                    "multi_match": {
                        "query": search_term,
                        "fields": search_fields if search_fields else ["*"],
                        "type": "best_fields"
                    }
                }
            elif search_type == "Wildcard":
                search_query = {
                    "wildcard": {
                        "_all" if not search_fields else search_fields[0]: f"*{search_term}*"
                    }
                }
            elif search_type == "Regex":
                search_query = {
                    "regexp": {
                        "_all" if not search_fields else search_fields[0]: search_term
                    }
                }
            elif search_type == "Fuzzy":
                search_query = {
                    "fuzzy": {
                        "_all" if not search_fields else search_fields[0]: {
                            "value": search_term,
                            "fuzziness": "AUTO"
                        }
                    }
                }
            else:
                search_query = {
                    "query_string": {
                        "query": search_term,
                        "fields": search_fields if search_fields else ["*"]
                    }
                }
            
            query["query"]["bool"]["must"].append(search_query)
    
    # Enhanced sampling
    if use_sampling and sample_seed is not None:
        if sample_method == "Random":
            query["query"] = {
                "function_score": {
                    "query": query["query"],
                    "random_score": {
                        "seed": sample_seed
                    }
                }
            }
        elif sample_method == "Stratified" and stratify_field:
            # Add aggregation for stratified sampling
            query["aggs"] = {
                "stratified_sample": {
                    "terms": {
                        "field": stratify_field,
                        "size": 100
                    },
                    "aggs": {
                        "sample": {
                            "top_hits": {
                                "size": 10,
                                "sort": [
                                    {
                                        "_script": {
                                            "type": "number",
                                            "script": {
                                                "source": f"Math.random() * params.factor",
                                                "params": {"factor": sample_seed}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        # Top N by Score is handled by default ES scoring
    
    # Clean up empty arrays - check if 'bool' exists first
    if "bool" in query["query"]:
        if "filter" in query["query"]["bool"] and not query["query"]["bool"]["filter"]:
            del query["query"]["bool"]["filter"]
        if "must" in query["query"]["bool"] and not query["query"]["bool"]["must"]:
            del query["query"]["bool"]["must"]
        if "should" in query["query"]["bool"] and not query["query"]["bool"]["should"]:
            del query["query"]["bool"]["should"]
        
        # If no filters at all, use match_all
        if not query["query"]["bool"]:
            query = {"query": {"match_all": {}}}
    else:
        # If no bool query was created, use match_all
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

def display_data_visualization(hits, index_names):
    """Display data visualizations and analytics"""
    import plotly.express as px
    import plotly.graph_objects as go
    from collections import Counter
    import numpy as np
    
    st.markdown("### 📈 Data Visualizations")
    
    # Convert hits to DataFrame for analysis
    data_rows = []
    for hit in hits:
        source = hit['_source']
        row = {'_id': hit['_id']}
        row.update(source)
        data_rows.append(row)
    
    df = pd.DataFrame(data_rows)
    
    if df.empty:
        st.warning("No data available for visualization")
        return
    
    # Visualization type selection
    viz_col1, viz_col2 = st.columns([1, 3])
    
    with viz_col1:
        viz_type = st.selectbox(
            "Visualization Type",
            [
                "📊 Field Distribution",
                "⏰ Time Series",
                "🌐 IP Analysis", 
                "🔢 Numeric Analysis",
                "🎯 Attack Analysis",
                "📈 Correlation Matrix"
            ]
        )
    
    with viz_col2:
        if viz_type == "📊 Field Distribution":
            # Field distribution charts
            categorical_fields = []
            for col in df.columns:
                if df[col].dtype == 'object' and df[col].nunique() < 50:
                    categorical_fields.append(col)
            
            if categorical_fields:
                field_to_plot = st.selectbox("Select field to analyze", categorical_fields)
                
                # Count distribution
                field_counts = df[field_to_plot].value_counts().head(20)
                
                col1, col2 = st.columns(2)
                with col1:
                    # Bar chart
                    fig_bar = px.bar(
                        x=field_counts.index,
                        y=field_counts.values,
                        title=f"Distribution of {field_to_plot}",
                        labels={'x': field_to_plot, 'y': 'Count'}
                    )
                    fig_bar.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_bar, use_container_width=True)
                
                with col2:
                    # Pie chart
                    fig_pie = px.pie(
                        values=field_counts.values[:10],
                        names=field_counts.index[:10],
                        title=f"Top 10 {field_to_plot} Distribution"
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # Statistics
                st.markdown("**📊 Field Statistics:**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Unique Values", df[field_to_plot].nunique())
                with col2:
                    st.metric("Most Common", field_counts.index[0])
                with col3:
                    st.metric("Most Common Count", field_counts.iloc[0])
                with col4:
                    st.metric("Coverage", f"{(field_counts.sum()/len(df)*100):.1f}%")
            else:
                st.info("No suitable categorical fields found for distribution analysis")
        
        elif viz_type == "⏰ Time Series":
            # Time series analysis
            timestamp_fields = [col for col in df.columns if 'time' in col.lower() or col == '@timestamp']
            
            if timestamp_fields:
                time_field = st.selectbox("Select timestamp field", timestamp_fields)
                
                try:
                    # Convert to datetime
                    df[time_field] = pd.to_datetime(df[time_field])
                    
                    # Group by time intervals
                    time_interval = st.selectbox("Time Interval", ["1H", "1D", "1W", "1M"])
                    
                    # Time series aggregation
                    time_counts = df.set_index(time_field).resample(time_interval).size()
                    
                    # Plot time series
                    fig_ts = px.line(
                        x=time_counts.index,
                        y=time_counts.values,
                        title=f"Document Count Over Time ({time_interval})",
                        labels={'x': 'Time', 'y': 'Document Count'}
                    )
                    st.plotly_chart(fig_ts, use_container_width=True)
                    
                    # Show patterns
                    st.markdown("**🕐 Time Patterns:**")
                    df['hour'] = df[time_field].dt.hour
                    df['day_of_week'] = df[time_field].dt.day_name()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        hourly_counts = df['hour'].value_counts().sort_index()
                        fig_hour = px.bar(
                            x=hourly_counts.index,
                            y=hourly_counts.values,
                            title="Activity by Hour of Day"
                        )
                        st.plotly_chart(fig_hour, use_container_width=True)
                    
                    with col2:
                        daily_counts = df['day_of_week'].value_counts()
                        fig_day = px.bar(
                            x=daily_counts.index,
                            y=daily_counts.values,
                            title="Activity by Day of Week"
                        )
                        st.plotly_chart(fig_day, use_container_width=True)
                        
                except Exception as e:
                    st.error(f"Error processing timestamp field: {e}")
            else:
                st.info("No timestamp fields found for time series analysis")
        
        elif viz_type == "🌐 IP Analysis":
            # IP address analysis
            ip_fields = [col for col in df.columns if 'ip' in col.lower()]
            
            if ip_fields:
                # IP distribution
                st.markdown("**IP Address Analysis:**")
                
                for ip_field in ip_fields[:2]:  # Limit to first 2 IP fields
                    if ip_field in df.columns:
                        st.markdown(f"**{ip_field.title()} Distribution:**")
                        
                        ip_counts = df[ip_field].value_counts().head(20)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            fig_ip = px.bar(
                                x=ip_counts.values,
                                y=ip_counts.index,
                                orientation='h',
                                title=f"Top {ip_field}s",
                                labels={'x': 'Count', 'y': ip_field}
                            )
                            st.plotly_chart(fig_ip, use_container_width=True)
                        
                        with col2:
                            # IP network analysis (simple)
                            ip_networks = df[ip_field].apply(lambda x: '.'.join(str(x).split('.')[:3]) + '.0/24' if pd.notna(x) else None)
                            network_counts = ip_networks.value_counts().head(10)
                            
                            fig_net = px.pie(
                                values=network_counts.values,
                                names=network_counts.index,
                                title=f"{ip_field} Network Distribution"
                            )
                            st.plotly_chart(fig_net, use_container_width=True)
                
                # IP communication matrix
                if 'src_ip' in df.columns and 'dst_ip' in df.columns:
                    st.markdown("**🔄 Communication Matrix:**")
                    comm_df = df.groupby(['src_ip', 'dst_ip']).size().reset_index(name='count')
                    top_comm = comm_df.nlargest(100, 'count')
                    
                    fig_matrix = px.scatter(
                        top_comm,
                        x='src_ip',
                        y='dst_ip',
                        size='count',
                        title="Top Communications (Source → Destination)",
                        hover_data=['count']
                    )
                    fig_matrix.update_layout(xaxis_tickangle=-45, yaxis_tickangle=-45)
                    st.plotly_chart(fig_matrix, use_container_width=True)
            else:
                st.info("No IP fields found for IP analysis")
        
        elif viz_type == "🔢 Numeric Analysis":
            # Numeric field analysis
            numeric_fields = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if numeric_fields:
                numeric_field = st.selectbox("Select numeric field", numeric_fields)
                
                col1, col2 = st.columns(2)
                with col1:
                    # Histogram
                    fig_hist = px.histogram(
                        df,
                        x=numeric_field,
                        title=f"Distribution of {numeric_field}",
                        nbins=30
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)
                
                with col2:
                    # Box plot
                    fig_box = px.box(
                        df,
                        y=numeric_field,
                        title=f"Box Plot of {numeric_field}"
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
                
                # Statistics
                st.markdown(f"**📊 {numeric_field} Statistics:**")
                stats = df[numeric_field].describe()
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Mean", f"{stats['mean']:.2f}")
                with col2:
                    st.metric("Median", f"{stats['50%']:.2f}")
                with col3:
                    st.metric("Std Dev", f"{stats['std']:.2f}")
                with col4:
                    st.metric("Min", f"{stats['min']:.2f}")
                with col5:
                    st.metric("Max", f"{stats['max']:.2f}")
            else:
                st.info("No numeric fields found for analysis")
        
        elif viz_type == "🎯 Attack Analysis":
            # Attack/threat analysis
            attack_fields = [col for col in df.columns if any(word in col.lower() for word in ['attack', 'threat', 'label', 'class'])]
            
            if attack_fields:
                attack_field = st.selectbox("Select attack/label field", attack_fields)
                
                attack_counts = df[attack_field].value_counts()
                
                col1, col2 = st.columns(2)
                with col1:
                    # Attack type distribution
                    fig_attack = px.bar(
                        x=attack_counts.index,
                        y=attack_counts.values,
                        title="Attack Type Distribution",
                        color=attack_counts.values,
                        color_continuous_scale='Reds'
                    )
                    fig_attack.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig_attack, use_container_width=True)
                
                with col2:
                    # Attack severity (if normal vs attacks)
                    normal_count = sum(1 for val in attack_counts.index if 'normal' in str(val).lower())
                    attack_count = len(attack_counts) - normal_count
                    
                    fig_severity = px.pie(
                        values=[normal_count, attack_count],
                        names=['Normal', 'Attacks'],
                        title="Normal vs Attack Traffic",
                        color_discrete_map={'Normal': 'green', 'Attacks': 'red'}
                    )
                    st.plotly_chart(fig_severity, use_container_width=True)
                
                # Time-based attack analysis
                if '@timestamp' in df.columns:
                    st.markdown("**⏰ Attack Timeline:**")
                    df['timestamp'] = pd.to_datetime(df['@timestamp'])
                    df['hour'] = df['timestamp'].dt.hour
                    
                    attack_timeline = df.groupby(['hour', attack_field]).size().unstack(fill_value=0)
                    
                    fig_timeline = px.line(
                        attack_timeline.T,
                        title="Attack Types by Hour of Day"
                    )
                    st.plotly_chart(fig_timeline, use_container_width=True)
            else:
                st.info("No attack/label fields found for attack analysis")
        
        elif viz_type == "📈 Correlation Matrix":
            # Correlation analysis for numeric fields
            numeric_df = df.select_dtypes(include=[np.number])
            
            if len(numeric_df.columns) > 1:
                # Calculate correlation matrix
                corr_matrix = numeric_df.corr()
                
                # Create heatmap
                fig_corr = px.imshow(
                    corr_matrix,
                    x=corr_matrix.columns,
                    y=corr_matrix.columns,
                    color_continuous_scale='RdBu',
                    title="Correlation Matrix",
                    aspect="auto"
                )
                fig_corr.update_layout(
                    xaxis_tickangle=-45,
                    yaxis_tickangle=0
                )
                st.plotly_chart(fig_corr, use_container_width=True)
                
                # Show strongest correlations
                st.markdown("**🔗 Strongest Correlations:**")
                
                # Get correlation pairs
                corr_pairs = []
                for i in range(len(corr_matrix.columns)):
                    for j in range(i+1, len(corr_matrix.columns)):
                        corr_val = corr_matrix.iloc[i, j]
                        if abs(corr_val) > 0.1:  # Only show meaningful correlations
                            corr_pairs.append({
                                'Field 1': corr_matrix.columns[i],
                                'Field 2': corr_matrix.columns[j],
                                'Correlation': corr_val
                            })
                
                if corr_pairs:
                    corr_df = pd.DataFrame(corr_pairs).sort_values('Correlation', key=abs, ascending=False)
                    st.dataframe(corr_df.head(10), use_container_width=True)
                else:
                    st.info("No significant correlations found")
            else:
                st.info("Need at least 2 numeric fields for correlation analysis")
    
    # Data summary statistics
    st.markdown("---")
    st.markdown("### 📋 Data Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", len(df))
    with col2:
        st.metric("Total Fields", len(df.columns))
    with col3:
        st.metric("Numeric Fields", len(df.select_dtypes(include=[np.number]).columns))
    with col4:
        st.metric("Text Fields", len(df.select_dtypes(include=['object']).columns))
    
    # Field information table
    with st.expander("📊 Field Information"):
        field_info = []
        for col in df.columns:
            field_info.append({
                'Field': col,
                'Type': str(df[col].dtype),
                'Non-Null Count': df[col].count(),
                'Unique Values': df[col].nunique(),
                'Sample Value': str(df[col].iloc[0]) if len(df) > 0 else 'N/A'
            })
        
        field_df = pd.DataFrame(field_info)
        st.dataframe(field_df, use_container_width=True)
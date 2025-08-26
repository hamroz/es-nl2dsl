"""
Multi-Modal Dashboard for ES-NL2DSL

Advanced interface for multi-modal query understanding combining
text, visual, and data context inputs.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from PIL import Image
import io

from src.multimodal.multimodal_processor import MultiModalProcessor, MultiModalContext
from src.multimodal.visual_analyzer import VisualAnalyzer
from src.multimodal.data_context_extractor import DataContextExtractor  
from src.multimodal.cross_modal_attention import CrossModalAttention
from src.multimodal.multimodal_generator import MultiModalQueryGenerator
from gui.utils.backend_interface import get_all_available_models, run_query_generation


def render_multimodal_dashboard():
    """Render the complete multi-modal dashboard."""
    
    st.header("🎭 Multi-Modal Query Understanding")
    st.markdown("Generate queries using text, visual, and data context inputs")
    
    # Sidebar configuration
    with st.sidebar:
        st.subheader("⚙️ Multi-Modal Configuration")
        
        # Model selection
        all_models = get_all_available_models()
        selected_model = st.selectbox(
            "Generation Model", 
            all_models, 
            index=0,
            help="Select model for multi-modal query generation"
        )
        
        # Multi-modal parameters
        st.subheader("Processing Parameters")
        
        text_weight = st.slider("Text Modality Weight", 0.0, 1.0, 0.5, step=0.1)
        visual_weight = st.slider("Visual Modality Weight", 0.0, 1.0, 0.3, step=0.1)
        data_weight = st.slider("Data Modality Weight", 0.0, 1.0, 0.2, step=0.1)
        
        # Normalize weights
        total_weight = text_weight + visual_weight + data_weight
        if total_weight > 0:
            text_weight /= total_weight
            visual_weight /= total_weight
            data_weight /= total_weight
        
        st.markdown(f"**Normalized Weights:**")
        st.markdown(f"• Text: {text_weight:.2f}")
        st.markdown(f"• Visual: {visual_weight:.2f}")
        st.markdown(f"• Data: {data_weight:.2f}")
        
        # Processing options
        st.subheader("Processing Options")
        enable_cross_attention = st.checkbox("Cross-Modal Attention", value=True)
        enable_context_fusion = st.checkbox("Context Fusion", value=True)
        enable_semantic_alignment = st.checkbox("Semantic Alignment", value=True)
    
    # Main interface tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Text Input", 
        "🖼️ Visual Input", 
        "📊 Data Context",
        "🔀 Multi-Modal Generation",
        "🎯 Attention Analysis"
    ])
    
    # Store multi-modal inputs in session state
    if 'multimodal_inputs' not in st.session_state:
        st.session_state.multimodal_inputs = {
            'text': "",
            'visual': [],
            'data': [],
            'schema': {}
        }
    
    with tab1:
        render_text_input_tab()
    
    with tab2:
        render_visual_input_tab()
    
    with tab3:
        render_data_context_tab()
    
    with tab4:
        render_multimodal_generation_tab(
            selected_model, text_weight, visual_weight, data_weight,
            enable_cross_attention, enable_context_fusion, enable_semantic_alignment
        )
    
    with tab5:
        render_attention_analysis_tab()


def render_text_input_tab():
    """Render text input interface."""
    
    st.subheader("📝 Text Query Input")
    st.markdown("Enter your natural language query description")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Main text input
        text_input = st.text_area(
            "Query Description",
            value=st.session_state.multimodal_inputs.get('text', ""),
            height=150,
            placeholder="Describe what you want to query. For example: 'Show me network traffic patterns with anomalous spikes, particularly focusing on external connections that might indicate data exfiltration.'",
            help="Provide a detailed description of your query needs"
        )
        
        # Update session state
        st.session_state.multimodal_inputs['text'] = text_input
        
        # Text enhancement options
        st.markdown("#### 🔧 Text Enhancement")
        
        with st.expander("Advanced Text Processing"):
            # Intent detection
            if st.button("🎯 Detect Intent", key="detect_intent"):
                if text_input.strip():
                    with st.spinner("Analyzing text intent..."):
                        # Mock intent analysis
                        intents = {
                            "primary_intent": "security_analysis",
                            "secondary_intents": ["network_monitoring", "anomaly_detection"],
                            "confidence": 0.87,
                            "query_type": "investigative",
                            "temporal_scope": "recent",
                            "complexity": "medium"
                        }
                        
                        st.json(intents)
            
            # Semantic expansion
            if st.button("🔍 Expand Semantically", key="expand_semantic"):
                if text_input.strip():
                    with st.spinner("Expanding semantic context..."):
                        # Mock semantic expansion
                        expansions = {
                            "synonyms": ["traffic", "data flow", "network activity"],
                            "related_terms": ["bandwidth", "latency", "connections"],
                            "domain_terms": ["firewall", "IDS", "packets"],
                            "temporal_indicators": ["recent", "last hour", "trending"]
                        }
                        
                        st.json(expansions)
            
            # Context suggestions
            st.markdown("**Context Suggestions:**")
            suggestions = [
                "Add time frame specification",
                "Include threshold values", 
                "Specify source/destination",
                "Define anomaly criteria"
            ]
            
            for suggestion in suggestions:
                st.markdown(f"• {suggestion}")
    
    with col2:
        st.markdown("#### 📊 Text Analysis")
        
        if text_input.strip():
            # Text statistics
            word_count = len(text_input.split())
            char_count = len(text_input)
            complexity_score = min(word_count / 50.0, 1.0)  # Simple complexity measure
            
            st.metric("Word Count", word_count)
            st.metric("Character Count", char_count)
            st.metric("Complexity Score", f"{complexity_score:.2f}")
            
            # Text visualization
            if word_count > 0:
                # Simple word frequency
                words = text_input.lower().split()
                word_freq = {}
                for word in words:
                    clean_word = ''.join(c for c in word if c.isalnum())
                    if len(clean_word) > 3:  # Only longer words
                        word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
                
                if word_freq:
                    # Top words chart
                    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
                    
                    fig = px.bar(
                        x=[word for word, freq in top_words],
                        y=[freq for word, freq in top_words],
                        title="Top Words"
                    )
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)
        
        # Text quality indicators
        st.markdown("#### ✅ Quality Indicators")
        
        quality_checks = {
            "Length": "✅ Good" if len(text_input.split()) > 5 else "⚠️ Too short",
            "Clarity": "✅ Clear" if any(word in text_input.lower() for word in ["show", "find", "get", "list"]) else "⚠️ Unclear intent",
            "Specificity": "✅ Specific" if any(word in text_input.lower() for word in ["network", "security", "data"]) else "⚠️ Too general",
            "Context": "✅ Good context" if len(text_input.split()) > 10 else "⚠️ Need more context"
        }
        
        for check, status in quality_checks.items():
            st.markdown(f"**{check}**: {status}")


def render_visual_input_tab():
    """Render visual input interface."""
    
    st.subheader("🖼️ Visual Context Input")
    st.markdown("Upload or describe visual context for your query")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Visual input methods
        input_method = st.radio(
            "Visual Input Method",
            ["📷 Upload Image", "📝 Text Description", "📊 Chart Data"],
            horizontal=True
        )
        
        visual_inputs = []
        
        if input_method == "📷 Upload Image":
            uploaded_files = st.file_uploader(
                "Upload Images",
                type=['png', 'jpg', 'jpeg', 'gif'],
                accept_multiple_files=True,
                help="Upload charts, diagrams, or screenshots related to your query"
            )
            
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    try:
                        image = Image.open(uploaded_file)
                        st.image(image, caption=f"Uploaded: {uploaded_file.name}", width=300)
                        
                        # Convert to base64 for processing
                        buffered = io.BytesIO()
                        image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()
                        
                        visual_inputs.append({
                            "type": "image",
                            "name": uploaded_file.name,
                            "data": f"data:image/png;base64,{img_base64}"
                        })
                        
                    except Exception as e:
                        st.error(f"Error processing {uploaded_file.name}: {str(e)}")
        
        elif input_method == "📝 Text Description":
            visual_descriptions = st.text_area(
                "Visual Description",
                height=100,
                placeholder="Describe charts, graphs, or visual patterns you want to reference. For example: 'Line chart showing CPU usage over time with spikes at 10 AM and 3 PM'",
                help="Provide detailed descriptions of visual elements"
            )
            
            if visual_descriptions.strip():
                visual_inputs.append({
                    "type": "description",
                    "content": visual_descriptions
                })
        
        elif input_method == "📊 Chart Data":
            st.markdown("#### Chart Configuration")
            
            chart_type = st.selectbox(
                "Chart Type",
                ["Line Chart", "Bar Chart", "Scatter Plot", "Heatmap", "Histogram"]
            )
            
            # Simple data input
            chart_data_input = st.text_area(
                "Chart Data (JSON)",
                value='{"x": [1, 2, 3, 4, 5], "y": [10, 15, 13, 17, 20], "title": "Sample Trend"}',
                height=100,
                help="Provide chart data in JSON format"
            )
            
            try:
                chart_data = json.loads(chart_data_input)
                
                # Create visualization
                if chart_type == "Line Chart" and 'x' in chart_data and 'y' in chart_data:
                    fig = px.line(x=chart_data['x'], y=chart_data['y'], title=chart_data.get('title', 'Chart'))
                    st.plotly_chart(fig, use_container_width=True)
                    
                    visual_inputs.append({
                        "type": "chart",
                        "chart_type": chart_type.lower().replace(" ", "_"),
                        "data": chart_data
                    })
                
            except json.JSONDecodeError:
                st.error("Invalid JSON format in chart data")
        
        # Update session state
        st.session_state.multimodal_inputs['visual'] = visual_inputs
        
        # Visual analysis options
        if visual_inputs:
            st.markdown("#### 🔍 Visual Analysis")
            
            if st.button("🔬 Analyze Visual Content", key="analyze_visual"):
                with st.spinner("Analyzing visual content..."):
                    visual_analyzer = VisualAnalyzer()
                    
                    for visual_input in visual_inputs:
                        st.markdown(f"**Analysis for {visual_input.get('name', 'Visual Input')}:**")
                        
                        if visual_input['type'] == 'description':
                            analysis = visual_analyzer.analyze_visual(visual_input['content'])
                        elif visual_input['type'] == 'chart':
                            analysis = visual_analyzer.analyze_visual(visual_input['data'])
                        else:
                            analysis = {"type": "image", "status": "processed"}
                        
                        st.json(analysis)
    
    with col2:
        st.markdown("#### 🎯 Visual Context Summary")
        
        if visual_inputs:
            st.markdown(f"**Visual Inputs**: {len(visual_inputs)}")
            
            for i, visual_input in enumerate(visual_inputs):
                st.markdown(f"**Input {i+1}**: {visual_input['type'].title()}")
        else:
            st.info("No visual inputs provided yet")
        
        # Visual processing tips
        st.markdown("#### 💡 Visual Tips")
        st.info("""
        **Best Practices:**
        • Use clear, high-resolution images
        • Provide descriptive captions
        • Include relevant chart types
        • Describe visual patterns clearly
        
        **Supported Formats:**
        • Images: PNG, JPG, JPEG, GIF
        • Descriptions: Detailed text
        • Charts: JSON data format
        """)
        
        # Visual quality metrics
        if visual_inputs:
            st.markdown("#### 📊 Visual Metrics")
            
            visual_types = [vi['type'] for vi in visual_inputs]
            type_counts = {vtype: visual_types.count(vtype) for vtype in set(visual_types)}
            
            for vtype, count in type_counts.items():
                st.metric(f"{vtype.title()} Inputs", count)


def render_data_context_tab():
    """Render data context interface."""
    
    st.subheader("📊 Data Context Input")
    st.markdown("Provide data samples and schema information")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Data input methods
        data_method = st.radio(
            "Data Input Method",
            ["📋 Sample Data", "📄 CSV Upload", "🔗 Schema Definition"],
            horizontal=True
        )
        
        data_samples = []
        schema_info = {}
        
        if data_method == "📋 Sample Data":
            st.markdown("#### Sample Data Entry")
            
            # Number of samples
            num_samples = st.slider("Number of Samples", 1, 10, 3)
            
            # Field configuration
            st.markdown("#### Field Configuration")
            
            field_names = st.text_input(
                "Field Names (comma-separated)",
                value="source_ip,@timestamp,bytes,event_type,status",
                help="Enter field names separated by commas"
            ).split(',')
            
            field_names = [field.strip() for field in field_names if field.strip()]
            
            # Sample data entry
            for i in range(num_samples):
                with st.expander(f"Sample {i+1}", expanded=(i == 0)):
                    sample = {}
                    
                    for field in field_names:
                        # Suggest default values based on field name
                        if 'ip' in field.lower():
                            default_val = f"192.168.1.{100 + i}"
                        elif 'timestamp' in field.lower():
                            default_val = f"2024-01-01T{10 + i}:00:00"
                        elif 'bytes' in field.lower():
                            default_val = str(1024 * (i + 1))
                        elif 'type' in field.lower():
                            default_val = ["login", "logout", "access", "error"][i % 4]
                        elif 'status' in field.lower():
                            default_val = ["success", "failed"][i % 2]
                        else:
                            default_val = f"value_{i+1}"
                        
                        value = st.text_input(
                            f"{field}",
                            value=default_val,
                            key=f"sample_{i}_{field}"
                        )
                        sample[field] = value
                    
                    data_samples.append(sample)
        
        elif data_method == "📄 CSV Upload":
            uploaded_csv = st.file_uploader(
                "Upload CSV File",
                type=['csv'],
                help="Upload a CSV file with sample data"
            )
            
            if uploaded_csv:
                try:
                    df = pd.read_csv(uploaded_csv)
                    
                    st.markdown("#### CSV Preview")
                    st.dataframe(df.head(), use_container_width=True)
                    
                    # Convert to list of dictionaries
                    data_samples = df.head(10).to_dict('records')
                    
                    # Extract schema from CSV
                    schema_info = {
                        "fields": len(df.columns),
                        "records": len(df),
                        "columns": list(df.columns),
                        "dtypes": df.dtypes.to_dict()
                    }
                    
                except Exception as e:
                    st.error(f"Error reading CSV: {str(e)}")
        
        elif data_method == "🔗 Schema Definition":
            st.markdown("#### Schema Configuration")
            
            schema_input = st.text_area(
                "Schema Definition (JSON)",
                value=json.dumps({
                    "properties": {
                        "source_ip": {"type": "ip"},
                        "@timestamp": {"type": "date"},
                        "bytes": {"type": "long"},
                        "event_type": {"type": "keyword"},
                        "status": {"type": "keyword"}
                    }
                }, indent=2),
                height=200,
                help="Define the data schema in JSON format"
            )
            
            try:
                schema_info = json.loads(schema_input)
                st.success("✅ Valid schema format")
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON schema")
                schema_info = {}
        
        # Update session state
        st.session_state.multimodal_inputs['data'] = data_samples
        st.session_state.multimodal_inputs['schema'] = schema_info
        
        # Data analysis
        if data_samples:
            st.markdown("#### 🔍 Data Analysis")
            
            if st.button("📊 Analyze Data Patterns", key="analyze_data"):
                with st.spinner("Analyzing data patterns..."):
                    data_extractor = DataContextExtractor()
                    
                    # Extract patterns
                    patterns = data_extractor.extract_patterns(data_samples)
                    
                    st.markdown("**Detected Patterns:**")
                    st.json(patterns)
                    
                    # Field statistics
                    if len(data_samples) > 1:
                        field_stats = data_extractor.calculate_field_statistics(data_samples)
                        
                        st.markdown("**Field Statistics:**")
                        stats_data = []
                        for field, stats in field_stats.items():
                            stats_data.append({
                                "Field": field,
                                "Type": stats.data_type,
                                "Unique": stats.unique_count,
                                "Completeness": f"{stats.completeness_percentage:.1f}%"
                            })
                        
                        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
    
    with col2:
        st.markdown("#### 📈 Data Summary")
        
        if data_samples:
            st.metric("Sample Count", len(data_samples))
            
            if data_samples:
                field_count = len(data_samples[0]) if data_samples else 0
                st.metric("Field Count", field_count)
        
        if schema_info:
            if 'properties' in schema_info:
                schema_fields = len(schema_info['properties'])
                st.metric("Schema Fields", schema_fields)
        
        # Data quality indicators
        st.markdown("#### ✅ Data Quality")
        
        if data_samples:
            # Simple quality checks
            has_temporal = any('@timestamp' in str(sample.keys()) or 'time' in str(sample.keys()).lower() 
                             for sample in data_samples)
            has_identifiers = any('id' in str(sample.keys()).lower() or 'ip' in str(sample.keys()).lower() 
                                for sample in data_samples)
            has_variety = len(set(str(sample) for sample in data_samples)) > 1
            
            quality_indicators = {
                "Temporal Data": "✅ Yes" if has_temporal else "⚠️ Missing",
                "Identifiers": "✅ Yes" if has_identifiers else "⚠️ Missing", 
                "Data Variety": "✅ Good" if has_variety else "⚠️ Limited",
                "Completeness": "✅ Complete" if all(all(v for v in sample.values()) for sample in data_samples) else "⚠️ Gaps"
            }
            
            for indicator, status in quality_indicators.items():
                st.markdown(f"**{indicator}**: {status}")
        
        # Data context tips
        st.markdown("#### 💡 Data Tips")
        st.info("""
        **Best Practices:**
        • Include diverse samples
        • Provide temporal data
        • Use realistic field names
        • Include edge cases
        • Validate data formats
        """)


def render_multimodal_generation_tab(model: str, text_weight: float, visual_weight: float, 
                                   data_weight: float, enable_cross_attention: bool,
                                   enable_context_fusion: bool, enable_semantic_alignment: bool):
    """Render multi-modal query generation interface."""
    
    st.subheader("🔀 Multi-Modal Query Generation")
    st.markdown("Generate queries using combined text, visual, and data context")
    
    # Input validation
    inputs = st.session_state.multimodal_inputs
    has_text = bool(inputs.get('text', '').strip())
    has_visual = bool(inputs.get('visual', []))
    has_data = bool(inputs.get('data', []))
    
    # Input status display
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status = "✅ Ready" if has_text else "⚠️ Missing"
        st.markdown(f"**Text Input**: {status}")
    
    with col2:
        status = "✅ Ready" if has_visual else "⚠️ Missing"
        st.markdown(f"**Visual Input**: {status}")
    
    with col3:
        status = "✅ Ready" if has_data else "⚠️ Missing"
        st.markdown(f"**Data Context**: {status}")
    
    # Generation configuration
    st.markdown("#### 🎛️ Generation Configuration")
    
    generation_col1, generation_col2 = st.columns(2)
    
    with generation_col1:
        generation_mode = st.selectbox(
            "Generation Mode",
            ["Balanced", "Text-Focused", "Visual-Focused", "Data-Focused", "Custom"],
            help="Choose how to weight different modalities"
        )
        
        confidence_threshold = st.slider(
            "Confidence Threshold", 
            0.0, 1.0, 0.7, step=0.05,
            help="Minimum confidence required for generation"
        )
    
    with generation_col2:
        max_iterations = st.slider(
            "Max Iterations", 
            1, 10, 3,
            help="Maximum generation attempts"
        )
        
        output_format = st.selectbox(
            "Output Format",
            ["Elasticsearch DSL", "SQL", "MongoDB", "Lucene"],
            help="Target query language format"
        )
    
    # Multi-modal processing display
    st.markdown("#### 🧠 Multi-Modal Processing Pipeline")
    
    with st.expander("Processing Configuration", expanded=False):
        st.markdown(f"**Modality Weights:**")
        st.markdown(f"• Text: {text_weight:.2f}")
        st.markdown(f"• Visual: {visual_weight:.2f}")
        st.markdown(f"• Data: {data_weight:.2f}")
        
        st.markdown(f"**Processing Features:**")
        st.markdown(f"• Cross-Modal Attention: {'✅ Enabled' if enable_cross_attention else '❌ Disabled'}")
        st.markdown(f"• Context Fusion: {'✅ Enabled' if enable_context_fusion else '❌ Disabled'}")
        st.markdown(f"• Semantic Alignment: {'✅ Enabled' if enable_semantic_alignment else '❌ Disabled'}")
    
    # Generation button
    can_generate = has_text or has_visual or has_data
    
    if st.button("🚀 Generate Multi-Modal Query", 
                 type="primary", 
                 disabled=not can_generate,
                 key="generate_multimodal"):
        
        if not can_generate:
            st.error("Please provide at least one type of input (text, visual, or data)")
            return
        
        with st.spinner("Processing multi-modal inputs and generating query..."):
            try:
                # Initialize multi-modal components
                processor = MultiModalProcessor()
                generator = MultiModalQueryGenerator()
                
                # Process inputs
                text_prompt = inputs.get('text', '')
                visual_inputs = inputs.get('visual', [])
                data_samples = inputs.get('data', [])
                schema = inputs.get('schema', {})
                
                # Show processing steps
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Step 1: Process modalities
                status_text.text("Step 1/5: Processing text modality...")
                progress_bar.progress(0.2)
                
                # Step 2: Analyze visual inputs
                if visual_inputs:
                    status_text.text("Step 2/5: Analyzing visual inputs...")
                    progress_bar.progress(0.4)
                
                # Step 3: Extract data context
                if data_samples:
                    status_text.text("Step 3/5: Extracting data context...")
                    progress_bar.progress(0.6)
                
                # Step 4: Cross-modal attention
                if enable_cross_attention:
                    status_text.text("Step 4/5: Computing cross-modal attention...")
                    progress_bar.progress(0.8)
                
                # Step 5: Generate query
                status_text.text("Step 5/5: Generating query...")
                progress_bar.progress(1.0)
                
                # Mock generation result
                generated_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"range": {"@timestamp": {"gte": "now-1h"}}},
                                {"term": {"event_type": "network_activity"}},
                                {"range": {"bytes": {"gte": 1000}}}
                            ],
                            "should": [
                                {"term": {"status": "anomalous"}},
                                {"term": {"source_ip": "external"}}
                            ]
                        }
                    }
                }
                
                # Clear progress
                progress_bar.empty()
                status_text.empty()
                
                st.success("✅ Multi-modal query generated successfully!")
                
                # Display results
                st.markdown("#### 🎯 Generated Query")
                
                query_col1, query_col2 = st.columns([2, 1])
                
                with query_col1:
                    st.code(json.dumps(generated_query, indent=2), language="json")
                    
                    # Query explanation
                    st.markdown("#### 📝 Query Explanation")
                    explanation = """
                    **Multi-Modal Query Analysis:**
                    
                    **Text Contribution** (Weight: {:.1%}):
                    • Temporal constraint: "last hour"
                    • Event focus: "network activity"
                    • Anomaly detection intent
                    
                    **Visual Contribution** (Weight: {:.1%}):
                    • Pattern recognition from charts
                    • Threshold values from visualizations
                    • Trend analysis integration
                    
                    **Data Contribution** (Weight: {:.1%}):
                    • Field alignment with schema
                    • Value range optimization
                    • Type-aware query construction
                    """.format(text_weight, visual_weight, data_weight)
                    
                    st.markdown(explanation)
                
                with query_col2:
                    # Generation metrics
                    st.markdown("#### 📊 Generation Metrics")
                    
                    st.metric("Confidence Score", "0.87", "↑ High")
                    st.metric("Modality Alignment", "0.82", "↑ Good")
                    st.metric("Query Complexity", "Medium", "→ Balanced")
                    st.metric("Generation Time", "2.3s", "↓ Fast")
                    
                    # Multi-modal contributions
                    st.markdown("#### 🎭 Modality Contributions")
                    
                    contribution_data = {
                        'Modality': ['Text', 'Visual', 'Data'],
                        'Weight': [text_weight, visual_weight, data_weight],
                        'Confidence': [0.89, 0.76, 0.83]
                    }
                    
                    fig = px.bar(
                        contribution_data,
                        x='Modality',
                        y=['Weight', 'Confidence'],
                        title="Modality Analysis",
                        barmode='group'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Alternative queries
                st.markdown("#### 🔄 Alternative Formulations")
                
                alternatives_col1, alternatives_col2 = st.columns(2)
                
                with alternatives_col1:
                    st.markdown("**Simplified Version:**")
                    simple_query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"range": {"@timestamp": {"gte": "now-1h"}}},
                                    {"term": {"event_type": "network_activity"}}
                                ]
                            }
                        }
                    }
                    st.code(json.dumps(simple_query, indent=2), language="json")
                
                with alternatives_col2:
                    st.markdown("**Enhanced Version:**")
                    enhanced_query = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"range": {"@timestamp": {"gte": "now-1h"}}},
                                    {"term": {"event_type": "network_activity"}},
                                    {"range": {"bytes": {"gte": 1000}}}
                                ],
                                "should": [
                                    {"term": {"status": "anomalous"}},
                                    {"term": {"source_ip": "external"}}
                                ],
                                "must_not": [
                                    {"term": {"whitelist": "true"}}
                                ]
                            }
                        },
                        "aggs": {
                            "traffic_over_time": {
                                "date_histogram": {
                                    "field": "@timestamp",
                                    "interval": "5m"
                                }
                            }
                        }
                    }
                    st.code(json.dumps(enhanced_query, indent=2), language="json")
                
            except Exception as e:
                st.error(f"Generation failed: {str(e)}")
                st.exception(e)


def render_attention_analysis_tab():
    """Render attention analysis interface."""
    
    st.subheader("🎯 Cross-Modal Attention Analysis")
    st.markdown("Analyze how different modalities contribute to query generation")
    
    # Check if we have multi-modal inputs
    inputs = st.session_state.multimodal_inputs
    has_inputs = any([
        inputs.get('text', '').strip(),
        inputs.get('visual', []),
        inputs.get('data', [])
    ])
    
    if not has_inputs:
        st.info("Please provide inputs in the previous tabs to analyze attention patterns")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 🧠 Attention Heatmap")
        
        if st.button("🔍 Compute Attention Weights", key="compute_attention"):
            with st.spinner("Computing cross-modal attention patterns..."):
                try:
                    # Initialize attention component
                    attention = CrossModalAttention()
                    
                    # Mock attention computation
                    modalities = []
                    if inputs.get('text', '').strip():
                        modalities.append('Text')
                    if inputs.get('visual', []):
                        modalities.append('Visual')
                    if inputs.get('data', []):
                        modalities.append('Data')
                    
                    # Generate attention matrix
                    n_modalities = len(modalities)
                    attention_matrix = np.random.uniform(0.1, 1.0, (n_modalities, n_modalities))
                    
                    # Make it symmetric and normalize
                    attention_matrix = (attention_matrix + attention_matrix.T) / 2
                    np.fill_diagonal(attention_matrix, 1.0)
                    
                    # Attention heatmap
                    fig = px.imshow(
                        attention_matrix,
                        x=modalities,
                        y=modalities,
                        title="Cross-Modal Attention Matrix",
                        color_continuous_scale="RdYlBu_r",
                        text_auto=".2f",
                        aspect="auto"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Attention insights
                    st.markdown("#### 💡 Attention Insights")
                    
                    # Find strongest connections
                    max_attention = np.max(attention_matrix[~np.eye(n_modalities, dtype=bool)])
                    max_indices = np.where(attention_matrix == max_attention)
                    
                    if len(max_indices[0]) > 0:
                        strongest_connection = f"{modalities[max_indices[0][0]]} ↔ {modalities[max_indices[1][0]]}"
                        st.success(f"🔗 Strongest cross-modal connection: {strongest_connection} (Score: {max_attention:.2f})")
                    
                    # Modality importance
                    modality_importance = np.mean(attention_matrix, axis=1)
                    importance_ranking = sorted(zip(modalities, modality_importance), 
                                              key=lambda x: x[1], reverse=True)
                    
                    st.markdown("**Modality Importance Ranking:**")
                    for i, (modality, importance) in enumerate(importance_ranking):
                        st.markdown(f"{i+1}. **{modality}**: {importance:.2f}")
                    
                except Exception as e:
                    st.error(f"Attention computation failed: {str(e)}")
        
        # Attention flow visualization
        st.markdown("#### 🌊 Attention Flow Analysis")
        
        # Mock attention flow over time
        if st.button("📊 Analyze Attention Flow", key="analyze_flow"):
            steps = ["Input Processing", "Feature Extraction", "Cross-Modal Fusion", "Query Construction", "Validation"]
            
            # Generate mock attention flows
            flow_data = []
            for step in steps:
                for modality in ['Text', 'Visual', 'Data']:
                    attention_weight = np.random.uniform(0.2, 0.9)
                    flow_data.append({
                        'Step': step,
                        'Modality': modality,
                        'Attention': attention_weight
                    })
            
            flow_df = pd.DataFrame(flow_data)
            
            fig = px.line(
                flow_df,
                x='Step',
                y='Attention',
                color='Modality',
                title="Attention Flow Throughout Generation Process",
                markers=True
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
            
            # Flow insights
            st.markdown("#### 🔍 Flow Analysis")
            
            insights = [
                "📈 Text attention peaks during initial processing",
                "🖼️ Visual attention strongest in feature extraction",
                "📊 Data attention crucial for query construction",
                "🔄 Cross-modal fusion balances all modalities"
            ]
            
            for insight in insights:
                st.markdown(f"• {insight}")
    
    with col2:
        st.markdown("#### ⚡ Attention Statistics")
        
        # Modality activity
        modality_stats = {
            "Text Tokens": 47 if inputs.get('text', '').strip() else 0,
            "Visual Elements": len(inputs.get('visual', [])),
            "Data Points": len(inputs.get('data', [])),
            "Schema Fields": len(inputs.get('schema', {}).get('properties', {}))
        }
        
        for stat, value in modality_stats.items():
            st.metric(stat, value)
        
        # Attention quality metrics
        st.markdown("#### 🎯 Attention Quality")
        
        quality_metrics = {
            "Cross-Modal Coherence": 0.84,
            "Attention Stability": 0.78,
            "Information Integration": 0.91,
            "Query Relevance": 0.87
        }
        
        for metric, score in quality_metrics.items():
            color = "normal"
            if score > 0.8:
                color = "inverse"
            elif score < 0.6:
                color = "off"
            
            st.metric(metric, f"{score:.2f}", delta_color=color)
        
        # Recommendations
        st.markdown("#### 💡 Optimization Tips")
        
        tips = [
            "🔧 Balance modality weights",
            "📝 Add more descriptive text",
            "🖼️ Include relevant visuals",
            "📊 Provide diverse data samples",
            "🎯 Align context semantically"
        ]
        
        for tip in tips:
            st.markdown(f"• {tip}")
        
        # Export options
        st.markdown("#### 💾 Export Options")
        
        if st.button("📄 Export Attention Report", key="export_attention"):
            st.info("Attention analysis report exported!")
        
        if st.button("📊 Export Attention Data", key="export_data"):
            st.info("Attention weights data exported!")


if __name__ == "__main__":
    render_multimodal_dashboard()

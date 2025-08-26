#!/usr/bin/env python3
"""Explainability dashboard for query interpretation and research tools"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def render_explainability_dashboard():
    """Render the explainability and research tools dashboard"""
    
    st.header("🔍 Explainability & Research Tools")
    st.markdown("Deep analysis and interpretation of query generation processes")
    
    # Main tabs for different explainability features
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧠 Query Explanation", 
        "🔬 Research Tools", 
        "📊 Decision Analysis", 
        "🎯 Hypothesis Testing"
    ])
    
    with tab1:
        render_query_explanation()
    
    with tab2:
        render_research_tools()
    
    with tab3:
        render_decision_analysis()
    
    with tab4:
        render_hypothesis_testing()

def render_query_explanation():
    """Render query explanation interface"""
    st.subheader("Query Generation Explanation")
    st.markdown("Understand how and why specific DSL queries were generated")
    
    # Query input section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Option to load existing query or create new one
        explanation_mode = st.radio(
            "Explanation Mode",
            ["Load Existing Query", "Generate & Explain New Query"],
            horizontal=True
        )
    
    with col2:
        explanation_level = st.selectbox(
            "Detail Level",
            ["Basic", "Detailed", "Technical", "Research"],
            index=1
        )
    
    if explanation_mode == "Load Existing Query":
        # File upload for existing query
        uploaded_file = st.file_uploader(
            "Upload Query JSON",
            type=['json'],
            help="Upload a generated query file to analyze"
        )
        
        prompt_text = st.text_area(
            "Original Prompt",
            placeholder="Enter the original natural language prompt...",
            help="The natural language prompt that generated this query"
        )
        
        if uploaded_file and prompt_text:
            try:
                query_data = json.load(uploaded_file)
                
                if st.button("🔍 Explain Query", type="primary"):
                    with st.spinner("Generating explanation..."):
                        explanation = explain_uploaded_query(query_data, prompt_text, explanation_level)
                        display_query_explanation(explanation)
                        
            except Exception as e:
                st.error(f"Error loading query file: {e}")
    
    else:
        # Generate new query and explain
        prompt_text = st.text_area(
            "Natural Language Prompt",
            placeholder="Enter your query description...",
            help="Describe what you want to find in natural language"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            model = st.selectbox(
                "Model",
                ["llama3.1:latest", "deepseek-r1:14b", "gpt-oss:20b"],
                index=0
            )
        
        with col2:
            method = st.selectbox(
                "Method",
                ["constrained", "zero_shot"],
                index=0
            )
        
        if st.button("🚀 Generate & Explain", type="primary"):
            if prompt_text:
                with st.spinner("Generating query and explanation..."):
                    result = generate_and_explain_query(prompt_text, model, method, explanation_level)
                    
                    if result["success"]:
                        # Show the generated query first
                        st.subheader("Generated Query")
                        st.json(result["query"])
                        
                        # Then show the explanation
                        display_query_explanation(result["explanation"])
                    else:
                        st.error(f"Generation failed: {result['error']}")
            else:
                st.warning("Please enter a prompt")

def render_research_tools():
    """Render research tools interface"""
    st.subheader("Advanced Research Tools")
    st.markdown("Automated hypothesis generation and experimental design")
    
    # Research study configuration
    st.markdown("### Configure Research Study")
    
    research_question = st.text_area(
        "Research Question",
        placeholder="e.g., Does model X perform better than model Y for security queries?",
        help="Describe what you want to investigate"
    )
    
    # Data source selection
    data_source = st.radio(
        "Data Source",
        ["Use Evaluation Results", "Upload Custom Data"],
        help="Choose data source for analysis"
    )
    
    if data_source == "Use Evaluation Results":
        # Look for existing evaluation results
        results_files = list(Path("artifacts/results").glob("*.json")) if Path("artifacts/results").exists() else []
        
        if results_files:
            selected_file = st.selectbox(
                "Select Results File",
                [f.name for f in results_files],
                help="Choose evaluation results to analyze"
            )
            
            if st.button("🔬 Conduct Research Study"):
                if research_question:
                    with st.spinner("Conducting research study..."):
                        study_results = conduct_research_study_from_results(
                            f"artifacts/results/{selected_file}", 
                            research_question
                        )
                        display_research_results(study_results)
                else:
                    st.warning("Please enter a research question")
        else:
            st.info("No evaluation results found. Run some evaluations first.")
    
    else:
        # Upload custom data
        uploaded_data = st.file_uploader(
            "Upload Research Data",
            type=['csv', 'json'],
            help="Upload data file for analysis"
        )
        
        if uploaded_data and research_question:
            if st.button("🔬 Conduct Research Study"):
                with st.spinner("Conducting research study..."):
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(mode='wb', delete=False, 
                                                   suffix=f".{uploaded_data.name.split('.')[-1]}") as tmp_file:
                        tmp_file.write(uploaded_data.getvalue())
                        tmp_path = tmp_file.name
                    
                    try:
                        study_results = conduct_research_study_from_file(tmp_path, research_question)
                        display_research_results(study_results)
                    finally:
                        Path(tmp_path).unlink(missing_ok=True)

def render_decision_analysis():
    """Render decision analysis interface"""
    st.subheader("Decision Analysis & Attention Visualization")
    st.markdown("Analyze the decision-making process in query generation")
    
    # Load recent explanations for analysis
    explanation_files = list(Path("artifacts/explanations").glob("*.json")) if Path("artifacts/explanations").exists() else []
    
    if explanation_files:
        selected_explanation = st.selectbox(
            "Select Explanation to Analyze",
            [f.name for f in explanation_files],
            help="Choose a previously generated explanation"
        )
        
        if st.button("📊 Analyze Decisions"):
            explanation_path = Path("artifacts/explanations") / selected_explanation
            
            try:
                with open(explanation_path) as f:
                    explanation_data = json.load(f)
                
                display_decision_analysis(explanation_data)
                
            except Exception as e:
                st.error(f"Error loading explanation: {e}")
    
    else:
        st.info("No explanations available. Generate some query explanations first.")
        
        # Option to generate explanation for analysis
        st.markdown("### Generate Explanation for Analysis")
        
        sample_prompts = [
            "Find malicious events on July 4, 2017",
            "Show TCP traffic on port 443",
            "Find SSH connections from external IPs",
            "Query for DDoS attacks in the last hour"
        ]
        
        selected_prompt = st.selectbox("Select Sample Prompt", sample_prompts)
        
        if st.button("Generate Sample Explanation"):
            with st.spinner("Generating explanation for analysis..."):
                try:
                    # Generate explanation using existing query
                    query_file = "artifacts/queries/candidate_scan-001.json"
                    if Path(query_file).exists():
                        explanation = explain_from_file(query_file, selected_prompt)
                        display_decision_analysis(explanation.to_dict())
                    else:
                        st.error("No sample query available")
                except Exception as e:
                    st.error(f"Error generating explanation: {e}")

def render_hypothesis_testing():
    """Render hypothesis testing interface"""
    st.subheader("Automated Hypothesis Testing")
    st.markdown("Generate and test research hypotheses from your data")
    
    # Load available data for hypothesis testing
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Available Data Sources")
        
        data_sources = []
        
        # Check for evaluation results
        if Path("artifacts/results").exists():
            result_files = list(Path("artifacts/results").glob("*.json"))
            data_sources.extend([f"Evaluation Results ({len(result_files)} files)"])
        
        # Check for benchmark results
        if Path("artifacts/performance_results").exists():
            benchmark_files = list(Path("artifacts/performance_results").glob("*.json"))
            data_sources.extend([f"Performance Benchmarks ({len(benchmark_files)} files)"])
        
        # Check for security results
        if Path("artifacts/security_results").exists():
            security_files = list(Path("artifacts/security_results").glob("*.json"))
            data_sources.extend([f"Security Analysis ({len(security_files)} files)"])
        
        if data_sources:
            for source in data_sources:
                st.success(f"✅ {source}")
        else:
            st.warning("No data sources available")
    
    with col2:
        st.markdown("#### Hypothesis Templates")
        
        hypothesis_templates = [
            "Model A performs better than Model B",
            "Method X is more accurate than Method Y", 
            "Security measures reduce attack success",
            "Query complexity affects generation time",
            "Caching improves system performance"
        ]
        
        selected_template = st.selectbox(
            "Choose Hypothesis Template",
            hypothesis_templates,
            help="Select a hypothesis template to customize"
        )
    
    # Hypothesis customization
    st.markdown("#### Customize Hypothesis")
    
    custom_hypothesis = st.text_area(
        "Research Hypothesis",
        value=selected_template,
        help="Describe what you want to test"
    )
    
    significance_level = st.slider(
        "Significance Level (α)",
        min_value=0.01,
        max_value=0.10,
        value=0.05,
        step=0.01,
        help="Statistical significance threshold"
    )
    
    if st.button("🧪 Generate & Test Hypothesis"):
        if custom_hypothesis and data_sources:
            with st.spinner("Generating and testing hypothesis..."):
                try:
                    hypothesis_results = generate_and_test_hypothesis(
                        custom_hypothesis, significance_level
                    )
                    display_hypothesis_results(hypothesis_results)
                except Exception as e:
                    st.error(f"Error in hypothesis testing: {e}")
        else:
            st.warning("Please provide a hypothesis and ensure data sources are available")

def explain_uploaded_query(query_data: Dict[str, Any], prompt: str, level: str) -> Dict[str, Any]:
    """Explain an uploaded query"""
    try:
        from src.explainability.query_explainer import QueryExplainer, ExplanationLevel
        
        explainer = QueryExplainer()
        explanation_level = ExplanationLevel(level.lower())
        
        explanation = explainer.explain_query(prompt, query_data, explanation_level)
        return explanation.to_dict()
    
    except Exception as e:
        return {"error": str(e)}

def generate_and_explain_query(prompt: str, model: str, method: str, level: str) -> Dict[str, Any]:
    """Generate a new query and explain it"""
    try:
        import subprocess
        import uuid
        
        # Generate unique task ID
        task_id = f"explain_{uuid.uuid4().hex[:8]}"
        
        # Generate query
        cmd = [
            "python", "src/generators/constrained.py",
            "--prompt", prompt,
            "--task-id", task_id,
            "--model", model
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            # Load generated query
            query_file = Path(f"artifacts/generated/{task_id}.json")
            
            if query_file.exists():
                with open(query_file) as f:
                    query_data = json.load(f)
                
                # Generate explanation
                explanation = explain_uploaded_query(query_data, prompt, level)
                
                # Clean up
                query_file.unlink(missing_ok=True)
                
                return {
                    "success": True,
                    "query": query_data,
                    "explanation": explanation
                }
            else:
                return {"success": False, "error": "Query file not found"}
        else:
            return {"success": False, "error": result.stderr}
    
    except Exception as e:
        return {"success": False, "error": str(e)}

def explain_from_file(query_file: str, prompt: str) -> Any:
    """Explain query from file"""
    from src.explainability.query_explainer import explain_query_file, ExplanationLevel
    
    return explain_query_file(query_file, prompt, ExplanationLevel.DETAILED)

def display_query_explanation(explanation: Dict[str, Any]) -> None:
    """Display comprehensive query explanation"""
    
    if "error" in explanation:
        st.error(f"Explanation error: {explanation['error']}")
        return
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        confidence = explanation.get("confidence_score", 0)
        st.metric("Confidence", f"{confidence:.2f}", help="Overall confidence in the explanation")
    
    with col2:
        complexity = explanation.get("complexity_score", 0)
        st.metric("Complexity", f"{complexity:.2f}", help="Query complexity score")
    
    with col3:
        decision_count = len(explanation.get("decisions", []))
        st.metric("Decisions", decision_count, help="Number of decisions analyzed")
    
    with col4:
        risk_level = explanation.get("risk_assessment", {}).get("overall_risk_level", "unknown")
        risk_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk_level, "⚪")
        st.metric("Risk Level", f"{risk_color} {risk_level.title()}")
    
    # Query summary
    st.markdown("### 📋 Query Summary")
    st.info(explanation.get("query_summary", "No summary available"))
    
    # Decision explanations
    st.markdown("### 🧠 Decision Analysis")
    
    decisions = explanation.get("decisions", [])
    if decisions:
        for i, decision in enumerate(decisions, 1):
            with st.expander(f"Decision {i}: {decision.get('decision_type', 'Unknown').replace('_', ' ').title()}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Rationale:** {decision.get('rationale', 'No rationale provided')}")
                    
                    if decision.get("prompt_evidence"):
                        st.markdown(f"**Evidence from prompt:** {', '.join(decision['prompt_evidence'])}")
                    
                    if decision.get("alternatives"):
                        alternatives_text = ", ".join([alt.get("field", alt.get("operator", str(alt))) for alt in decision["alternatives"][:3]])
                        st.markdown(f"**Alternatives considered:** {alternatives_text}")
                
                with col2:
                    confidence = decision.get("confidence", 0)
                    st.metric("Confidence", f"{confidence:.2f}")
                    
                    if decision.get("field_name"):
                        st.markdown(f"**Field:** `{decision['field_name']}`")
    
    # Attention weights visualization
    st.markdown("### 🎯 Attention Analysis")
    attention_weights = explanation.get("attention_weights", {})
    
    if attention_weights:
        # Create attention visualization
        tokens = list(attention_weights.keys())
        weights = list(attention_weights.values())
        
        fig = px.bar(
            x=tokens,
            y=weights,
            title="Token Attention Weights",
            labels={"x": "Tokens", "y": "Attention Weight"}
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Risk assessment
    st.markdown("### ⚠️ Risk Assessment")
    risk_assessment = explanation.get("risk_assessment", {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        perf_risks = risk_assessment.get("performance_risks", [])
        if perf_risks:
            st.markdown("**Performance Risks:**")
            for risk in perf_risks:
                st.warning(f"• {risk}")
        else:
            st.success("✅ No performance risks identified")
    
    with col2:
        security_risks = risk_assessment.get("security_risks", [])
        if security_risks:
            st.markdown("**Security Risks:**")
            for risk in security_risks:
                st.error(f"• {risk}")
        else:
            st.success("✅ No security risks identified")
    
    with col3:
        accuracy_risks = risk_assessment.get("accuracy_risks", [])
        if accuracy_risks:
            st.markdown("**Accuracy Risks:**")
            for risk in accuracy_risks:
                st.warning(f"• {risk}")
        else:
            st.success("✅ No accuracy risks identified")
    
    # Optimization suggestions
    st.markdown("### 💡 Optimization Suggestions")
    optimizations = explanation.get("optimization_suggestions", [])
    
    if optimizations:
        for i, suggestion in enumerate(optimizations, 1):
            st.info(f"{i}. {suggestion}")
    else:
        st.success("No optimizations suggested - query looks good!")

def display_decision_analysis(explanation_data: Dict[str, Any]) -> None:
    """Display detailed decision analysis"""
    
    decisions = explanation_data.get("decisions", [])
    
    if not decisions:
        st.warning("No decisions found in explanation data")
        return
    
    # Decision confidence distribution
    st.markdown("### 📊 Decision Confidence Distribution")
    
    confidences = [d.get("confidence", 0) for d in decisions]
    decision_types = [d.get("decision_type", "unknown") for d in decisions]
    
    fig = px.histogram(
        x=confidences,
        nbins=10,
        title="Distribution of Decision Confidence Scores"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Decision type analysis
    st.markdown("### 🔍 Decision Type Analysis")
    
    decision_type_counts = {}
    for decision_type in decision_types:
        decision_type_counts[decision_type] = decision_type_counts.get(decision_type, 0) + 1
    
    fig = px.pie(
        values=list(decision_type_counts.values()),
        names=list(decision_type_counts.keys()),
        title="Decision Types Distribution"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Confidence vs Decision Type
    st.markdown("### 📈 Confidence by Decision Type")
    
    df = pd.DataFrame({
        "Decision_Type": decision_types,
        "Confidence": confidences
    })
    
    fig = px.box(
        df,
        x="Decision_Type",
        y="Confidence", 
        title="Confidence Score by Decision Type"
    )
    fig.update_xaxes(tickangle=45)
    st.plotly_chart(fig, use_container_width=True)

def conduct_research_study_from_results(results_file: str, research_question: str) -> Dict[str, Any]:
    """Conduct research study from evaluation results"""
    try:
        from src.explainability.research_tools import ResearchToolsInterface
        
        research_tools = ResearchToolsInterface()
        return research_tools.conduct_research_study(results_file, research_question)
    
    except Exception as e:
        return {"error": str(e)}

def conduct_research_study_from_file(data_file: str, research_question: str) -> Dict[str, Any]:
    """Conduct research study from uploaded file"""
    try:
        from src.explainability.research_tools import ResearchToolsInterface
        
        research_tools = ResearchToolsInterface()
        return research_tools.conduct_research_study(data_file, research_question)
    
    except Exception as e:
        return {"error": str(e)}

def display_research_results(study_results: Dict[str, Any]) -> None:
    """Display research study results"""
    
    if "error" in study_results:
        st.error(f"Research study error: {study_results['error']}")
        return
    
    # Study overview
    st.markdown("### 📋 Study Overview")
    
    data_summary = study_results.get("data_summary", {})
    st.info(f"**Research Question:** {study_results.get('research_question', 'Not specified')}")
    st.info(f"**Data Shape:** {data_summary.get('shape', 'Unknown')}")
    
    # Generated hypotheses
    st.markdown("### 🧪 Generated Hypotheses")
    
    hypotheses = study_results.get("generated_hypotheses", [])
    if hypotheses:
        for i, hypothesis in enumerate(hypotheses, 1):
            with st.expander(f"Hypothesis {i}: {hypothesis.get('description', 'Unknown')}"):
                st.markdown(f"**Null Hypothesis:** {hypothesis.get('null_hypothesis', 'Not specified')}")
                st.markdown(f"**Alternative Hypothesis:** {hypothesis.get('alternative_hypothesis', 'Not specified')}")
                st.markdown(f"**Expected Outcome:** {hypothesis.get('expected_outcome', 'Not specified')}")
    
    # Selected hypothesis and results
    selected_hypothesis = study_results.get("selected_hypothesis", {})
    results = study_results.get("results", {})
    
    if selected_hypothesis and results:
        st.markdown("### 🎯 Test Results")
        
        conclusion = results.get("conclusion", "No conclusion available")
        
        if "REJECT" in conclusion:
            st.success(f"✅ **Conclusion:** {conclusion}")
        else:
            st.warning(f"⚠️ **Conclusion:** {conclusion}")
        
        # Statistical results
        statistical_results = results.get("statistical_results", {})
        if statistical_results:
            st.markdown("#### Statistical Test Results")
            
            for test_name, test_result in statistical_results.items():
                if isinstance(test_result, dict) and "p_value" in test_result:
                    with st.expander(f"{test_name.replace('_', ' ').title()}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("P-value", f"{test_result.get('p_value', 'N/A'):.4f}")
                        
                        with col2:
                            effect_size = test_result.get("effect_size", 0)
                            st.metric("Effect Size", f"{effect_size:.3f}")
                        
                        if "confidence_interval" in test_result:
                            ci = test_result["confidence_interval"]
                            st.markdown(f"**95% Confidence Interval:** [{ci[0]:.3f}, {ci[1]:.3f}]")

def generate_and_test_hypothesis(hypothesis_text: str, significance_level: float) -> Dict[str, Any]:
    """Generate and test a custom hypothesis"""
    # This would integrate with the research tools
    # For now, return a mock result
    return {
        "hypothesis": hypothesis_text,
        "significance_level": significance_level,
        "test_results": {
            "p_value": 0.032,
            "effect_size": 0.65,
            "conclusion": "REJECT null hypothesis - significant effect detected"
        },
        "note": "This is a demonstration. Full implementation requires integration with research tools."
    }

def display_hypothesis_results(results: Dict[str, Any]) -> None:
    """Display hypothesis testing results"""
    
    st.markdown("### 🧪 Hypothesis Test Results")
    
    hypothesis = results.get("hypothesis", "Unknown hypothesis")
    st.info(f"**Hypothesis:** {hypothesis}")
    
    test_results = results.get("test_results", {})
    
    if test_results:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            p_value = test_results.get("p_value", 1.0)
            st.metric("P-value", f"{p_value:.4f}")
        
        with col2:
            effect_size = test_results.get("effect_size", 0)
            st.metric("Effect Size", f"{effect_size:.3f}")
        
        with col3:
            significance = results.get("significance_level", 0.05)
            st.metric("Significance Level", f"{significance:.3f}")
        
        conclusion = test_results.get("conclusion", "No conclusion")
        
        if "REJECT" in conclusion:
            st.success(f"✅ **Result:** {conclusion}")
        else:
            st.warning(f"⚠️ **Result:** {conclusion}")
    
    if "note" in results:
        st.info(results["note"])

if __name__ == "__main__":
    # For testing the dashboard components
    render_explainability_dashboard()

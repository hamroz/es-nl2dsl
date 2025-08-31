#!/usr/bin/env python3
"""
Query Explainer: Comprehensive interpretability framework for DSL generation

This module provides advanced explainability and interpretability capabilities for the ES-NL2DSL
system, offering deep insights into query generation decisions and reasoning processes. It analyzes
natural language prompts, traces decision-making paths, and generates comprehensive explanations
for generated Elasticsearch DSL queries with confidence scoring and optimization suggestions.

Key capabilities:
- Multi-level explanation generation (basic, detailed, technical, research)
- Decision tracing with confidence scoring and rationale
- Prompt analysis with semantic component extraction
- Attention weight calculation for input tokens
- Query structure analysis and complexity assessment
- Risk assessment for performance, security, and accuracy
- Optimization suggestions for query improvement
- Interactive explanations for research and debugging

The framework supports various explanation levels from high-level summaries to deep technical
analysis, enabling both end-users and researchers to understand system behavior and improve
query generation quality through interpretable AI techniques.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""
import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from pathlib import Path

class ExplanationLevel(Enum):
    """Different levels of explanation detail"""
    BASIC = "basic"           # High-level overview
    DETAILED = "detailed"     # Component-by-component analysis
    TECHNICAL = "technical"   # Deep technical details
    RESEARCH = "research"     # Research-oriented explanations

class DecisionType(Enum):
    """Types of decisions made during query generation"""
    FIELD_SELECTION = "field_selection"
    OPERATOR_CHOICE = "operator_choice"
    TIME_FILTERING = "time_filtering"
    LOGICAL_STRUCTURE = "logical_structure"
    AGGREGATION = "aggregation"
    OPTIMIZATION = "optimization"

@dataclass
class DecisionExplanation:
    """Explanation for a specific decision in query generation"""
    decision_type: DecisionType
    component: str              # The specific DSL component (e.g., "term", "range")
    field_name: Optional[str]   # Field being operated on
    value: Any                  # The chosen value/operator
    confidence: float           # Confidence score (0-1)
    rationale: str             # Human-readable explanation
    alternatives: List[Dict[str, Any]]  # Alternative choices considered
    prompt_evidence: List[str]  # Parts of prompt that influenced this decision
    technical_details: Dict[str, Any]  # Technical implementation details
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["decision_type"] = self.decision_type.value
        return result

@dataclass
class QueryExplanation:
    """Comprehensive explanation of a generated query"""
    original_prompt: str
    generated_query: Dict[str, Any]
    query_summary: str
    complexity_score: float
    confidence_score: float
    decisions: List[DecisionExplanation]
    attention_weights: Dict[str, float]  # Attention over prompt tokens
    risk_assessment: Dict[str, Any]
    optimization_suggestions: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["decisions"] = [d.to_dict() for d in self.decisions]
        return result

class PromptAnalyzer:
    """Analyzes natural language prompts to extract semantic information"""
    
    def __init__(self):
        self.temporal_patterns = [
            (r'\b(\d{4}-\d{2}-\d{2})\b', 'date'),
            (r'\b(yesterday|today|tomorrow)\b', 'relative_date'),
            (r'\b(last|past)\s+(\d+)\s+(hour|day|week|month)s?\b', 'relative_duration'),
            (r'\b(between|from)\s+(.+?)\s+(to|and)\s+(.+)', 'date_range'),
            (r'\b(July|January|February|March|April|May|June|August|September|October|November|December)\b', 'month'),
            (r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 'weekday')
        ]
        
        self.field_patterns = [
            (r'\b(source|src)\s+(ip|address)\b', 'src_ip'),
            (r'\b(destination|dst)\s+(ip|address)\b', 'dst_ip'),
            (r'\b(source|src)\s+port\b', 'src_port'),
            (r'\b(destination|dst)\s+port\b', 'dst_port'),
            (r'\bport\s+(\d+)\b', 'port_specific'),
            (r'\b(protocol)\b', 'protocol'),
            (r'\b(TCP|UDP|ICMP)\b', 'protocol_specific'),
            (r'\b(label|classification)\b', 'label'),
            (r'\b(malicious|attack|intrusion|benign)\b', 'label_value'),
            (r'\b(duration|time)\b', 'flow_duration'),
            (r'\b(packet|byte)s?\b', 'traffic_volume')
        ]
        
        self.operator_patterns = [
            (r'\b(equal|equals|is|exactly)\b', 'term'),
            (r'\b(contains|includes|has)\b', 'wildcard'),
            (r'\b(greater than|more than|above)\s+(\d+)\b', 'range_gt'),
            (r'\b(less than|below|under)\s+(\d+)\b', 'range_lt'),
            (r'\b(between)\s+(\d+)\s+and\s+(\d+)\b', 'range_between'),
            (r'\b(not|exclude|without)\b', 'must_not'),
            (r'\b(and|also|additionally)\b', 'must'),
            (r'\b(or|either|alternatively)\b', 'should')
        ]
        
        self.security_patterns = [
            (r'\b(attack|intrusion|malicious|threat)\b', 'security_event'),
            (r'\b(scan|probe|reconnaissance)\b', 'scanning_activity'),
            (r'\b(ddos|denial of service)\b', 'ddos_attack'),
            (r'\b(ssh|ftp|http|https)\b', 'protocol_service'),
            (r'\b(external|internal|private|public)\b', 'network_location'),
            (r'\b(suspicious|anomalous|unusual)\b', 'anomaly_detection')
        ]
    
    def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """Analyze prompt and extract semantic components"""
        prompt_lower = prompt.lower()
        
        analysis = {
            "temporal_components": self._extract_temporal_info(prompt_lower),
            "field_references": self._extract_field_references(prompt_lower),
            "operator_hints": self._extract_operator_hints(prompt_lower),
            "security_context": self._extract_security_context(prompt_lower),
            "complexity_indicators": self._assess_complexity(prompt_lower),
            "attention_tokens": self._calculate_attention_weights(prompt.split())
        }
        
        return analysis
    
    def _extract_temporal_info(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract temporal information from prompt"""
        temporal_info = []
        
        for pattern, temp_type in self.temporal_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                temporal_info.append({
                    "type": temp_type,
                    "text": match.group(),
                    "position": match.span(),
                    "confidence": 0.9 if temp_type == "date" else 0.7
                })
        
        return temporal_info
    
    def _extract_field_references(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract field references from prompt"""
        field_refs = []
        
        for pattern, field_type in self.field_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                field_refs.append({
                    "type": field_type,
                    "text": match.group(),
                    "position": match.span(),
                    "confidence": 0.8 if "specific" in field_type else 0.6
                })
        
        return field_refs
    
    def _extract_operator_hints(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract operator hints from prompt"""
        operator_hints = []
        
        for pattern, op_type in self.operator_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                operator_hints.append({
                    "type": op_type,
                    "text": match.group(),
                    "position": match.span(),
                    "confidence": 0.7
                })
        
        return operator_hints
    
    def _extract_security_context(self, prompt: str) -> List[Dict[str, Any]]:
        """Extract security-related context"""
        security_context = []
        
        for pattern, context_type in self.security_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                security_context.append({
                    "type": context_type,
                    "text": match.group(),
                    "position": match.span(),
                    "confidence": 0.8
                })
        
        return security_context
    
    def _assess_complexity(self, prompt: str) -> Dict[str, Any]:
        """Assess prompt complexity"""
        word_count = len(prompt.split())
        unique_words = len(set(prompt.split()))
        
        # Count logical connectors
        logical_connectors = len(re.findall(r'\b(and|or|not|but|however|also)\b', prompt))
        
        # Count conditional phrases
        conditionals = len(re.findall(r'\b(if|when|where|unless|except)\b', prompt))
        
        # Count temporal references
        temporal_refs = len(re.findall(r'\b(before|after|during|since|until)\b', prompt))
        
        complexity_score = min(1.0, (
            (word_count / 20) * 0.3 +
            (logical_connectors / 3) * 0.3 +
            (conditionals / 2) * 0.2 +
            (temporal_refs / 2) * 0.2
        ))
        
        return {
            "word_count": word_count,
            "unique_words": unique_words,
            "logical_connectors": logical_connectors,
            "conditionals": conditionals,
            "temporal_refs": temporal_refs,
            "complexity_score": complexity_score
        }
    
    def _calculate_attention_weights(self, tokens: List[str]) -> Dict[str, float]:
        """Calculate attention weights for tokens"""
        attention_weights = {}
        
        # Important word categories with base weights
        important_categories = {
            'temporal': ['yesterday', 'today', 'july', 'morning', 'afternoon', '2017'],
            'security': ['malicious', 'attack', 'intrusion', 'suspicious', 'threat'],
            'network': ['ip', 'port', 'tcp', 'udp', 'protocol', 'source', 'destination'],
            'action': ['find', 'show', 'query', 'search', 'get', 'list'],
            'filter': ['where', 'with', 'having', 'containing', 'equals', 'greater', 'less']
        }
        
        for token in tokens:
            token_lower = token.lower()
            weight = 0.1  # Base weight
            
            # Increase weight based on category
            for category, words in important_categories.items():
                if any(word in token_lower for word in words):
                    if category == 'security':
                        weight = 0.9
                    elif category == 'temporal':
                        weight = 0.8
                    elif category == 'network':
                        weight = 0.7
                    elif category == 'action':
                        weight = 0.6
                    elif category == 'filter':
                        weight = 0.5
                    break
            
            # Numbers get medium attention
            if re.match(r'\d+', token):
                weight = max(weight, 0.6)
            
            # Quoted strings get high attention
            if token.startswith('"') or token.endswith('"'):
                weight = max(weight, 0.8)
            
            attention_weights[token] = weight
        
        # Normalize weights
        total_weight = sum(attention_weights.values())
        if total_weight > 0:
            attention_weights = {k: v/total_weight for k, v in attention_weights.items()}
        
        return attention_weights

class QueryExplainer:
    """Main class for explaining query generation decisions"""
    
    def __init__(self):
        self.prompt_analyzer = PromptAnalyzer()
        
        # Decision confidence thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
        
        # Common field mappings for explanation
        self.field_explanations = {
            "@timestamp": "Event timestamp for temporal filtering",
            "src_ip": "Source IP address of network traffic",
            "dst_ip": "Destination IP address of network traffic", 
            "src_port": "Source port number",
            "dst_port": "Destination port number",
            "protocol": "Network protocol (TCP, UDP, ICMP)",
            "label": "Event classification (malicious, benign)",
            "flow_duration": "Duration of network flow",
            "tot_fwd_pkts": "Total forward packets",
            "tot_bwd_pkts": "Total backward packets"
        }
    
    def explain_query(self, prompt: str, query: Dict[str, Any], 
                     level: ExplanationLevel = ExplanationLevel.DETAILED) -> QueryExplanation:
        """Generate comprehensive explanation for a query"""
        
        # Analyze the prompt
        prompt_analysis = self.prompt_analyzer.analyze_prompt(prompt)
        
        # Analyze the generated query structure
        query_analysis = self._analyze_query_structure(query)
        
        # Generate decision explanations
        decisions = self._explain_decisions(prompt_analysis, query_analysis, query)
        
        # Calculate overall confidence
        confidence_score = self._calculate_overall_confidence(decisions)
        
        # Generate query summary
        query_summary = self._generate_query_summary(query, prompt_analysis)
        
        # Assess risks
        risk_assessment = self._assess_query_risks(query, decisions)
        
        # Generate optimization suggestions
        optimizations = self._generate_optimizations(query, decisions, prompt_analysis)
        
        # Calculate complexity
        complexity_score = self._calculate_query_complexity(query)
        
        explanation = QueryExplanation(
            original_prompt=prompt,
            generated_query=query,
            query_summary=query_summary,
            complexity_score=complexity_score,
            confidence_score=confidence_score,
            decisions=decisions,
            attention_weights=prompt_analysis["attention_tokens"],
            risk_assessment=risk_assessment,
            optimization_suggestions=optimizations,
            metadata={
                "explanation_level": level.value,
                "prompt_analysis": prompt_analysis,
                "query_analysis": query_analysis,
                "generation_timestamp": Path().cwd().name  # Placeholder
            }
        )
        
        return explanation
    
    def _analyze_query_structure(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the structure of the generated query"""
        structure = {
            "has_query": "query" in query,
            "has_aggregations": "aggs" in query or "aggregations" in query,
            "has_sorting": "sort" in query,
            "has_size_limit": "size" in query,
            "query_type": None,
            "filters": [],
            "logical_structure": None,
            "field_count": 0,
            "temporal_filters": [],
            "complexity_indicators": {}
        }
        
        if "query" in query:
            query_body = query["query"]
            structure["query_type"] = self._identify_query_type(query_body)
            structure["filters"] = self._extract_filters(query_body)
            structure["logical_structure"] = self._analyze_logical_structure(query_body)
            structure["field_count"] = len(self._extract_fields(query_body))
            structure["temporal_filters"] = self._extract_temporal_filters(query_body)
        
        return structure
    
    def _identify_query_type(self, query_body: Dict[str, Any]) -> str:
        """Identify the main query type"""
        if "bool" in query_body:
            return "boolean"
        elif "term" in query_body:
            return "term"
        elif "terms" in query_body:
            return "terms"
        elif "range" in query_body:
            return "range"
        elif "match" in query_body:
            return "match"
        elif "match_all" in query_body:
            return "match_all"
        else:
            return "unknown"
    
    def _extract_filters(self, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all filters from query"""
        filters = []
        
        def extract_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["term", "terms", "range", "match", "wildcard"]:
                        filters.append({
                            "type": key,
                            "content": value,
                            "path": path
                        })
                    elif isinstance(value, (dict, list)):
                        extract_recursive(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_recursive(item, f"{path}[{i}]")
        
        extract_recursive(query_body)
        return filters
    
    def _analyze_logical_structure(self, query_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze boolean/logical structure"""
        if "bool" not in query_body:
            return None
        
        bool_query = query_body["bool"]
        structure = {
            "has_must": "must" in bool_query,
            "has_should": "should" in bool_query,
            "has_must_not": "must_not" in bool_query,
            "has_filter": "filter" in bool_query,
            "clause_counts": {}
        }
        
        for clause_type in ["must", "should", "must_not", "filter"]:
            if clause_type in bool_query:
                if isinstance(bool_query[clause_type], list):
                    structure["clause_counts"][clause_type] = len(bool_query[clause_type])
                else:
                    structure["clause_counts"][clause_type] = 1
        
        return structure
    
    def _extract_fields(self, query_body: Dict[str, Any]) -> List[str]:
        """Extract all field names used in query"""
        fields = set()
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["term", "terms", "range", "match", "wildcard"] and isinstance(value, dict):
                        fields.update(value.keys())
                    elif isinstance(value, (dict, list)):
                        extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(query_body)
        return list(fields)
    
    def _extract_temporal_filters(self, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract temporal filters (usually @timestamp ranges)"""
        temporal_filters = []
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                if "range" in obj and "@timestamp" in obj["range"]:
                    temporal_filters.append(obj["range"]["@timestamp"])
                else:
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(query_body)
        return temporal_filters
    
    def _explain_decisions(self, prompt_analysis: Dict[str, Any], 
                          query_analysis: Dict[str, Any], 
                          query: Dict[str, Any]) -> List[DecisionExplanation]:
        """Generate explanations for all decisions made during query generation"""
        decisions = []
        
        # Explain field selections
        fields_used = query_analysis.get("field_count", 0)
        if fields_used > 0:
            field_names = self._extract_fields(query.get("query", {}))
            for field in field_names:
                decision = self._explain_field_selection(field, prompt_analysis)
                decisions.append(decision)
        
        # Explain temporal filtering decisions
        temporal_filters = query_analysis.get("temporal_filters", [])
        if temporal_filters:
            for temp_filter in temporal_filters:
                decision = self._explain_temporal_decision(temp_filter, prompt_analysis)
                decisions.append(decision)
        
        # Explain logical structure decisions
        logical_structure = query_analysis.get("logical_structure")
        if logical_structure:
            decision = self._explain_logical_structure(logical_structure, prompt_analysis)
            decisions.append(decision)
        
        # Explain operator choices
        filters = query_analysis.get("filters", [])
        for filter_info in filters:
            decision = self._explain_operator_choice(filter_info, prompt_analysis)
            decisions.append(decision)
        
        return decisions
    
    def _explain_field_selection(self, field: str, prompt_analysis: Dict[str, Any]) -> DecisionExplanation:
        """Explain why a specific field was selected"""
        field_refs = prompt_analysis.get("field_references", [])
        
        # Find relevant field references in prompt
        relevant_refs = [ref for ref in field_refs if field in ref.get("text", "").lower()]
        
        confidence = 0.8 if relevant_refs else 0.5
        
        rationale = f"Selected field '{field}' "
        if relevant_refs:
            rationale += f"based on prompt reference: '{relevant_refs[0]['text']}'"
        else:
            rationale += "as it's commonly used for this type of query"
        
        # Add field explanation if available
        if field in self.field_explanations:
            rationale += f". {self.field_explanations[field]}"
        
        prompt_evidence = [ref["text"] for ref in relevant_refs]
        
        return DecisionExplanation(
            decision_type=DecisionType.FIELD_SELECTION,
            component="field",
            field_name=field,
            value=field,
            confidence=confidence,
            rationale=rationale,
            alternatives=[{"field": alt, "confidence": 0.3} for alt in ["src_ip", "dst_ip", "protocol"] if alt != field][:2],
            prompt_evidence=prompt_evidence,
            technical_details={"field_type": "keyword", "indexed": True}
        )
    
    def _explain_temporal_decision(self, temp_filter: Dict[str, Any], prompt_analysis: Dict[str, Any]) -> DecisionExplanation:
        """Explain temporal filtering decisions"""
        temporal_components = prompt_analysis.get("temporal_components", [])
        
        confidence = 0.9 if temporal_components else 0.6
        
        rationale = "Applied temporal filter on @timestamp "
        if temporal_components:
            time_refs = [comp["text"] for comp in temporal_components]
            rationale += f"based on time references in prompt: {', '.join(time_refs[:2])}"
        else:
            rationale += "as temporal filtering is recommended for log analysis"
        
        if "gte" in temp_filter and "lte" in temp_filter:
            rationale += f" (range: {temp_filter['gte']} to {temp_filter['lte']})"
        
        prompt_evidence = [comp["text"] for comp in temporal_components]
        
        return DecisionExplanation(
            decision_type=DecisionType.TIME_FILTERING,
            component="range",
            field_name="@timestamp",
            value=temp_filter,
            confidence=confidence,
            rationale=rationale,
            alternatives=[{"type": "match_all", "rationale": "No time filtering"}],
            prompt_evidence=prompt_evidence,
            technical_details={"filter_type": "range", "performance_impact": "positive"}
        )
    
    def _explain_logical_structure(self, logical_structure: Dict[str, Any], prompt_analysis: Dict[str, Any]) -> DecisionExplanation:
        """Explain logical structure (bool query) decisions"""
        operator_hints = prompt_analysis.get("operator_hints", [])
        
        # Determine primary logical operator used
        clause_counts = logical_structure.get("clause_counts", {})
        primary_operator = max(clause_counts.keys(), key=lambda k: clause_counts[k]) if clause_counts else "must"
        
        confidence = 0.7
        if any("and" in hint["text"] for hint in operator_hints):
            primary_operator = "must"
            confidence = 0.9
        elif any("or" in hint["text"] for hint in operator_hints):
            primary_operator = "should"
            confidence = 0.9
        
        rationale = f"Used boolean query with primary operator '{primary_operator}' "
        relevant_hints = [hint["text"] for hint in operator_hints if primary_operator in hint["text"] or "and" in hint["text"] or "or" in hint["text"]]
        
        if relevant_hints:
            rationale += f"based on logical indicators: {', '.join(relevant_hints[:2])}"
        else:
            rationale += "as it allows combining multiple conditions effectively"
        
        return DecisionExplanation(
            decision_type=DecisionType.LOGICAL_STRUCTURE,
            component="bool",
            field_name=None,
            value={"primary_operator": primary_operator, "clause_counts": clause_counts},
            confidence=confidence,
            rationale=rationale,
            alternatives=[{"operator": "term", "rationale": "Single condition query"}],
            prompt_evidence=relevant_hints,
            technical_details={"query_efficiency": "high", "flexibility": "high"}
        )
    
    def _explain_operator_choice(self, filter_info: Dict[str, Any], prompt_analysis: Dict[str, Any]) -> DecisionExplanation:
        """Explain operator choice decisions"""
        operator_type = filter_info["type"]
        operator_hints = prompt_analysis.get("operator_hints", [])
        
        # Find relevant operator hints
        relevant_hints = [hint for hint in operator_hints if operator_type in hint["type"]]
        
        confidence = 0.8 if relevant_hints else 0.6
        
        operator_explanations = {
            "term": "exact match for precise filtering",
            "terms": "multiple value matching",
            "range": "numeric or date range filtering",
            "match": "text search with analysis",
            "wildcard": "pattern matching"
        }
        
        rationale = f"Chose '{operator_type}' operator for {operator_explanations.get(operator_type, 'appropriate filtering')}"
        
        if relevant_hints:
            rationale += f" based on prompt language: '{relevant_hints[0]['text']}'"
        
        # Extract field and value from filter
        filter_content = filter_info.get("content", {})
        field_name = list(filter_content.keys())[0] if filter_content else None
        filter_value = filter_content.get(field_name) if field_name else None
        
        return DecisionExplanation(
            decision_type=DecisionType.OPERATOR_CHOICE,
            component=operator_type,
            field_name=field_name,
            value=filter_value,
            confidence=confidence,
            rationale=rationale,
            alternatives=[{"operator": alt, "confidence": 0.4} for alt in ["term", "match", "range"] if alt != operator_type][:2],
            prompt_evidence=[hint["text"] for hint in relevant_hints],
            technical_details={"operator_performance": "fast" if operator_type == "term" else "medium"}
        )
    
    def _calculate_overall_confidence(self, decisions: List[DecisionExplanation]) -> float:
        """Calculate overall confidence score"""
        if not decisions:
            return 0.5
        
        # Weighted average based on decision importance
        importance_weights = {
            DecisionType.FIELD_SELECTION: 0.3,
            DecisionType.TIME_FILTERING: 0.2,
            DecisionType.LOGICAL_STRUCTURE: 0.2,
            DecisionType.OPERATOR_CHOICE: 0.2,
            DecisionType.AGGREGATION: 0.1
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for decision in decisions:
            weight = importance_weights.get(decision.decision_type, 0.1)
            weighted_sum += decision.confidence * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5
    
    def _generate_query_summary(self, query: Dict[str, Any], prompt_analysis: Dict[str, Any]) -> str:
        """Generate human-readable query summary"""
        summary_parts = []
        
        # Start with action
        summary_parts.append("This query searches for")
        
        # Add security context if present
        security_context = prompt_analysis.get("security_context", [])
        if security_context:
            security_terms = [ctx["text"] for ctx in security_context[:2]]
            summary_parts.append(f"{' and '.join(security_terms)} events")
        else:
            summary_parts.append("log events")
        
        # Add temporal context
        temporal_components = prompt_analysis.get("temporal_components", [])
        if temporal_components:
            time_refs = [comp["text"] for comp in temporal_components[:1]]
            summary_parts.append(f"from {time_refs[0]}")
        
        # Add field constraints
        if "query" in query:
            fields = self._extract_fields(query["query"])
            if fields:
                field_summary = f"filtering by {', '.join(fields[:3])}"
                if len(fields) > 3:
                    field_summary += f" and {len(fields) - 3} other fields"
                summary_parts.append(field_summary)
        
        return " ".join(summary_parts) + "."
    
    def _assess_query_risks(self, query: Dict[str, Any], decisions: List[DecisionExplanation]) -> Dict[str, Any]:
        """Assess potential risks in the query"""
        risks = {
            "performance_risks": [],
            "security_risks": [],
            "accuracy_risks": [],
            "overall_risk_level": "low"
        }
        
        # Check for performance risks
        if "size" not in query:
            risks["performance_risks"].append("No size limit - may return excessive results")
        
        has_temporal_filter = any(d.decision_type == DecisionType.TIME_FILTERING for d in decisions)
        if not has_temporal_filter:
            risks["performance_risks"].append("No temporal filtering - query may be slow")
        
        # Check for security risks
        if any("match_all" in str(query).lower() for _ in [1]):
            risks["security_risks"].append("Overly broad query - may expose sensitive data")
        
        # Check for accuracy risks
        low_confidence_decisions = [d for d in decisions if d.confidence < 0.6]
        if low_confidence_decisions:
            risks["accuracy_risks"].append(f"Low confidence in {len(low_confidence_decisions)} decisions")
        
        # Calculate overall risk level
        total_risks = len(risks["performance_risks"]) + len(risks["security_risks"]) + len(risks["accuracy_risks"])
        if total_risks >= 3:
            risks["overall_risk_level"] = "high"
        elif total_risks >= 1:
            risks["overall_risk_level"] = "medium"
        
        return risks
    
    def _generate_optimizations(self, query: Dict[str, Any], decisions: List[DecisionExplanation], 
                              prompt_analysis: Dict[str, Any]) -> List[str]:
        """Generate optimization suggestions"""
        optimizations = []
        
        # Size limit optimization
        if "size" not in query:
            optimizations.append("Add size limit to prevent excessive results: e.g., 'size': 1000")
        
        # Temporal filter optimization
        has_temporal = any(d.decision_type == DecisionType.TIME_FILTERING for d in decisions)
        if not has_temporal:
            optimizations.append("Add temporal filtering to improve performance and relevance")
        
        # Field optimization
        used_fields = [d.field_name for d in decisions if d.field_name]
        if len(used_fields) > 5:
            optimizations.append("Consider reducing number of filter fields to improve performance")
        
        # Index optimization
        optimizations.append("Ensure filtered fields are properly indexed for optimal performance")
        
        # Low confidence optimization
        low_conf_decisions = [d for d in decisions if d.confidence < 0.6]
        if low_conf_decisions:
            optimizations.append(f"Review {len(low_conf_decisions)} low-confidence decisions for accuracy")
        
        return optimizations
    
    def _calculate_query_complexity(self, query: Dict[str, Any]) -> float:
        """Calculate query complexity score"""
        complexity_factors = {
            "query_depth": self._calculate_nesting_depth(query),
            "filter_count": len(self._extract_filters(query.get("query", {}))),
            "field_count": len(self._extract_fields(query.get("query", {}))),
            "has_aggregations": 1 if ("aggs" in query or "aggregations" in query) else 0,
            "has_sorting": 1 if "sort" in query else 0
        }
        
        # Normalize and weight factors
        normalized_complexity = (
            min(complexity_factors["query_depth"] / 5, 1.0) * 0.3 +
            min(complexity_factors["filter_count"] / 10, 1.0) * 0.25 +
            min(complexity_factors["field_count"] / 8, 1.0) * 0.25 +
            complexity_factors["has_aggregations"] * 0.1 +
            complexity_factors["has_sorting"] * 0.1
        )
        
        return normalized_complexity
    
    def _calculate_nesting_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of query structure"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_nesting_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

def explain_query_file(query_file: str, prompt: str, level: ExplanationLevel = ExplanationLevel.DETAILED) -> QueryExplanation:
    """Explain a query from a file"""
    with open(query_file) as f:
        query = json.load(f)
    
    explainer = QueryExplainer()
    return explainer.explain_query(prompt, query, level)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Explain ES DSL query generation")
    parser.add_argument("--query", required=True, help="JSON file containing ES DSL query")
    parser.add_argument("--prompt", required=True, help="Original natural language prompt")
    parser.add_argument("--level", choices=["basic", "detailed", "technical", "research"], 
                       default="detailed", help="Explanation detail level")
    parser.add_argument("--output", help="Output file for explanation")
    
    args = parser.parse_args()
    
    # Generate explanation
    level = ExplanationLevel(args.level)
    explanation = explain_query_file(args.query, args.prompt, level)
    
    # Print summary
    print("=== QUERY EXPLANATION ===")
    print(f"Prompt: {explanation.original_prompt}")
    print(f"Summary: {explanation.query_summary}")
    print(f"Confidence: {explanation.confidence_score:.2f}")
    print(f"Complexity: {explanation.complexity_score:.2f}")
    print(f"Risk Level: {explanation.risk_assessment['overall_risk_level']}")
    
    print(f"\n=== DECISIONS ({len(explanation.decisions)}) ===")
    for i, decision in enumerate(explanation.decisions, 1):
        print(f"{i}. {decision.decision_type.value.title()}: {decision.rationale}")
        print(f"   Confidence: {decision.confidence:.2f}")
        if decision.prompt_evidence:
            print(f"   Evidence: {', '.join(decision.prompt_evidence)}")
    
    if explanation.optimization_suggestions:
        print(f"\n=== OPTIMIZATIONS ===")
        for i, opt in enumerate(explanation.optimization_suggestions, 1):
            print(f"{i}. {opt}")
    
    # Save detailed explanation if output specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(explanation.to_dict(), f, indent=2)
        print(f"\nDetailed explanation saved to {args.output}")

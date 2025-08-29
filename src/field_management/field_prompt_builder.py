"""
Field-Aware Prompt Builder - Enhances prompts with dynamic field examples and corrections
"""

import json
import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class FieldPromptBuilder:
    """Builds enhanced prompts with field-specific examples and corrections."""
    
    def __init__(self, field_context_manager=None, field_validator=None, field_trainer=None):
        self.field_context_manager = field_context_manager
        self.field_validator = field_validator
        self.field_trainer = field_trainer
        
    def build_enhanced_prompt(self, 
                            base_prompt: str, 
                            user_query: str, 
                            index: str = None,
                            include_examples: bool = True,
                            include_negative_examples: bool = True,
                            include_learned_corrections: bool = True) -> str:
        """Build an enhanced prompt with field-specific guidance."""
        
        enhanced_sections = [
            self._build_field_reference_section(index),
            self._build_field_rules_section(),
            base_prompt
        ]
        
        if include_examples:
            examples_section = self._build_examples_section(user_query, index)
            if examples_section:
                enhanced_sections.insert(-1, examples_section)
        
        if include_negative_examples:
            negative_section = self._build_negative_examples_section(user_query, index)
            if negative_section:
                enhanced_sections.insert(-1, negative_section)
        
        if include_learned_corrections and self.field_trainer:
            corrections_section = self._build_learned_corrections_section(user_query, index)
            if corrections_section:
                enhanced_sections.insert(-1, corrections_section)
        
        # Add final validation reminder
        enhanced_sections.append(self._build_validation_reminder())
        
        return "\n\n".join(enhanced_sections)
    
    def _build_field_reference_section(self, index: str = None) -> str:
        """Build comprehensive field reference section."""
        if not self.field_context_manager:
            return "=== FIELD REFERENCE ===\nUSE ONLY VALID FIELD NAMES"
        
        return self.field_context_manager.build_field_prompt_context(index)
    
    def _build_field_rules_section(self) -> str:
        """Build field usage rules section."""
        return """=== CRITICAL FIELD RULES ===
🚨 FIELD NAME ENFORCEMENT:
• NEVER use dot notation (source.ip, destination.port) - use underscores
• NEVER use ECS field names - use exact field names from reference above
• NEVER guess field names - use only fields listed in reference
• Timestamp field is ALWAYS '@timestamp' (with @), never 'timestamp'
• IP fields: use 'src_ip' and 'dst_ip', NOT 'source_ip' or 'destination_ip'
• Port fields: use 'src_port' and 'dst_port', NOT 'source_port' or 'destination_port'

⚡ IMMEDIATE REJECTION for queries using invalid field names!"""
    
    def _build_examples_section(self, user_query: str, index: str = None) -> Optional[str]:
        """Build examples section with relevant field usage."""
        if not self.field_context_manager:
            return None
        
        # Detect potential fields mentioned in query
        potential_fields = self._extract_field_hints_from_query(user_query)
        
        if not potential_fields:
            return self._build_general_examples()
        
        examples = []
        examples.append("=== FIELD USAGE EXAMPLES ===")
        
        for field_hint in potential_fields[:3]:  # Limit to 3 examples
            field_examples = self._generate_field_specific_examples(field_hint, index)
            if field_examples:
                examples.extend(field_examples)
        
        return "\n".join(examples) if len(examples) > 1 else None
    
    def _build_negative_examples_section(self, user_query: str, index: str = None) -> Optional[str]:
        """Build section showing what NOT to do."""
        negative_examples = [
            "=== WRONG FIELD USAGE (DO NOT DO THIS) ===",
            "❌ BAD: {\"term\": {\"source.ip\": \"192.168.1.1\"}}",
            "✅ CORRECT: {\"term\": {\"src_ip\": \"192.168.1.1\"}}",
            "",
            "❌ BAD: {\"range\": {\"timestamp\": {\"gte\": \"2024-01-01\"}}}",
            "✅ CORRECT: {\"range\": {\"@timestamp\": {\"gte\": \"2024-01-01\"}}}",
            "",
            "❌ BAD: {\"term\": {\"destination_port\": 80}}",
            "✅ CORRECT: {\"term\": {\"dst_port\": 80}}"
        ]
        
        # Add learned negative examples
        if self.field_trainer:
            learned_negatives = self._get_learned_negative_examples(user_query)
            if learned_negatives:
                negative_examples.append("")
                negative_examples.append("🔥 COMMON MISTAKES TO AVOID:")
                negative_examples.extend(learned_negatives)
        
        return "\n".join(negative_examples)
    
    def _build_learned_corrections_section(self, user_query: str, index: str = None) -> Optional[str]:
        """Build section with learned field corrections."""
        if not self.field_trainer:
            return None
        
        learned_mappings = self.field_trainer.get_learned_mappings()
        if not learned_mappings:
            return None
        
        corrections = [
            "=== LEARNED FIELD CORRECTIONS ===",
            "🧠 Based on previous corrections:"
        ]
        
        # Show most relevant corrections
        query_lower = user_query.lower()
        relevant_corrections = []
        
        for wrong_field, correct_field in learned_mappings.items():
            # Check if this correction is relevant to the query
            if (wrong_field.lower() in query_lower or 
                any(word in query_lower for word in wrong_field.split('_')) or
                self._is_semantically_relevant(user_query, wrong_field, correct_field)):
                relevant_corrections.append((wrong_field, correct_field))
        
        # If no relevant corrections, show top general ones
        if not relevant_corrections:
            relevant_corrections = list(learned_mappings.items())[:5]
        
        for wrong, correct in relevant_corrections[:5]:
            corrections.append(f"• NEVER use '{wrong}' → ALWAYS use '{correct}'")
        
        return "\n".join(corrections) if len(corrections) > 2 else None
    
    def _build_validation_reminder(self) -> str:
        """Build final validation reminder."""
        return """⚠️ FINAL VALIDATION CHECKPOINT:
Before generating your query, verify:
1. All field names match EXACTLY the reference above
2. No dot notation used (no source.ip, destination.port, etc.)
3. Timestamp field uses '@timestamp' with @
4. IP fields use src_ip/dst_ip format
5. Port fields use src_port/dst_port format

GENERATE QUERY ONLY IF ALL FIELDS ARE VALID!"""
    
    def _extract_field_hints_from_query(self, query: str) -> List[str]:
        """Extract potential field references from user query."""
        field_hints = []
        query_lower = query.lower()
        
        # Common field indicators
        field_patterns = {
            "src_ip": ["source ip", "source address", "from ip", "client ip", "src ip"],
            "dst_ip": ["destination ip", "dest ip", "to ip", "server ip", "target ip"],
            "src_port": ["source port", "from port", "client port", "src port"],
            "dst_port": ["destination port", "dest port", "to port", "server port", "target port"],
            "@timestamp": ["timestamp", "time", "date", "when", "during", "between"],
            "protocol": ["protocol", "tcp", "udp", "http", "https"],
            "bytes_in": ["bytes received", "inbound", "incoming bytes", "download"],
            "bytes_out": ["bytes sent", "outbound", "outgoing bytes", "upload"],
            "label": ["label", "classification", "type", "category", "malicious", "benign"]
        }
        
        for field, indicators in field_patterns.items():
            if any(indicator in query_lower for indicator in indicators):
                field_hints.append(field)
        
        return field_hints
    
    def _generate_field_specific_examples(self, field: str, index: str = None) -> List[str]:
        """Generate specific examples for a field."""
        if not self.field_context_manager:
            return []
        
        context = self.field_context_manager.get_field_context(field)
        if not context:
            return []
        
        examples = [f"\n📋 {field.upper()} Examples:"]
        
        # Add type-specific examples
        field_type = context.get("type", "unknown")
        example_values = context.get("examples", [])
        
        if field_type == "keyword" and example_values:
            examples.append(f"  Term query: {{\"term\": {{\"{field}\": \"{example_values[0]}\"}}}}")
            if len(example_values) > 1:
                examples.append(f"  Terms query: {{\"terms\": {{\"{field}\": {json.dumps(example_values[:3])}}}}}")
        
        elif field_type in ["integer", "long", "float"] and example_values:
            examples.append(f"  Exact match: {{\"term\": {{\"{field}\": {example_values[0]}}}}}")
            examples.append(f"  Range query: {{\"range\": {{\"{field}\": {{\"gte\": {example_values[0]}, \"lte\": {example_values[1] if len(example_values) > 1 else example_values[0] * 2}}}}}}}")
        
        elif field_type == "date":
            examples.append(f"  Time range: {{\"range\": {{\"{field}\": {{\"gte\": \"2024-01-01T00:00:00Z\", \"lte\": \"2024-01-02T00:00:00Z\"}}}}}}")
            examples.append(f"  Field exists: {{\"exists\": {{\"field\": \"{field}\"}}}}")
        
        return examples
    
    def _build_general_examples(self) -> str:
        """Build general field usage examples."""
        return """=== GENERAL FIELD EXAMPLES ===
✅ IP Address Filtering:
{"term": {"src_ip": "192.168.1.100"}}
{"term": {"dst_ip": "10.0.0.1"}}

✅ Port Filtering:
{"term": {"src_port": 80}}
{"range": {"dst_port": {"gte": 8000, "lte": 9000}}}

✅ Time Range:
{"range": {"@timestamp": {"gte": "2024-01-01T00:00:00Z", "lte": "2024-01-02T00:00:00Z"}}}

✅ Protocol and Label:
{"term": {"protocol": "tcp"}}
{"term": {"label": "malicious"}}"""
    
    def _get_learned_negative_examples(self, query: str) -> List[str]:
        """Get learned negative examples relevant to query."""
        if not self.field_trainer:
            return []
        
        learned_mappings = self.field_trainer.get_learned_mappings()
        query_lower = query.lower()
        
        relevant_mistakes = []
        for wrong_field, correct_field in learned_mappings.items():
            if (wrong_field.lower() in query_lower or 
                any(word in query_lower for word in wrong_field.split('_'))):
                relevant_mistakes.append(f"• NEVER '{wrong_field}' → USE '{correct_field}'")
        
        return relevant_mistakes[:3]  # Limit to top 3
    
    def _is_semantically_relevant(self, query: str, wrong_field: str, correct_field: str) -> bool:
        """Check if a field correction is semantically relevant to the query."""
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        field_words = set(re.findall(r'\b\w+\b', wrong_field.lower() + ' ' + correct_field.lower()))
        
        # Simple overlap check
        overlap = len(query_words & field_words)
        return overlap >= 1
    
    def build_validation_prompt(self, generated_query: Dict, original_prompt: str, index: str = None) -> str:
        """Build prompt for validating a generated query."""
        validation_prompt = f"""=== QUERY VALIDATION REQUEST ===
Original prompt: {original_prompt}
Generated query: {json.dumps(generated_query, indent=2)}
Target index: {index or 'unspecified'}

Please validate this query for:
1. Field name correctness (no ECS names, no dot notation)
2. Field existence in target index
3. Proper query structure
4. Type compatibility

"""
        
        if self.field_validator:
            # Add field-specific validation context
            validation_prompt += self._build_field_reference_section(index)
            validation_prompt += "\n\n" + self._build_field_rules_section()
        
        validation_prompt += """
Respond with:
- VALID: if query uses correct field names and structure  
- INVALID: if any field names are incorrect, with specific corrections needed
- SUGGESTIONS: any recommended improvements"""
        
        return validation_prompt
    
    def extract_and_enhance_field_context(self, query: str, index: str = None) -> Dict:
        """Extract field context from query and enhance with suggestions."""
        context = {
            "detected_fields": [],
            "field_suggestions": {},
            "validation_status": {},
            "enhancement_recommendations": []
        }
        
        # Extract fields from query
        if isinstance(query, str):
            try:
                query_dict = json.loads(query)
            except:
                return context
        else:
            query_dict = query
        
        # Get fields using validator
        if self.field_validator:
            extracted_fields = self.field_validator._extract_fields_from_query(query_dict)
            context["detected_fields"] = list(extracted_fields)
            
            # Validate each field
            for field in extracted_fields:
                is_valid, suggestion, confidence = self.field_validator.validate_field(field, index)
                context["validation_status"][field] = {
                    "is_valid": is_valid,
                    "suggestion": suggestion,
                    "confidence": confidence
                }
                
                if not is_valid and suggestion:
                    context["field_suggestions"][field] = suggestion
        
        # Add enhancement recommendations
        if context["field_suggestions"]:
            context["enhancement_recommendations"].append(
                f"Found {len(context['field_suggestions'])} field corrections needed"
            )
        
        return context
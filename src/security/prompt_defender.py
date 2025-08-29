"""
Prompt defender for protecting against prompt injection attacks.
Implements multiple layers of defense including input isolation and prompt verification.
"""

import re
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from .patterns import get_compiled_patterns, INJECTION_PATTERNS

@dataclass
class PromptDefense:
    """Results of prompt defense analysis."""
    is_safe: bool
    confidence: float
    detected_injections: List[str]
    isolation_applied: bool
    risk_level: str
    sanitized_input: str
    explanation: str

class PromptDefender:
    """Defends against prompt injection attacks through multiple security layers."""
    
    def __init__(self):
        self.compiled_patterns = get_compiled_patterns()
        
        # Extended injection patterns beyond base patterns
        self.advanced_injection_patterns = [
            # System prompt markers
            r'(?i)\b(system|user|assistant|human|ai)\s*[:=]\s*',
            r'(?i)<\s*(system|user|assistant|human|ai)\s*>',
            r'(?i)\[\s*(system|user|assistant|human|ai)\s*\]',
            r'(?i)```\s*(system|user|assistant|human|ai)',
            
            # Prompt termination attempts  
            r'(?i)(end\s+of\s+prompt|prompt\s+ends?)',
            r'(?i)(start\s+new\s+prompt|new\s+prompt\s+begins?)',
            r'(?i)(ignore\s+above|forget\s+previous)',
            r'(?i)(override\s+instructions|new\s+instructions)',
            
            # Control sequence injections
            r'\\n\\n|\\r\\n|\\t',  # Encoded newlines/tabs
            r'%0[aA]|%0[dD]|%09',  # URL-encoded control chars
            r'&#10;|&#13;|&#09;',  # HTML-encoded control chars
            
            # Template injection attempts
            r'\{\{\s*.*\s*\}\}',  # Template expressions
            r'\$\{.*\}',  # Variable substitutions
            r'<%.*%>',  # ASP/JSP style
            
            # Code injection patterns
            r'(?i)(exec|eval|import|require)\s*\(',
            r'(?i)(script|javascript|python|bash)\s*:',
            r'(?i)<script[^>]*>',
        ]
        self.compiled_advanced_patterns = [re.compile(p) for p in self.advanced_injection_patterns]
        
        # Trusted prompt markers for verification
        self.trusted_markers = {
            'system_start': '<!-- SYSTEM_PROMPT_START -->',
            'system_end': '<!-- SYSTEM_PROMPT_END -->',
            'user_start': '<!-- USER_INPUT_START -->',
            'user_end': '<!-- USER_INPUT_END -->'
        }
        
        # Isolation boundary patterns
        self.boundary_patterns = [
            r'(?i)(end|stop|finish|conclude)\s+(prompt|instruction|system)',
            r'(?i)(new|different|alternative)\s+(prompt|instruction|task)',
            r'(?i)(switch|change|modify)\s+(mode|role|behavior)',
        ]
        self.compiled_boundary_patterns = [re.compile(p) for p in self.boundary_patterns]
    
    def detect_prompt_injections(self, text: str) -> List[Tuple[str, float, str]]:
        """Detect various types of prompt injection attempts."""
        detections = []
        
        # Check base injection patterns
        for pattern in self.compiled_patterns['injection']:
            matches = pattern.finditer(text)
            for match in matches:
                detections.append((
                    "basic_injection", 
                    0.8, 
                    f"Pattern: {match.group()[:20]}..."
                ))
        
        # Check advanced injection patterns
        for i, pattern in enumerate(self.compiled_advanced_patterns):
            matches = pattern.finditer(text)
            for match in matches:
                injection_type = self._classify_injection_type(i, match.group())
                confidence = self._calculate_injection_confidence(injection_type, match.group())
                detections.append((
                    injection_type,
                    confidence,
                    f"Pattern: {match.group()[:30]}..."
                ))
        
        # Check for boundary violations
        for pattern in self.compiled_boundary_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                detections.append((
                    "boundary_violation",
                    0.7,
                    f"Boundary: {match.group()}"
                ))
        
        return detections
    
    def _classify_injection_type(self, pattern_index: int, matched_text: str) -> str:
        """Classify the type of injection based on pattern index and content."""
        if pattern_index < 4:
            return "system_marker_injection"
        elif pattern_index < 8:
            return "prompt_termination"
        elif pattern_index < 11:
            return "control_sequence_injection"
        elif pattern_index < 14:
            return "template_injection"
        else:
            return "code_injection"
    
    def _calculate_injection_confidence(self, injection_type: str, matched_text: str) -> float:
        """Calculate confidence based on injection type and content."""
        base_confidence = {
            "system_marker_injection": 0.9,
            "prompt_termination": 0.8,
            "control_sequence_injection": 0.7,
            "template_injection": 0.6,
            "code_injection": 0.9,
            "boundary_violation": 0.7
        }.get(injection_type, 0.5)
        
        # Boost confidence for suspicious combinations
        if 'system' in matched_text.lower() and ':' in matched_text:
            base_confidence += 0.1
        
        if len(matched_text) > 20:  # Long injections are more suspicious
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def isolate_user_input(self, user_input: str) -> str:
        """Isolate user input to prevent prompt bleeding."""
        # Remove or neutralize control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', user_input)
        
        # Escape potential injection markers
        sanitized = sanitized.replace('```', '\\`\\`\\`')
        sanitized = sanitized.replace('System:', 'System\\:')
        sanitized = sanitized.replace('User:', 'User\\:')
        sanitized = sanitized.replace('Assistant:', 'Assistant\\:')
        
        # Remove HTML/XML-like tags
        sanitized = re.sub(r'<[^>]+>', '', sanitized)
        
        # Wrap in isolation markers
        isolated = f"{self.trusted_markers['user_start']}\n{sanitized}\n{self.trusted_markers['user_end']}"
        
        return isolated
    
    def verify_prompt_integrity(self, full_prompt: str) -> Tuple[bool, str]:
        """Verify that the prompt hasn't been compromised."""
        # Check for trusted markers
        has_start_marker = self.trusted_markers['user_start'] in full_prompt
        has_end_marker = self.trusted_markers['user_end'] in full_prompt
        
        if not (has_start_marker and has_end_marker):
            return False, "Missing isolation markers"
        
        # Extract user section
        try:
            start_pos = full_prompt.find(self.trusted_markers['user_start'])
            end_pos = full_prompt.find(self.trusted_markers['user_end'])
            
            if start_pos == -1 or end_pos == -1 or start_pos >= end_pos:
                return False, "Malformed isolation markers"
            
            user_section = full_prompt[start_pos:end_pos + len(self.trusted_markers['user_end'])]
            
            # Check for injection attempts within user section
            injections = self.detect_prompt_injections(user_section)
            if injections:
                return False, f"Injections detected in user section: {len(injections)}"
            
        except Exception as e:
            return False, f"Error parsing prompt structure: {e}"
        
        return True, "Prompt integrity verified"
    
    def calculate_defense_confidence(self, injections: List[Tuple[str, float, str]],
                                   isolation_applied: bool, integrity_verified: bool) -> float:
        """Calculate overall confidence in defense effectiveness."""
        if not injections:
            base_confidence = 0.9
        else:
            # Confidence decreases with injection severity
            max_injection_conf = max(conf for _, conf, _ in injections)
            base_confidence = 1.0 - max_injection_conf
        
        # Boost confidence if isolation and verification applied
        if isolation_applied:
            base_confidence += 0.1
        
        if integrity_verified:
            base_confidence += 0.1
        
        # Reduce confidence for multiple injections
        if len(injections) > 1:
            base_confidence *= 0.9
        
        if len(injections) > 3:
            base_confidence *= 0.8
        
        return min(base_confidence, 1.0)
    
    def defend(self, user_input: str, apply_isolation: bool = True) -> PromptDefense:
        """Comprehensive prompt defense analysis and protection."""
        if not user_input:
            return PromptDefense(
                is_safe=True,
                confidence=1.0,
                detected_injections=[],
                isolation_applied=False,
                risk_level='low',
                sanitized_input='',
                explanation="Empty input is safe"
            )
        
        # Detect injection attempts
        injections = self.detect_prompt_injections(user_input)
        
        # Apply isolation if requested
        sanitized_input = user_input
        isolation_applied = False
        
        if apply_isolation:
            sanitized_input = self.isolate_user_input(user_input)
            isolation_applied = True
        
        # Verify prompt integrity if isolation applied
        integrity_verified = False
        if isolation_applied:
            integrity_verified, _ = self.verify_prompt_integrity(sanitized_input)
        
        # Calculate defense confidence
        confidence = self.calculate_defense_confidence(
            injections, isolation_applied, integrity_verified
        )
        
        # Determine safety
        is_safe = confidence > 0.6 and (not injections or isolation_applied)
        
        # Determine risk level
        risk_level = self._determine_risk_level(confidence, injections)
        
        # Extract injection details for reporting
        detected_injections = [f"{inj_type}: {desc}" for inj_type, _, desc in injections]
        
        # Generate explanation
        explanation = self._generate_explanation(
            is_safe, confidence, injections, isolation_applied, integrity_verified
        )
        
        return PromptDefense(
            is_safe=is_safe,
            confidence=confidence,
            detected_injections=detected_injections,
            isolation_applied=isolation_applied,
            risk_level=risk_level,
            sanitized_input=sanitized_input,
            explanation=explanation
        )
    
    def _determine_risk_level(self, confidence: float, 
                            injections: List[Tuple[str, float, str]]) -> str:
        """Determine risk level based on confidence and injection types."""
        if confidence > 0.8 and not injections:
            return 'low'
        elif confidence > 0.6 and len(injections) <= 1:
            return 'medium'
        elif confidence > 0.4 or any('system_marker' in inj[0] for inj in injections):
            return 'high'
        else:
            return 'critical'
    
    def _generate_explanation(self, is_safe: bool, confidence: float,
                            injections: List[Tuple[str, float, str]],
                            isolation_applied: bool, integrity_verified: bool) -> str:
        """Generate human-readable explanation of defense results."""
        if is_safe and confidence > 0.8:
            protection_desc = "Input is safe"
            if isolation_applied:
                protection_desc += " with isolation applied"
            return f"{protection_desc} (confidence: {confidence:.2f})"
        
        issues = []
        
        if injections:
            injection_types = list(set(inj[0] for inj in injections))
            issues.append(f"Injections detected: {', '.join(injection_types)}")
        
        if isolation_applied:
            issues.append("Isolation applied")
        
        if not integrity_verified and isolation_applied:
            issues.append("Integrity verification failed")
        
        issue_summary = "; ".join(issues) if issues else "Prompt defense analysis complete"
        
        safety_desc = "SAFE" if is_safe else "UNSAFE"
        
        return f"{safety_desc}: {issue_summary} (confidence: {confidence:.2f})"
    
    def quick_check(self, text: str) -> bool:
        """Quick check for obvious injection attempts."""
        if not text:
            return True
        
        # Quick pattern checks
        for pattern in self.compiled_patterns['injection'][:3]:  # First 3 patterns
            if pattern.search(text):
                return False
        
        for pattern in self.compiled_advanced_patterns[:5]:  # First 5 advanced
            if pattern.search(text):
                return False
        
        return True
"""
Context validator for protecting against role confusion and context manipulation attacks.
Ensures queries stay within legitimate security analysis scope.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from .patterns import (
    ROLE_CONFUSION_PATTERNS,
    SOCIAL_ENGINEERING_PATTERNS,
    VALID_SECURITY_CONTEXTS,
    INVALID_CONTEXTS,
    get_compiled_patterns
)

@dataclass
class ContextValidation:
    """Results of context validation analysis."""
    is_valid: bool
    confidence: float
    violations: List[str]
    detected_attacks: List[str]
    security_context: Optional[str]
    risk_level: str
    explanation: str

class ContextValidator:
    """Validates query context and protects against role confusion attacks."""
    
    def __init__(self):
        self.compiled_patterns = get_compiled_patterns()
        
        # System boundary protection patterns
        self.boundary_violations = [
            r'(?i)\b(you\s+are\s+not|stop\s+being)\s+.*(assistant|ai|bot)',
            r'(?i)\b(forget|ignore|override|bypass)\s+.*(instructions|guidelines|rules)',
            r'(?i)\b(new\s+role|different\s+role|change\s+your\s+role)',
            r'(?i)\b(break\s+character|step\s+out\s+of\s+character)',
            r'(?i)\b(disable|turn\s+off)\s+.*(safety|filters|restrictions)',
            r'(?i)\b(act\s+like|behave\s+like|pretend\s+to\s+be)\s+(?!.*security)',
        ]
        self.compiled_boundary_patterns = [re.compile(p) for p in self.boundary_violations]
        
        # Valid security query contexts
        self.security_context_patterns = [
            (r'(?i)\b(detect|find|identify|locate)\s+.*(threat|malware|intrusion|attack)', 'threat_detection'),
            (r'(?i)\b(monitor|watch|track|observe)\s+.*(activity|behavior|traffic|logs)', 'network_monitoring'),
            (r'(?i)\b(analyze|investigate|examine)\s+.*(incident|event|breach|compromise)', 'incident_response'),
            (r'(?i)\b(audit|check|verify|validate)\s+.*(compliance|security|access)', 'compliance_check'),
            (r'(?i)\b(hunt|search|look\s+for)\s+.*(indicators|iocs|artifacts)', 'threat_hunting'),
            (r'(?i)\b(forensic|digital\s+investigation|evidence)', 'forensic_analysis'),
            # Network analysis patterns (legitimate cybersecurity use cases)
            (r'(?i)\b(find|show|get|search)\s+.*(traffic|network|connection|flow)', 'network_analysis'),
            (r'(?i)\b(filter|query)\s+.*(events|data|logs|activity)', 'log_analysis'),
            (r'(?i)\b(from|to|with)\s+.*(ip|address|port|protocol)', 'network_filtering'),
            (r'(?i)\b(events|data|logs|activity)\s+.*(from|to|with|on)', 'data_analysis'),
            (r'(?i)\b(yesterday|today|recent|between|during|time)', 'temporal_analysis'),
        ]
        self.compiled_security_patterns = [(re.compile(p), ctx) for p, ctx in self.security_context_patterns]
        
        # Invalid context indicators
        self.invalid_context_patterns = [
            (r'(?i)\b(extract|download|steal|exfiltrate)\s+.*(data|files|information)', 'data_extraction'),
            (r'(?i)\b(performance|optimization|tuning|benchmark)', 'performance_monitoring'),
            (r'(?i)\b(marketing|sales|customer|business\s+analytics)', 'business_analytics'),
            (r'(?i)\b(personal|private|individual)\s+.*(data|information|details)', 'privacy_violation'),
            (r'(?i)\b(system\s+administration|admin|root|sudo)', 'system_administration'),
        ]
        self.compiled_invalid_patterns = [(re.compile(p), ctx) for p, ctx in self.invalid_context_patterns]
        
        # Authority manipulation patterns
        self.authority_patterns = [
            r'(?i)\b(i\s+am|i\'m)\s+.*(admin|administrator|root|superuser)',
            r'(?i)\b(my\s+boss|supervisor|manager)\s+.*(said|told|authorized)',
            r'(?i)\b(emergency|urgent|critical)\s+.*(access|override|bypass)',
            r'(?i)\b(special\s+permission|authorized\s+user|clearance)',
            r'(?i)\b(on\s+behalf\s+of|representing)\s+.*(company|organization)',
        ]
        self.compiled_authority_patterns = [re.compile(p) for p in self.authority_patterns]
    
    def detect_role_confusion(self, text: str) -> List[Tuple[str, float]]:
        """Detect attempts to confuse or change system role."""
        detections = []
        
        # Check for role confusion patterns
        for pattern in self.compiled_patterns['role_confusion']:
            if pattern.search(text):
                detections.append(("role_confusion", 0.8))
        
        # Check for boundary violations
        for pattern in self.compiled_boundary_patterns:
            if pattern.search(text):
                detections.append(("boundary_violation", 0.9))
        
        # Check for social engineering
        for pattern in self.compiled_patterns['social_engineering']:
            if pattern.search(text):
                detections.append(("social_engineering", 0.7))
        
        # Check for authority manipulation
        for pattern in self.compiled_authority_patterns:
            if pattern.search(text):
                detections.append(("authority_manipulation", 0.6))
        
        return detections
    
    def classify_security_context(self, text: str) -> Optional[str]:
        """Classify the security context of the query."""
        # Check for valid security contexts
        for pattern, context in self.compiled_security_patterns:
            if pattern.search(text):
                return context
        
        # Check for invalid contexts
        for pattern, context in self.compiled_invalid_patterns:
            if pattern.search(text):
                return f"invalid:{context}"
        
        return None
    
    def detect_context_switching(self, text: str) -> List[str]:
        """Detect attempts to switch context mid-query."""
        switches = []
        
        # Look for context transition markers
        transition_patterns = [
            r'(?i)\b(but\s+really|actually|however|instead)',
            r'(?i)\b(forget\s+that|never\s+mind|scratch\s+that)',
            r'(?i)\b(what\s+i\s+really\s+want|what\s+i\s+actually\s+need)',
            r'(?i)\b(the\s+real\s+question|my\s+actual\s+goal)',
        ]
        
        for pattern in transition_patterns:
            if re.search(pattern, text):
                switches.append(pattern)
        
        return switches
    
    def validate_query_scope(self, text: str) -> Tuple[bool, str]:
        """Validate that query stays within security analysis scope."""
        # Check for out-of-scope requests
        out_of_scope_patterns = [
            r'(?i)\b(general\s+purpose|any\s+topic|anything\s+i\s+want)',
            r'(?i)\b(creative\s+writing|story|fiction|roleplay)',
            r'(?i)\b(personal\s+assistant|help\s+with\s+homework)',
            r'(?i)\b(weather|sports|entertainment|cooking)',
            r'(?i)\b(programming\s+tutorial|how\s+to\s+code)',
        ]
        
        for pattern in out_of_scope_patterns:
            if re.search(pattern, text):
                return False, f"Out of scope: {pattern}"
        
        # Must contain security-related terms or legitimate network analysis terms
        security_terms = [
            'security', 'attack', 'threat', 'malicious', 'intrusion',
            'breach', 'vulnerability', 'incident', 'forensic', 'audit',
            'monitor', 'detect', 'analyze', 'investigate', 'log', 'pattern',
            'suspicious', 'anomalous', 'indicators', 'compromise',
            # Network analysis terms (legitimate for cybersecurity)
            'traffic', 'network', 'connection', 'flow', 'packet', 'bytes',
            'port', 'protocol', 'ip', 'address', 'src', 'dst', 'source', 'destination',
            'events', 'activity', 'data', 'query', 'search', 'find', 'show', 'get',
            # Time-based analysis terms
            'yesterday', 'today', 'recent', 'between', 'during', 'time', 'range'
        ]
        
        text_lower = text.lower()
        has_security_context = any(term in text_lower for term in security_terms)
        
        if not has_security_context:
            return False, "No security context detected"
        
        return True, "Valid security scope"
    
    def calculate_context_confidence(self, detections: List[Tuple[str, float]], 
                                   text: str) -> float:
        """Calculate confidence in context validation."""
        if not detections:
            # Check if query is in valid scope
            in_scope, _ = self.validate_query_scope(text)
            return 0.9 if in_scope else 0.3
        
        # Base confidence from detections (inverted - high detection = low confidence)
        max_detection_conf = max(conf for _, conf in detections)
        base_confidence = 1.0 - max_detection_conf
        
        # Reduce confidence for multiple violations
        if len(detections) > 1:
            base_confidence *= 0.8
        
        if len(detections) > 2:
            base_confidence *= 0.7
        
        return max(base_confidence, 0.0)
    
    def validate(self, text: str) -> ContextValidation:
        """Comprehensive context validation."""
        if not text:
            return ContextValidation(
                is_valid=False,
                confidence=0.0,
                violations=[],
                detected_attacks=[],
                security_context=None,
                risk_level='low',
                explanation="Empty input"
            )
        
        # Detect role confusion attempts
        role_detections = self.detect_role_confusion(text)
        
        # Classify security context
        security_context = self.classify_security_context(text)
        
        # Detect context switching
        context_switches = self.detect_context_switching(text)
        
        # Validate query scope
        in_scope, scope_message = self.validate_query_scope(text)
        
        # Calculate confidence
        confidence = self.calculate_context_confidence(role_detections, text)
        
        # Compile violations
        violations = []
        detected_attacks = [attack for attack, _ in role_detections]
        
        if not in_scope:
            violations.append(f"Scope violation: {scope_message}")
        
        if security_context and security_context.startswith('invalid:'):
            violations.append(f"Invalid context: {security_context[8:]}")
        
        if context_switches:
            violations.append(f"Context switching detected: {len(context_switches)} instances")
        
        # Determine validity
        is_valid = (
            confidence > 0.6 and
            in_scope and
            len(detected_attacks) == 0 and
            (not security_context or not security_context.startswith('invalid:'))
        )
        
        # Determine risk level
        risk_level = self._determine_risk_level(confidence, detected_attacks, violations)
        
        # Generate explanation
        explanation = self._generate_explanation(
            is_valid, confidence, detected_attacks, violations, security_context
        )
        
        return ContextValidation(
            is_valid=is_valid,
            confidence=confidence,
            violations=violations,
            detected_attacks=detected_attacks,
            security_context=security_context,
            risk_level=risk_level,
            explanation=explanation
        )
    
    def _determine_risk_level(self, confidence: float, attacks: List[str], 
                            violations: List[str]) -> str:
        """Determine risk level based on validation results."""
        if confidence > 0.8 and not attacks and not violations:
            return 'low'
        elif confidence > 0.6 and len(attacks) <= 1:
            return 'medium'
        elif confidence > 0.3 or 'boundary_violation' in attacks:
            return 'high'
        else:
            return 'critical'
    
    def _generate_explanation(self, is_valid: bool, confidence: float, 
                            attacks: List[str], violations: List[str],
                            security_context: Optional[str]) -> str:
        """Generate human-readable explanation."""
        if is_valid and confidence > 0.8:
            context_desc = f"Valid {security_context}" if security_context else "Valid security context"
            return f"{context_desc} detected (confidence: {confidence:.2f})"
        
        issues = []
        
        if attacks:
            issues.append(f"Context attacks: {', '.join(set(attacks))}")
        
        if violations:
            issues.append(f"Violations: {len(violations)} detected")
        
        if security_context and security_context.startswith('invalid:'):
            issues.append(f"Invalid context: {security_context[8:]}")
        
        issue_summary = "; ".join(issues) if issues else "Context validation failed"
        
        return f"{issue_summary} (confidence: {confidence:.2f})"
    
    def quick_check(self, text: str) -> bool:
        """Quick check for obvious context violations."""
        if not text:
            return False
        
        # Quick check for role confusion
        for pattern in self.compiled_patterns['role_confusion'][:3]:  # Check first 3
            if pattern.search(text):
                return False
        
        # Quick boundary violation check
        for pattern in self.compiled_boundary_patterns[:2]:  # Check first 2
            if pattern.search(text):
                return False
        
        return True
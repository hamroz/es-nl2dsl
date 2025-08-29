"""
Semantic evasion detector for identifying obfuscated malicious intent.
Handles euphemisms, context manipulation, and semantic obfuscation.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from .patterns import (
    detect_euphemisms,
    MALICIOUS_KEYWORDS,
    EVASION_EUPHEMISMS,
    LEGITIMATE_SECURITY_PATTERNS,
    get_compiled_patterns
)

@dataclass
class EvasionDetection:
    """Results of evasion detection analysis."""
    is_evasive: bool
    confidence: float
    detected_patterns: List[str]
    euphemisms: List[str]
    obfuscated_intent: Optional[str]
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    explanation: str

class EvasionDetector:
    """Detects semantic evasion attempts in natural language queries."""
    
    def __init__(self):
        self.compiled_patterns = get_compiled_patterns()
        
        # Intent classification patterns
        self.malicious_intent_patterns = [
            r'(?i)\b(how\s+to|ways\s+to|methods\s+to)\s+.*(bypass|circumvent|evade)',
            r'(?i)\b(show\s+me|give\s+me|provide)\s+.*(exploit|vulnerability)',
            r'(?i)\b(create|generate|build)\s+.*(malware|virus|payload)',
            r'(?i)\b(find|identify|locate)\s+.*(weakness|backdoor|loophole)',
            r'(?i)\b(help\s+me|assist\s+me)\s+.*(infiltrate|breach|compromise)',
        ]
        self.compiled_malicious_patterns = [re.compile(p) for p in self.malicious_intent_patterns]
        
        # Contextual red flags
        self.context_red_flags = [
            r'(?i)\b(just|only|simply)\s+(for\s+)?(research|educational|academic)',
            r'(?i)\b(hypothetical|theoretical)\s+(question|scenario|case)',
            r'(?i)\b(asking\s+for\s+a\s+friend|friend\s+wants\s+to\s+know)',
            r'(?i)\b(out\s+of\s+curiosity|just\s+curious)',
            r'(?i)\b(no\s+malicious\s+intent|not\s+for\s+bad\s+purposes)',
            r'(?i)\b(legitimate\s+use\s+case|valid\s+reason)',
            r'(?i)\b(security\s+professional|pen\s+tester|white\s+hat)',
        ]
        self.compiled_context_flags = [re.compile(p) for p in self.context_red_flags]
        
        # Semantic similarity keywords for intent matching
        self.attack_synonyms = {
            'attack': ['assault', 'offensive', 'strike', 'raid', 'invasion'],
            'exploit': ['leverage', 'utilize', 'take advantage of', 'abuse'],
            'hack': ['breach', 'break into', 'crack', 'penetrate', 'infiltrate'],
            'malicious': ['harmful', 'dangerous', 'destructive', 'threatening'],
            'unauthorized': ['illegal', 'forbidden', 'prohibited', 'illicit'],
        }
    
    def detect_intent_obfuscation(self, text: str) -> List[Tuple[str, float]]:
        """Detect obfuscated malicious intent using pattern matching."""
        detections = []
        text_lower = text.lower()
        
        # Check for direct malicious patterns
        for pattern in self.compiled_malicious_patterns:
            if pattern.search(text):
                detections.append(("malicious_instruction", 0.8))
        
        # Check for euphemistic references
        euphemisms = detect_euphemisms(text)
        for euphemism in euphemisms:
            confidence = 0.6 if 'research' in euphemism else 0.7
            detections.append((f"euphemism: {euphemism}", confidence))
        
        # Check for contextual red flags
        for pattern in self.compiled_context_flags:
            if pattern.search(text):
                detections.append(("suspicious_context", 0.5))
        
        # Semantic similarity check
        for base_word, synonyms in self.attack_synonyms.items():
            if base_word in text_lower:
                continue  # Direct match, not obfuscated
            
            for synonym in synonyms:
                if synonym in text_lower:
                    detections.append((f"synonym_obfuscation: {synonym}->{base_word}", 0.6))
        
        return detections
    
    def analyze_query_legitimacy(self, text: str) -> Tuple[bool, float]:
        """Determine if query represents legitimate security analysis."""
        # Check for legitimate security patterns
        legitimate_score = 0.0
        for pattern in self.compiled_patterns['legitimate_security']:
            if pattern.search(text):
                legitimate_score += 0.2
        
        # Legitimate security terms
        legitimate_terms = [
            'detect', 'monitor', 'analyze', 'investigate', 'identify',
            'alert', 'log', 'audit', 'compliance', 'forensic',
            'incident response', 'threat hunting', 'soc', 'siem'
        ]
        
        text_lower = text.lower()
        for term in legitimate_terms:
            if term in text_lower:
                legitimate_score += 0.1
        
        # Cap at 1.0 and determine legitimacy
        legitimate_score = min(legitimate_score, 1.0)
        is_legitimate = legitimate_score > 0.6
        
        return is_legitimate, legitimate_score
    
    def calculate_evasion_confidence(self, detections: List[Tuple[str, float]], 
                                   text: str) -> float:
        """Calculate overall confidence in evasion attempt."""
        if not detections:
            return 0.0
        
        # Base confidence from detections
        base_confidence = max(conf for _, conf in detections)
        
        # Boost confidence for multiple indicators
        if len(detections) > 1:
            base_confidence += 0.2
        
        if len(detections) > 2:
            base_confidence += 0.1
        
        # Reduce confidence if legitimate patterns present
        is_legitimate, legit_score = self.analyze_query_legitimacy(text)
        if is_legitimate:
            base_confidence *= (1.0 - legit_score * 0.5)
        
        return min(base_confidence, 1.0)
    
    def determine_risk_level(self, confidence: float, detections: List[Tuple[str, float]]) -> str:
        """Determine risk level based on confidence and detection types."""
        if confidence < 0.3:
            return 'low'
        elif confidence < 0.6:
            return 'medium'
        elif confidence < 0.8:
            return 'high'
        else:
            return 'critical'
    
    def detect(self, text: str) -> EvasionDetection:
        """Comprehensive evasion detection analysis."""
        if not text:
            return EvasionDetection(
                is_evasive=False,
                confidence=0.0,
                detected_patterns=[],
                euphemisms=[],
                obfuscated_intent=None,
                risk_level='low',
                explanation="Empty input"
            )
        
        # Detect intent obfuscation
        intent_detections = self.detect_intent_obfuscation(text)
        
        # Extract euphemisms separately for detailed reporting
        euphemisms = detect_euphemisms(text)
        
        # Calculate confidence
        confidence = self.calculate_evasion_confidence(intent_detections, text)
        
        # Determine if evasive
        is_evasive = confidence > 0.4 or len(euphemisms) > 0
        
        # Determine risk level
        risk_level = self.determine_risk_level(confidence, intent_detections)
        
        # Extract detected patterns for reporting
        detected_patterns = [pattern for pattern, _ in intent_detections]
        
        # Determine obfuscated intent
        obfuscated_intent = None
        if confidence > 0.6:
            if any('malicious' in pattern for pattern in detected_patterns):
                obfuscated_intent = "malicious_activity"
            elif euphemisms:
                obfuscated_intent = "attack_research"
            else:
                obfuscated_intent = "suspicious_intent"
        
        # Generate explanation
        explanation = self._generate_explanation(
            confidence, detected_patterns, euphemisms, risk_level
        )
        
        return EvasionDetection(
            is_evasive=is_evasive,
            confidence=confidence,
            detected_patterns=detected_patterns,
            euphemisms=euphemisms,
            obfuscated_intent=obfuscated_intent,
            risk_level=risk_level,
            explanation=explanation
        )
    
    def _generate_explanation(self, confidence: float, patterns: List[str], 
                            euphemisms: List[str], risk_level: str) -> str:
        """Generate human-readable explanation of detection results."""
        if confidence < 0.3:
            return "No significant evasion patterns detected."
        
        explanations = []
        
        if euphemisms:
            explanations.append(f"Euphemistic language detected: {', '.join(euphemisms[:2])}")
        
        if any('malicious' in pattern for pattern in patterns):
            explanations.append("Direct malicious instruction patterns found")
        
        if any('suspicious_context' in pattern for pattern in patterns):
            explanations.append("Suspicious contextual framing detected")
        
        if any('synonym_obfuscation' in pattern for pattern in patterns):
            explanations.append("Semantic obfuscation through synonyms detected")
        
        base_explanation = "; ".join(explanations)
        
        risk_explanation = {
            'medium': "Moderate risk of evasion attempt",
            'high': "High likelihood of semantic evasion",
            'critical': "Critical: Strong evasion patterns detected"
        }.get(risk_level, "Low risk detected")
        
        return f"{base_explanation}. {risk_explanation} (confidence: {confidence:.2f})"
    
    def quick_check(self, text: str) -> bool:
        """Quick check for obvious evasion attempts."""
        if not text:
            return False
        
        # Quick euphemism check
        text_lower = text.lower()
        for euphemism in EVASION_EUPHEMISMS:
            if euphemism in text_lower:
                return True
        
        # Quick pattern check
        for pattern in self.compiled_malicious_patterns[:2]:  # Check first 2 patterns only
            if pattern.search(text):
                return True
        
        return False
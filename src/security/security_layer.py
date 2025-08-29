"""
Main security layer that orchestrates all security components.
Provides a unified interface for comprehensive security validation.
"""

import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .input_sanitizer import InputSanitizer
from .evasion_detector import EvasionDetector
from .context_validator import ContextValidator
from .prompt_defender import PromptDefender

@dataclass
class SecurityResult:
    """Comprehensive security analysis result."""
    is_secure: bool
    confidence: float
    risk_level: str
    sanitized_input: str
    violations: List[str]
    detections: Dict[str, any]
    processing_time: float
    explanation: str

class SecurityLayer:
    """Main security orchestrator that coordinates all security components."""
    
    def __init__(self, enable_all: bool = True):
        """Initialize security layer with configurable components."""
        self.sanitizer = InputSanitizer()
        self.evasion_detector = EvasionDetector()
        self.context_validator = ContextValidator() 
        self.prompt_defender = PromptDefender()
        
        # Configuration flags
        self.enable_sanitization = enable_all
        self.enable_evasion_detection = enable_all
        self.enable_context_validation = enable_all
        self.enable_prompt_defense = enable_all
        
        # Security thresholds
        self.confidence_threshold = 0.6
        self.risk_threshold = 'medium'  # Block 'high' and 'critical'
        
        # Performance tracking
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'average_processing_time': 0.0,
            'component_failures': {}
        }
    
    def quick_security_check(self, text: str) -> bool:
        """Fast security check for performance-critical paths."""
        if not text:
            return True
        
        # Quick checks from all components
        try:
            if self.enable_sanitization and not self.sanitizer.quick_check(text):
                return False
            
            if self.enable_evasion_detection and self.evasion_detector.quick_check(text):
                return False  # Returns True if evasion detected
            
            if self.enable_context_validation and not self.context_validator.quick_check(text):
                return False
            
            if self.enable_prompt_defense and not self.prompt_defender.quick_check(text):
                return False
            
            return True
            
        except Exception:
            # Fail secure - if quick check fails, do full analysis
            return False
    
    def analyze_security(self, text: str, apply_isolation: bool = True) -> SecurityResult:
        """Comprehensive security analysis using all components."""
        start_time = time.time()
        self.stats['total_requests'] += 1
        
        if not text:
            return SecurityResult(
                is_secure=True,
                confidence=1.0,
                risk_level='low',
                sanitized_input='',
                violations=[],
                detections={},
                processing_time=0.0,
                explanation="Empty input is secure"
            )
        
        violations = []
        detections = {}
        sanitized_input = text
        
        try:
            # 1. Input Sanitization
            if self.enable_sanitization:
                sanitization_result = self.sanitizer.sanitize(text)
                sanitized_input = sanitization_result['sanitized_text']
                detections['sanitization'] = sanitization_result
                
                if sanitization_result['is_suspicious']:
                    violations.append(f"Suspicious input patterns detected (score: {sanitization_result['obfuscation_score']:.2f})")
            
            # 2. Evasion Detection
            if self.enable_evasion_detection:
                # Use original text for evasion detection (it has its own normalization)
                evasion_result = self.evasion_detector.detect(text)
                detections['evasion'] = evasion_result
                
                if evasion_result.is_evasive:
                    violations.append(f"Semantic evasion detected: {evasion_result.obfuscated_intent}")
            
            # 3. Context Validation
            if self.enable_context_validation:
                # Use original text for context validation (sanitized text loses meaning)
                context_result = self.context_validator.validate(text)
                detections['context'] = context_result
                
                if not context_result.is_valid:
                    violations.extend(context_result.violations)
            
            # 4. Prompt Defense
            if self.enable_prompt_defense:
                # Use original text for prompt defense (needs to detect actual injection patterns)
                prompt_result = self.prompt_defender.defend(text, apply_isolation)
                detections['prompt'] = prompt_result
                
                if not prompt_result.is_safe:
                    violations.append(f"Prompt injection detected: {len(prompt_result.detected_injections)} patterns")
                
                # Update sanitized input with isolation if applied
                if prompt_result.isolation_applied:
                    sanitized_input = prompt_result.sanitized_input
            
            # Calculate overall security assessment
            overall_confidence, risk_level, is_secure = self._calculate_overall_security(detections)
            
            # Generate comprehensive explanation
            explanation = self._generate_comprehensive_explanation(
                is_secure, overall_confidence, risk_level, violations, detections
            )
            
            # Update statistics
            processing_time = time.time() - start_time
            self.stats['average_processing_time'] = (
                (self.stats['average_processing_time'] * (self.stats['total_requests'] - 1) + processing_time) /
                self.stats['total_requests']
            )
            
            if not is_secure:
                self.stats['blocked_requests'] += 1
            
            return SecurityResult(
                is_secure=is_secure,
                confidence=overall_confidence,
                risk_level=risk_level,
                sanitized_input=sanitized_input,
                violations=violations,
                detections=detections,
                processing_time=processing_time,
                explanation=explanation
            )
            
        except Exception as e:
            # Log component failure
            self.stats['component_failures'][str(e)] = self.stats['component_failures'].get(str(e), 0) + 1
            
            # Fail secure
            return SecurityResult(
                is_secure=False,
                confidence=0.0,
                risk_level='critical',
                sanitized_input=text,
                violations=[f"Security analysis failed: {e}"],
                detections={'error': str(e)},
                processing_time=time.time() - start_time,
                explanation=f"Security layer error: {e}"
            )
    
    def _calculate_overall_security(self, detections: Dict[str, any]) -> Tuple[float, str, bool]:
        """Calculate overall security confidence and risk level."""
        confidences = []
        risk_levels = []
        
        # Collect confidence scores and risk levels from all components
        if 'sanitization' in detections and detections['sanitization']['is_suspicious']:
            confidences.append(1.0 - detections['sanitization']['obfuscation_score'])
            risk_levels.append('medium' if detections['sanitization']['obfuscation_score'] > 0.5 else 'low')
        
        if 'evasion' in detections:
            confidences.append(1.0 - detections['evasion'].confidence)
            risk_levels.append(detections['evasion'].risk_level)
        
        if 'context' in detections:
            confidences.append(detections['context'].confidence)
            risk_levels.append(detections['context'].risk_level)
        
        if 'prompt' in detections:
            confidences.append(detections['prompt'].confidence)
            risk_levels.append(detections['prompt'].risk_level)
        
        # Calculate overall confidence (use minimum for security)
        overall_confidence = min(confidences) if confidences else 1.0
        
        # Calculate overall risk level (use maximum for security)
        risk_priority = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        max_risk_level = 'low'
        
        for risk in risk_levels:
            if risk_priority.get(risk, 1) > risk_priority.get(max_risk_level, 1):
                max_risk_level = risk
        
        # Determine if secure based on thresholds
        is_secure = (
            overall_confidence >= self.confidence_threshold and
            risk_priority.get(max_risk_level, 1) <= risk_priority.get(self.risk_threshold, 2)
        )
        
        return overall_confidence, max_risk_level, is_secure
    
    def _generate_comprehensive_explanation(self, is_secure: bool, confidence: float,
                                          risk_level: str, violations: List[str],
                                          detections: Dict[str, any]) -> str:
        """Generate comprehensive explanation of security analysis."""
        status = "SECURE" if is_secure else "BLOCKED"
        
        explanations = [f"{status} (confidence: {confidence:.2f}, risk: {risk_level})"]
        
        if violations:
            explanations.append(f"Violations: {len(violations)} detected")
            # Add first few violation details
            for violation in violations[:2]:
                explanations.append(f"  - {violation}")
        
        # Add component-specific details
        component_summaries = []
        
        if 'sanitization' in detections and detections['sanitization']['is_suspicious']:
            issues = detections['sanitization']['issues']
            component_summaries.append(f"Sanitization: {len(issues)} issues")
        
        if 'evasion' in detections and detections['evasion'].is_evasive:
            patterns = len(detections['evasion'].detected_patterns)
            component_summaries.append(f"Evasion: {patterns} patterns")
        
        if 'context' in detections and not detections['context'].is_valid:
            attacks = len(detections['context'].detected_attacks)
            component_summaries.append(f"Context: {attacks} attacks")
        
        if 'prompt' in detections and not detections['prompt'].is_safe:
            injections = len(detections['prompt'].detected_injections)
            component_summaries.append(f"Prompt: {injections} injections")
        
        if component_summaries:
            explanations.append(f"Components: {'; '.join(component_summaries)}")
        
        return " | ".join(explanations)
    
    def configure_thresholds(self, confidence_threshold: float = None,
                           risk_threshold: str = None):
        """Configure security thresholds."""
        if confidence_threshold is not None:
            self.confidence_threshold = max(0.0, min(1.0, confidence_threshold))
        
        if risk_threshold is not None and risk_threshold in ['low', 'medium', 'high', 'critical']:
            self.risk_threshold = risk_threshold
    
    def enable_components(self, sanitization: bool = None, evasion_detection: bool = None,
                         context_validation: bool = None, prompt_defense: bool = None):
        """Enable or disable individual security components."""
        if sanitization is not None:
            self.enable_sanitization = sanitization
        if evasion_detection is not None:
            self.enable_evasion_detection = evasion_detection
        if context_validation is not None:
            self.enable_context_validation = context_validation
        if prompt_defense is not None:
            self.enable_prompt_defense = prompt_defense
    
    def get_statistics(self) -> Dict[str, any]:
        """Get security layer performance statistics."""
        block_rate = 0.0
        if self.stats['total_requests'] > 0:
            block_rate = self.stats['blocked_requests'] / self.stats['total_requests']
        
        return {
            'total_requests': self.stats['total_requests'],
            'blocked_requests': self.stats['blocked_requests'],
            'block_rate': block_rate,
            'average_processing_time': self.stats['average_processing_time'],
            'component_failures': dict(self.stats['component_failures']),
            'configuration': {
                'confidence_threshold': self.confidence_threshold,
                'risk_threshold': self.risk_threshold,
                'enabled_components': {
                    'sanitization': self.enable_sanitization,
                    'evasion_detection': self.enable_evasion_detection,
                    'context_validation': self.enable_context_validation,
                    'prompt_defense': self.enable_prompt_defense
                }
            }
        }
    
    def reset_statistics(self):
        """Reset performance statistics."""
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'average_processing_time': 0.0,
            'component_failures': {}
        }
"""
Security-aware generator wrapper that integrates the security layer with existing generators.
Provides comprehensive security validation before query generation.
"""

import time
import logging
from typing import Dict, Optional, Tuple, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.security import SecurityLayer

logger = logging.getLogger(__name__)

class SecureGenerator:
    """Security-aware wrapper for existing generators."""
    
    def __init__(self, enable_full_security: bool = True, 
                 confidence_threshold: float = 0.6,
                 risk_threshold: str = 'medium'):
        """Initialize secure generator with configurable security settings."""
        self.security_layer = SecurityLayer(enable_all=enable_full_security)
        self.security_layer.configure_thresholds(confidence_threshold, risk_threshold)
        
        # Performance vs security trade-off
        self.use_quick_check = True  # Enable for better performance
        self.log_blocked_requests = True
        
        logger.info(f"SecureGenerator initialized with security={'full' if enable_full_security else 'basic'}")
    
    def validate_input_security(self, task_prompt: str, index: Optional[str] = None) -> Dict[str, Any]:
        """Comprehensive input security validation."""
        if not task_prompt:
            return {
                "is_secure": False,
                "reason": "Empty task prompt",
                "metrics": {"processing_time": 0.0}
            }
        
        start_time = time.time()
        
        # Quick security check first for performance
        if self.use_quick_check:
            if not self.security_layer.quick_security_check(task_prompt):
                logger.warning(f"Quick security check failed for prompt: {task_prompt[:50]}...")
                # Fall through to full analysis
        
        # Comprehensive security analysis
        security_result = self.security_layer.analyze_security(task_prompt, apply_isolation=True)
        
        # Log blocked requests if enabled
        if not security_result.is_secure and self.log_blocked_requests:
            logger.warning(
                f"BLOCKED REQUEST - Risk: {security_result.risk_level}, "
                f"Confidence: {security_result.confidence:.2f}, "
                f"Violations: {len(security_result.violations)}, "
                f"Prompt: {task_prompt[:100]}..."
            )
            
            # Log specific violations for analysis
            for violation in security_result.violations[:3]:  # Log first 3
                logger.warning(f"  Violation: {violation}")
        
        return {
            "is_secure": security_result.is_secure,
            "reason": security_result.explanation,
            "sanitized_prompt": security_result.sanitized_input,
            "security_result": security_result,
            "metrics": {
                "processing_time": security_result.processing_time,
                "confidence": security_result.confidence,
                "risk_level": security_result.risk_level
            }
        }
    
    def secure_generate_with_retries(self, generator_func, task_prompt: str, 
                                   *args, **kwargs) -> Dict[str, Any]:
        """Secure wrapper for any generator function."""
        # Extract index if provided in kwargs
        index = kwargs.get('index', None)
        
        # Security validation
        security_validation = self.validate_input_security(task_prompt, index)
        
        if not security_validation["is_secure"]:
            return {
                "abstain": True,
                "reason": f"Security validation failed: {security_validation['reason']}",
                "security_metrics": security_validation["metrics"],
                "blocked_by": "security_layer"
            }
        
        # Use sanitized prompt for generation
        sanitized_prompt = security_validation["sanitized_prompt"]
        
        # Call original generator with sanitized input
        try:
            result = generator_func(sanitized_prompt, *args, **kwargs)
            
            # Add security metrics to result
            if isinstance(result, dict):
                result["security_metrics"] = security_validation["metrics"]
                result["security_validated"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Generator function failed: {e}")
            return {
                "abstain": True, 
                "reason": f"Generation failed after security validation: {e}",
                "security_metrics": security_validation["metrics"],
                "error": str(e)
            }
    
    def get_security_statistics(self) -> Dict[str, Any]:
        """Get security layer statistics."""
        return self.security_layer.get_statistics()
    
    def configure_security(self, confidence_threshold: float = None,
                          risk_threshold: str = None,
                          enable_components: Dict[str, bool] = None):
        """Configure security layer settings."""
        if confidence_threshold is not None or risk_threshold is not None:
            self.security_layer.configure_thresholds(confidence_threshold, risk_threshold)
        
        if enable_components:
            self.security_layer.enable_components(**enable_components)
    
    def reset_security_stats(self):
        """Reset security statistics."""
        self.security_layer.reset_statistics()

# Global secure generator instance
_secure_generator = None

def get_secure_generator(**kwargs) -> SecureGenerator:
    """Get or create global secure generator instance."""
    global _secure_generator
    if _secure_generator is None:
        _secure_generator = SecureGenerator(**kwargs)
    return _secure_generator

def secure_generate_wrapper(generator_func):
    """Decorator to add security validation to any generator function."""
    def wrapper(task_prompt, *args, **kwargs):
        secure_gen = get_secure_generator()
        return secure_gen.secure_generate_with_retries(generator_func, task_prompt, *args, **kwargs)
    
    wrapper.__name__ = f"secure_{generator_func.__name__}"
    wrapper.__doc__ = f"Security-validated version of {generator_func.__name__}"
    
    return wrapper
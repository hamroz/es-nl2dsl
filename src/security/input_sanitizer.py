"""
Input sanitizer for comprehensive text normalization and cleaning.
Handles character-based obfuscation, control sequences, and suspicious patterns.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from .patterns import (
    normalize_leet_speak, 
    detect_obfuscated_keywords,
    MALICIOUS_KEYWORDS,
    OBFUSCATION_PATTERNS
)

class InputSanitizer:
    """Comprehensive input sanitization for security purposes."""
    
    def __init__(self):
        self.suspicious_chars = set()
        self._build_suspicious_char_set()
        
        # Control character patterns
        self.control_patterns = [
            r'[\x00-\x1f\x7f-\x9f]',  # Control characters
            r'[\ufeff\u200b-\u200f\u2028-\u202f]',  # Zero-width and formatting
            r'[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff]',  # Combining diacritics
        ]
        self.compiled_control_patterns = [re.compile(p) for p in self.control_patterns]
        
        # Suspicious encoding patterns
        self.encoding_patterns = [
            r'%[0-9a-fA-F]{2}',  # URL encoding
            r'\\x[0-9a-fA-F]{2}',  # Hex escapes
            r'\\u[0-9a-fA-F]{4}',  # Unicode escapes
            r'\\U[0-9a-fA-F]{8}',  # Long unicode escapes
            r'&#\d+;',  # HTML numeric entities
            r'&#x[0-9a-fA-F]+;',  # HTML hex entities
        ]
        self.compiled_encoding_patterns = [re.compile(p) for p in self.encoding_patterns]
    
    def _build_suspicious_char_set(self):
        """Build set of suspicious characters from obfuscation patterns."""
        for pattern_dict in OBFUSCATION_PATTERNS:
            self.suspicious_chars.update(pattern_dict.keys())
    
    def normalize_unicode(self, text: str) -> str:
        """Normalize Unicode to canonical form."""
        # Decompose and recompose to normalize combining characters
        normalized = unicodedata.normalize('NFKD', text)
        # Remove combining characters (diacritics used for obfuscation)
        normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
        # Recompose
        normalized = unicodedata.normalize('NFKC', normalized)
        return normalized
    
    def remove_control_characters(self, text: str) -> str:
        """Remove control characters and suspicious formatting."""
        cleaned = text
        for pattern in self.compiled_control_patterns:
            cleaned = pattern.sub(' ', cleaned)
        
        # Collapse multiple whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()
    
    def detect_encoding_attacks(self, text: str) -> List[str]:
        """Detect encoded attack patterns."""
        attacks = []
        for pattern in self.compiled_encoding_patterns:
            matches = pattern.findall(text)
            if matches:
                attacks.extend(matches)
        return attacks
    
    def normalize_spacing(self, text: str) -> str:
        """Normalize suspicious spacing patterns."""
        # Remove extra spaces between characters (common evasion)
        normalized = re.sub(r'(\w)\s+(\w)', r'\1\2', text)
        
        # Normalize punctuation spacing
        normalized = re.sub(r'\s*([.,:;!?])\s*', r'\1 ', normalized)
        
        # Remove repeated punctuation (e.g., "!!!" -> "!")
        normalized = re.sub(r'([.,:;!?]){2,}', r'\1', normalized)
        
        return normalized.strip()
    
    def detect_homoglyphs(self, text: str) -> List[Tuple[str, str, int]]:
        """Detect homoglyph substitutions with positions."""
        detections = []
        
        for i, char in enumerate(text):
            if char in self.suspicious_chars:
                # Find which pattern this belongs to
                for pattern_dict in OBFUSCATION_PATTERNS:
                    if char in pattern_dict:
                        original = pattern_dict[char]
                        detections.append((char, original, i))
                        break
        
        return detections
    
    def calculate_obfuscation_score(self, text: str) -> float:
        """Calculate overall obfuscation score (0-1)."""
        if not text:
            return 0.0
            
        score_factors = []
        
        # Character-based obfuscation
        homoglyphs = self.detect_homoglyphs(text)
        homoglyph_ratio = len(homoglyphs) / len(text)
        score_factors.append(homoglyph_ratio * 0.3)
        
        # Encoding attacks
        encoding_attacks = self.detect_encoding_attacks(text)
        if encoding_attacks:
            score_factors.append(0.4)
        
        # Suspicious spacing
        spaces = len(re.findall(r'\s+', text))
        if spaces > len(text.split()) * 2:  # Excessive spacing
            score_factors.append(0.2)
        
        # L33t speak density
        leet_chars = sum(1 for c in text.lower() if c in '0134567@$!+')
        leet_ratio = leet_chars / len(text)
        score_factors.append(leet_ratio * 0.3)
        
        # Control characters
        control_matches = sum(1 for p in self.compiled_control_patterns 
                            if p.search(text))
        if control_matches:
            score_factors.append(0.5)
        
        return min(sum(score_factors), 1.0)
    
    def sanitize(self, text: str) -> Dict[str, any]:
        """Comprehensive text sanitization with detailed analysis."""
        if not text:
            return {
                'sanitized_text': '',
                'is_suspicious': False,
                'obfuscation_score': 0.0,
                'issues': []
            }
        
        original_text = text
        issues = []
        
        # 1. Detect initial issues
        homoglyphs = self.detect_homoglyphs(text)
        if homoglyphs:
            issues.append(f"Homoglyph characters detected: {len(homoglyphs)}")
        
        encoding_attacks = self.detect_encoding_attacks(text)
        if encoding_attacks:
            issues.append(f"Encoding attacks detected: {encoding_attacks[:3]}")
        
        # 2. Normalize Unicode
        text = self.normalize_unicode(text)
        
        # 3. Remove control characters
        text = self.remove_control_characters(text)
        
        # 4. Normalize l33t speak and obfuscation
        text = normalize_leet_speak(text)
        
        # 5. Normalize spacing
        text = self.normalize_spacing(text)
        
        # 6. Detect obfuscated malicious keywords
        obfuscated_keywords = detect_obfuscated_keywords(original_text)
        if obfuscated_keywords:
            issues.append(f"Obfuscated keywords: {[kw[0] for kw in obfuscated_keywords[:3]]}")
        
        # 7. Calculate final obfuscation score
        obfuscation_score = self.calculate_obfuscation_score(original_text)
        
        # 8. Determine if suspicious
        is_suspicious = (
            obfuscation_score > 0.3 or
            len(homoglyphs) > 2 or
            len(encoding_attacks) > 0 or
            len(obfuscated_keywords) > 0
        )
        
        return {
            'sanitized_text': text,
            'is_suspicious': is_suspicious,
            'obfuscation_score': obfuscation_score,
            'issues': issues,
            'homoglyphs_detected': len(homoglyphs),
            'encoding_attacks': len(encoding_attacks),
            'obfuscated_keywords': [kw[0] for kw in obfuscated_keywords],
            'original_length': len(original_text),
            'sanitized_length': len(text)
        }
    
    def quick_check(self, text: str) -> bool:
        """Quick suspicious text detection for performance."""
        if not text:
            return False
            
        # Quick checks for obvious obfuscation
        if any(c in text for c in self.suspicious_chars):
            return True
        
        if any(p.search(text) for p in self.compiled_encoding_patterns):
            return True
            
        # Quick l33t speak check
        leet_count = sum(1 for c in text.lower() if c in '0134567@$!+')
        if leet_count > len(text) * 0.2:  # >20% l33t characters
            return True
        
        return False
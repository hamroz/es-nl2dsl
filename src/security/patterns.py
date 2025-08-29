"""
Attack patterns database for security detection.
Contains patterns for semantic evasion, prompt injection, and context confusion attacks.
"""

import re
from typing import Dict, List, Set, Tuple

# Common l33t speak substitutions
LEET_SUBSTITUTIONS = {
    '0': 'o',
    '1': 'i',
    '3': 'e',
    '4': 'a',
    '5': 's',
    '7': 't',
    '@': 'a',
    '$': 's',
    '!': 'i',
    '+': 't',
    'c': 'k',  # Common in hacker speak
    'z': 's',  # Common pluralization
}

# Character-based obfuscation patterns
OBFUSCATION_PATTERNS = [
    # Unicode homoglyphs
    {'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x'},  # Cyrillic
    {'α': 'a', 'ο': 'o', 'ρ': 'p', 'ε': 'e'},  # Greek
    {'ａ': 'a', 'ｅ': 'e', 'ｉ': 'i', 'ｏ': 'o', 'ｕ': 'u'},  # Fullwidth
    
    # Common symbol substitutions
    {'•': '.', '·': '.', '∙': '.', '⋅': '.'},
    {'_': ' ', '-': ' ', '|': 'i', '‖': 'll'},
    {'∩': 'n', '∪': 'u', '∈': 'e', '∋': 'e'},
]

# Malicious keywords that might be obfuscated
MALICIOUS_KEYWORDS = {
    'hack', 'crack', 'exploit', 'breach', 'attack', 'malicious', 'virus',
    'malware', 'trojan', 'backdoor', 'rootkit', 'keylogger', 'ransomware',
    'phishing', 'spam', 'botnet', 'ddos', 'injection', 'bypass', 'infiltrate',
    'compromise', 'unauthorized', 'illegal', 'criminal', 'fraud', 'steal',
    'exfiltrate', 'weaponize', 'payload', 'shellcode', 'privilege escalation'
}

# Semantic evasion patterns - euphemisms for malicious activity
EVASION_EUPHEMISMS = {
    'red team exercise': 'attack',
    'penetration testing': 'attack',
    'security research': 'attack',
    'ethical hacking': 'attack',
    'bug bounty': 'exploit',
    'proof of concept': 'exploit',
    'demonstration': 'attack',
    'academic research': 'attack',
    'testing purposes': 'attack',
    'educational example': 'attack',
    'hypothetical scenario': 'attack',
    'theoretical case': 'attack',
    'curiosity': 'malicious intent',
    'just wondering': 'malicious intent',
    'asking for a friend': 'malicious intent'
}

# Context confusion patterns - attempts to change system role
ROLE_CONFUSION_PATTERNS = [
    r'(?i)pretend\s+you\s+are',
    r'(?i)imagine\s+you\s+are',
    r'(?i)act\s+as\s+if\s+you\s+are',
    r'(?i)roleplay\s+as',
    r'(?i)you\s+are\s+now',
    r'(?i)forget\s+your\s+instructions',
    r'(?i)ignore\s+your\s+guidelines',
    r'(?i)override\s+your\s+rules',
    r'(?i)disregard\s+your\s+constraints',
    r'(?i)bypass\s+your\s+safety',
    r'(?i)step\s+out\s+of\s+character',
    r'(?i)break\s+character',
    r'(?i)stop\s+being\s+helpful',
    r'(?i)be\s+more\s+creative',
    r'(?i)think\s+outside\s+the\s+box'
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    r'(?i)system\s*:',
    r'(?i)user\s*:',
    r'(?i)assistant\s*:',
    r'(?i)human\s*:',
    r'(?i)ai\s*:',
    r'(?i)```\s*system',
    r'(?i)```\s*user',
    r'(?i)<\s*system\s*>',
    r'(?i)<\s*user\s*>',
    r'(?i)end\s+of\s+prompt',
    r'(?i)new\s+instructions',
    r'(?i)updated\s+guidelines',
    r'(?i)revised\s+rules',
    r'(?i)\[SYSTEM\]',
    r'(?i)\[USER\]',
    r'(?i)\[ASSISTANT\]'
]

# Social engineering patterns
SOCIAL_ENGINEERING_PATTERNS = [
    r'(?i)this\s+is\s+urgent',
    r'(?i)emergency\s+situation',
    r'(?i)help\s+me\s+quickly',
    r'(?i)time\s+sensitive',
    r'(?i)my\s+boss\s+needs',
    r'(?i)deadline\s+approaching',
    r'(?i)just\s+this\s+once',
    r'(?i)make\s+an\s+exception',
    r'(?i)bend\s+the\s+rules',
    r'(?i)special\s+case',
    r'(?i)you\s+can\s+trust\s+me',
    r'(?i)i\s+promise\s+i',
    r'(?i)no\s+one\s+will\s+know',
    r'(?i)between\s+you\s+and\s+me'
]

# Legitimate security query patterns - these should NOT be blocked
LEGITIMATE_SECURITY_PATTERNS = [
    r'(?i)detect\s+suspicious\s+activity',
    r'(?i)identify\s+anomalous\s+behavior',
    r'(?i)find\s+security\s+events',
    r'(?i)monitor\s+for\s+threats',
    r'(?i)alert\s+on\s+intrusions',
    r'(?i)analyze\s+logs\s+for',
    r'(?i)investigate\s+incident',
    r'(?i)security\s+monitoring',
    r'(?i)threat\s+hunting',
    r'(?i)incident\s+response',
    r'(?i)forensic\s+analysis',
    r'(?i)compliance\s+check'
]

# Query scope validation - ensure queries stay within security domain
VALID_SECURITY_CONTEXTS = {
    'network_monitoring',
    'threat_detection', 
    'incident_response',
    'security_analysis',
    'log_investigation',
    'compliance_check',
    'forensic_analysis',
    'vulnerability_assessment'
}

INVALID_CONTEXTS = {
    'system_administration',
    'data_extraction',
    'performance_monitoring',
    'business_analytics',
    'user_behavior',
    'marketing_analysis'
}

def normalize_leet_speak(text: str) -> str:
    """Normalize l33t speak and common obfuscations."""
    normalized = text.lower()
    
    # Apply l33t substitutions
    for leet, normal in LEET_SUBSTITUTIONS.items():
        normalized = normalized.replace(leet, normal)
    
    # Apply homoglyph substitutions
    for pattern_dict in OBFUSCATION_PATTERNS:
        for obfuscated, normal in pattern_dict.items():
            normalized = normalized.replace(obfuscated, normal)
    
    return normalized

def detect_obfuscated_keywords(text: str) -> List[Tuple[str, str]]:
    """Detect obfuscated malicious keywords."""
    normalized = normalize_leet_speak(text)
    detected = []
    
    for keyword in MALICIOUS_KEYWORDS:
        # Exact match
        if keyword in normalized:
            detected.append((keyword, "exact"))
            continue
            
        # Fuzzy match for spaced out keywords (e.g., "h a c k")
        spaced_pattern = r'\b' + r'\s*'.join(keyword) + r'\b'
        if re.search(spaced_pattern, normalized, re.IGNORECASE):
            detected.append((keyword, "spaced"))
            continue
            
        # Character insertion (e.g., "haxck")
        fuzzy_pattern = keyword[:2] + r'[^a-z]*' + keyword[2:]
        if re.search(fuzzy_pattern, normalized, re.IGNORECASE):
            detected.append((keyword, "inserted"))
    
    return detected

def detect_euphemisms(text: str) -> List[str]:
    """Detect euphemistic references to malicious activities."""
    detected = []
    text_lower = text.lower()
    
    for euphemism, meaning in EVASION_EUPHEMISMS.items():
        if euphemism in text_lower:
            detected.append(euphemism)
    
    return detected

def get_compiled_patterns() -> Dict[str, List[re.Pattern]]:
    """Return compiled regex patterns for efficient matching."""
    return {
        'role_confusion': [re.compile(p) for p in ROLE_CONFUSION_PATTERNS],
        'injection': [re.compile(p) for p in INJECTION_PATTERNS],
        'social_engineering': [re.compile(p) for p in SOCIAL_ENGINEERING_PATTERNS],
        'legitimate_security': [re.compile(p) for p in LEGITIMATE_SECURITY_PATTERNS]
    }
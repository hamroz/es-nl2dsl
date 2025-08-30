#!/usr/bin/env python3
import json
import sys
import argparse
import subprocess
import yaml
import time
import logging
import asyncio
from pathlib import Path
from jsonschema import validate, ValidationError

# Configure logging with robust path handling
def setup_logging():
    """Setup logging with fallback for different execution contexts"""
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Try to add file handler with robust path resolution
    try:
        # Try relative to current working directory first
        log_path = Path('logs/gui_backend.log')
        if not log_path.parent.exists():
            # Try relative to project root
            project_root = Path(__file__).parent.parent.parent
            log_path = project_root / 'logs' / 'gui_backend.log'
            
        # Create logs directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        handlers.append(logging.FileHandler(str(log_path), mode='a'))
    except Exception as e:
        # If file logging fails, just use console logging
        print(f"Warning: Could not setup file logging: {e}")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [CONSTRAINED] - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override any existing configuration
    )

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)
# Add project root to path for absolute imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import prompt enhancer if available
try:
    from src.external.prompt_enhancer import enhance_prompt, build_enhanced_prompt
    ENHANCER_AVAILABLE = True
except ImportError:
    ENHANCER_AVAILABLE = False

# Import sophisticated security filter
try:
    from src.utils.security_filter import check_security_violations_advanced, SophisticatedSecurityFilter
    ADVANCED_SECURITY = True
except ImportError:
    ADVANCED_SECURITY = False

# Import new security layer
try:
    from src.generators.secure_generator import get_secure_generator
    NEW_SECURITY_AVAILABLE = True
except ImportError:
    NEW_SECURITY_AVAILABLE = False

# Import dynamic index analyzer
try:
    from src.generators.index_analyzer import get_index_analyzer, build_field_catalog
    INDEX_ANALYZER_AVAILABLE = True
except ImportError:
    INDEX_ANALYZER_AVAILABLE = False
    logger.warning("Index analyzer not available, falling back to static field catalog")

# Import smart field matcher
try:
    from src.generators.field_matcher import get_field_matcher, extract_constraints_from_prompt
    FIELD_MATCHER_AVAILABLE = True
except ImportError:
    FIELD_MATCHER_AVAILABLE = False
    logger.warning("Field matcher not available, using basic field corrections")

# Static field catalog (fallback when dynamic discovery isn't available)
STATIC_FIELD_CATALOG = {
    "@timestamp": {"type": "date", "description": "Event timestamp"},
    "src_ip": {"type": "keyword", "description": "Source IP address"},
    "dst_ip": {"type": "keyword", "description": "Destination IP address"},
    "src_port": {"type": "integer", "description": "Source port number"},
    "dst_port": {"type": "integer", "description": "Destination port number"},
    "protocol": {"type": "keyword", "description": "Network protocol (TCP, UDP, etc)"},
    "bytes_in": {"type": "long", "description": "Bytes received"},
    "bytes_out": {"type": "long", "description": "Bytes sent"},
    "label": {"type": "keyword", "description": "Classification label (malicious, benign)"},
    "message": {"type": "text", "description": "Log message (not searchable)"}
}

def get_field_catalog_for_index(index_name=None):
    """Get field catalog dynamically or fall back to static"""
    if index_name and INDEX_ANALYZER_AVAILABLE:
        try:
            analyzer = get_index_analyzer()
            fields = analyzer.get_index_fields(index_name)
            if fields:
                logger.info(f"Using dynamic field catalog for {index_name}: {len(fields)} fields")
                return fields
        except Exception as e:
            logger.warning(f"Failed to get dynamic fields for {index_name}: {e}")
    
    # Fallback to static catalog
    return STATIC_FIELD_CATALOG

def enhance_prompt_with_field_matching(task_prompt, index_name):
    """
    Preprocess the prompt to identify field-value pairs and provide hints to the LLM
    """
    if not index_name or not FIELD_MATCHER_AVAILABLE or not INDEX_ANALYZER_AVAILABLE:
        return task_prompt
    
    try:
        # Get available fields
        analyzer = get_index_analyzer()
        fields = analyzer.get_index_fields(index_name)
        if not fields:
            return task_prompt
        
        available_field_names = list(fields.keys())
        
        # Extract constraints from the prompt
        matcher = get_field_matcher()
        constraints = matcher.extract_field_value_pairs(task_prompt, available_field_names)
        
        # Analyze boolean logic
        boolean_logic = matcher.analyze_boolean_logic(task_prompt)
        
        # Extract special constraint types
        negated_constraints = matcher.extract_negated_constraints(task_prompt, available_field_names)
        range_constraints = matcher.extract_range_constraints(task_prompt, available_field_names)
        
        # Combine all constraints
        all_constraints = constraints + negated_constraints + range_constraints
        
        if not all_constraints:
            return task_prompt
        
        # Build enhanced prompt with field mappings
        enhanced_prompt = task_prompt + "\n\n"
        enhanced_prompt += "=" * 60 + "\n"
        enhanced_prompt += "MANDATORY FIELD MAPPINGS - USE EXACTLY AS SPECIFIED:\n"
        enhanced_prompt += "=" * 60 + "\n"
        
        # Add boolean logic information
        if boolean_logic['complexity'] == 'complex':
            enhanced_prompt += f"BOOLEAN LOGIC: {boolean_logic['primary_logic']} logic detected\n"
            if boolean_logic['has_or']:
                enhanced_prompt += "- Use 'should' clauses for OR conditions\n"
            if boolean_logic['has_not']:
                enhanced_prompt += "- Use 'must_not' clauses for NOT/excluded conditions\n"
            enhanced_prompt += "\n"
        
        # Regular constraints
        if constraints:
            enhanced_prompt += "POSITIVE CONSTRAINTS (use 'filter' or 'must'):\n"
            for constraint in constraints:
                field_match = constraint['field_match']
                value = constraint['value']
                original = constraint['original_text']
                confidence = field_match['confidence']
                
                enhanced_prompt += f"'{original}' → MUST use field '{field_match['field']}' with value '{value}'\n"
                logger.info(f"Field mapping: '{original}' → {field_match['field']} (confidence: {confidence:.2f})")
        
        # Negated constraints
        if negated_constraints:
            enhanced_prompt += "\nNEGATED CONSTRAINTS (use 'must_not'):\n"
            for constraint in negated_constraints:
                field_match = constraint['field_match']
                value = constraint.get('value', 'any')
                original = constraint['original_text']
                
                enhanced_prompt += f"'{original}' → MUST use 'must_not' with field '{field_match['field']}'"
                if value:
                    enhanced_prompt += f" and value '{value}'"
                enhanced_prompt += "\n"
                logger.info(f"Negated constraint: '{original}' → must_not {field_match['field']}")
        
        # Range constraints
        if range_constraints:
            enhanced_prompt += "\nRANGE CONSTRAINTS (use 'range'):\n"
            for constraint in range_constraints:
                field_match = constraint['field_match']
                original = constraint['original_text']
                range_type = constraint['range_type']
                
                if range_type == 'between':
                    enhanced_prompt += f"'{original}' → MUST use 'range' with field '{field_match['field']}' gte:{constraint['value_min']} lte:{constraint['value_max']}\n"
                elif range_type == 'gt':
                    enhanced_prompt += f"'{original}' → MUST use 'range' with field '{field_match['field']}' gt:{constraint['value']}\n"
                elif range_type == 'lt':
                    enhanced_prompt += f"'{original}' → MUST use 'range' with field '{field_match['field']}' lt:{constraint['value']}\n"
                
                logger.info(f"Range constraint: '{original}' → range {field_match['field']}")
        
        enhanced_prompt += "\n" + "=" * 60 + "\n"
        enhanced_prompt += "CRITICAL INSTRUCTIONS:\n"
        enhanced_prompt += "1. You MUST use ONLY the field names listed above\n"
        enhanced_prompt += "2. Do NOT substitute with similar fields (e.g., do NOT use 'label' when 'log_type.keyword' is specified)\n"
        enhanced_prompt += "3. Do NOT use any field names not explicitly provided above\n"
        enhanced_prompt += "4. If a field mapping specifies '.keyword', use the .keyword version exactly\n"
        enhanced_prompt += "5. Follow the exact field→value mappings shown above\n"
        enhanced_prompt += "6. Use appropriate ES query structures: 'filter' for AND, 'should' for OR, 'must_not' for NOT\n"
        enhanced_prompt += "=" * 60 + "\n"
        
        return enhanced_prompt
        
    except Exception as e:
        logger.warning(f"Failed to enhance prompt with field matching: {e}")
        return task_prompt

def _build_enhanced_field_context(field_catalog, catalog_info, analyzer, index):
    """
    Build enhanced field context with grouping, samples, and relationships
    """
    context = ""
    
    # Group fields by type
    field_groups = {
        'Timestamp Fields': [],
        'Text/Keyword Fields': [],
        'Numeric Fields': [],
        'IP Address Fields': [],
        'Port Fields': [],
        'Boolean Fields': [],
        'Other Fields': []
    }
    
    for field_name, field_info in field_catalog.items():
        field_type = field_info.get('type', 'unknown')
        description = field_info.get('description', '')
        
        if field_type == 'date':
            field_groups['Timestamp Fields'].append((field_name, field_info))
        elif 'ip' in field_name.lower() or 'address' in field_name.lower():
            field_groups['IP Address Fields'].append((field_name, field_info))
        elif 'port' in field_name.lower():
            field_groups['Port Fields'].append((field_name, field_info))
        elif field_type in ['keyword', 'text']:
            field_groups['Text/Keyword Fields'].append((field_name, field_info))
        elif field_type in ['integer', 'long', 'float', 'double']:
            field_groups['Numeric Fields'].append((field_name, field_info))
        elif field_type == 'boolean':
            field_groups['Boolean Fields'].append((field_name, field_info))
        else:
            field_groups['Other Fields'].append((field_name, field_info))
    
    # Build organized field display
    total_fields = len(field_catalog)
    context += f"INDEX SCHEMA ({total_fields} fields organized by type):\n\n"
    
    for group_name, fields in field_groups.items():
        if not fields:
            continue
            
        context += f"{group_name} ({len(fields)} fields):\n"
        
        # Show all fields if not too many, otherwise show important ones
        fields_to_show = fields[:15] if len(fields) > 15 else fields
        
        for field_name, field_info in fields_to_show:
            field_type = field_info.get('type', 'unknown')
            description = field_info.get('description', f'Field of type {field_type}')
            
            # Add usage hints for important field types
            usage_hint = ""
            if field_name.endswith('.keyword'):
                usage_hint = " [USE FOR EXACT MATCH]"
            elif field_type == 'text':
                usage_hint = " [USE FOR FULL-TEXT SEARCH]"
            elif field_type == 'date':
                usage_hint = " [USE FOR TIME RANGES]"
            elif field_type in ['integer', 'long', 'float', 'double']:
                usage_hint = " [USE FOR NUMERIC RANGES]"
            
            context += f"  • {field_name} ({field_type}): {description}{usage_hint}\n"
        
        if len(fields) > 15:
            context += f"  ... and {len(fields) - 15} more {group_name.lower()}\n"
        
        context += "\n"
    
    # Add sample values section for key fields
    context += "SAMPLE VALUES FOR KEY FIELDS:\n"
    
    # Get sample values for important categorical fields
    key_fields = [
        'log_type', 'log_type.keyword', 'action', 'action.keyword',
        'protocol', 'protocol.keyword', 'status', 'status.keyword',
        'threat_label', 'threat_label.keyword', 'attack_type'
    ]
    
    sample_count = 0
    for field_name in key_fields:
        if field_name in field_catalog and sample_count < 5:  # Limit to 5 sample fields
            try:
                # Get sample values if analyzer is available
                if analyzer:
                    stats = analyzer.get_field_statistics(index, field_name, max_samples=3)
                    samples = stats.get('samples', [])
                    if samples:
                        context += f"  • {field_name}: {', '.join(str(s) for s in samples[:3])}\n"
                        sample_count += 1
            except Exception:
                # Skip if can't get samples
                pass
    
    if sample_count == 0:
        context += "  (Sample values not available)\n"
    
    context += "\n"
    
    # Add field usage recommendations
    context += "FIELD USAGE RECOMMENDATIONS:\n"
    context += "• Use .keyword fields (e.g., log_type.keyword) for exact matching and aggregations\n"
    context += "• Use text fields for full-text search and partial matching\n"
    context += "• Use numeric fields with range queries (gt, lt, gte, lte)\n"
    context += "• Always include a timestamp range for performance\n"
    
    # Add specific field mapping hints
    if 'log_type.keyword' in field_catalog:
        context += "• For 'log type': ALWAYS use 'log_type.keyword' field\n"
    if 'action.keyword' in field_catalog:
        context += "• For 'action': ALWAYS use 'action.keyword' field\n"
    
    context += "\n"
    
    return context

# Common field mapping errors from LLMs (maps incorrect field names to correct ones)
FIELD_CORRECTIONS = {
    # ECS-style fields to actual fields
    "event.label": "label",
    "event.type": "label",
    "event.category": "label",
    "source.ip": "src_ip",
    "source.port": "src_port",
    "destination.ip": "dst_ip",
    "destination.port": "dst_port",
    "destination_port": "dst_port",
    "source_port": "src_port",
    "source_ip": "src_ip",
    "destination_ip": "dst_ip",
    "network.protocol": "protocol",
    "network.bytes_in": "bytes_in",
    "network.bytes_out": "bytes_out",
    # Common variants
    "timestamp": "@timestamp",
    "time": "@timestamp",
    "datetime": "@timestamp",
    "src": "src_ip",
    "dst": "dst_ip",
    "srcip": "src_ip",
    "dstip": "dst_ip",
    "srcport": "src_port",
    "dstport": "dst_port",
    "bytes_received": "bytes_in",
    "bytes_sent": "bytes_out",
    "bytes_transferred": "bytes_out",
    "inbound_bytes": "bytes_in",
    "outbound_bytes": "bytes_out",
    "traffic_type": "label",
    "attack_label": "label",
    "malicious": "label",
    # CIC-specific corrections
    "flow.packets_s": "flow_packets_s",
    "flow.bytes_s": "flow_bytes_s",
    "attack.type": "attack_type",
    "day": "day_of_week",
    "weekday": "day_of_week"
}

ALLOWED_OPERATORS = {
    "bool": "Combines multiple conditions with filter (AND) or must (AND)",
    "term": "Exact match for a single value",
    "terms": "Match any of multiple values",
    "range": "Range queries with gte, gt, lte, lt for dates and numbers"
}

# Terms that are too vague to convert to specific time ranges
AMBIGUOUS_TERMS = [
    "recently", "lately", "soon", "earlier", "later", "sometime",
    "a while ago", "not long ago", "previously"
]

# Terms that can be converted to specific dates (not ambiguous)
CONVERTIBLE_TIME_TERMS = [
    "today", "yesterday", "tomorrow", "this week", "last week",
    "this month", "last month", "last hour", "past hour", "last 24 hours",
    "past 24 hours", "past day", "past week", "past month", "in the past 24",
    "in the past day", "in the past week", "in the past month", "in the last"
]

# Security patterns that should be blocked - DEPRECATED (now handled in check_security_violations)
# Keeping empty list to avoid breaking other code that might reference it
SECURITY_PATTERNS = []

def load_fewshot_examples(index=None):
    """Load few-shot examples from file"""
    # Check for CIC-specific examples if CIC index is used
    if index and "cic" in index.lower():
        cic_path = Path(__file__).parent.parent / "artifacts" / "few_shot_cic.yaml"
        if cic_path.exists():
            with open(cic_path) as f:
                data = yaml.safe_load(f)
                return data.get('examples', [])
    
    # Default examples
    fewshot_path = Path(__file__).parent.parent / "tasks" / "fewshot.yaml"
    if fewshot_path.exists():
        with open(fewshot_path) as f:
            return yaml.safe_load(f)
    return []

def get_dynamic_index_info(index):
    """Get dynamic information about an index with robust error handling"""
    if not index:
        return None
    
    # Cache to prevent repeated failed attempts
    if not hasattr(get_dynamic_index_info, '_failed_indices'):
        get_dynamic_index_info._failed_indices = set()
    
    if index in get_dynamic_index_info._failed_indices:
        # Don't retry failed indices to prevent loops
        return {"has_profile": False, "field_catalog": {}}
        
    try:
        # Import here to avoid circular dependencies
        from src.data_adaptation.mapping_storage import MappingStorage
        mapping_storage = MappingStorage()
        
        # Get field mapping and date range with timeout/retry protection
        field_mapping = mapping_storage.get_field_mapping_for_query_generation(index)
        date_range = mapping_storage.get_dynamic_date_range(index)
        field_catalog = mapping_storage.get_field_catalog_for_index(index)
        
        if field_mapping and field_mapping.get("all_fields"):
            return {
                "has_profile": True,
                "field_mapping": field_mapping,
                "date_range": date_range,
                "field_catalog": field_catalog,
                "timestamp_field": field_mapping.get("primary_timestamp", "@timestamp"),
                "system_type": field_mapping.get("system_type", "Unknown")
            }
    except Exception as e:
        # Cache failed index to prevent retry loops
        get_dynamic_index_info._failed_indices.add(index)
        logger.debug(f"Could not get dynamic info for {index}: {e}")
    
    return {"has_profile": False, "field_catalog": {}}

def build_prompt(task_prompt, index=None):
    """Build the constrained generation prompt with dynamic index awareness"""
    # PHASE 2: First apply smart field matching to enhance the task prompt
    enhanced_task_prompt = enhance_prompt_with_field_matching(task_prompt, index)
    
    prompt = "You are an Elasticsearch DSL query generator for cybersecurity log analysis.\n\n"
    
    # First try our new dynamic index analyzer
    field_catalog = None
    catalog_info = None
    
    if index and INDEX_ANALYZER_AVAILABLE:
        try:
            analyzer = get_index_analyzer()
            catalog_info = analyzer.build_field_catalog(index)
            field_catalog = catalog_info.get('fields', {})
            
            if field_catalog:
                logger.info(f"Using dynamic field discovery for {index}: {len(field_catalog)} fields found")
        except Exception as e:
            logger.warning(f"Dynamic field discovery failed: {e}")
    
    # If dynamic discovery worked, use ALL fields
    if field_catalog and catalog_info:
        prompt += f"Index: {index} with {len(field_catalog)} available fields\n\n"
        
        # Get timestamp field
        timestamp_field = catalog_info.get('primary_timestamp', '@timestamp')
        
        # PHASE 4: Enhanced field organization and context
        prompt += _build_enhanced_field_context(field_catalog, catalog_info, analyzer, index)
        
        # Add field relationships and patterns
        if catalog_info.get('common_patterns'):
            prompt += "FIELD RELATIONSHIPS & PATTERNS:\n"
            for pattern_type, fields in catalog_info['common_patterns'].items():
                if fields:
                    pattern_name = pattern_type.replace('_', ' ').title()
                    prompt += f"- {pattern_name}: {', '.join(fields[:5])}"
                    if len(fields) > 5:
                        prompt += f" (+{len(fields)-5} more)"
                    prompt += "\n"
            prompt += "\n"
    
    # Fallback to old dynamic info if new analyzer didn't work
    elif index:
        dynamic_info = get_dynamic_index_info(index)
        
        if dynamic_info and dynamic_info["has_profile"]:
            # Use old dynamic index information
            field_catalog = dynamic_info["field_catalog"]
            system_type = dynamic_info["system_type"]
            timestamp_field = dynamic_info["timestamp_field"]
            
            prompt += f"Dataset: {index}"
            if system_type != "Unknown":
                prompt += f" ({system_type})"
            prompt += f" with {len(field_catalog)} available fields\n\n"
            
            prompt += "Key fields:\n"
            # Add most important fields (limit to prevent prompt bloat)
            important_keywords = ["timestamp", "ip", "port", "protocol", "label", "attack", "status", "action", "bytes", "type", "log", "firewall", "user", "host"]
            field_count = 0
            max_fields = 20  # Increased from 12
            
            for field_name, field_info in field_catalog.items():
                if field_count >= max_fields:
                    break
                if any(keyword in field_name.lower() for keyword in important_keywords):
                    prompt += f"- {field_name} ({field_info['type']}): {field_info['description']}\n"
                    field_count += 1
            
            if len(field_catalog) > max_fields:
                prompt += f"... and {len(field_catalog) - field_count} more fields\n"
            prompt += "\n"
        
    elif index and "cic" in index.lower():
        prompt += "Dataset: CIC-IDS2017 network traffic with attack labels\n\n"
        prompt += "Key fields for CIC data:\n"
        prompt += "- src_ip (keyword): Source IP address\n"
        prompt += "- dst_ip (keyword): Destination IP address\n"
        prompt += "- src_port (integer): Source port number\n"
        prompt += "- dst_port (integer): Destination port number\n"
        prompt += "- protocol (keyword): Network protocol (tcp/udp/icmp)\n"
        prompt += "- attack_type (keyword): Attack category (normal, dos, scan, bruteforce, web_attack)\n"
        prompt += "- label (keyword): Specific attack label (BENIGN, DDoS, PortScan, SSH-Patator, etc.)\n"
        prompt += "- flow_packets_s (float): Packet rate per second\n"
        prompt += "- flow_bytes_s (float): Bytes per second (bandwidth)\n"
        prompt += "- flow_duration (long): Flow duration in milliseconds\n"
        prompt += "- syn_flag_count (int): Number of SYN flags\n"
        prompt += "- day_of_week (keyword): Day name (Monday, Tuesday, etc.)\n"
        prompt += "- @timestamp (date): Event timestamp\n\n"
        prompt += "IMPORTANT mappings:\n"
        prompt += "- For 'DDoS attacks': use attack_type:dos\n"
        prompt += "- For 'port scans': use attack_type:scan\n"
        prompt += "- For 'brute force': use attack_type:bruteforce\n"
        prompt += "- ALWAYS include specific ports if mentioned (e.g., 'port 443' → dst_port:443)\n"
        prompt += "- ALWAYS include IP addresses if mentioned (e.g., 'from 192.168.1.1' → src_ip:192.168.1.1)\n"
        prompt += "- For 'high packet rate': use flow_packets_s >= 100\n"
        prompt += "- For 'high bandwidth': use flow_bytes_s >= 1000000\n"
        prompt += "- Always include @timestamp range for time windowing\n\n"
    else:
        # Use static catalog as last resort
        static_catalog = get_field_catalog_for_index(None)
        prompt += "Available fields:\n"
        for field, info in static_catalog.items():
            if field != "message":  # Skip non-searchable field
                prompt += f"- {field} ({info['type']}): {info['description']}\n"
    
    prompt += "\nIMPORTANT: USE ONLY THE FIELDS LISTED ABOVE!\n"
    prompt += "Map natural language terms to the closest matching field from the list.\n"
    prompt += "For example: 'log type' might map to 'type' or 'log_type' if those fields exist.\n\n"
    
    prompt += "Allowed query operators:\n"
    for op, desc in ALLOWED_OPERATORS.items():
        prompt += f"- {op}: {desc}\n"
    
    prompt += "\nRules:\n"
    prompt += "- Always use bool.filter for combining conditions\n"
    prompt += "- MUST use only fields from the list above - do not invent field names\n"
    
    # Set timestamp field based on what we found
    timestamp_field = '@timestamp'  # default
    if catalog_info and catalog_info.get('primary_timestamp'):
        timestamp_field = catalog_info['primary_timestamp']
    
    # Use dynamic timestamp field and date range if available
    dynamic_info = get_dynamic_index_info(index) if index else None
    if dynamic_info and dynamic_info["has_profile"]:
        timestamp_field = dynamic_info["timestamp_field"]
        date_range = dynamic_info["date_range"]
        prompt += f"- Always include a time range filter using {timestamp_field}\n"
        
        if date_range and date_range.get("min_date") and date_range.get("max_date"):
            min_date = date_range["min_date"][:10]  # Just date part
            max_date = date_range["max_date"][:10]
            prompt += f"- Use dates between {min_date} and {max_date} for time ranges\n"
        else:
            prompt += "- Use appropriate dates based on the query context\n"
    else:
        prompt += "- Always include a time range filter using @timestamp\n"
        prompt += "- For CIC data, use dates in 2017 (e.g., gte: '2017-01-01', lte: '2017-12-31')\n"
    prompt += "- Use term for exact matches, terms for multiple values\n"
    prompt += "- Use range only for date and numeric fields\n"
    prompt += "- Output only valid JSON, no explanations\n\n"
    
    prompt += "Examples:\n"
    fewshot_examples = load_fewshot_examples(index)
    for example in fewshot_examples[:3]:  # Use first 3 examples
        prompt += f"Input: {example['prompt']}\n"
        prompt += f"Output: {json.dumps(example['query'], indent=2)}\n\n"
    
    prompt += f"Input: {enhanced_task_prompt}\n"
    prompt += "Output:"
    
    return prompt

def call_local_model(prompt, model="llama3.1:latest"):
    """Call Ollama local model with adaptive timeout"""
    # Set timeout based on model size
    timeout_seconds = 60  # Default
    if "20b" in model.lower() or "gpt-oss" in model.lower():
        timeout_seconds = 180  # 3 minutes for 20B models
    elif "14b" in model.lower() or "13b" in model.lower():
        timeout_seconds = 120  # 2 minutes for 13-14B models
    elif "70b" in model.lower():
        timeout_seconds = 240  # 4 minutes for 70B models
    
    print(f"Calling {model} with timeout={timeout_seconds}s...")
    
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )
        if result.returncode != 0:
            raise RuntimeError(f"Model call failed: {result.stderr}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Model call timed out after {timeout_seconds} seconds")
    except FileNotFoundError:
        raise RuntimeError("Ollama not found. Please install Ollama and pull a model.")

def validate_against_schema(query_json, schema_path):
    """Validate query against ES DSL schema"""
    with open(schema_path) as f:
        schema = json.load(f)
    
    try:
        validate(instance=query_json, schema=schema)
        return True, None
    except ValidationError as e:
        return False, str(e)

def validate_with_validator(query_json, rules_path):
    """Run the validator.py script"""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(query_json, f)
        temp_path = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, "src/validator.py", "--dsl", temp_path, "--rules", rules_path],
            capture_output=True,
            text=True
        )
        Path(temp_path).unlink()
        
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stdout + result.stderr
    except Exception as e:
        Path(temp_path).unlink()
        return False, str(e)

def check_security_violations(prompt_text):
    """Check for security violations using sophisticated filtering when available"""
    # Use advanced security filter if available
    if ADVANCED_SECURITY:
        is_violation, reason = check_security_violations_advanced(prompt_text)
        if is_violation:
            return is_violation, reason
        # If advanced filter passes, still do basic checks for compatibility
        return check_security_violations_basic(prompt_text)
    else:
        # Fallback to basic checks
        return check_security_violations_basic(prompt_text)

def check_security_violations_basic(prompt_text):
    """Check for security violations and ambiguous terms"""
    prompt_lower = prompt_text.lower()
    
    # Check for SQL injection patterns FIRST (more specific patterns)
    sql_patterns = [
        "drop table", "drop database", "delete from", "insert into", "update set",
        "union select", "exec(", "execute(", "xp_cmdshell", "sp_executesql"
    ]
    for pattern in sql_patterns:
        if pattern in prompt_lower:
            return True, f"SQL injection attempt detected: '{pattern}'"
    
    # Check for logical bypass attempts (check before broad patterns)
    bypass_patterns = [
        "or 1=1", "or 1 = 1", "or true", "' or '", '" or "',
        "or1==1", "or 1==1", " 1==1",  # Additional patterns with space
        "ignore previous", "ignore all previous", "bypass validator",
        "ignore validation", "skip validation", "raw query"
    ]
    for pattern in bypass_patterns:
        if pattern in prompt_lower:
            return True, f"Bypass attempt detected: '{pattern}'"
    
    # Check for command injection patterns
    command_patterns = [
        "erase all", "delete all", "drop all", "truncate", "rm -rf",
        "format c:", "/etc/passwd", "sudo", "chmod 777"
    ]
    for pattern in command_patterns:
        if pattern in prompt_lower:
            return True, f"Command injection attempt detected: '{pattern}'"
    
    # Check ambiguous time references (after more serious violations)
    # But allow convertible time terms like "today", "yesterday" etc.
    for term in AMBIGUOUS_TERMS:
        if term in prompt_lower:
            # Special case: "in the past X" is usually specific enough
            import re
            if re.search(r'in the past \d+ (hours?|days?|weeks?|months?)', prompt_lower):
                continue
            # Double-check it's not a convertible term
            is_convertible = any(conv in prompt_lower for conv in CONVERTIBLE_TIME_TERMS)
            if not is_convertible:
                return True, f"Ambiguous time reference detected: '{term}'"
    
    # Check for overly broad data requests WITH context
    # "all data" is only bad if not qualified (e.g., "all data from today" is OK)
    # BUT check for SQL injection BEFORE broad patterns
    broad_patterns = [
        ("all data", ["from", "between", "on", "during", "today", "yesterday", "last", "where", "in", "with"]),
        ("everything", ["from", "between", "on", "during", "today", "yesterday", "where", "in", "last", "past"]),
        ("entire database", []),  # Always bad
        ("full database", []),    # Always bad
        ("no restrictions", []),  # Always bad
        ("no limits", []),        # Always bad
        ("unrestricted", []),     # Always bad
    ]
    
    for pattern, allowed_qualifiers in broad_patterns:
        if pattern in prompt_lower:
            # Skip if this is part of a SQL injection pattern already caught
            if any(x in prompt_lower for x in ["or 1=", "or 1 =", "1==1"]):
                continue  # Already handled by bypass patterns
            # Check if any qualifier is present
            has_qualifier = any(qual in prompt_lower for qual in allowed_qualifiers)
            if not allowed_qualifiers or not has_qualifier:
                return True, f"Overly broad data request: '{pattern}'"
    
    # Check for sensitive field access
    import re
    sensitive_fields = [
        "passwords?", "passwd", "credentials?", "secret_key", "private_key",
        "api_key", "tokens?", "ssn", "social security", "credit_card"
    ]
    for field in sensitive_fields:
        # More precise matching - check for word boundaries
        if re.search(r'\b' + field + r'\b', prompt_lower):
            # Extract the actual matched word for the error message
            match = re.search(r'\b' + field + r'\b', prompt_lower)
            return True, f"Attempt to access sensitive field: '{match.group()}'"
    
    # Check for excessive time ranges
    excessive_ranges = [
        "last 5 years", "last 10 years", "last decade", "all time",
        "since 2000", "since beginning", "years of data"
    ]
    for range_term in excessive_ranges:
        if range_term in prompt_lower:
            return True, f"Excessive time range request: '{range_term}'"
    
    # Check for attack-related queries - these should be ALLOWED for security analysis
    # Only block if trying to PERFORM attacks, not analyze them
    attack_actions = [
        "perform attack", "execute attack", "launch attack", "start attack",
        "initiate ddos", "start ddos", "flood the", "overwhelm the"
    ]
    for action in attack_actions:
        if action in prompt_lower:
            return True, f"Attack action attempt: '{action}'"
    
    return False, None

def correct_field_mappings_with_index_awareness(query_json, index=None):
    """Recursively correct field name mistakes, but be aware of index-specific fields"""
    # Get dynamic info to know what fields actually exist
    dynamic_info = get_dynamic_index_info(index)
    
    if isinstance(query_json, dict):
        corrected = {}
        for key, value in query_json.items():
            # Check if this key is a field name that needs correction
            if key in FIELD_CORRECTIONS:
                corrected_key = FIELD_CORRECTIONS[key]
                
                # If we have index info, check if the original field actually exists
                should_correct = True
                if dynamic_info and dynamic_info.get("field_catalog"):
                    available_fields = set(dynamic_info["field_catalog"].keys())
                    # If the original field exists in the index, don't correct it
                    if key in available_fields:
                        should_correct = False
                        logger.debug(f"Keeping field '{key}' as it exists in index {index}")
                
                if should_correct:
                    print(f"Field correction: '{key}' → '{corrected_key}'")
                    corrected[corrected_key] = correct_field_mappings_with_index_awareness(value, index)
                else:
                    corrected[key] = correct_field_mappings_with_index_awareness(value, index)
            else:
                # For term/terms/range operators, check field names inside
                if key in ["term", "terms", "range", "match", "exists"]:
                    if isinstance(value, dict):
                        corrected_value = {}
                        for field, field_value in value.items():
                            if field in FIELD_CORRECTIONS:
                                corrected_field = FIELD_CORRECTIONS[field]
                                
                                # Check if original field exists in index
                                should_correct = True
                                if dynamic_info and dynamic_info.get("field_catalog"):
                                    available_fields = set(dynamic_info["field_catalog"].keys())
                                    if field in available_fields:
                                        should_correct = False
                                
                                if should_correct:
                                    print(f"Field correction: '{field}' → '{corrected_field}'")
                                    corrected_value[corrected_field] = field_value
                                else:
                                    corrected_value[field] = field_value
                            else:
                                corrected_value[field] = field_value
                        corrected[key] = corrected_value
                    else:
                        corrected[key] = correct_field_mappings_with_index_awareness(value, index)
                else:
                    corrected[key] = correct_field_mappings_with_index_awareness(value, index)
        return corrected
    elif isinstance(query_json, list):
        return [correct_field_mappings_with_index_awareness(item, index) for item in query_json]
    else:
        return query_json

def correct_field_mappings(query_json):
    """Original field mapping correction function for backward compatibility"""
    return correct_field_mappings_with_index_awareness(query_json, None)

# Import optimized field mapping and async LLM with robust fallback
OPTIMIZATIONS_AVAILABLE = False

# Try relative imports first (when used as module)
try:
    from .optimized_field_mapping import correct_field_mappings_with_index_awareness_optimized
    from .async_llm import call_local_model_async, get_async_llm_manager
    OPTIMIZATIONS_AVAILABLE = True
    print("✅ Phase 2 optimizations available: async LLM + optimized field mapping")
except (ImportError, ValueError) as e:
    # Try absolute imports (when run directly or from different context)
    try:
        import sys
        from pathlib import Path
        
        # Add the generators directory to path if not already there
        generators_dir = Path(__file__).parent
        if str(generators_dir) not in sys.path:
            sys.path.insert(0, str(generators_dir))
        
        from optimized_field_mapping import correct_field_mappings_with_index_awareness_optimized
        from async_llm import call_local_model_async, get_async_llm_manager
        OPTIMIZATIONS_AVAILABLE = True
        print("✅ Phase 2 optimizations available: async LLM + optimized field mapping (absolute imports)")
    except ImportError as e2:
        OPTIMIZATIONS_AVAILABLE = False
        print(f"⚠️ Phase 2 optimizations not available: {e2}")
        print("   Falling back to original sync processing...")

async def generate_with_retries_async(task_prompt, schema_path, rules_path, max_retries=2, index=None, model="llama3.1:latest"):
    """Async version of generate_with_retries for improved performance"""
    start_time = time.time()
    metrics = {
        "attempts": 0,
        "latency_seconds": 0,
        "retry_reasons": [],
        "async_enabled": True
    }
    
    # Use new comprehensive security layer if available, fallback to old system
    if NEW_SECURITY_AVAILABLE:
        secure_gen = get_secure_generator()
        security_validation = secure_gen.validate_input_security(task_prompt, index)
        if not security_validation["is_secure"]:
            metrics["latency_seconds"] = time.time() - start_time
            return {
                "abstain": True, 
                "reason": f"Security validation failed: {security_validation['reason']}", 
                "metrics": metrics,
                "security_metrics": security_validation["metrics"]
            }
        task_prompt = security_validation["sanitized_prompt"]
    else:
        is_violation, violation_reason = check_security_violations(task_prompt)
        if is_violation:
            metrics["latency_seconds"] = time.time() - start_time
            return {"abstain": True, "reason": f"Security violation: {violation_reason}", "metrics": metrics}
    
    # Enhance prompt if CIC index and enhancer available
    enhanced_task_prompt = task_prompt
    if ENHANCER_AVAILABLE and index and "cic" in index.lower():
        enhancements = enhance_prompt(task_prompt)
        if enhancements['field_constraints'] or enhancements['time_constraints']:
            enhanced_task_prompt = build_enhanced_prompt(task_prompt, enhancements)
            print(f"Enhanced prompt with extracted constraints")
    
    prompt = build_prompt(enhanced_task_prompt, index)
    
    for attempt in range(max_retries + 1):
        metrics["attempts"] = attempt + 1
        print(f"Generation attempt {attempt + 1}/{max_retries + 1} (async)")
        
        try:
            # Call model asynchronously
            if OPTIMIZATIONS_AVAILABLE:
                response = await call_local_model_async(prompt, model, method="constrained")
            else:
                # Fallback to sync call
                response = call_local_model(prompt, model)
            
            # Extract JSON (handle markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Parse JSON
            query_json = json.loads(response)
            
            # Apply optimized field corrections BEFORE validation
            if OPTIMIZATIONS_AVAILABLE:
                query_json = correct_field_mappings_with_index_awareness_optimized(query_json, index)
            else:
                query_json = correct_field_mappings_with_index_awareness(query_json, index)
            
            # Validate against schema
            schema_valid, schema_error = validate_against_schema(query_json, schema_path)
            if not schema_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed schema validation: {schema_error}\n"
                    prompt += "Please fix the schema issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"schema: {schema_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Schema validation failed: {schema_error}", "metrics": metrics}
            
            # Validate with validator.py
            validator_valid, validator_error = validate_with_validator(query_json, rules_path)
            if not validator_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed validation: {validator_error}\n"
                    prompt += "Please fix the validation issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"validator: {validator_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Validation failed: {validator_error}", "metrics": metrics}
            
            # Success!
            metrics["latency_seconds"] = time.time() - start_time
            return {"query": query_json, "metrics": metrics}
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                prompt = build_prompt(task_prompt)
                prompt += f"\n\nPrevious attempt produced invalid JSON: {str(e)}\n"
                prompt += "Please return valid JSON only.\n"
                continue
            else:
                metrics["retry_reasons"].append(f"json: {str(e)}")
                metrics["latency_seconds"] = time.time() - start_time
                return {"abstain": True, "reason": f"JSON parsing failed: {str(e)}", "metrics": metrics}
        
        except Exception as e:
            if attempt < max_retries:
                print(f"Attempt {attempt + 1} failed: {e}")
                continue
            else:
                metrics["retry_reasons"].append(f"error: {str(e)}")
                metrics["latency_seconds"] = time.time() - start_time
                return {"abstain": True, "reason": f"Generation failed: {str(e)}", "metrics": metrics}
    
    # Should not reach here
    metrics["latency_seconds"] = time.time() - start_time
    return {"abstain": True, "reason": "Max retries exceeded", "metrics": metrics}

def generate_with_retries_smart(task_prompt, schema_path, rules_path, max_retries=2, index=None, model="llama3.1:latest", prefer_async=True):
    """
    Smart wrapper that automatically chooses between async and sync generation.
    Uses async when possible for better performance, falls back to sync.
    """
    if prefer_async and OPTIMIZATIONS_AVAILABLE:
        try:
            # Try to use async if we're in an async context or can create one
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, but we need to return a sync result
                # Create a task and run it in a thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(generate_with_retries_async(
                            task_prompt, schema_path, rules_path, max_retries, index, model
                        ))
                    )
                    return future.result(timeout=300)  # 5 minute timeout
                    
            except RuntimeError:
                # No running loop, we can use asyncio.run directly
                return asyncio.run(generate_with_retries_async(
                    task_prompt, schema_path, rules_path, max_retries, index, model
                ))
                
        except Exception as e:
            print(f"⚠️ Async generation failed, falling back to sync: {e}")
            # Fall back to sync
            return generate_with_retries(task_prompt, schema_path, rules_path, max_retries, index, model)
    else:
        # Use sync generation
        return generate_with_retries(task_prompt, schema_path, rules_path, max_retries, index, model)

def generate_with_retries(task_prompt, schema_path, rules_path, max_retries=2, index=None, model="llama3.1:latest"):
    """Generate query with validation and retries"""
    start_time = time.time()
    metrics = {
        "attempts": 0,
        "latency_seconds": 0,
        "retry_reasons": []
    }
    
    # Use new comprehensive security layer if available, fallback to old system
    if NEW_SECURITY_AVAILABLE:
        secure_gen = get_secure_generator()
        security_validation = secure_gen.validate_input_security(task_prompt, index)
        if not security_validation["is_secure"]:
            metrics["latency_seconds"] = time.time() - start_time
            return {
                "abstain": True, 
                "reason": f"Security validation failed: {security_validation['reason']}", 
                "metrics": metrics,
                "security_metrics": security_validation["metrics"]
            }
        # Use sanitized prompt for generation
        task_prompt = security_validation["sanitized_prompt"]
    else:
        # Fallback to old security check
        is_violation, violation_reason = check_security_violations(task_prompt)
        if is_violation:
            metrics["latency_seconds"] = time.time() - start_time
            return {"abstain": True, "reason": f"Security violation: {violation_reason}", "metrics": metrics}
    
    # Enhance prompt if CIC index and enhancer available
    enhanced_task_prompt = task_prompt
    if ENHANCER_AVAILABLE and index and "cic" in index.lower():
        enhancements = enhance_prompt(task_prompt)
        if enhancements['field_constraints'] or enhancements['time_constraints']:
            enhanced_task_prompt = build_enhanced_prompt(task_prompt, enhancements)
            print(f"Enhanced prompt with extracted constraints")
    
    prompt = build_prompt(enhanced_task_prompt, index)
    
    for attempt in range(max_retries + 1):
        metrics["attempts"] = attempt + 1
        print(f"Generation attempt {attempt + 1}/{max_retries + 1}")
        
        try:
            # Call model
            response = call_local_model(prompt, model)
            
            # Extract JSON (handle markdown code blocks)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            # Parse JSON
            query_json = json.loads(response)
            
            # Apply optimized field corrections BEFORE validation
            if OPTIMIZATIONS_AVAILABLE:
                query_json = correct_field_mappings_with_index_awareness_optimized(query_json, index)
            else:
                query_json = correct_field_mappings_with_index_awareness(query_json, index)
            
            # Validate against schema
            schema_valid, schema_error = validate_against_schema(query_json, schema_path)
            if not schema_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed schema validation: {schema_error}\n"
                    prompt += "Please fix the schema issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"schema: {schema_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Schema validation failed: {schema_error}", "metrics": metrics}
            
            # Validate with validator.py
            validator_valid, validator_error = validate_with_validator(query_json, rules_path)
            if not validator_valid:
                if attempt < max_retries:
                    prompt = build_prompt(task_prompt)
                    prompt += f"\n\nPrevious attempt failed validation: {validator_error}\n"
                    prompt += "Please fix the validation issues and try again.\n"
                    continue
                else:
                    metrics["retry_reasons"].append(f"validator: {validator_error}")
                    metrics["latency_seconds"] = time.time() - start_time
                    return {"abstain": True, "reason": f"Validation failed: {validator_error}", "metrics": metrics}
            
            # Success!
            metrics["latency_seconds"] = time.time() - start_time
            query_json["_generation_metrics"] = metrics
            return query_json
            
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                prompt = build_prompt(task_prompt)
                prompt += f"\n\nPrevious attempt produced invalid JSON: {e}\n"
                prompt += "Please output valid JSON only.\n"
                continue
            else:
                metrics["retry_reasons"].append(f"json: {e}")
                metrics["latency_seconds"] = time.time() - start_time
                return {"abstain": True, "reason": f"Invalid JSON: {e}", "metrics": metrics}
        except Exception as e:
            metrics["latency_seconds"] = time.time() - start_time
            return {"abstain": True, "reason": f"Generation error: {e}", "metrics": metrics}
    
    metrics["latency_seconds"] = time.time() - start_time
    return {"abstain": True, "reason": "Max retries exceeded", "metrics": metrics}

def get_phase2_performance_stats():
    """Get Phase 2 performance optimization statistics"""
    stats = {"phase2_enabled": OPTIMIZATIONS_AVAILABLE}
    
    if OPTIMIZATIONS_AVAILABLE:
        # Get async LLM manager stats
        try:
            async_manager = get_async_llm_manager()
            stats["async_llm"] = async_manager.get_stats()
        except Exception as e:
            stats["async_llm"] = {"error": str(e)}
        
        # Get optimized field mapping stats
        try:
            from .optimized_field_mapping import get_optimized_field_mapper
            field_mapper = get_optimized_field_mapper()
            stats["field_mapping"] = field_mapper.get_stats()
        except Exception as e:
            stats["field_mapping"] = {"error": str(e)}
    
    return stats

def clear_phase2_caches():
    """Clear all Phase 2 optimization caches"""
    if OPTIMIZATIONS_AVAILABLE:
        try:
            # Clear async LLM manager stats
            async_manager = get_async_llm_manager()
            async_manager.clear_stats()
            
            # Clear field mapping cache
            from .optimized_field_mapping import get_optimized_field_mapper
            field_mapper = get_optimized_field_mapper()
            field_mapper.clear_cache()
            
            print("✅ Phase 2 caches cleared")
            return True
        except Exception as e:
            print(f"⚠️ Error clearing Phase 2 caches: {e}")
            return False
    else:
        print("⚠️ Phase 2 optimizations not available")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate constrained ES DSL queries")
    parser.add_argument("--prompt", required=True, help="Query prompt")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--schema", default="artifacts/esdsl_schema.json", help="Schema file")
    parser.add_argument("--rules", default="artifacts/validator_rules.yaml", help="Validator rules")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Output directory")
    parser.add_argument("--model", default="llama3.1:latest", help="Ollama model to use")
    parser.add_argument("--index", help="Target index (auto-selects appropriate rules)")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible generation")
    
    args = parser.parse_args()
    
    # Set random seed if provided
    if args.seed is not None:
        import random
        import numpy as np
        random.seed(args.seed)
        np.random.seed(args.seed)
        print(f"Set random seed to {args.seed} for reproducible generation")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Auto-select rules based on index
    rules_file = args.rules
    if args.index and "cic" in args.index.lower():
        cic_rules = Path("artifacts/validator_rules_cic.yaml")
        if cic_rules.exists():
            rules_file = str(cic_rules)
            print(f"Using CIC-IDS2017 validator rules for index: {args.index}")
    
    # Generate query
    result = generate_with_retries(args.prompt, args.schema, rules_file, index=args.index, model=args.model)
    
    # Save result
    if args.task_id:
        output_file = output_dir / f"{args.task_id}.json"
    else:
        output_file = output_dir / "generated.json"
    
    # Extract metrics before saving
    metrics = None
    if "_generation_metrics" in result and "abstain" not in result:
        metrics = result.pop("_generation_metrics")
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    if "abstain" in result:
        print(f"Generation abstained: {result['reason']}")
        if "metrics" in result:
            print(f"Metrics: {result['metrics']['attempts']} attempts, {result['metrics']['latency_seconds']:.2f}s")
        sys.exit(1)
    else:
        print(f"Successfully generated query saved to {output_file}")
        if metrics:
            print(f"Metrics: {metrics['attempts']} attempts, {metrics['latency_seconds']:.2f}s")
            # Save metrics separately
            metrics_file = output_file.parent / f"{output_file.stem}.metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
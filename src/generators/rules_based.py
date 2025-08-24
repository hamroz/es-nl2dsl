#!/usr/bin/env python3
"""Rule-based baseline query generator (no LLM)"""
import json
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Import shared field mapping utilities
try:
    from .utils.field_mapping import FIELD_CORRECTIONS, correct_field_mappings
except ImportError:
    # For direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.generators.utils.field_mapping import FIELD_CORRECTIONS, correct_field_mappings

def extract_date_patterns(prompt):
    """Extract date patterns from prompt"""
    # Specific date patterns
    specific_date = re.search(r'(\d{4})-(\d{2})-(\d{2})', prompt)
    if specific_date:
        date_str = specific_date.group(0)
        start = f"{date_str}T00:00:00Z"
        end = f"{date_str}T23:59:59Z"
        return {"gte": start, "lte": end}
    
    # Date range patterns
    range_match = re.search(r'between\s+\w+\s+(\d+)-(\d+),\s+(\d{4})', prompt, re.IGNORECASE)
    if range_match:
        start_day = int(range_match.group(1))
        end_day = int(range_match.group(2))
        year = int(range_match.group(3))
        month = 7  # Assume July for simplicity
        start = f"{year:04d}-{month:02d}-{start_day:02d}T00:00:00Z"
        end = f"{year:04d}-{month:02d}-{end_day:02d}T23:59:59Z"
        return {"gte": start, "lte": end}
    
    # Default to a recent window
    return {
        "gte": "2017-07-04T00:00:00Z",
        "lte": "2017-07-04T23:59:59Z"
    }

def extract_ip_patterns(prompt):
    """Extract IP address patterns"""
    filters = []
    
    # Specific IP
    ip_match = re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', prompt)
    if ip_match:
        ip = ip_match.group(1)
        if "source" in prompt.lower() or "src" in prompt.lower() or "from" in prompt.lower():
            filters.append({"term": {"src_ip": ip}})
        elif "destination" in prompt.lower() or "dst" in prompt.lower() or "to" in prompt.lower():
            filters.append({"term": {"dst_ip": ip}})
        else:
            # Guess source if not specified
            filters.append({"term": {"src_ip": ip}})
    
    # IP prefix patterns
    if "192.168" in prompt:
        # Simplified - would need actual prefix matching in production
        filters.append({"terms": {"src_ip": [
            "192.168.1.50", "192.168.1.100", "192.168.1.150", "192.168.2.50"
        ]}})
    
    return filters

def extract_port_patterns(prompt):
    """Extract port patterns"""
    filters = []
    
    # Multiple ports
    multi_port = re.findall(r'ports?\s+(\d+)(?:\s+or\s+(\d+))?', prompt, re.IGNORECASE)
    if multi_port:
        ports = []
        for match in multi_port:
            ports.extend([int(p) for p in match if p])
        if ports:
            if "destination" in prompt.lower() or "dst" in prompt.lower() or "to" in prompt.lower():
                filters.append({"terms": {"dst_port": ports}})
            else:
                filters.append({"terms": {"dst_port": ports}})
    
    # Well-known ports
    if "ssh" in prompt.lower():
        filters.append({"term": {"dst_port": 22}})
    elif "http" in prompt.lower() and "https" not in prompt.lower():
        filters.append({"term": {"dst_port": 80}})
    elif "https" in prompt.lower():
        filters.append({"term": {"dst_port": 443}})
    elif "rdp" in prompt.lower():
        filters.append({"term": {"dst_port": 3389}})
    elif "smb" in prompt.lower():
        filters.append({"term": {"dst_port": 445}})
    elif "dns" in prompt.lower():
        filters.append({"term": {"dst_port": 53}})
    
    return filters

def extract_protocol_patterns(prompt):
    """Extract protocol patterns"""
    prompt_lower = prompt.lower()
    
    if "tcp" in prompt_lower:
        return [{"term": {"protocol": "TCP"}}]
    elif "udp" in prompt_lower:
        return [{"term": {"protocol": "UDP"}}]
    
    return []

def extract_label_patterns(prompt):
    """Extract label/classification patterns"""
    prompt_lower = prompt.lower()
    
    if "malicious" in prompt_lower:
        return [{"term": {"label": "malicious"}}]
    elif "benign" in prompt_lower:
        return [{"term": {"label": "benign"}}]
    
    return []

def extract_bytes_patterns(prompt):
    """Extract byte transfer patterns"""
    filters = []
    
    # Look for byte patterns
    bytes_match = re.search(r'(\d+)\s*(?:bytes|kb|mb)', prompt, re.IGNORECASE)
    if bytes_match:
        value = int(bytes_match.group(1))
        unit = bytes_match.group(0).lower()
        
        # Convert to bytes if needed
        if 'kb' in unit:
            value *= 1024
        elif 'mb' in unit:
            value *= 1024 * 1024
        
        # Determine field and operator
        if "more than" in prompt.lower() or "greater than" in prompt.lower() or ">" in prompt:
            op = "gt"
        elif "less than" in prompt.lower() or "<" in prompt:
            op = "lt"
        else:
            op = "gte"
        
        # Determine which field
        if "outbound" in prompt.lower() or "sent" in prompt.lower() or "transferred" in prompt.lower():
            filters.append({"range": {"bytes_out": {op: value}}})
        elif "inbound" in prompt.lower() or "received" in prompt.lower():
            filters.append({"range": {"bytes_in": {op: value}}})
        else:
            # Default to bytes_out for "transferred"
            filters.append({"range": {"bytes_out": {op: value}}})
    
    return filters

def generate_rule_based_query(prompt):
    """Generate query using rule-based patterns"""
    filters = []
    
    # Always add time window
    time_range = extract_date_patterns(prompt)
    filters.append({"range": {"@timestamp": time_range}})
    
    # Extract various patterns
    filters.extend(extract_label_patterns(prompt))
    filters.extend(extract_protocol_patterns(prompt))
    filters.extend(extract_ip_patterns(prompt))
    filters.extend(extract_port_patterns(prompt))
    filters.extend(extract_bytes_patterns(prompt))
    
    # Build query
    query = {
        "query": {
            "bool": {
                "filter": filters
            }
        }
    }
    
    return query

def main():
    parser = argparse.ArgumentParser(description="Rule-based baseline query generator")
    parser.add_argument("--prompt", required=True, help="Query prompt")
    parser.add_argument("--task-id", help="Task ID for output naming")
    parser.add_argument("--output-dir", default="artifacts/generated", help="Output directory")
    
    args = parser.parse_args()
    
    # Generate query
    query = generate_rule_based_query(args.prompt)
    
    # Apply field corrections
    query = correct_field_mappings(query)
    
    # Save result
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.task_id:
        output_file = output_dir / f"rules_{args.task_id}.json"
    else:
        output_file = output_dir / "rules_generated.json"
    
    with open(output_file, 'w') as f:
        json.dump(query, f, indent=2)
    
    print(f"Rule-based query generated and saved to {output_file}")
    print(json.dumps(query, indent=2))

if __name__ == "__main__":
    main()
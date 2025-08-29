"""
Field Context Manager - Provides rich context about fields for better LLM understanding
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

class FieldContextManager:
    """Manages field context, relationships, and semantic understanding."""
    
    def __init__(self):
        self.field_descriptions = {}
        self.field_relationships = defaultdict(set)
        self.field_examples = defaultdict(list)
        self.field_constraints = {}
        self.semantic_groups = {}
        self.common_mistakes = defaultdict(list)
        self.usage_statistics = defaultdict(int)
        self.last_update = time.time()
        
        # Initialize with known field contexts
        self._initialize_field_contexts()
        
    def _initialize_field_contexts(self):
        """Initialize with comprehensive field contexts."""
        
        # Core field descriptions with rich context
        self.field_descriptions = {
            # Timestamp fields
            "@timestamp": {
                "type": "date",
                "description": "Primary timestamp for events",
                "common_names": ["timestamp", "time", "datetime", "event_time"],
                "ecs_equivalent": "@timestamp",
                "examples": ["2017-07-04T00:00:00Z", "2024-01-15T14:30:00Z"],
                "usage": "ALWAYS use for time-based filtering",
                "constraints": "ISO 8601 format required"
            },
            
            # IP Address fields
            "src_ip": {
                "type": "keyword",
                "description": "Source IP address",
                "common_names": ["source_ip", "source.ip", "src", "srcip", "client_ip"],
                "ecs_equivalent": "source.ip",
                "examples": ["192.168.1.100", "10.0.0.5", "172.16.0.1"],
                "usage": "Use for filtering by source IP",
                "constraints": "IPv4 or IPv6 format"
            },
            "dst_ip": {
                "type": "keyword",
                "description": "Destination IP address",
                "common_names": ["destination_ip", "destination.ip", "dst", "dstip", "server_ip"],
                "ecs_equivalent": "destination.ip",
                "examples": ["192.168.1.1", "8.8.8.8", "172.16.0.254"],
                "usage": "Use for filtering by destination IP",
                "constraints": "IPv4 or IPv6 format"
            },
            
            # Port fields
            "src_port": {
                "type": "integer",
                "description": "Source port number",
                "common_names": ["source_port", "source.port", "srcport", "client_port"],
                "ecs_equivalent": "source.port",
                "examples": [80, 443, 22, 3389, 8080],
                "usage": "Use for filtering by source port",
                "constraints": "Range: 0-65535"
            },
            "dst_port": {
                "type": "integer", 
                "description": "Destination port number",
                "common_names": ["destination_port", "destination.port", "dstport", "server_port"],
                "ecs_equivalent": "destination.port",
                "examples": [80, 443, 22, 3389, 8080],
                "usage": "Use for filtering by destination port",
                "constraints": "Range: 0-65535"
            },
            
            # Protocol field
            "protocol": {
                "type": "keyword",
                "description": "Network protocol",
                "common_names": ["network.protocol", "proto", "ip_protocol"],
                "ecs_equivalent": "network.protocol",
                "examples": ["tcp", "udp", "icmp", "http", "https"],
                "usage": "Use for filtering by protocol type",
                "constraints": "Lowercase protocol names"
            },
            
            # Traffic volume fields
            "bytes_in": {
                "type": "long",
                "description": "Bytes received/inbound",
                "common_names": ["bytes_received", "inbound_bytes", "network.bytes_in", "rx_bytes"],
                "ecs_equivalent": "source.bytes",
                "examples": [1024, 5000, 1048576],
                "usage": "Use for filtering by incoming data volume",
                "constraints": "Positive integer"
            },
            "bytes_out": {
                "type": "long",
                "description": "Bytes sent/outbound",
                "common_names": ["bytes_sent", "outbound_bytes", "network.bytes_out", "tx_bytes"],
                "ecs_equivalent": "destination.bytes",
                "examples": [2048, 10000, 2097152],
                "usage": "Use for filtering by outgoing data volume",
                "constraints": "Positive integer"
            },
            
            # Classification fields
            "label": {
                "type": "keyword",
                "description": "Event classification label",
                "common_names": ["event.label", "event.type", "traffic_type", "classification"],
                "ecs_equivalent": "event.category",
                "examples": ["malicious", "benign", "BENIGN", "DDoS", "PortScan"],
                "usage": "Use for filtering by event classification",
                "constraints": "Case-sensitive exact match"
            },
            
            # CIC-IDS2017 specific fields
            "attack_type": {
                "type": "keyword",
                "description": "Type of attack detected",
                "common_names": ["attack.type", "threat_type", "incident_type"],
                "ecs_equivalent": "threat.indicator.type",
                "examples": ["dos", "scan", "bruteforce", "web_attack", "normal"],
                "usage": "Use for filtering by attack category",
                "constraints": "Lowercase attack categories"
            },
            "flow_packets_s": {
                "type": "float",
                "description": "Packet rate per second",
                "common_names": ["flow.packets_s", "packet_rate", "pps"],
                "ecs_equivalent": "network.packets_per_second",
                "examples": [10.5, 100.0, 1000.0],
                "usage": "Use for detecting high packet rate attacks",
                "constraints": "Non-negative float"
            },
            "flow_bytes_s": {
                "type": "float",
                "description": "Byte rate per second",
                "common_names": ["flow.bytes_s", "byte_rate", "bps", "bandwidth"],
                "ecs_equivalent": "network.bytes_per_second",
                "examples": [1024.5, 10000.0, 1000000.0],
                "usage": "Use for detecting high bandwidth attacks",
                "constraints": "Non-negative float"
            }
        }
        
        # Define semantic groups
        self.semantic_groups = {
            "network_identifiers": ["src_ip", "dst_ip", "src_port", "dst_port"],
            "traffic_metrics": ["bytes_in", "bytes_out", "flow_packets_s", "flow_bytes_s"],
            "temporal": ["@timestamp", "day_of_week", "hour_of_day"],
            "classification": ["label", "attack_type"],
            "protocols": ["protocol"]
        }
        
        # Define field relationships
        self.field_relationships = {
            "src_ip": {"related_to": ["src_port", "bytes_out"], "opposite": "dst_ip"},
            "dst_ip": {"related_to": ["dst_port", "bytes_in"], "opposite": "src_ip"},
            "src_port": {"related_to": ["src_ip", "protocol"], "opposite": "dst_port"},
            "dst_port": {"related_to": ["dst_ip", "protocol"], "opposite": "src_port"},
            "bytes_in": {"related_to": ["dst_ip", "dst_port"], "opposite": "bytes_out"},
            "bytes_out": {"related_to": ["src_ip", "src_port"], "opposite": "bytes_in"}
        }
        
        # Track common mistakes from field corrections
        self.common_mistakes = {
            "src_ip": ["source.ip", "source_ip", "srcip", "src"],
            "dst_ip": ["destination.ip", "destination_ip", "dstip", "dst"],
            "src_port": ["source.port", "source_port", "srcport"],
            "dst_port": ["destination.port", "destination_port", "dstport"],
            "@timestamp": ["timestamp", "time", "datetime"],
            "label": ["event.label", "event.type", "traffic_type"],
            "bytes_in": ["bytes_received", "inbound_bytes", "network.bytes_in"],
            "bytes_out": ["bytes_sent", "outbound_bytes", "network.bytes_out"]
        }
    
    def get_field_context(self, field_name: str) -> Dict:
        """Get comprehensive context for a field."""
        context = self.field_descriptions.get(field_name, {})
        
        # Add usage statistics
        context["usage_count"] = self.usage_statistics.get(field_name, 0)
        
        # Add relationships
        if field_name in self.field_relationships:
            context["relationships"] = self.field_relationships[field_name]
        
        # Add semantic group
        for group_name, fields in self.semantic_groups.items():
            if field_name in fields:
                context["semantic_group"] = group_name
                context["group_members"] = fields
                break
        
        # Add common mistakes
        if field_name in self.common_mistakes:
            context["common_mistakes"] = self.common_mistakes[field_name]
        
        return context
    
    def get_field_suggestions(self, incorrect_field: str) -> List[Tuple[str, float]]:
        """Get suggestions for correcting an incorrect field name."""
        suggestions = []
        incorrect_lower = incorrect_field.lower()
        
        # Check direct mapping from common mistakes
        for correct_field, mistakes in self.common_mistakes.items():
            if incorrect_field in mistakes or incorrect_lower in [m.lower() for m in mistakes]:
                suggestions.append((correct_field, 1.0))
        
        # Check for partial matches
        for field_name, desc in self.field_descriptions.items():
            # Check common names
            if "common_names" in desc:
                for common_name in desc["common_names"]:
                    if incorrect_lower == common_name.lower():
                        suggestions.append((field_name, 0.9))
                    elif incorrect_lower in common_name.lower() or common_name.lower() in incorrect_lower:
                        suggestions.append((field_name, 0.7))
            
            # Check ECS equivalent
            if "ecs_equivalent" in desc and incorrect_lower == desc["ecs_equivalent"].lower():
                suggestions.append((field_name, 0.85))
        
        # Remove duplicates and sort by confidence
        seen = set()
        unique_suggestions = []
        for field, conf in sorted(suggestions, key=lambda x: x[1], reverse=True):
            if field not in seen:
                seen.add(field)
                unique_suggestions.append((field, conf))
        
        return unique_suggestions
    
    def build_field_prompt_context(self, index: str = None, fields_used: List[str] = None) -> str:
        """Build comprehensive field context for prompts."""
        prompt = "\n=== FIELD REFERENCE ===\n"
        prompt += "IMPORTANT: Use ONLY these exact field names in your query:\n\n"
        
        # Group fields by semantic category
        for group_name, field_list in self.semantic_groups.items():
            group_title = group_name.replace("_", " ").title()
            prompt += f"{group_title}:\n"
            
            for field in field_list:
                if field in self.field_descriptions:
                    desc = self.field_descriptions[field]
                    prompt += f"  • {field} ({desc['type']}): {desc['description']}\n"
                    
                    # Add examples
                    if "examples" in desc and desc["examples"]:
                        examples = desc["examples"][:3]  # Limit examples
                        if desc["type"] in ["keyword", "text"]:
                            example_str = ', '.join(f'"{ex}"' for ex in examples)
                        else:
                            example_str = ', '.join(str(ex) for ex in examples)
                        prompt += f"    Examples: {example_str}\n"
                    
                    # Add common mistakes to avoid
                    if field in self.common_mistakes:
                        mistakes = self.common_mistakes[field][:3]  # Limit mistakes shown
                        prompt += f"    ⚠️ DO NOT USE: {', '.join(mistakes)}\n"
            prompt += "\n"
        
        # Add field correction reminders
        prompt += "=== FIELD NAME RULES ===\n"
        prompt += "• NEVER use dot notation (e.g., source.ip) - use underscores (src_ip)\n"
        prompt += "• NEVER use ECS field names - use the exact field names above\n"
        prompt += "• Timestamp field is '@timestamp' (with @), not 'timestamp'\n"
        prompt += "• Use 'src_ip/dst_ip', not 'source_ip/destination_ip'\n"
        prompt += "• Use 'src_port/dst_port', not 'source_port/destination_port'\n\n"
        
        return prompt
    
    def track_field_usage(self, field_name: str, was_corrected: bool = False):
        """Track field usage for analytics."""
        self.usage_statistics[field_name] += 1
        
        if was_corrected:
            # Track that this field needed correction
            if "correction_count" not in self.usage_statistics:
                self.usage_statistics["correction_count"] = defaultdict(int)
            self.usage_statistics["correction_count"][field_name] += 1
    
    def get_field_analytics(self) -> Dict:
        """Get analytics about field usage and corrections."""
        total_uses = sum(v for k, v in self.usage_statistics.items() if not isinstance(v, dict))
        correction_counts = self.usage_statistics.get("correction_count", {})
        
        analytics = {
            "total_field_uses": total_uses,
            "unique_fields_used": len([k for k in self.usage_statistics.keys() if not isinstance(self.usage_statistics[k], dict)]),
            "most_used_fields": sorted(
                [(k, v) for k, v in self.usage_statistics.items() if not isinstance(v, dict)],
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "most_corrected_fields": sorted(
                correction_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10] if correction_counts else [],
            "correction_rate": sum(correction_counts.values()) / total_uses if total_uses > 0 else 0
        }
        
        return analytics
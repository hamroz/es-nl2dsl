"""Shared field mapping utilities for query generation"""

# Common field mapping errors from LLMs (maps incorrect field names to correct ones)
FIELD_CORRECTIONS = {
    # ECS-style fields to actual fields
    "event.label": "label",
    "event.type": "label",
    "source.ip": "src_ip",
    "source.port": "src_port",
    "destination.ip": "dst_ip",
    "destination.port": "dst_port",
    "destination_port": "dst_port",
    "source_port": "src_port",
    "timestamp": "@timestamp",
    # Common variants
    "bytes_received": "bytes_in",
    "bytes_sent": "bytes_out",
    "traffic_type": "label",
}

def correct_field_mappings(query_json):
    """Recursively correct common field name mistakes in the query"""
    if isinstance(query_json, dict):
        corrected = {}
        for key, value in query_json.items():
            # Check if this key is a field that needs correction
            if key in FIELD_CORRECTIONS:
                corrected[FIELD_CORRECTIONS[key]] = correct_field_mappings(value)
            # Check within specific query types
            elif key == "term" and isinstance(value, dict):
                # term queries have structure {"field_name": value}
                term_corrected = {}
                for field, field_value in value.items():
                    corrected_field = FIELD_CORRECTIONS.get(field, field)
                    term_corrected[corrected_field] = field_value
                corrected[key] = term_corrected
            elif key == "terms" and isinstance(value, dict):
                # terms queries have structure {"field_name": [values]}
                terms_corrected = {}
                for field, field_values in value.items():
                    corrected_field = FIELD_CORRECTIONS.get(field, field)
                    terms_corrected[corrected_field] = field_values
                corrected[key] = terms_corrected
            elif key == "range" and isinstance(value, dict):
                # range queries have structure {"field_name": {"gte": ..., "lte": ...}}
                range_corrected = {}
                for field, range_spec in value.items():
                    corrected_field = FIELD_CORRECTIONS.get(field, field)
                    range_corrected[corrected_field] = range_spec
                corrected[key] = range_corrected
            elif key == "match" and isinstance(value, dict):
                # match queries have structure {"field_name": value}
                match_corrected = {}
                for field, field_value in value.items():
                    corrected_field = FIELD_CORRECTIONS.get(field, field)
                    match_corrected[corrected_field] = field_value
                corrected[key] = match_corrected
            elif key == "exists" and isinstance(value, dict) and "field" in value:
                # exists queries have structure {"field": "field_name"}
                field = value["field"]
                corrected_field = FIELD_CORRECTIONS.get(field, field)
                corrected[key] = {"field": corrected_field}
            else:
                # Recursively process nested structures
                corrected[key] = correct_field_mappings(value)
        return corrected
    elif isinstance(query_json, list):
        return [correct_field_mappings(item) for item in query_json]
    else:
        return query_json
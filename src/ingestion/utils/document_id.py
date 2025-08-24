"""Shared document ID generation utilities for data ingestion"""
import hashlib
import orjson

def make_deterministic_id(doc):
    """Generate deterministic document ID based on key fields
    
    Args:
        doc: Document dictionary
        
    Returns:
        SHA1 hash of the document's key fields
    """
    # Define key fields for consistent ID generation
    key_fields = ["@timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "protocol"]
    
    # Extract key fields, using None for missing fields
    key_data = {field: doc.get(field) for field in key_fields if field in doc}
    
    # Create consistent JSON representation
    key = orjson.dumps(key_data, option=orjson.OPT_SORT_KEYS)
    
    # Generate SHA1 hash
    return hashlib.sha1(key).hexdigest()

def make_simple_id(doc):
    """Generate simple document ID using all fields
    
    Args:
        doc: Document dictionary
        
    Returns:
        SHA1 hash of the entire document
    """
    key = orjson.dumps(doc, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha1(key).hexdigest()

def make_timestamp_id(doc):
    """Generate ID based primarily on timestamp with additional entropy
    
    Args:
        doc: Document dictionary
        
    Returns:
        SHA1 hash including timestamp and identifying fields
    """
    # Use timestamp as primary key with additional fields for uniqueness
    key_data = {
        "@timestamp": doc.get("@timestamp"),
        "src_ip": doc.get("src_ip"),
        "dst_ip": doc.get("dst_ip"),
        "label": doc.get("label")
    }
    
    key = orjson.dumps({k: v for k, v in key_data.items() if v is not None}, 
                      option=orjson.OPT_SORT_KEYS)
    return hashlib.sha1(key).hexdigest()
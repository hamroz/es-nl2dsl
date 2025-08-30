#!/usr/bin/env python3
"""Data Adapter for processing and ingesting new log data"""
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import requests
import subprocess

logger = logging.getLogger(__name__)

class DataAdapter:
    """Adapter for processing and ingesting new data into Elasticsearch"""
    
    def __init__(self, elasticsearch_url: str = "http://localhost:9200"):
        self.es_url = elasticsearch_url
    
    def ingest_data_file(self, file_path: str, index_name: str, mapping: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest a data file into Elasticsearch"""
        try:
            # Validate mapping against CSV columns if provided
            if mapping and Path(file_path).suffix.lower() == '.csv':
                validation_result = self._validate_mapping_against_csv(file_path, mapping)
                if not validation_result["is_valid"]:
                    logger.error(f"Mapping validation failed: {validation_result['error']}")
                    return {
                        "error": f"Mapping validation failed: {validation_result['error']}",
                        "missing_fields": validation_result.get("missing_fields", []),
                        "extra_fields": validation_result.get("extra_fields", [])
                    }
            
            # Create index with mapping if provided
            if mapping:
                created = self._create_index_with_mapping(index_name, mapping)
                if not created:
                    return {"error": "Failed to create index with mapping"}
                
                # Ensure reader user has access to the new index
                self._grant_reader_access_to_logs_indices()
            
            path = Path(file_path)
            
            if path.suffix.lower() == '.csv':
                return self._ingest_csv(file_path, index_name)
            elif path.suffix.lower() == '.json':
                return self._ingest_json(file_path, index_name)
            elif path.suffix.lower() in ['.jsonl', '.ndjson']:
                return self._ingest_jsonl(file_path, index_name)
            else:
                return {"error": f"Unsupported file format: {path.suffix}"}
                
        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")
            return {"error": str(e)}
    
    def _create_index_with_mapping(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """Create Elasticsearch index with mapping"""
        try:
            url = f"{self.es_url}/{index_name}"
            headers = {'Content-Type': 'application/json'}
            auth = ('elastic', 'ChangeMe_123')  # Use admin credentials
            
            response = requests.put(url, json=mapping, headers=headers, auth=auth)
            
            if response.status_code in [200, 201]:
                logger.info(f"Created index {index_name} with mapping")
                return True
            else:
                logger.warning(f"Failed to create index: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
    
    def _ingest_csv(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Ingest CSV file"""
        df = pd.read_csv(file_path)
        
        # Convert DataFrame to JSONL format for bulk upload
        jsonl_file = f"/tmp/{index_name}_bulk.jsonl"
        
        with open(jsonl_file, 'w') as f:
            for _, row in df.iterrows():
                # Index action
                index_action = {"index": {"_index": index_name}}
                f.write(json.dumps(index_action) + '\n')
                
                # Document
                doc = row.to_dict()
                # Convert NaN to None
                doc = {k: (None if pd.isna(v) else v) for k, v in doc.items()}
                f.write(json.dumps(doc) + '\n')
        
        return self._bulk_upload(jsonl_file, len(df))
    
    def _ingest_json(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Ingest JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        # Convert to JSONL format for bulk upload
        jsonl_file = f"/tmp/{index_name}_bulk.jsonl"
        
        with open(jsonl_file, 'w') as f:
            for item in data:
                # Index action
                index_action = {"index": {"_index": index_name}}
                f.write(json.dumps(index_action) + '\n')
                
                # Document
                f.write(json.dumps(item) + '\n')
        
        return self._bulk_upload(jsonl_file, len(data))
    
    def _ingest_jsonl(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Ingest JSONL file"""
        # Convert to Elasticsearch bulk format
        jsonl_file = f"/tmp/{index_name}_bulk.jsonl"
        doc_count = 0
        
        with open(file_path, 'r') as input_f, open(jsonl_file, 'w') as output_f:
            for line in input_f:
                line = line.strip()
                if line:
                    try:
                        # Parse to validate JSON
                        doc = json.loads(line)
                        
                        # Index action
                        index_action = {"index": {"_index": index_name}}
                        output_f.write(json.dumps(index_action) + '\n')
                        
                        # Document
                        output_f.write(json.dumps(doc) + '\n')
                        doc_count += 1
                        
                    except json.JSONDecodeError:
                        continue
        
        return self._bulk_upload(jsonl_file, doc_count)
    
    def _bulk_upload(self, jsonl_file: str, doc_count: int) -> Dict[str, Any]:
        """Upload JSONL file to Elasticsearch using bulk API with enhanced error reporting"""
        try:
            url = f"{self.es_url}/_bulk"
            headers = {'Content-Type': 'application/x-ndjson'}
            auth = ('elastic', 'ChangeMe_123')  # Use admin credentials
            
            with open(jsonl_file, 'rb') as f:
                response = requests.post(
                    url,
                    data=f,
                    headers=headers,
                    auth=auth
                )
            
            if response.status_code == 200:
                result = response.json()
                errors = []
                success_count = 0
                field_rejection_errors = []
                mapping_errors = []
                
                for item in result.get('items', []):
                    if 'index' in item:
                        if item['index'].get('status') in [200, 201]:
                            success_count += 1
                        else:
                            error_info = item['index'].get('error', {})
                            error_type = error_info.get('type', 'unknown_error')
                            error_reason = error_info.get('reason', 'Unknown error')
                            
                            # Categorize errors for better debugging
                            if 'strict_dynamic_mapping_exception' in error_type:
                                field_rejection_errors.append({
                                    'type': error_type,
                                    'reason': error_reason,
                                    'field': self._extract_rejected_field(error_reason)
                                })
                            elif 'mapper_parsing_exception' in error_type:
                                mapping_errors.append({
                                    'type': error_type,
                                    'reason': error_reason
                                })
                            else:
                                errors.append(error_info)
                
                # Clean up temp file
                Path(jsonl_file).unlink(missing_ok=True)
                
                # Detailed error reporting
                if field_rejection_errors:
                    logger.error(f"Field rejection errors: {len(field_rejection_errors)} documents rejected due to unknown fields")
                    for error in field_rejection_errors[:3]:  # Log first 3 for debugging
                        logger.error(f"Rejected field: {error['field']}, reason: {error['reason']}")
                
                if mapping_errors:
                    logger.error(f"Mapping errors: {len(mapping_errors)} documents had mapping issues")
                    for error in mapping_errors[:3]:
                        logger.error(f"Mapping error: {error['reason']}")
                
                return {
                    "success": True,
                    "total_docs": doc_count,
                    "successful": success_count,
                    "errors": len(errors) + len(field_rejection_errors) + len(mapping_errors),
                    "error_details": {
                        "field_rejections": field_rejection_errors[:3],
                        "mapping_errors": mapping_errors[:3],
                        "other_errors": errors[:3]
                    }
                }
            else:
                logger.error(f"Bulk upload HTTP error: {response.status_code} - {response.text}")
                return {"error": f"Bulk upload failed: HTTP {response.status_code} - {response.text}"}
                
        except Exception as e:
            logger.error(f"Exception during bulk upload: {e}")
            return {"error": str(e)}
    
    def _extract_rejected_field(self, error_reason: str) -> str:
        """Extract field name from strict mapping error message"""
        try:
            # Parse error messages like: "mapping set to strict, dynamic introduction of [field_name] within [_doc] is not allowed"
            if 'dynamic introduction of [' in error_reason:
                start = error_reason.find('dynamic introduction of [') + len('dynamic introduction of [')
                end = error_reason.find(']', start)
                return error_reason[start:end]
            return "unknown_field"
        except Exception:
            return "unknown_field"
    
    def test_elasticsearch_connection(self) -> Dict[str, Any]:
        """Test connection to Elasticsearch"""
        try:
            auth = ('elastic', 'ChangeMe_123')  # Use admin credentials
            response = requests.get(self.es_url, auth=auth)
            if response.status_code == 200:
                info = response.json()
                return {
                    "connected": True,
                    "cluster_name": info.get("cluster_name", "unknown"),
                    "version": info.get("version", {}).get("number", "unknown")
                }
            else:
                return {"connected": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def list_indices(self) -> List[str]:
        """List all Elasticsearch indices"""
        try:
            auth = ('elastic', 'ChangeMe_123')  # Use admin credentials
            response = requests.get(f"{self.es_url}/_cat/indices?format=json", auth=auth)
            if response.status_code == 200:
                indices = response.json()
                return [idx.get("index", "") for idx in indices if not idx.get("index", "").startswith(".")]
            else:
                return []
        except Exception as e:
            logger.error(f"Error listing indices: {e}")
            return []
    
    def get_index_info(self, index_name: str) -> Dict[str, Any]:
        """Get information about a specific index"""
        try:
            auth = ('elastic', 'ChangeMe_123')  # Use admin credentials
            # Get index stats
            stats_response = requests.get(f"{self.es_url}/{index_name}/_stats", auth=auth)
            mapping_response = requests.get(f"{self.es_url}/{index_name}/_mapping", auth=auth)
            
            info = {"index": index_name}
            
            if stats_response.status_code == 200:
                stats = stats_response.json()
                index_stats = stats.get("indices", {}).get(index_name, {})
                info.update({
                    "document_count": index_stats.get("total", {}).get("docs", {}).get("count", 0),
                    "size_bytes": index_stats.get("total", {}).get("store", {}).get("size_in_bytes", 0)
                })
            
            if mapping_response.status_code == 200:
                mapping = mapping_response.json()
                index_mapping = mapping.get(index_name, {}).get("mappings", {})
                properties = index_mapping.get("properties", {})
                info["fields"] = list(properties.keys())
                info["field_count"] = len(properties)
            
            return info
            
        except Exception as e:
            return {"error": str(e)}
    
    def create_sample_queries(self, index_name: str, field_patterns: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """Create sample queries for the new index"""
        queries = []
        
        # Basic match all
        queries.append({
            "name": "Get all documents",
            "description": "Retrieve all documents from the index",
            "dsl": json.dumps({
                "query": {"match_all": {}},
                "size": 10
            }, indent=2)
        })
        
        # Time-based queries if timestamp fields exist
        if 'timestamp_fields' in field_patterns:
            timestamp_field = field_patterns['timestamp_fields'][0]
            queries.extend([
                {
                    "name": "Recent events",
                    "description": f"Events from the last hour using {timestamp_field}",
                    "dsl": json.dumps({
                        "query": {
                            "range": {
                                timestamp_field: {
                                    "gte": "now-1h"
                                }
                            }
                        }
                    }, indent=2)
                },
                {
                    "name": "Date range query",
                    "description": f"Events from a specific date range using {timestamp_field}",
                    "dsl": json.dumps({
                        "query": {
                            "range": {
                                timestamp_field: {
                                    "gte": "2024-01-01",
                                    "lte": "2024-01-31"
                                }
                            }
                        }
                    }, indent=2)
                }
            ])
        
        # Status-based queries
        if 'status_fields' in field_patterns:
            status_field = field_patterns['status_fields'][0]
            queries.append({
                "name": "Filter by status",
                "description": f"Filter events by status using {status_field}",
                "dsl": json.dumps({
                    "query": {
                        "term": {
                            f"{status_field}.keyword": "success"
                        }
                    }
                }, indent=2)
            })
        
        # IP-based queries
        if 'ip_fields' in field_patterns:
            ip_field = field_patterns['ip_fields'][0]
            queries.append({
                "name": "IP address filter",
                "description": f"Filter by IP address using {ip_field}",
                "dsl": json.dumps({
                    "query": {
                        "term": {
                            ip_field: "192.168.1.1"
                        }
                    }
                }, indent=2)
            })
        
        return queries
    
    def _grant_reader_access_to_logs_indices(self) -> bool:
        """Ensure reader user has access to all logs_* indices"""
        try:
            auth = ('elastic', 'ChangeMe_123')
            url = f"{self.es_url}/_security/role/logs_net_reader"
            
            role_config = {
                "cluster": ["monitor"],
                "indices": [
                    {
                        "names": ["logs_*"],
                        "privileges": ["read", "view_index_metadata"]
                    }
                ]
            }
            
            response = requests.put(url, json=role_config, auth=auth)
            
            if response.status_code in [200, 201]:
                logger.info("Updated reader role to access all logs_* indices")
                return True
            else:
                logger.warning(f"Failed to update reader role: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating reader role: {e}")
            return False
    
    def _validate_mapping_against_csv(self, csv_path: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that mapping covers all CSV columns"""
        try:
            # Read just the header row to get column names
            df = pd.read_csv(csv_path, nrows=0)
            csv_columns = set(df.columns)
            
            # Get mapping field names
            mapping_fields = set(mapping.get("mappings", {}).get("properties", {}).keys())
            
            # Find missing and extra fields
            missing_fields = csv_columns - mapping_fields
            extra_fields = mapping_fields - csv_columns
            
            if missing_fields:
                error_msg = f"CSV columns missing from mapping: {missing_fields}"
                logger.error(error_msg)
                return {
                    "is_valid": False,
                    "error": error_msg,
                    "missing_fields": list(missing_fields),
                    "extra_fields": list(extra_fields)
                }
            
            if extra_fields:
                logger.warning(f"Mapping fields not in CSV: {extra_fields}")
            
            logger.info(f"Mapping validation successful: {len(csv_columns)} CSV columns matched")
            return {
                "is_valid": True,
                "missing_fields": [],
                "extra_fields": list(extra_fields)
            }
            
        except Exception as e:
            error_msg = f"Error validating CSV against mapping: {e}"
            logger.error(error_msg)
            return {
                "is_valid": False,
                "error": error_msg,
                "missing_fields": [],
                "extra_fields": []
            }
    
    def verify_ingestion_success(self, index_name: str, expected_doc_count: int, expected_fields: List[str]) -> Dict[str, Any]:
        """Verify that ingestion was successful and all fields are present"""
        try:
            auth = ('elastic', 'ChangeMe_123')
            
            # Refresh index to ensure all documents are searchable
            refresh_response = requests.post(f"{self.es_url}/{index_name}/_refresh", auth=auth)
            if refresh_response.status_code not in [200, 201]:
                logger.warning(f"Failed to refresh index {index_name}")
            
            # Get index stats
            stats_response = requests.get(f"{self.es_url}/{index_name}/_stats", auth=auth)
            if stats_response.status_code != 200:
                return {"success": False, "error": f"Failed to get index stats: {stats_response.text}"}
            
            stats = stats_response.json()
            actual_doc_count = stats.get("indices", {}).get(index_name, {}).get("total", {}).get("docs", {}).get("count", 0)
            
            # Get index mapping
            mapping_response = requests.get(f"{self.es_url}/{index_name}/_mapping", auth=auth)
            if mapping_response.status_code != 200:
                return {"success": False, "error": f"Failed to get index mapping: {mapping_response.text}"}
            
            mapping = mapping_response.json()
            actual_fields = list(mapping.get(index_name, {}).get("mappings", {}).get("properties", {}).keys())
            
            # Check document count
            doc_count_ok = actual_doc_count >= (expected_doc_count * 0.9)  # Allow 10% tolerance
            
            # Check fields presence
            missing_fields = set(expected_fields) - set(actual_fields)
            fields_ok = len(missing_fields) == 0
            
            success = doc_count_ok and fields_ok
            
            result = {
                "success": success,
                "document_count": {
                    "expected": expected_doc_count,
                    "actual": actual_doc_count,
                    "ok": doc_count_ok
                },
                "fields": {
                    "expected": expected_fields,
                    "actual": actual_fields,
                    "missing": list(missing_fields),
                    "ok": fields_ok
                }
            }
            
            if success:
                logger.info(f"Ingestion verification successful for {index_name}: {actual_doc_count} docs, {len(actual_fields)} fields")
            else:
                logger.error(f"Ingestion verification failed for {index_name}: missing fields {missing_fields}, doc count {actual_doc_count}/{expected_doc_count}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error verifying ingestion for {index_name}: {e}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

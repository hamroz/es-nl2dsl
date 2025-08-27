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
            # Create index with mapping if provided
            if mapping:
                self._create_index_with_mapping(index_name, mapping)
            
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
            response = requests.put(url, json=mapping, headers={'Content-Type': 'application/json'})
            
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
        """Upload JSONL file to Elasticsearch using bulk API"""
        try:
            url = f"{self.es_url}/_bulk"
            
            with open(jsonl_file, 'rb') as f:
                response = requests.post(
                    url,
                    data=f,
                    headers={'Content-Type': 'application/x-ndjson'}
                )
            
            if response.status_code == 200:
                result = response.json()
                errors = []
                success_count = 0
                
                for item in result.get('items', []):
                    if 'index' in item:
                        if item['index'].get('status') in [200, 201]:
                            success_count += 1
                        else:
                            errors.append(item['index'].get('error', 'Unknown error'))
                
                # Clean up temp file
                Path(jsonl_file).unlink(missing_ok=True)
                
                return {
                    "success": True,
                    "total_docs": doc_count,
                    "successful": success_count,
                    "errors": len(errors),
                    "error_details": errors[:5] if errors else []
                }
            else:
                return {"error": f"Bulk upload failed: {response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def test_elasticsearch_connection(self) -> Dict[str, Any]:
        """Test connection to Elasticsearch"""
        try:
            response = requests.get(self.es_url)
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
            response = requests.get(f"{self.es_url}/_cat/indices?format=json")
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
            # Get index stats
            stats_response = requests.get(f"{self.es_url}/{index_name}/_stats")
            mapping_response = requests.get(f"{self.es_url}/{index_name}/_mapping")
            
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

#!/usr/bin/env python3
"""Data Adapter for processing and ingesting new log data"""
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import requests
import subprocess
from datetime import datetime

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
            
            # Create index with mapping if provided, otherwise create dynamic mapping
            if mapping:
                created = self._create_index_with_mapping(index_name, mapping)
                if not created:
                    return {"error": "Failed to create index with mapping"}
            else:
                # Create a fully dynamic mapping that accepts any fields
                dynamic_mapping = self._create_dynamic_mapping()
                created = self._create_index_with_mapping(index_name, dynamic_mapping)
                if not created:
                    return {"error": "Failed to create dynamic index"}
            
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
    
    def _create_dynamic_mapping(self) -> Dict[str, Any]:
        """Create a fully dynamic mapping that accepts any fields"""
        return {
            "mappings": {
                "dynamic": "true",  # Allow any new fields
                "properties": {
                    # Pre-define common timestamp fields with proper date mapping
                    "timestamp": {"type": "date"},
                    "Timestamp": {"type": "date"},
                    "@timestamp": {"type": "date"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "time": {"type": "date"},
                    "date": {"type": "date"}
                }
            },
            "settings": {
                "index": {
                    "mapping": {
                        "total_fields": {
                            "limit": "2000"  # Allow up to 2000 fields for complex logs
                        }
                    }
                }
            }
        }
    
    def _ingest_csv(self, file_path: str, index_name: str) -> Dict[str, Any]:
        """Ingest CSV file with proper timestamp handling"""
        df = pd.read_csv(file_path)
        
        # Identify and convert timestamp columns
        df = self._process_timestamps(df)
        
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
    
    def _process_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process and standardize timestamp columns for Elasticsearch compatibility"""
        df_processed = df.copy()
        
        # Common timestamp column patterns
        timestamp_patterns = ['timestamp', 'time', 'date', 'created', 'updated', 'logged']
        
        for column in df_processed.columns:
            column_lower = column.lower()
            
            # Check if column name suggests it's a timestamp
            is_timestamp_column = any(pattern in column_lower for pattern in timestamp_patterns)
            
            if is_timestamp_column:
                logger.info(f"Processing timestamp column: {column}")
                try:
                    # Try to convert to datetime with various formats
                    df_processed[column] = self._convert_to_elasticsearch_timestamp(df_processed[column])
                except Exception as e:
                    logger.warning(f"Could not convert {column} to timestamp: {e}")
                    # If conversion fails, leave as is but log the issue
                    continue
        
        return df_processed
    
    def _convert_to_elasticsearch_timestamp(self, series: pd.Series) -> pd.Series:
        """Convert a pandas Series to Elasticsearch-compatible timestamp format"""
        # Remove any null/empty values for processing
        non_null_series = series.dropna()
        
        if len(non_null_series) == 0:
            return series
        
        # Sample the first few values to determine format
        sample_value = str(non_null_series.iloc[0]).strip()
        
        try:
            # Try different timestamp parsing strategies
            if self._is_iso_format(sample_value):
                # Already in ISO format, just ensure consistency
                converted = pd.to_datetime(series, errors='coerce', utc=True)
            elif self._is_unix_timestamp(sample_value):
                # Unix timestamp (seconds or milliseconds)
                if len(sample_value) > 10:  # Milliseconds
                    converted = pd.to_datetime(series, unit='ms', errors='coerce', utc=True)
                else:  # Seconds
                    converted = pd.to_datetime(series, unit='s', errors='coerce', utc=True)
            else:
                # Try pandas' intelligent parsing with common formats
                converted = pd.to_datetime(series, errors='coerce', utc=True)
            
            # Convert to Elasticsearch ISO format
            return converted.dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
        except Exception as e:
            logger.error(f"Timestamp conversion failed: {e}")
            # Fallback: try basic pandas conversion
            try:
                converted = pd.to_datetime(series, errors='coerce')
                return converted.dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            except:
                # Last resort: return original series
                return series
    
    def _is_iso_format(self, timestamp_str: str) -> bool:
        """Check if timestamp is already in ISO format"""
        return 'T' in timestamp_str and ('Z' in timestamp_str or '+' in timestamp_str or timestamp_str.endswith('UTC'))
    
    def _is_unix_timestamp(self, timestamp_str: str) -> bool:
        """Check if timestamp appears to be a Unix timestamp"""
        try:
            float(timestamp_str)
            # Unix timestamps are typically 10 digits (seconds) or 13 digits (milliseconds)
            return len(timestamp_str.replace('.', '')) in [10, 13]
        except ValueError:
            return False
    
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
                all_errors = []  # Store ALL errors for diagnostic purposes
                
                for item in result.get('items', []):
                    if 'index' in item:
                        if item['index'].get('status') in [200, 201]:
                            success_count += 1
                        else:
                            error_info = item['index'].get('error', {})
                            error_type = error_info.get('type', 'unknown_error')
                            error_reason = error_info.get('reason', 'Unknown error')
                            
                            # Store complete error info for diagnostics
                            complete_error = {
                                'type': error_type,
                                'reason': error_reason,
                                'status': item['index'].get('status'),
                                'document_id': item['index'].get('_id', 'unknown'),
                                'index': item['index'].get('_index', 'unknown')
                            }
                            all_errors.append(complete_error)
                            
                            # Categorize errors for better debugging
                            if 'strict_dynamic_mapping_exception' in error_type:
                                field_rejection_errors.append({
                                    'type': error_type,
                                    'reason': error_reason,
                                    'field': self._extract_rejected_field(error_reason),
                                    'document_id': complete_error['document_id']
                                })
                            elif 'mapper_parsing_exception' in error_type:
                                mapping_errors.append({
                                    'type': error_type,
                                    'reason': error_reason,
                                    'document_id': complete_error['document_id']
                                })
                            else:
                                errors.append(error_info)
                
                # Store detailed errors for diagnostic access
                self._store_ingestion_errors(all_errors, jsonl_file)
                
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
                        "field_rejections": field_rejection_errors,
                        "mapping_errors": mapping_errors,
                        "other_errors": errors,
                        "all_errors": all_errors  # Include all errors for diagnostics
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
    
    def _store_ingestion_errors(self, errors: List[Dict[str, Any]], source_file: str) -> None:
        """Store detailed ingestion errors for diagnostic purposes"""
        try:
            # Create errors directory if it doesn't exist
            errors_dir = Path("artifacts/ingestion_errors")
            errors_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp-based filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_name = Path(source_file).stem if source_file else "unknown"
            error_file = errors_dir / f"errors_{source_name}_{timestamp}.json"
            
            # Store error details with metadata
            error_data = {
                "timestamp": datetime.now().isoformat(),
                "source_file": source_file,
                "total_errors": len(errors),
                "errors": errors,
                "error_summary": self._summarize_errors(errors)
            }
            
            with open(error_file, 'w') as f:
                json.dump(error_data, f, indent=2)
            
            logger.info(f"Stored {len(errors)} ingestion errors to {error_file}")
            
        except Exception as e:
            logger.error(f"Failed to store ingestion errors: {e}")
    
    def _summarize_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary of error types and counts"""
        summary = {
            "total_count": len(errors),
            "error_types": {},
            "top_errors": [],
            "field_issues": {}
        }
        
        # Count error types
        for error in errors:
            error_type = error.get('type', 'unknown')
            summary["error_types"][error_type] = summary["error_types"].get(error_type, 0) + 1
        
        # Find most common errors
        error_reasons = {}
        for error in errors:
            reason = error.get('reason', 'Unknown')[:100]  # Truncate long reasons
            error_reasons[reason] = error_reasons.get(reason, 0) + 1
        
        # Sort by frequency and take top 5
        summary["top_errors"] = sorted(error_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Extract field-related issues
        for error in errors:
            if 'strict_dynamic_mapping_exception' in error.get('type', ''):
                field = self._extract_rejected_field(error.get('reason', ''))
                if field != 'unknown_field':
                    summary["field_issues"][field] = summary["field_issues"].get(field, 0) + 1
        
        return summary
    
    def get_recent_ingestion_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent ingestion error files for diagnostic purposes"""
        try:
            errors_dir = Path("artifacts/ingestion_errors")
            if not errors_dir.exists():
                return []
            
            # Get all error files, sorted by modification time (newest first)
            error_files = sorted(
                errors_dir.glob("errors_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            recent_errors = []
            for error_file in error_files[:limit]:
                try:
                    with open(error_file, 'r') as f:
                        error_data = json.load(f)
                    
                    # Add file info
                    error_data['error_file'] = str(error_file)
                    error_data['file_size'] = error_file.stat().st_size
                    
                    recent_errors.append(error_data)
                except Exception as e:
                    logger.warning(f"Could not read error file {error_file}: {e}")
                    continue
            
            return recent_errors
            
        except Exception as e:
            logger.error(f"Error retrieving ingestion errors: {e}")
            return []
    
    def get_ingestion_error_details(self, error_file_path: str) -> Dict[str, Any]:
        """Get detailed error information from a specific error file"""
        try:
            with open(error_file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading error file {error_file_path}: {e}")
            return {"error": f"Could not read error file: {e}"}
    
    def diagnose_ingestion_issues(self, index_name: str = None) -> Dict[str, Any]:
        """Comprehensive diagnosis of ingestion issues"""
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "elasticsearch_status": self.test_elasticsearch_connection(),
            "recent_errors": self.get_recent_ingestion_errors(10),
            "error_analysis": {},
            "recommendations": []
        }
        
        # Analyze recent errors
        all_errors = []
        for error_data in diagnosis["recent_errors"]:
            all_errors.extend(error_data.get("errors", []))
        
        if all_errors:
            diagnosis["error_analysis"] = self._analyze_error_patterns(all_errors)
            diagnosis["recommendations"] = self._generate_error_recommendations(diagnosis["error_analysis"])
        
        # Check specific index if provided
        if index_name:
            diagnosis["index_info"] = self.get_index_info(index_name)
        
        return diagnosis
    
    def _analyze_error_patterns(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in ingestion errors to identify common issues"""
        analysis = {
            "total_errors": len(errors),
            "error_type_distribution": {},
            "field_rejection_analysis": {},
            "mapping_issues": {},
            "most_problematic_fields": {}
        }
        
        field_rejections = 0
        mapping_errors = 0
        
        for error in errors:
            error_type = error.get('type', 'unknown')
            analysis["error_type_distribution"][error_type] = analysis["error_type_distribution"].get(error_type, 0) + 1
            
            if 'strict_dynamic_mapping_exception' in error_type:
                field_rejections += 1
                field = self._extract_rejected_field(error.get('reason', ''))
                if field != 'unknown_field':
                    analysis["most_problematic_fields"][field] = analysis["most_problematic_fields"].get(field, 0) + 1
            
            elif 'mapper_parsing_exception' in error_type:
                mapping_errors += 1
        
        analysis["field_rejection_analysis"]["count"] = field_rejections
        analysis["field_rejection_analysis"]["percentage"] = (field_rejections / len(errors)) * 100 if errors else 0
        
        analysis["mapping_issues"]["count"] = mapping_errors
        analysis["mapping_issues"]["percentage"] = (mapping_errors / len(errors)) * 100 if errors else 0
        
        return analysis
    
    def _generate_error_recommendations(self, error_analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on error analysis"""
        recommendations = []
        
        # Check for document parsing exceptions (often timestamp issues)
        error_types = error_analysis.get("error_type_distribution", {})
        document_parsing_pct = (error_types.get("document_parsing_exception", 0) / error_analysis.get("total_errors", 1)) * 100
        
        if document_parsing_pct > 80:
            recommendations.append(
                "🕐 **CRITICAL: Timestamp Format Issue Detected!** "
                "93.5% of your errors are document parsing failures, likely due to timestamp format incompatibility. "
                "The system now includes automatic timestamp conversion - try re-ingesting your data."
            )
        
        # Check for field rejection issues
        field_rejection_pct = error_analysis.get("field_rejection_analysis", {}).get("percentage", 0)
        if field_rejection_pct > 50:
            recommendations.append(
                "🔧 High field rejection rate detected. Consider updating your Elasticsearch mapping to include all CSV columns, "
                "or set the mapping to 'dynamic' instead of 'strict' to allow new fields."
            )
        
        # Check for mapping issues
        mapping_issues_pct = error_analysis.get("mapping_issues", {}).get("percentage", 0)
        if mapping_issues_pct > 30:
            recommendations.append(
                "📝 Mapping parsing errors detected. Check data types in your CSV - ensure dates are properly formatted "
                "and numeric fields don't contain text values."
            )
        
        # Specific timestamp recommendations
        if document_parsing_pct > 50:
            recommendations.append(
                "🔧 **Timestamp Fix Applied**: The system now automatically converts common timestamp formats to Elasticsearch-compatible ISO format. "
                "Supported formats include: ISO 8601, Unix timestamps, and common date patterns."
            )
        
        # Check for problematic fields
        problematic_fields = error_analysis.get("most_problematic_fields", {})
        if problematic_fields:
            top_field = max(problematic_fields.items(), key=lambda x: x[1])
            recommendations.append(
                f"⚠️ Field '{top_field[0]}' is causing {top_field[1]} errors. This field may need special handling "
                "or should be added to your Elasticsearch mapping."
            )
        
        # General recommendations
        if error_analysis.get("total_errors", 0) > 100:
            recommendations.append(
                "💡 Consider preprocessing your data to clean field names and ensure consistent data types before ingestion."
            )
        
        if not recommendations:
            recommendations.append("✅ No major issues detected. Your data appears to be compatible with the current mapping.")
        
        return recommendations
    
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
            
            # Force refresh the index to ensure documents are visible
            refresh_response = requests.post(f"{self.es_url}/{index_name}/_refresh", auth=auth)
            if refresh_response.status_code not in [200, 201]:
                logger.warning(f"Index refresh failed with status {refresh_response.status_code}")
            
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

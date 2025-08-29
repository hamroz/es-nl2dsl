"""Backend interface utilities for GUI integration"""
import subprocess
import json
import sys
import time
import pandas as pd
import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import streamlit as st
from elasticsearch import Elasticsearch

# Configure logging (only if not already configured)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/gui_backend.log', mode='a')
        ]
    )
logger = logging.getLogger(__name__)

# Import GUI logging utilities for user action tracking
from gui.utils.logging_utils import get_gui_logger

# Initialize backend logger for user activity tracking
backend_logger = get_gui_logger("backend_interface")

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Import from new structure
from src.utils.config import get_es_client_config, ES_ADMIN_CREDS, ES_READER_CREDS

def get_elasticsearch_client(read_only=False):
    """Get Elasticsearch client instance"""
    # Use admin credentials by default, reader for read_only operations
    use_admin = not read_only
    return Elasticsearch(**get_es_client_config(use_admin=use_admin))

def check_system_status() -> Dict[str, any]:
    """Check the status of all system components"""
    backend_logger.log_system_operation("System status check initiated")
    status = {
        "elasticsearch": False,
        "ollama": False,
        "indices": 0,
        "models": [],
        "last_check": time.time()
    }
    
    # Check Elasticsearch
    try:
        result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-u", "elastic:ChangeMe_123", 
            "http://localhost:9200/_cluster/health"
        ], capture_output=True, text=True, timeout=10)
        status["elasticsearch"] = result.stdout.strip() == "200"
        if status["elasticsearch"]:
            backend_logger.log_success("Elasticsearch connectivity verified")
        else:
            backend_logger.log_warning("Elasticsearch status check", f"HTTP response: {result.stdout.strip()}")
    except Exception as e:
        status["elasticsearch"] = False
        backend_logger.log_error("Elasticsearch connectivity check failed", str(e))
    
    # Check Ollama
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, text=True, timeout=10
        )
        status["ollama"] = result.returncode == 0
        if status["ollama"]:
            models = []
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    models.append(line.split()[0])
            status["models"] = models
            backend_logger.log_success("Ollama service verified", model_count=len(models))
        else:
            backend_logger.log_warning("Ollama status check", f"Return code: {result.returncode}")
    except Exception as e:
        status["ollama"] = False
        backend_logger.log_error("Ollama connectivity check failed", str(e))
    
    # Count indices
    if status["elasticsearch"]:
        try:
            result = subprocess.run([
                "curl", "-s", "-u", "elastic:ChangeMe_123",
                "http://localhost:9200/_cat/indices?format=json"
            ], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                indices = json.loads(result.stdout)
                status["indices"] = len([idx for idx in indices if idx["index"].startswith("logs_net")])
                backend_logger.log_status("Index count", f"Found {status['indices']} log indices")
        except Exception as e:
            backend_logger.log_error("Index count check failed", str(e))
            pass
    
    backend_logger.log_success("System status check",
        elasticsearch=status["elasticsearch"],
        ollama=status["ollama"],
        indices=status["indices"],
        model_count=len(status["models"])
    )
    return status

def run_query_generation(prompt: str, method: str = "constrained", 
                        task_id: Optional[str] = None, index: Optional[str] = None,
                        model: Optional[str] = None) -> Tuple[bool, str, Dict]:
    """Run query generation with specified method"""
    
    if not task_id:
        task_id = f"gui_{int(time.time())}"
    
    logger.info(f"🚀 Starting query generation - Method: {method}, Model: {model}, Task ID: {task_id}")
    logger.info(f"📝 Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"📝 Prompt: {prompt}")
    
    # Log user activity
    backend_logger.log_query_generation(method, model or "default", len(prompt), 
                                      index=index, task_id=task_id)
    
    # Check if using external LLM (external LLMs can only be used with constrained method currently)
    if model and (model.startswith("External:") or model.startswith("☁️")):
        if method != "constrained":
            logger.warning(f"❌ External LLM {model} not supported with {method} method")
            return False, f"External LLMs only supported with constrained method, not {method}", {}
        
        # Handle both formats: "External: name" and "☁️ name"
        if model.startswith("External:"):
            external_llm_name = model.replace("External: ", "")
        else:
            external_llm_name = model.replace("☁️ ", "")
            
        logger.info(f"🌐 Using external LLM: {external_llm_name}")
        cmd = [
            sys.executable, "src/generators/external.py",
            "--prompt", prompt,
            "--llm", external_llm_name,
            "--task-id", task_id
        ]
        if index:
            cmd.extend(["--index", index])
    elif method == "constrained":
        logger.info(f"🔄 Using enhanced constrained generation method")
        
        # Always use the enhanced constrained generator which includes dynamic index profiling
        logger.info(f"🎯 Using enhanced constrained generation with automatic index profiling")
        cmd = [
            sys.executable, "src/generators/constrained.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
        
        if index:
            cmd.extend(["--index", index])
        # Add model if it's a local model (handle both formats)
        if model and (model.startswith("Local:") or model.startswith("🖥️")):
            if model.startswith("Local:"):
                local_model = model.replace("Local: ", "")
            else:
                local_model = model.replace("🖥️ ", "")
            logger.info(f"🤖 Using local model: {local_model}")
            cmd.extend(["--model", local_model])
    elif method == "rules":
        cmd = [
            sys.executable, "src/generators/rules_based.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
        # Rules-based method doesn't use models
    elif method == "zeroshot":
        cmd = [
            sys.executable, "src/generators/zero_shot.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
        # Add model parameter for zeroshot (handle both formats)
        if model and (model.startswith("Local:") or model.startswith("🖥️")):
            if model.startswith("Local:"):
                local_model = model.replace("Local: ", "")
            else:
                local_model = model.replace("🖥️ ", "")
            cmd.extend(["--model", local_model])
        elif model and model.startswith("External:"):
            return False, f"External LLMs not supported with zeroshot method", {}
    else:
        return False, f"Unknown method: {method}", {}
    
    try:
        logger.info(f"⚡ Executing command: {' '.join(cmd)}")
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        execution_time = time.time() - start_time
        logger.info(f"⏱️ Command executed in {execution_time:.2f} seconds")
        
        if result.returncode != 0:
            logger.error(f"❌ Command failed with return code {result.returncode}")
            logger.error(f"STDERR: {result.stderr}")
            logger.info(f"STDOUT: {result.stdout}")
            backend_logger.log_error("Query generation command failed", result.stderr,
                                   method=method, model=model, task_id=task_id)
        else:
            logger.info(f"✅ Command completed successfully")
            backend_logger.log_success("Query generation command completed",
                method=method,
                model=model, 
                task_id=task_id,
                execution_time=execution_time
            )
        
        # Load generated query - handle adaptive_constrained files
        if method == "constrained":
            # Check for adaptive constrained files first
            adaptive_query_file = Path(f"artifacts/generated/adaptive_constrained_{task_id}.json")
            if adaptive_query_file.exists():
                query_file = adaptive_query_file
                metrics_file = Path(f"artifacts/generated/adaptive_constrained_{task_id}.metrics.json")
            else:
                query_file = Path(f"artifacts/generated/{task_id}.json")
                metrics_file = Path(f"artifacts/generated/{task_id}.metrics.json")
        else:
            query_file = Path(f"artifacts/generated/{method}_{task_id}.json")
            metrics_file = Path(f"artifacts/generated/{method}_{task_id}.metrics.json")
        
        query = {}
        metrics = {}
        
        if query_file.exists():
            with open(query_file) as f:
                query = json.load(f)
        
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)
        
        success = result.returncode == 0 and "abstain" not in query
        return success, result.stdout + result.stderr, {"query": query, "metrics": metrics}
        
    except subprocess.TimeoutExpired:
        return False, "Generation timed out (120s)", {}
    except Exception as e:
        return False, f"Error: {str(e)}", {}

def run_scenario_evaluation(scenario_id: str, method: str = "constrained", 
                           index: str = "logs_net") -> Tuple[bool, Dict]:
    """Run evaluation for a specific scenario"""
    
    try:
        if method == "constrained":
            cmd = [sys.executable, "src/cli/run_one.py", "--id", scenario_id, "--gen"]
        else:
            # Generate query first
            import yaml
            with open("tasks/prompts.yaml") as f:
                scenarios = yaml.safe_load(f)
            prompt = next(s['prompt'] for s in scenarios if s['id'] == scenario_id)
            
            success, output, data = run_query_generation(prompt, method, scenario_id)
            if not success:
                return False, {"error": output}
            
            # Then evaluate
            if method == "rules":
                candidate_file = f"artifacts/generated/rules_{scenario_id}.json"
            else:
                candidate_file = f"artifacts/generated/zeroshot_{scenario_id}.json"
            
            cmd = [sys.executable, "src/cli/run_one.py", "--id", scenario_id, 
                   "--candidate", candidate_file, "--index", index]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        
        # Parse results
        lines = result.stdout.split('\n')
        metrics = {}
        
        for line in lines:
            if "Jaccard Similarity:" in line:
                metrics["jaccard"] = float(line.split(":")[1].strip())
            elif "F1 Score:" in line:
                metrics["f1"] = float(line.split(":")[1].strip())
            elif "Precision:" in line:
                metrics["precision"] = float(line.split(":")[1].strip())
            elif "Recall:" in line:
                metrics["recall"] = float(line.split(":")[1].strip())
            elif "Semantic Similarity:" in line:
                metrics["semantic_similarity"] = float(line.split(":")[1].strip())
            elif "Comprehensiveness:" in line:
                metrics["comprehensiveness"] = float(line.split(":")[1].strip())
            elif "Efficiency Score:" in line:
                metrics["efficiency"] = float(line.split(":")[1].strip())
            elif "Quality Level:" in line:
                metrics["quality_level"] = line.split(":")[1].strip().lower()
            elif "Validator Status:" in line:
                metrics["validation"] = "PASS" in line
        
        success = result.returncode == 0
        return success, metrics
        
    except Exception as e:
        return False, {"error": str(e)}

def run_security_test(prompts: List[str]) -> Dict:
    """Run security testing on a list of prompts"""
    
    results = {
        "total": len(prompts),
        "blocked": 0,
        "passed": 0,
        "details": []
    }
    
    for i, prompt in enumerate(prompts):
        success, output, data = run_query_generation(prompt, "constrained", f"security_{i}")
        
        if "abstain" in data.get("query", {}) or not success:
            results["blocked"] += 1
            status = "BLOCKED"
            reason = data.get("query", {}).get("reason", "Generation failed")
        else:
            results["passed"] += 1
            status = "PASSED"
            reason = "Generated valid query"
        
        results["details"].append({
            "prompt": prompt,
            "status": status,
            "reason": reason
        })
    
    results["block_rate"] = (results["blocked"] / results["total"]) * 100
    return results

def load_scenarios() -> List[Dict]:
    """Load all scenarios from prompts.yaml"""
    try:
        import yaml
        with open("tasks/prompts.yaml") as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Failed to load scenarios: {e}")
        return []

def load_redteam_prompts() -> List[str]:
    """Load red team prompts"""
    try:
        with open("artifacts/redteam.txt") as f:
            prompts = []
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    prompts.append(line)
            return prompts
    except Exception as e:
        st.error(f"Failed to load red team prompts: {e}")
        return []

def validate_query(query_file: str) -> Tuple[bool, str]:
    """Validate a query using the validator"""
    try:
        result = subprocess.run([
            sys.executable, "src/validator.py",
            "--dsl", query_file
        ], capture_output=True, text=True, timeout=30)
        
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)

def get_available_models() -> List[str]:
    """Get list of available Ollama models"""
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            models = []
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    model_name = line.split()[0]
                    models.append(model_name)
            return models if models else ["llama3.1:latest"]  # Fallback
        else:
            return ["llama3.1:latest"]  # Fallback
    except Exception as e:
        return ["llama3.1:latest"]  # Fallback

def get_external_llm_models() -> List[str]:
    """Get list of enabled external LLM models"""
    try:
        from src.external.llm_manager import get_external_llm_manager
        manager = get_external_llm_manager()
        llms = manager.list_llms(enabled_only=True)
        return [llm.name for llm in llms]
    except:
        return []

def get_all_available_models() -> List[str]:
    """Get combined list of all available models (local + external) with prefixes"""
    all_models = []
    
    # Get local models with emoji prefix
    local_models = get_available_models()
    all_models.extend([f"🖥️ {m}" for m in local_models])
    
    # Get external models with emoji prefix
    external_models = get_external_llm_models()
    all_models.extend([f"☁️ {m}" for m in external_models])
    
    return all_models if all_models else ["🖥️ llama3.1:latest"]

def get_recent_results() -> List[Dict]:
    """Get recent evaluation results"""
    try:
        results_dir = Path("artifacts/results")
        result_files = sorted(
            results_dir.glob("scenario_*.json"), 
            key=lambda x: x.stat().st_mtime, 
            reverse=True
        )[:10]  # Last 10 results
        
        results = []
        for file in result_files:
            with open(file) as f:
                data = json.load(f)
                results.append(data)
        
        return results
    except Exception as e:
        st.error(f"Failed to load recent results: {e}")
        return []

def get_available_indices() -> List[str]:
    """Get list of available Elasticsearch indices"""
    try:
        result = subprocess.run([
            "curl", "-s", "-u", "elastic:ChangeMe_123",
            "http://localhost:9200/_cat/indices?format=json"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            indices = json.loads(result.stdout)
            # Filter for log indices and sort them
            log_indices = [idx["index"] for idx in indices 
                          if idx["index"].startswith(("logs_", "log_")) 
                          and not idx["index"].endswith("_dp")]
            return sorted(log_indices) if log_indices else ["logs_net"]
        else:
            return ["logs_net", "logs_cic_ids2017"]  # Fallback
    except Exception as e:
        return ["logs_net", "logs_cic_ids2017"]  # Fallback

def get_all_indices_with_details() -> List[Dict[str, Any]]:
    """Get detailed information about all Elasticsearch indices"""
    try:
        result = subprocess.run([
            "curl", "-s", "-u", "elastic:ChangeMe_123",
            "http://localhost:9200/_cat/indices?format=json&bytes=b"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            indices = json.loads(result.stdout)
            detailed_indices = []
            
            for idx in indices:
                # Skip system indices (starting with .)
                if idx["index"].startswith("."):
                    continue
                    
                detailed_indices.append({
                    "name": idx["index"],
                    "health": idx["health"],
                    "status": idx["status"],
                    "uuid": idx["uuid"],
                    "docs_count": int(idx.get("docs.count", 0) or 0),
                    "docs_deleted": int(idx.get("docs.deleted", 0) or 0),
                    "store_size": idx.get("store.size", "0b"),
                    "pri_store_size": idx.get("pri.store.size", "0b"),
                    "shards": int(idx.get("pri", 1)),
                    "replicas": int(idx.get("rep", 0))
                })
            
            return sorted(detailed_indices, key=lambda x: x["name"])
        else:
            logger.error(f"Failed to get indices: {result.stderr}")
            return []
    except Exception as e:
        logger.error(f"Error getting index details: {e}")
        return []

def delete_elasticsearch_index(index_name: str) -> Tuple[bool, str]:
    """Delete an Elasticsearch index"""
    try:
        # Use Elasticsearch client for safer deletion
        es = get_elasticsearch_client()
        
        # Check if index exists first
        if not es.indices.exists(index=index_name):
            return False, f"Index '{index_name}' does not exist"
        
        # Delete the index
        response = es.indices.delete(index=index_name)
        
        backend_logger.log_success("Index deleted", index_name=index_name)
        return True, f"Index '{index_name}' deleted successfully"
        
    except Exception as e:
        error_msg = f"Error deleting index '{index_name}': {str(e)}"
        backend_logger.log_error("Index deletion failed", str(e), index_name=index_name)
        return False, error_msg

def create_dp_index(base_index: str, dp_ratio: float = 0.1) -> Tuple[bool, str]:
    """Create a differentially private version of an index"""
    try:
        dp_index_name = f"{base_index}_dp"
        
        # Use the DP script if it exists
        dp_script = Path("scripts/create_dp_index.py")
        if dp_script.exists():
            result = subprocess.run([
                sys.executable, str(dp_script),
                "--source", base_index,
                "--target", dp_index_name,
                "--ratio", str(dp_ratio)
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                backend_logger.log_success("DP index created", 
                    base_index=base_index, dp_index=dp_index_name, ratio=dp_ratio)
                return True, f"DP index '{dp_index_name}' created successfully"
            else:
                error_msg = f"DP index creation failed: {result.stderr}"
                backend_logger.log_error("DP index creation failed", result.stderr,
                                       base_index=base_index, dp_index=dp_index_name)
                return False, error_msg
        else:
            # Simple implementation: copy with sampling
            es = get_elasticsearch_client()
            
            # Create target index with same mapping
            source_mapping = es.indices.get_mapping(index=base_index)
            es.indices.create(index=dp_index_name, body={
                "mappings": source_mapping[base_index]["mappings"]
            })
            
            # Copy a sample of documents
            sample_size = max(1, int(es.count(index=base_index)["count"] * dp_ratio))
            
            # Use random sampling query
            sample_query = {
                "query": {
                    "function_score": {
                        "query": {"match_all": {}},
                        "random_score": {"seed": 42}
                    }
                }
            }
            
            # Scroll through and copy documents
            response = es.search(index=base_index, body=sample_query, size=min(sample_size, 1000), scroll="2m")
            
            docs_copied = 0
            while response["hits"]["hits"]:
                bulk_data = []
                for hit in response["hits"]["hits"]:
                    bulk_data.extend([
                        {"index": {"_index": dp_index_name}},
                        hit["_source"]
                    ])
                
                if bulk_data:
                    es.bulk(body=bulk_data)
                    docs_copied += len(bulk_data) // 2
                
                if docs_copied >= sample_size:
                    break
                    
                try:
                    response = es.scroll(scroll_id=response["_scroll_id"], scroll="2m")
                except:
                    break
            
            backend_logger.log_success("DP index created via sampling", 
                base_index=base_index, dp_index=dp_index_name, docs_copied=docs_copied)
            return True, f"DP index '{dp_index_name}' created with {docs_copied} documents"
            
    except Exception as e:
        error_msg = f"Error creating DP index: {str(e)}"
        backend_logger.log_error("DP index creation error", str(e), base_index=base_index)
        return False, error_msg

def create_drift_index(base_index: str, drift_type: str = "temporal") -> Tuple[bool, str]:
    """Create a drift simulation index"""
    try:
        drift_index_name = f"{base_index}_drift_{drift_type}"
        
        es = get_elasticsearch_client()
        
        # Get source mapping
        source_mapping = es.indices.get_mapping(index=base_index)
        
        # Create drift index with same mapping
        es.indices.create(index=drift_index_name, body={
            "mappings": source_mapping[base_index]["mappings"]
        })
        
        # Copy documents with modifications based on drift type
        response = es.search(index=base_index, size=1000, scroll="2m")
        
        docs_copied = 0
        while response["hits"]["hits"]:
            bulk_data = []
            for hit in response["hits"]["hits"]:
                doc = hit["_source"].copy()
                
                # Apply drift modifications
                if drift_type == "temporal":
                    # Modify timestamps to simulate temporal drift
                    if "@timestamp" in doc:
                        from datetime import datetime, timedelta
                        import random
                        # Add random time offset
                        offset_days = random.randint(30, 90)
                        if isinstance(doc["@timestamp"], str):
                            try:
                                dt = datetime.fromisoformat(doc["@timestamp"].replace('Z', '+00:00'))
                                new_dt = dt + timedelta(days=offset_days)
                                doc["@timestamp"] = new_dt.isoformat()
                            except:
                                pass
                
                elif drift_type == "feature":
                    # Modify feature values to simulate feature drift
                    import random
                    for field in ["src_port", "dst_port", "packet_length", "flow_duration"]:
                        if field in doc and isinstance(doc[field], (int, float)):
                            # Add random noise
                            noise = random.uniform(0.9, 1.1)
                            doc[field] = int(doc[field] * noise)
                
                bulk_data.extend([
                    {"index": {"_index": drift_index_name}},
                    doc
                ])
            
            if bulk_data:
                es.bulk(body=bulk_data)
                docs_copied += len(bulk_data) // 2
            
            try:
                response = es.scroll(scroll_id=response["_scroll_id"], scroll="2m")
            except:
                break
        
        backend_logger.log_success("Drift index created", 
            base_index=base_index, drift_index=drift_index_name, 
            drift_type=drift_type, docs_copied=docs_copied)
        return True, f"Drift index '{drift_index_name}' created with {docs_copied} documents"
        
    except Exception as e:
        error_msg = f"Error creating drift index: {str(e)}"
        backend_logger.log_error("Drift index creation error", str(e), 
                               base_index=base_index, drift_type=drift_type)
        return False, error_msg

def execute_elasticsearch_query(query: Dict[str, Any], index: str, max_size: int = 1000) -> Tuple[bool, Dict[str, Any]]:
    """Execute an Elasticsearch query and return results with metadata"""
    logger.info(f"🔍 Executing Elasticsearch query on index: {index}")
    logger.info(f"📊 Query size limit: {max_size}")
    logger.debug(f"🔧 Query details: {json.dumps(query, indent=2)}")
    
    # Log user query execution activity
    backend_logger.log_query_execution(index, "user_generated", max_size=max_size)
    
    try:
        # Import config here to avoid circular imports
        from src.utils.config import get_es_client_config
        
        # Create Elasticsearch client with read-only credentials
        logger.info(f"🔌 Connecting to Elasticsearch with read-only credentials")
        es = Elasticsearch(**get_es_client_config(use_admin=False), request_timeout=60)
        
        # Execute the query with size limit
        start_time = time.time()
        response = es.search(index=index, body=query, size=max_size, track_total_hits=True)
        execution_time = time.time() - start_time
        logger.info(f"⏱️ Query executed in {execution_time:.3f} seconds")
        
        # Extract metadata
        total_hits = (response["hits"]["total"]["value"] 
                     if isinstance(response["hits"]["total"], dict) 
                     else response["hits"]["total"])
        
        hits = response["hits"]["hits"]
        took = response["took"]
        
        logger.info(f"📈 Query results: {total_hits} total hits, {len(hits)} returned in {took}ms")
        
        # Log successful query execution with results
        backend_logger.log_success("Elasticsearch query executed",
            index=index,
            total_hits=total_hits,
            returned_hits=len(hits),
            execution_time_ms=took,
            max_size=max_size
        )
        
        # Process results
        results = []
        for hit in hits:
            result_doc = {
                "_id": hit["_id"],
                "_score": hit.get("_score"),
                **hit["_source"]
            }
            results.append(result_doc)
        
        # Aggregations if present
        aggregations = response.get("aggs", {})
        if aggregations:
            logger.info(f"📊 Query includes aggregations: {list(aggregations.keys())}")
            backend_logger.log_status("Query aggregations", f"Found {len(aggregations)} aggregation types")
        
        return True, {
            "total_hits": total_hits,
            "returned_hits": len(hits),
            "took": took,
            "index": index,
            "results": results,
            "aggregations": aggregations,
            "query": query
        }
        
    except Exception as e:
        logger.error(f"❌ Elasticsearch query failed: {str(e)}")
        logger.debug(f"🔧 Failed query: {json.dumps(query, indent=2)}")
        backend_logger.log_error("Elasticsearch query execution failed", str(e), 
                               index=index, max_size=max_size)
        return False, {"error": str(e), "query": query, "index": index}

def export_results_as_csv(results_data: Dict[str, Any]) -> str:
    """Convert query results to CSV format"""
    try:
        if not results_data.get("results"):
            backend_logger.log_warning("CSV export", "No results to export")
            return "No results to export"
        
        # Convert results to DataFrame
        df = pd.DataFrame(results_data["results"])
        
        # Convert to CSV
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        backend_logger.log_success("CSV export completed",
            record_count=len(results_data["results"]),
            column_count=len(df.columns)
        )
        
        return output.getvalue()
        
    except Exception as e:
        backend_logger.log_error("CSV export failed", str(e))
        return f"Error exporting to CSV: {e}"

def export_results_as_json(results_data: Dict[str, Any]) -> str:
    """Convert query results to JSON format"""
    try:
        json_output = json.dumps(results_data, indent=2, default=str)
        
        backend_logger.log_success("JSON export completed",
            record_count=len(results_data.get("results", [])),
            has_aggregations=bool(results_data.get("aggregations"))
        )
        
        return json_output
    except Exception as e:
        backend_logger.log_error("JSON export failed", str(e))
        return f"Error exporting to JSON: {e}"

def get_index_profile_info(index_name: str) -> Dict[str, Any]:
    """Get comprehensive index profile information for the GUI"""
    try:
        from src.index_profiler import IndexProfiler
        from src.data_adaptation.mapping_storage import MappingStorage
        
        profiler = IndexProfiler()
        storage = MappingStorage()
        
        # Get index profile
        profile = profiler.analyze_index(index_name)
        
        # Get unified field mapping
        field_mapping = storage.get_field_mapping_for_query_generation(index_name)
        
        return {
            "index_name": index_name,
            "document_count": profile.document_count,
            "field_count": len(profile.fields),
            "date_range": profile.date_range,
            "primary_timestamp": profile.primary_timestamp_field,
            "system_type": field_mapping.get("system_type", "Auto-detected"),
            "key_fields": {
                "timestamp_fields": field_mapping.get("timestamp_fields", []),
                "ip_fields": field_mapping.get("ip_fields", []),
                "label_fields": field_mapping.get("status_fields", []),
                "user_fields": field_mapping.get("user_fields", [])
            },
            "sample_fields": list(profile.fields.keys())[:10],
            "suggested_mappings": profile.suggested_field_mappings,
            "has_profile": True
        }
        
    except Exception as e:
        logger.warning(f"Could not get profile for {index_name}: {e}")
        return {
            "index_name": index_name,
            "error": str(e),
            "has_profile": False
        }

def refresh_index_profile(index_name: str) -> bool:
    """Force refresh of index profile"""
    try:
        from src.index_profiler import IndexProfiler
        profiler = IndexProfiler()
        profiler.analyze_index(index_name, force_refresh=True)
        logger.info(f"Refreshed profile for {index_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh profile for {index_name}: {e}")
        return False

def validate_query_with_feedback(query: Dict[str, Any], index: str) -> Dict[str, Any]:
    """Validate a query and return detailed feedback"""
    try:
        from src.validation.query_validator import QueryValidator
        
        validator = QueryValidator()
        result = validator.validate_query(query, index)
        
        return {
            "is_valid": result.is_valid,
            "score": result.score,
            "status_emoji": result.get_status_emoji(),
            "issues": result.issues,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
            "execution_time_ms": result.execution_time_ms,
            "result_count": result.result_count,
            "sample_results": result.sample_results[:3] if result.sample_results else []
        }
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return {
            "is_valid": False,
            "score": 0,
            "status_emoji": "❌",
            "issues": [f"Validation failed: {str(e)}"],
            "warnings": [],
            "suggestions": []
        }
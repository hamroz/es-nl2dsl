"""Backend interface utilities for GUI integration"""
import subprocess
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import streamlit as st

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def check_system_status() -> Dict[str, any]:
    """Check the status of all system components"""
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
    except:
        status["elasticsearch"] = False
    
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
    except:
        status["ollama"] = False
    
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
        except:
            pass
    
    return status

def run_query_generation(prompt: str, method: str = "constrained", 
                        task_id: Optional[str] = None) -> Tuple[bool, str, Dict]:
    """Run query generation with specified method"""
    
    if not task_id:
        task_id = f"gui_{int(time.time())}"
    
    if method == "constrained":
        cmd = [
            sys.executable, "src/generate_constrained.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
    elif method == "rules":
        cmd = [
            sys.executable, "src/baseline_rules.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
    elif method == "zeroshot":
        cmd = [
            sys.executable, "src/baseline_zeroshot.py",
            "--prompt", prompt,
            "--task-id", task_id
        ]
    else:
        return False, f"Unknown method: {method}", {}
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        # Load generated query
        if method == "constrained":
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
            cmd = [sys.executable, "src/run_one.py", "--id", scenario_id, "--gen"]
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
            
            cmd = [sys.executable, "src/run_one.py", "--id", scenario_id, 
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
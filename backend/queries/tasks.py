from celery import shared_task
from django.utils import timezone
from django.conf import settings
import json
import subprocess
import sys
import time
from pathlib import Path
import requests

@shared_task(bind=True, max_retries=2)
def generate_query_task(self, task_id: str, prompt: str, method: str, 
                       index: str = None, model: str = None):
    """
    Async query generation task - calls actual generation scripts
    """
    from .models import QueryTask, GeneratedQuery
    
    try:
        # Update task status to running
        task = QueryTask.objects.get(task_id=task_id)
        task.status = 'running'
        task.save()
        
        # Determine paths relative to project root
        project_root = settings.BASE_DIR.parent
        artifacts_path = project_root / "artifacts" / "generated"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        # Build command based on method
        start_time = time.time()
        
        if method == 'constrained':
            cmd = [
                sys.executable, 
                str(project_root / "src" / "generate_constrained.py"),
                "--prompt", prompt,
                "--task-id", task_id,
                "--output-dir", str(artifacts_path),
                "--model", model or "llama3.1:latest"
            ]
            if index:
                cmd.extend(["--index", index])
                
        elif method == 'rules':
            cmd = [
                sys.executable,
                str(project_root / "src" / "baseline_rules.py"),
                "--prompt", prompt,
                "--task-id", task_id,
                "--output-dir", str(artifacts_path)
            ]
            
        elif method == 'zeroshot':
            cmd = [
                sys.executable,
                str(project_root / "src" / "baseline_zeroshot.py"),
                "--prompt", prompt,
                "--task-id", task_id,
                "--output-dir", str(artifacts_path),
                "--model", model or "llama3.1:latest"
            ]
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Execute the generation command
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=120,
            cwd=str(project_root)
        )
        
        generation_time = time.time() - start_time
        
        if result.returncode != 0:
            raise RuntimeError(f"Generation failed: {result.stderr}")
        
        # Load generated files
        query_file = artifacts_path / f"{task_id}.json"
        metrics_file = artifacts_path / f"{task_id}.metrics.json"
        
        if not query_file.exists():
            raise FileNotFoundError(f"Generated query file not found: {query_file}")
        
        with open(query_file) as f:
            query_data = json.load(f)
        
        # Load or create metrics
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics_data = json.load(f)
        else:
            metrics_data = {
                "generation_time": generation_time,
                "retry_count": self.request.retries,
                "method": method,
                "model": model or "llama3.1:latest"
            }
        
        # Run validation using existing validator
        validation_result = run_validation(str(query_file), project_root)
        
        # Create GeneratedQuery record
        GeneratedQuery.objects.create(
            task=task,
            elasticsearch_dsl=query_data,
            validation_status='PASS' if validation_result['valid'] else 'FAIL',
            validation_errors=validation_result.get('errors', []),
            generation_metrics=metrics_data,
            retry_count=self.request.retries,
            file_path=str(query_file)
        )
        
        # Update task status
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'query_file': str(query_file),
            'metrics_file': str(metrics_file)
        }
        
    except Exception as e:
        # Update task with error
        try:
            task = QueryTask.objects.get(task_id=task_id)
            task.error_message = str(e)
            if self.request.retries >= self.max_retries:
                task.status = 'failed'
            task.save()
        except:
            pass
        
        # Retry logic
        if self.request.retries < self.max_retries:
            self.retry(countdown=60, exc=e)
        else:
            return {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }

def run_validation(query_file_path, project_root):
    """
    Run validation using the existing validator script
    """
    try:
        cmd = [
            sys.executable,
            str(project_root / "src" / "validator.py"),
            "--dsl", query_file_path,
            "--rules", str(project_root / "artifacts" / "validator_rules.yaml")
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            return {'valid': True, 'errors': []}
        else:
            # Parse validation errors from stderr
            errors = result.stderr.strip().split('\n') if result.stderr else ['Validation failed']
            return {'valid': False, 'errors': errors}
            
    except Exception as e:
        return {'valid': False, 'errors': [f'Validation error: {str(e)}']}

@shared_task
def execute_query_task(task_id: str, query_data: dict, index: str, max_size: int = 1000):
    """
    Execute query against Elasticsearch and store results
    """
    from .models import QueryTask, QueryExecution
    import csv
    import io
    
    try:
        task = QueryTask.objects.get(task_id=task_id)
        
        # Prepare Elasticsearch query
        es_query = {
            "size": max_size,
            **query_data
        }
        
        # Execute query against Elasticsearch
        es_url = f"http://{settings.ELASTICSEARCH_HOST}/{index}/_search"
        auth = (settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD)
        
        start_time = time.time()
        response = requests.post(
            es_url,
            json=es_query,
            auth=auth,
            timeout=30,
            headers={'Content-Type': 'application/json'}
        )
        execution_time = int((time.time() - start_time) * 1000)
        
        if response.status_code != 200:
            raise RuntimeError(f"Elasticsearch error: {response.text}")
        
        es_result = response.json()
        
        # Extract results
        hits = es_result.get('hits', {})
        total_hits = hits.get('total', {}).get('value', 0)
        documents = hits.get('hits', [])
        returned_hits = len(documents)
        aggregations = es_result.get('aggregations', {})
        
        # Process documents - extract _source and flatten
        processed_results = []
        for doc in documents:
            source = doc.get('_source', {})
            source['_id'] = doc.get('_id')
            source['_score'] = doc.get('_score')
            processed_results.append(source)
        
        # Generate export files
        artifacts_path = settings.ARTIFACTS_PATH / "exports"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        
        # Export as CSV
        csv_path = artifacts_path / f"{task_id}_results.csv"
        if processed_results:
            fieldnames = set()
            for result in processed_results:
                fieldnames.update(result.keys())
            fieldnames = sorted(list(fieldnames))
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for result in processed_results:
                    writer.writerow(result)
        else:
            # Create empty CSV with headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['No results found'])
        
        # Export as JSON
        json_path = artifacts_path / f"{task_id}_results.json"
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump({
                'total_hits': total_hits,
                'returned_hits': returned_hits,
                'execution_time_ms': execution_time,
                'results': processed_results,
                'aggregations': aggregations
            }, jsonfile, indent=2, default=str)
        
        # Create QueryExecution record
        execution = QueryExecution.objects.create(
            task=task,
            total_hits=total_hits,
            returned_hits=returned_hits,
            execution_time_ms=execution_time,
            max_size=max_size,
            results=processed_results,
            aggregations=aggregations,
            export_csv_path=str(csv_path),
            export_json_path=str(json_path)
        )
        
        return {
            'task_id': task_id,
            'total_hits': total_hits,
            'returned_hits': returned_hits,
            'took': execution_time,
            'results': processed_results,
            'aggregations': aggregations,
            'export_urls': {
                'csv': f'/api/v1/queries/{task_id}/export/csv/',
                'json': f'/api/v1/queries/{task_id}/export/json/'
            }
        }
        
    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'failed',
            'error': str(e)
        }
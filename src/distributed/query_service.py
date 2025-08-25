#!/usr/bin/env python3
"""Distributed query generation service with load balancing"""
import asyncio
import aiohttp
import time
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

class ServiceStatus(Enum):
    """Service status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"

class WorkerType(Enum):
    """Worker type enumeration"""
    OLLAMA = "ollama"
    EXTERNAL_API = "external_api"
    HYBRID = "hybrid"

@dataclass
class WorkerNode:
    """Represents a worker node in the distributed system"""
    node_id: str
    worker_type: WorkerType
    endpoint: str
    status: ServiceStatus
    current_load: int
    max_capacity: int
    avg_response_time: float
    total_requests: int
    successful_requests: int
    last_heartbeat: float
    models: List[str]
    
    @property
    def load_percentage(self) -> float:
        """Calculate current load percentage"""
        return (self.current_load / self.max_capacity) * 100 if self.max_capacity > 0 else 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        return (self.successful_requests / self.total_requests) * 100 if self.total_requests > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class QueryRequest:
    """Query generation request"""
    request_id: str
    prompt: str
    task_id: str
    model: str
    method: str
    timeout: int
    priority: int
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class QueryResponse:
    """Query generation response"""
    request_id: str
    success: bool
    query: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time: float
    worker_id: str
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class LoadBalancer:
    """Intelligent load balancer for query generation workers"""
    
    def __init__(self):
        self.workers: Dict[str, WorkerNode] = {}
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.response_cache: Dict[str, QueryResponse] = {}
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.max_cache_size = 1000
        
        # Performance tracking
        self.total_requests = 0
        self.total_response_time = 0.0
        self.request_history: List[Dict[str, Any]] = []
        
        # Logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
    
    def register_worker(self, worker: WorkerNode) -> bool:
        """Register a new worker node"""
        self.workers[worker.node_id] = worker
        self.logger.info(f"Registered worker {worker.node_id} ({worker.worker_type.value})")
        return True
    
    def unregister_worker(self, node_id: str) -> bool:
        """Unregister a worker node"""
        if node_id in self.workers:
            del self.workers[node_id]
            self.logger.info(f"Unregistered worker {node_id}")
            return True
        return False
    
    def get_optimal_worker(self, request: QueryRequest) -> Optional[WorkerNode]:
        """Select optimal worker based on load, performance, and model availability"""
        available_workers = []
        
        # Filter workers by model availability and health
        for worker in self.workers.values():
            if (worker.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED] and
                worker.current_load < worker.max_capacity and
                (not request.model or request.model in worker.models)):
                available_workers.append(worker)
        
        if not available_workers:
            return None
        
        # Score workers based on multiple criteria
        def score_worker(worker: WorkerNode) -> float:
            # Load factor (lower is better)
            load_factor = 1.0 - (worker.load_percentage / 100)
            
            # Performance factor (faster is better)
            if worker.avg_response_time > 0:
                perf_factor = 1.0 / (1.0 + worker.avg_response_time / 1000)  # Normalize to seconds
            else:
                perf_factor = 1.0
            
            # Success rate factor
            success_factor = worker.success_rate / 100
            
            # Health factor
            health_factor = 1.0 if worker.status == ServiceStatus.HEALTHY else 0.5
            
            # Weighted score
            score = (0.4 * load_factor + 
                    0.3 * perf_factor + 
                    0.2 * success_factor + 
                    0.1 * health_factor)
            
            return score
        
        # Select worker with highest score
        best_worker = max(available_workers, key=score_worker)
        return best_worker
    
    def generate_cache_key(self, request: QueryRequest) -> str:
        """Generate cache key for request"""
        # Cache based on prompt, model, and method
        key_components = [request.prompt, request.model, request.method]
        key_string = "|".join(key_components)
        return f"query_cache_{hash(key_string) % 1000000}"
    
    def get_cached_response(self, request: QueryRequest) -> Optional[QueryResponse]:
        """Get cached response if available and valid"""
        cache_key = self.generate_cache_key(request)
        
        if cache_key in self.response_cache:
            cached_response = self.response_cache[cache_key]
            
            # Check if cache is still valid
            cache_age = time.time() - cached_response.metrics.get("cache_timestamp", 0)
            if cache_age < self.cache_ttl:
                self.logger.info(f"Cache hit for request {request.request_id}")
                return cached_response
            else:
                # Remove expired cache entry
                del self.response_cache[cache_key]
        
        return None
    
    def cache_response(self, request: QueryRequest, response: QueryResponse):
        """Cache successful response"""
        if response.success:
            cache_key = self.generate_cache_key(request)
            
            # Add cache metadata
            response.metrics["cache_timestamp"] = time.time()
            response.metrics["cached"] = True
            
            # Implement LRU eviction if cache is full
            if len(self.response_cache) >= self.max_cache_size:
                # Remove oldest entry (simple approach - could be optimized)
                oldest_key = min(self.response_cache.keys(), 
                               key=lambda k: self.response_cache[k].metrics.get("cache_timestamp", 0))
                del self.response_cache[oldest_key]
            
            self.response_cache[cache_key] = response
            self.logger.info(f"Cached response for request {request.request_id}")
    
    async def process_request(self, request: QueryRequest) -> QueryResponse:
        """Process a query generation request"""
        start_time = time.time()
        
        # Check cache first
        cached_response = self.get_cached_response(request)
        if cached_response:
            # Update metrics for cache hit
            cached_response.request_id = request.request_id
            cached_response.metrics["cache_hit"] = True
            return cached_response
        
        # Select optimal worker
        worker = self.get_optimal_worker(request)
        if not worker:
            return QueryResponse(
                request_id=request.request_id,
                success=False,
                query=None,
                error="No available workers",
                execution_time=time.time() - start_time,
                worker_id="none",
                metrics={"error_type": "no_workers_available"}
            )
        
        # Update worker load
        worker.current_load += 1
        
        try:
            # Execute query generation
            response = await self._execute_on_worker(worker, request)
            
            # Update worker statistics
            worker.total_requests += 1
            if response.success:
                worker.successful_requests += 1
            
            # Update average response time
            if worker.total_requests > 0:
                worker.avg_response_time = (
                    (worker.avg_response_time * (worker.total_requests - 1) + response.execution_time) 
                    / worker.total_requests
                )
            
            # Cache successful responses
            if response.success:
                self.cache_response(request, response)
            
            # Update global statistics
            self.total_requests += 1
            self.total_response_time += response.execution_time
            
            # Log request for analysis
            self.request_history.append({
                "timestamp": start_time,
                "request_id": request.request_id,
                "worker_id": worker.node_id,
                "execution_time": response.execution_time,
                "success": response.success,
                "cached": False
            })
            
            # Trim history to last 1000 requests
            if len(self.request_history) > 1000:
                self.request_history = self.request_history[-1000:]
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error processing request {request.request_id}: {e}")
            return QueryResponse(
                request_id=request.request_id,
                success=False,
                query=None,
                error=str(e),
                execution_time=time.time() - start_time,
                worker_id=worker.node_id,
                metrics={"error_type": "execution_error"}
            )
        finally:
            # Always decrease worker load
            worker.current_load = max(0, worker.current_load - 1)
    
    async def _execute_on_worker(self, worker: WorkerNode, request: QueryRequest) -> QueryResponse:
        """Execute query generation on a specific worker"""
        start_time = time.time()
        
        if worker.worker_type == WorkerType.OLLAMA:
            return await self._execute_ollama_worker(worker, request, start_time)
        elif worker.worker_type == WorkerType.EXTERNAL_API:
            return await self._execute_external_worker(worker, request, start_time)
        else:
            raise ValueError(f"Unsupported worker type: {worker.worker_type}")
    
    async def _execute_ollama_worker(self, worker: WorkerNode, request: QueryRequest, start_time: float) -> QueryResponse:
        """Execute on Ollama worker"""
        try:
            # Use subprocess to call the existing generation code
            cmd = [
                sys.executable, "src/generators/constrained.py",
                "--prompt", request.prompt,
                "--task-id", request.task_id,
                "--model", request.model
            ]
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor, 
                    lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=request.timeout)
                )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                # Load generated query
                query_file = Path(f"artifacts/generated/{request.task_id}.json")
                if query_file.exists():
                    with open(query_file) as f:
                        query = json.load(f)
                    
                    return QueryResponse(
                        request_id=request.request_id,
                        success=True,
                        query=query,
                        error=None,
                        execution_time=execution_time * 1000,  # Convert to ms
                        worker_id=worker.node_id,
                        metrics={
                            "worker_type": "ollama",
                            "model": request.model,
                            "stdout_length": len(result.stdout)
                        }
                    )
                else:
                    return QueryResponse(
                        request_id=request.request_id,
                        success=False,
                        query=None,
                        error="Query file not found",
                        execution_time=execution_time * 1000,
                        worker_id=worker.node_id,
                        metrics={"error_type": "file_not_found"}
                    )
            else:
                return QueryResponse(
                    request_id=request.request_id,
                    success=False,
                    query=None,
                    error=result.stderr,
                    execution_time=execution_time * 1000,
                    worker_id=worker.node_id,
                    metrics={"error_type": "generation_failed", "return_code": result.returncode}
                )
                
        except asyncio.TimeoutError:
            return QueryResponse(
                request_id=request.request_id,
                success=False,
                query=None,
                error="Timeout",
                execution_time=request.timeout * 1000,
                worker_id=worker.node_id,
                metrics={"error_type": "timeout"}
            )
        except Exception as e:
            return QueryResponse(
                request_id=request.request_id,
                success=False,
                query=None,
                error=str(e),
                execution_time=(time.time() - start_time) * 1000,
                worker_id=worker.node_id,
                metrics={"error_type": "exception"}
            )
    
    async def _execute_external_worker(self, worker: WorkerNode, request: QueryRequest, start_time: float) -> QueryResponse:
        """Execute on external API worker"""
        # Placeholder for external API integration
        # This would integrate with OpenAI, Anthropic, etc.
        
        execution_time = time.time() - start_time
        return QueryResponse(
            request_id=request.request_id,
            success=False,
            query=None,
            error="External API workers not implemented yet",
            execution_time=execution_time * 1000,
            worker_id=worker.node_id,
            metrics={"error_type": "not_implemented"}
        )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        healthy_workers = [w for w in self.workers.values() if w.status == ServiceStatus.HEALTHY]
        degraded_workers = [w for w in self.workers.values() if w.status == ServiceStatus.DEGRADED]
        unhealthy_workers = [w for w in self.workers.values() if w.status in [ServiceStatus.UNHEALTHY, ServiceStatus.OFFLINE]]
        
        # Calculate cache statistics
        cache_hits = sum(1 for entry in self.request_history if entry.get("cached", False))
        cache_hit_rate = (cache_hits / len(self.request_history)) * 100 if self.request_history else 0
        
        # Calculate average response time
        if self.request_history:
            avg_response_time = sum(r["execution_time"] for r in self.request_history) / len(self.request_history)
        else:
            avg_response_time = 0
        
        # Calculate success rate
        successful_requests = sum(1 for r in self.request_history if r["success"])
        success_rate = (successful_requests / len(self.request_history)) * 100 if self.request_history else 0
        
        return {
            "workers": {
                "total": len(self.workers),
                "healthy": len(healthy_workers),
                "degraded": len(degraded_workers),
                "unhealthy": len(unhealthy_workers),
                "total_capacity": sum(w.max_capacity for w in self.workers.values()),
                "current_load": sum(w.current_load for w in self.workers.values())
            },
            "requests": {
                "total": len(self.request_history),
                "successful": successful_requests,
                "success_rate": success_rate,
                "avg_response_time_ms": avg_response_time
            },
            "cache": {
                "size": len(self.response_cache),
                "max_size": self.max_cache_size,
                "hit_rate": cache_hit_rate,
                "ttl_seconds": self.cache_ttl
            },
            "load_distribution": [
                {
                    "worker_id": w.node_id,
                    "load_percentage": w.load_percentage,
                    "avg_response_time": w.avg_response_time,
                    "success_rate": w.success_rate
                }
                for w in self.workers.values()
            ]
        }

class DistributedQueryService:
    """Main distributed query service"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.load_balancer = LoadBalancer()
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        
        # Initialize workers based on config
        self._initialize_workers()
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for distributed service"""
        return {
            "workers": [
                {
                    "node_id": "local_ollama_1",
                    "worker_type": "ollama",
                    "endpoint": "http://localhost:11434",
                    "max_capacity": 4,
                    "models": ["llama3.1:latest", "deepseek-r1:14b"]
                }
            ],
            "cache": {
                "enabled": True,
                "ttl_seconds": 3600,
                "max_size": 1000
            },
            "performance": {
                "request_timeout": 120,
                "max_concurrent_requests": 10
            }
        }
    
    def _initialize_workers(self):
        """Initialize workers from configuration"""
        for worker_config in self.config.get("workers", []):
            worker = WorkerNode(
                node_id=worker_config["node_id"],
                worker_type=WorkerType(worker_config["worker_type"]),
                endpoint=worker_config["endpoint"],
                status=ServiceStatus.HEALTHY,
                current_load=0,
                max_capacity=worker_config["max_capacity"],
                avg_response_time=0.0,
                total_requests=0,
                successful_requests=0,
                last_heartbeat=time.time(),
                models=worker_config["models"]
            )
            self.load_balancer.register_worker(worker)
    
    async def generate_query(self, prompt: str, model: str = "llama3.1:latest", 
                           method: str = "constrained", task_id: Optional[str] = None) -> QueryResponse:
        """Generate query using distributed workers"""
        
        if not task_id:
            task_id = f"distributed_{uuid.uuid4().hex[:8]}"
        
        request = QueryRequest(
            request_id=str(uuid.uuid4()),
            prompt=prompt,
            task_id=task_id,
            model=model,
            method=method,
            timeout=self.config["performance"]["request_timeout"],
            priority=1,
            timestamp=time.time()
        )
        
        response = await self.load_balancer.process_request(request)
        return response
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status and metrics"""
        metrics = self.load_balancer.get_performance_metrics()
        
        return {
            "service": {
                "running": self.is_running,
                "uptime": time.time() - getattr(self, 'start_time', time.time()),
                "version": "1.0.0"
            },
            "performance": metrics
        }

# Convenience functions for integration

async def create_distributed_service(config_file: Optional[str] = None) -> DistributedQueryService:
    """Create and configure distributed query service"""
    config = None
    if config_file and Path(config_file).exists():
        with open(config_file) as f:
            config = json.load(f)
    
    service = DistributedQueryService(config)
    service.is_running = True
    service.start_time = time.time()
    
    return service

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Distributed Query Generation Service")
    parser.add_argument("--config", help="Configuration file")
    parser.add_argument("--prompt", help="Test prompt")
    parser.add_argument("--model", default="llama3.1:latest", help="Model to use")
    
    args = parser.parse_args()
    
    async def main():
        service = await create_distributed_service(args.config)
        
        if args.prompt:
            print("Testing distributed query generation...")
            response = await service.generate_query(args.prompt, args.model)
            
            print(f"Request ID: {response.request_id}")
            print(f"Success: {response.success}")
            print(f"Execution Time: {response.execution_time:.1f}ms")
            print(f"Worker: {response.worker_id}")
            
            if response.success:
                print("Generated Query:")
                print(json.dumps(response.query, indent=2))
            else:
                print(f"Error: {response.error}")
        
        # Print service status
        status = service.get_status()
        print("\nService Status:")
        print(json.dumps(status, indent=2))
    
    asyncio.run(main())

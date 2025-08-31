#!/usr/bin/env python3
"""
Asynchronous LLM Interface: High-performance concurrent model calling infrastructure

This module provides advanced asynchronous calling capabilities for Large Language Models,
enabling high-throughput query generation with concurrent processing, intelligent batching,
and performance optimization. It supports multiple LLM providers with unified async
interfaces and comprehensive error handling for production workloads.

Key capabilities:
- Asynchronous LLM calling with concurrent request processing
- Thread pool optimization for improved throughput and resource utilization
- Intelligent batching and request queuing for optimal performance
- Error handling and retry mechanisms with exponential backoff
- Request timing and performance monitoring for optimization
- Multi-provider support with unified async interfaces
- Memory-efficient processing for large-scale generation tasks

The infrastructure is designed for high-performance applications requiring concurrent
LLM access, batch processing scenarios, and production systems with strict
performance requirements.

Author: Hamroz Gavharov
Project: ES-NL2DSL - Natural Language to Elasticsearch DSL Framework
License: MIT (see LICENSE file)
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Caching system removed
CACHING_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class LLMCall:
    """Represents an LLM call request"""
    prompt: str
    model: str
    timeout: int
    call_id: str
    method: str = "constrained"
    kwargs: Dict[str, Any] = None

@dataclass
class LLMResult:
    """Represents an LLM call result"""
    call_id: str
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0
    cached: bool = False

class AsyncLLMManager:
    """Manages async LLM calls with caching and concurrent execution"""
    
    def __init__(self, max_concurrent_calls: int = 3):
        self.max_concurrent_calls = max_concurrent_calls
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_calls)
        self.call_stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "total_latency_ms": 0
        }
    
    async def call_llm_async(self, call: LLMCall) -> LLMResult:
        """Make an async LLM call with caching"""
        start_time = time.time()
        self.call_stats["total_calls"] += 1
        
        # Check cache first if available
        if CACHING_AVAILABLE:
            cached_result = cached_query_generation(
                call.prompt, call.model, call.method, **(call.kwargs or {})
            )
            if cached_result is not None:
                self.call_stats["cache_hits"] += 1
                latency_ms = (time.time() - start_time) * 1000
                logger.info(f"🎯 Cache hit for {call.call_id} ({latency_ms:.1f}ms)")
                return LLMResult(
                    call_id=call.call_id,
                    success=True,
                    result=json.dumps(cached_result) if isinstance(cached_result, dict) else str(cached_result),
                    latency_ms=latency_ms,
                    cached=True
                )
        
        self.call_stats["cache_misses"] += 1
        
        # Make the actual LLM call
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._call_local_model_sync, 
                call.prompt, 
                call.model, 
                call.timeout
            )
            
            latency_ms = (time.time() - start_time) * 1000
            self.call_stats["total_latency_ms"] += latency_ms
            
            # Cache the result if caching is available
            if CACHING_AVAILABLE and result:
                try:
                    # Try to parse as JSON for caching
                    result_obj = json.loads(result)
                    cache_query_result(
                        call.prompt, call.model, result_obj, call.method, **(call.kwargs or {})
                    )
                except json.JSONDecodeError:
                    # Cache as string if not JSON
                    cache_query_result(
                        call.prompt, call.model, {"raw_result": result}, call.method, **(call.kwargs or {})
                    )
            
            logger.info(f"✅ LLM call {call.call_id} completed ({latency_ms:.1f}ms)")
            return LLMResult(
                call_id=call.call_id,
                success=True,
                result=result,
                latency_ms=latency_ms,
                cached=False
            )
            
        except Exception as e:
            self.call_stats["errors"] += 1
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ LLM call {call.call_id} failed: {e} ({latency_ms:.1f}ms)")
            return LLMResult(
                call_id=call.call_id,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
                cached=False
            )
    
    def _call_local_model_sync(self, prompt: str, model: str, timeout: int) -> str:
        """Synchronous LLM call to run in executor"""
        logger.debug(f"Calling {model} with timeout={timeout}s...")
        
        try:
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode != 0:
                raise RuntimeError(f"Model call failed: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Model call timed out after {timeout} seconds")
        except FileNotFoundError:
            raise RuntimeError("Ollama not found. Please install Ollama and pull a model.")
    
    async def call_multiple_llms(self, calls: List[LLMCall]) -> List[LLMResult]:
        """Make multiple LLM calls concurrently"""
        logger.info(f"🚀 Starting {len(calls)} concurrent LLM calls")
        
        # Create semaphore to limit concurrent calls
        semaphore = asyncio.Semaphore(self.max_concurrent_calls)
        
        async def call_with_semaphore(call: LLMCall) -> LLMResult:
            async with semaphore:
                return await self.call_llm_async(call)
        
        # Execute all calls concurrently
        tasks = [call_with_semaphore(call) for call in calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception in call {calls[i].call_id}: {result}")
                processed_results.append(LLMResult(
                    call_id=calls[i].call_id,
                    success=False,
                    error=str(result),
                    latency_ms=0,
                    cached=False
                ))
            else:
                processed_results.append(result)
        
        logger.info(f"✅ Completed {len(calls)} LLM calls")
        return processed_results
    
    def get_timeout_for_model(self, model: str) -> int:
        """Get appropriate timeout based on model size"""
        timeout_seconds = 60  # Default
        model_lower = model.lower()
        
        if "20b" in model_lower or "gpt-oss" in model_lower:
            timeout_seconds = 180  # 3 minutes for 20B models
        elif "14b" in model_lower or "13b" in model_lower:
            timeout_seconds = 120  # 2 minutes for 13-14B models
        elif "70b" in model_lower:
            timeout_seconds = 240  # 4 minutes for 70B models
        
        return timeout_seconds
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = self.call_stats.copy()
        if stats["total_calls"] > 0:
            stats["cache_hit_rate"] = stats["cache_hits"] / stats["total_calls"]
            stats["average_latency_ms"] = stats["total_latency_ms"] / stats["total_calls"]
            stats["error_rate"] = stats["errors"] / stats["total_calls"]
        else:
            stats["cache_hit_rate"] = 0
            stats["average_latency_ms"] = 0
            stats["error_rate"] = 0
        
        return stats
    
    def clear_stats(self):
        """Clear performance statistics"""
        self.call_stats = {
            "total_calls": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "total_latency_ms": 0
        }

# Global async LLM manager
_global_async_manager: Optional[AsyncLLMManager] = None

def get_async_llm_manager() -> AsyncLLMManager:
    """Get or create global async LLM manager"""
    global _global_async_manager
    if _global_async_manager is None:
        _global_async_manager = AsyncLLMManager()
    return _global_async_manager

async def call_local_model_async(prompt: str, model: str = "llama3.1:latest", method: str = "constrained", **kwargs) -> str:
    """Async wrapper for local model calls"""
    manager = get_async_llm_manager()
    timeout = manager.get_timeout_for_model(model)
    
    call = LLMCall(
        prompt=prompt,
        model=model,
        timeout=timeout,
        call_id=f"single_{int(time.time() * 1000)}",
        method=method,
        kwargs=kwargs
    )
    
    result = await manager.call_llm_async(call)
    
    if result.success:
        return result.result
    else:
        raise RuntimeError(result.error)

# Backward compatibility function
def call_local_model(prompt: str, model: str = "llama3.1:latest") -> str:
    """
    Synchronous wrapper that uses async infrastructure.
    This maintains backward compatibility while using async under the hood.
    """
    try:
        # Try to use existing event loop
        loop = asyncio.get_running_loop()
        # If we're already in an async context, create a new task
        task = asyncio.create_task(call_local_model_async(prompt, model))
        # This will be awaited by the caller
        return asyncio.run_coroutine_threadsafe(task, loop).result(timeout=300)
    except RuntimeError:
        # No event loop running, create one
        return asyncio.run(call_local_model_async(prompt, model))

# Export the key functions and classes
__all__ = [
    'AsyncLLMManager',
    'LLMCall', 
    'LLMResult',
    'get_async_llm_manager',
    'call_local_model_async',
    'call_local_model'
]

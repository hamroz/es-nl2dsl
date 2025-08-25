#!/usr/bin/env python3
"""Comprehensive performance benchmarking system"""
import asyncio
import time
import json
import statistics
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import numpy as np

@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    execution_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error: Optional[str]
    worker_id: Optional[str]
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    test_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    
    # Timing metrics
    total_time_seconds: float
    avg_execution_time_ms: float
    median_execution_time_ms: float
    p95_execution_time_ms: float
    p99_execution_time_ms: float
    min_execution_time_ms: float
    max_execution_time_ms: float
    
    # Throughput metrics
    operations_per_second: float
    queries_per_minute: float
    
    # Resource metrics
    avg_memory_usage_mb: float
    peak_memory_usage_mb: float
    avg_cpu_usage_percent: float
    peak_cpu_usage_percent: float
    
    # Reliability metrics
    success_rate_percent: float
    error_rate_percent: float
    
    # Concurrency metrics
    avg_concurrent_operations: float
    max_concurrent_operations: int
    
    # Raw data
    individual_metrics: List[PerformanceMetrics]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert individual metrics to dicts
        result["individual_metrics"] = [m.to_dict() for m in self.individual_metrics]
        return result

class SystemMonitor:
    """Monitor system resources during benchmarking"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics: List[Dict[str, Any]] = []
        self.monitor_thread: Optional[threading.Thread] = None
    
    def start_monitoring(self, interval: float = 0.5):
        """Start system monitoring"""
        self.monitoring = True
        self.metrics = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,))
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self, interval: float):
        """Monitor system resources in a loop"""
        while self.monitoring:
            try:
                # Get current process info
                process = psutil.Process()
                
                # Memory usage
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # CPU usage
                cpu_percent = process.cpu_percent()
                
                # System-wide metrics
                system_memory = psutil.virtual_memory()
                system_cpu = psutil.cpu_percent()
                
                self.metrics.append({
                    "timestamp": time.time(),
                    "process_memory_mb": memory_mb,
                    "process_cpu_percent": cpu_percent,
                    "system_memory_percent": system_memory.percent,
                    "system_cpu_percent": system_cpu,
                    "available_memory_mb": system_memory.available / 1024 / 1024
                })
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"Monitoring error: {e}")
                break
    
    def get_peak_metrics(self) -> Dict[str, Any]:
        """Get peak resource usage"""
        if not self.metrics:
            return {}
        
        peak_memory = max(m["process_memory_mb"] for m in self.metrics)
        peak_cpu = max(m["process_cpu_percent"] for m in self.metrics)
        avg_memory = statistics.mean(m["process_memory_mb"] for m in self.metrics)
        avg_cpu = statistics.mean(m["process_cpu_percent"] for m in self.metrics)
        
        return {
            "peak_memory_mb": peak_memory,
            "peak_cpu_percent": peak_cpu,
            "avg_memory_mb": avg_memory,
            "avg_cpu_percent": avg_cpu,
            "total_samples": len(self.metrics)
        }

class PerformanceBenchmark:
    """Comprehensive performance benchmarking system"""
    
    def __init__(self):
        self.monitor = SystemMonitor()
        self.results: List[BenchmarkResult] = []
    
    async def benchmark_query_generation(self, 
                                       prompts: List[str],
                                       models: List[str],
                                       concurrency_levels: List[int],
                                       iterations_per_test: int = 10) -> List[BenchmarkResult]:
        """Benchmark query generation with different configurations"""
        
        all_results = []
        
        for model in models:
            for concurrency in concurrency_levels:
                test_name = f"query_gen_{model}_{concurrency}c_{iterations_per_test}i"
                print(f"Running benchmark: {test_name}")
                
                result = await self._run_concurrent_benchmark(
                    test_name=test_name,
                    prompts=prompts[:iterations_per_test],
                    model=model,
                    concurrency=concurrency
                )
                
                all_results.append(result)
                print(f"  Completed: {result.operations_per_second:.1f} ops/sec, {result.success_rate_percent:.1f}% success")
        
        return all_results
    
    async def _run_concurrent_benchmark(self, 
                                      test_name: str,
                                      prompts: List[str],
                                      model: str,
                                      concurrency: int) -> BenchmarkResult:
        """Run benchmark with specified concurrency"""
        
        # Start system monitoring
        self.monitor.start_monitoring()
        
        start_time = time.time()
        metrics: List[PerformanceMetrics] = []
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)
        concurrent_operations = 0
        max_concurrent = 0
        
        async def generate_single_query(prompt: str, task_id: str) -> PerformanceMetrics:
            nonlocal concurrent_operations, max_concurrent
            
            async with semaphore:
                concurrent_operations += 1
                max_concurrent = max(max_concurrent, concurrent_operations)
                
                op_start_time = time.time()
                memory_before = psutil.Process().memory_info().rss / 1024 / 1024
                
                try:
                    # Run query generation
                    cmd = [
                        sys.executable, "src/generators/constrained.py",
                        "--prompt", prompt,
                        "--task-id", task_id,
                        "--model", model
                    ]
                    
                    result = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await result.communicate()
                    
                    execution_time = (time.time() - op_start_time) * 1000  # Convert to ms
                    memory_after = psutil.Process().memory_info().rss / 1024 / 1024
                    memory_usage = memory_after - memory_before
                    
                    success = result.returncode == 0
                    error = stderr.decode() if stderr else None
                    
                    return PerformanceMetrics(
                        execution_time_ms=execution_time,
                        memory_usage_mb=memory_usage,
                        cpu_usage_percent=psutil.Process().cpu_percent(),
                        success=success,
                        error=error,
                        worker_id="local",
                        timestamp=op_start_time
                    )
                    
                except Exception as e:
                    execution_time = (time.time() - op_start_time) * 1000
                    return PerformanceMetrics(
                        execution_time_ms=execution_time,
                        memory_usage_mb=0,
                        cpu_usage_percent=0,
                        success=False,
                        error=str(e),
                        worker_id="local",
                        timestamp=op_start_time
                    )
                finally:
                    concurrent_operations -= 1
        
        # Generate tasks
        tasks = []
        for i, prompt in enumerate(prompts):
            task_id = f"{test_name}_task_{i}"
            tasks.append(generate_single_query(prompt, task_id))
        
        # Execute all tasks
        metrics = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        system_metrics = self.monitor.get_peak_metrics()
        
        # Calculate statistics
        successful_ops = [m for m in metrics if m.success]
        failed_ops = [m for m in metrics if not m.success]
        
        execution_times = [m.execution_time_ms for m in successful_ops]
        
        if execution_times:
            avg_time = statistics.mean(execution_times)
            median_time = statistics.median(execution_times)
            p95_time = np.percentile(execution_times, 95)
            p99_time = np.percentile(execution_times, 99)
            min_time = min(execution_times)
            max_time = max(execution_times)
        else:
            avg_time = median_time = p95_time = p99_time = min_time = max_time = 0
        
        # Create result
        result = BenchmarkResult(
            test_name=test_name,
            total_operations=len(metrics),
            successful_operations=len(successful_ops),
            failed_operations=len(failed_ops),
            total_time_seconds=total_time,
            avg_execution_time_ms=avg_time,
            median_execution_time_ms=median_time,
            p95_execution_time_ms=p95_time,
            p99_execution_time_ms=p99_time,
            min_execution_time_ms=min_time,
            max_execution_time_ms=max_time,
            operations_per_second=len(successful_ops) / total_time if total_time > 0 else 0,
            queries_per_minute=(len(successful_ops) / total_time) * 60 if total_time > 0 else 0,
            avg_memory_usage_mb=system_metrics.get("avg_memory_mb", 0),
            peak_memory_usage_mb=system_metrics.get("peak_memory_mb", 0),
            avg_cpu_usage_percent=system_metrics.get("avg_cpu_percent", 0),
            peak_cpu_usage_percent=system_metrics.get("peak_cpu_percent", 0),
            success_rate_percent=(len(successful_ops) / len(metrics)) * 100 if metrics else 0,
            error_rate_percent=(len(failed_ops) / len(metrics)) * 100 if metrics else 0,
            avg_concurrent_operations=sum(range(1, concurrency + 1)) / concurrency,
            max_concurrent_operations=max_concurrent,
            individual_metrics=metrics
        )
        
        self.results.append(result)
        return result
    
    def benchmark_load_testing(self, 
                             base_prompt: str,
                             load_levels: List[int],
                             duration_seconds: int = 60) -> List[BenchmarkResult]:
        """Benchmark system under different load levels"""
        
        results = []
        
        for load_level in load_levels:
            print(f"Running load test: {load_level} concurrent users for {duration_seconds}s")
            
            result = self._run_load_test(
                test_name=f"load_test_{load_level}users_{duration_seconds}s",
                prompt=base_prompt,
                concurrent_users=load_level,
                duration_seconds=duration_seconds
            )
            
            results.append(result)
            print(f"  Load test completed: {result.operations_per_second:.1f} ops/sec")
        
        return results
    
    def _run_load_test(self, 
                      test_name: str,
                      prompt: str,
                      concurrent_users: int,
                      duration_seconds: int) -> BenchmarkResult:
        """Run sustained load test"""
        
        self.monitor.start_monitoring()
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        metrics = []
        operation_counter = 0
        max_concurrent = 0
        current_concurrent = 0
        
        def user_simulation():
            """Simulate a single user generating queries continuously"""
            nonlocal operation_counter, max_concurrent, current_concurrent
            
            while time.time() < end_time:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
                
                op_start = time.time()
                operation_counter += 1
                task_id = f"{test_name}_op_{operation_counter}"
                
                try:
                    # Run query generation
                    cmd = [
                        sys.executable, "src/generators/constrained.py",
                        "--prompt", prompt,
                        "--task-id", task_id,
                        "--model", "llama3.1:latest"
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    
                    execution_time = (time.time() - op_start) * 1000
                    success = result.returncode == 0
                    
                    metrics.append(PerformanceMetrics(
                        execution_time_ms=execution_time,
                        memory_usage_mb=psutil.Process().memory_info().rss / 1024 / 1024,
                        cpu_usage_percent=psutil.Process().cpu_percent(),
                        success=success,
                        error=result.stderr if result.stderr else None,
                        worker_id="local",
                        timestamp=op_start
                    ))
                    
                except Exception as e:
                    execution_time = (time.time() - op_start) * 1000
                    metrics.append(PerformanceMetrics(
                        execution_time_ms=execution_time,
                        memory_usage_mb=0,
                        cpu_usage_percent=0,
                        success=False,
                        error=str(e),
                        worker_id="local",
                        timestamp=op_start
                    ))
                finally:
                    current_concurrent -= 1
                
                # Small delay to prevent overwhelming
                time.sleep(0.1)
        
        # Start user threads
        threads = []
        for _ in range(concurrent_users):
            thread = threading.Thread(target=user_simulation)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        system_metrics = self.monitor.get_peak_metrics()
        
        # Calculate statistics (similar to concurrent benchmark)
        successful_ops = [m for m in metrics if m.success]
        failed_ops = [m for m in metrics if not m.success]
        
        execution_times = [m.execution_time_ms for m in successful_ops]
        
        if execution_times:
            avg_time = statistics.mean(execution_times)
            median_time = statistics.median(execution_times)
            p95_time = np.percentile(execution_times, 95)
            p99_time = np.percentile(execution_times, 99)
            min_time = min(execution_times)
            max_time = max(execution_times)
        else:
            avg_time = median_time = p95_time = p99_time = min_time = max_time = 0
        
        result = BenchmarkResult(
            test_name=test_name,
            total_operations=len(metrics),
            successful_operations=len(successful_ops),
            failed_operations=len(failed_ops),
            total_time_seconds=total_time,
            avg_execution_time_ms=avg_time,
            median_execution_time_ms=median_time,
            p95_execution_time_ms=p95_time,
            p99_execution_time_ms=p99_time,
            min_execution_time_ms=min_time,
            max_execution_time_ms=max_time,
            operations_per_second=len(successful_ops) / total_time if total_time > 0 else 0,
            queries_per_minute=(len(successful_ops) / total_time) * 60 if total_time > 0 else 0,
            avg_memory_usage_mb=system_metrics.get("avg_memory_mb", 0),
            peak_memory_usage_mb=system_metrics.get("peak_memory_mb", 0),
            avg_cpu_usage_percent=system_metrics.get("avg_cpu_percent", 0),
            peak_cpu_usage_percent=system_metrics.get("peak_cpu_percent", 0),
            success_rate_percent=(len(successful_ops) / len(metrics)) * 100 if metrics else 0,
            error_rate_percent=(len(failed_ops) / len(metrics)) * 100 if metrics else 0,
            avg_concurrent_operations=concurrent_users,
            max_concurrent_operations=max_concurrent,
            individual_metrics=metrics
        )
        
        self.results.append(result)
        return result
    
    def generate_performance_report(self, output_dir: str = "artifacts/performance_results"):
        """Generate comprehensive performance report"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save raw results
        with open(output_path / "benchmark_results.json", 'w') as f:
            json.dump([r.to_dict() for r in self.results], f, indent=2)
        
        # Generate summary report
        self._generate_summary_report(output_path)
        
        # Generate performance charts
        self._generate_performance_charts(output_path)
        
        print(f"Performance report generated in {output_path}")
    
    def _generate_summary_report(self, output_path: Path):
        """Generate summary performance report"""
        
        report = []
        report.append("# Performance Benchmark Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        if not self.results:
            report.append("No benchmark results available.")
            with open(output_path / "performance_summary.md", 'w') as f:
                f.write('\n'.join(report))
            return
        
        # Overall summary
        total_operations = sum(r.total_operations for r in self.results)
        successful_operations = sum(r.successful_operations for r in self.results)
        overall_success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0
        
        report.append("## Overall Summary")
        report.append(f"- Total Operations: {total_operations:,}")
        report.append(f"- Successful Operations: {successful_operations:,}")
        report.append(f"- Overall Success Rate: {overall_success_rate:.1f}%")
        report.append("")
        
        # Best performing configurations
        best_throughput = max(self.results, key=lambda r: r.operations_per_second)
        best_latency = min(self.results, key=lambda r: r.avg_execution_time_ms)
        best_reliability = max(self.results, key=lambda r: r.success_rate_percent)
        
        report.append("## Top Performers")
        report.append(f"- **Best Throughput**: {best_throughput.test_name} ({best_throughput.operations_per_second:.1f} ops/sec)")
        report.append(f"- **Best Latency**: {best_latency.test_name} ({best_latency.avg_execution_time_ms:.1f}ms avg)")
        report.append(f"- **Best Reliability**: {best_reliability.test_name} ({best_reliability.success_rate_percent:.1f}% success)")
        report.append("")
        
        # Detailed results table
        report.append("## Detailed Results")
        report.append("")
        report.append("| Test Name | Ops/Sec | Avg Latency (ms) | P95 Latency (ms) | Success Rate (%) | Peak Memory (MB) |")
        report.append("|-----------|---------|------------------|------------------|------------------|------------------|")
        
        for result in sorted(self.results, key=lambda r: r.operations_per_second, reverse=True):
            report.append(f"| {result.test_name} | {result.operations_per_second:.1f} | {result.avg_execution_time_ms:.1f} | {result.p95_execution_time_ms:.1f} | {result.success_rate_percent:.1f} | {result.peak_memory_usage_mb:.1f} |")
        
        report.append("")
        
        # Performance recommendations
        report.append("## Performance Recommendations")
        
        if any(r.success_rate_percent < 95 for r in self.results):
            report.append("- **Reliability**: Some configurations show success rates below 95%. Consider implementing retries or error handling.")
        
        if any(r.peak_memory_usage_mb > 1000 for r in self.results):
            report.append("- **Memory**: Peak memory usage exceeds 1GB in some tests. Consider memory optimization.")
        
        if any(r.p95_execution_time_ms > 10000 for r in self.results):
            report.append("- **Latency**: P95 latency exceeds 10 seconds in some configurations. Consider timeout optimization.")
        
        # Save report
        with open(output_path / "performance_summary.md", 'w') as f:
            f.write('\n'.join(report))
    
    def _generate_performance_charts(self, output_path: Path):
        """Generate performance visualization charts"""
        
        if not self.results:
            return
        
        # Throughput vs Latency scatter plot
        plt.figure(figsize=(10, 6))
        
        throughputs = [r.operations_per_second for r in self.results]
        latencies = [r.avg_execution_time_ms for r in self.results]
        test_names = [r.test_name for r in self.results]
        
        plt.scatter(latencies, throughputs, alpha=0.7, s=60)
        
        for i, name in enumerate(test_names):
            plt.annotate(name, (latencies[i], throughputs[i]), 
                        xytext=(5, 5), textcoords='offset points', fontsize=8)
        
        plt.xlabel('Average Latency (ms)')
        plt.ylabel('Throughput (ops/sec)')
        plt.title('Performance Trade-off: Throughput vs Latency')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / "throughput_vs_latency.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Success rate comparison
        plt.figure(figsize=(12, 6))
        
        success_rates = [r.success_rate_percent for r in self.results]
        test_names_short = [name[:20] + "..." if len(name) > 20 else name for name in test_names]
        
        bars = plt.bar(range(len(success_rates)), success_rates, alpha=0.7)
        
        # Color bars based on success rate
        for i, bar in enumerate(bars):
            if success_rates[i] >= 95:
                bar.set_color('green')
            elif success_rates[i] >= 90:
                bar.set_color('orange')
            else:
                bar.set_color('red')
        
        plt.xlabel('Test Configuration')
        plt.ylabel('Success Rate (%)')
        plt.title('Reliability Comparison Across Configurations')
        plt.xticks(range(len(test_names_short)), test_names_short, rotation=45, ha='right')
        plt.grid(True, alpha=0.3, axis='y')
        
        # Add horizontal line at 95%
        plt.axhline(y=95, color='red', linestyle='--', alpha=0.5, label='95% Target')
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(output_path / "success_rate_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()

def load_test_prompts() -> List[str]:
    """Load test prompts for benchmarking"""
    
    try:
        import yaml
        with open("tasks/prompts.yaml") as f:
            scenarios = yaml.safe_load(f)
        
        prompts = [scenario['prompt'] for scenario in scenarios[:5]]  # Use first 5
    except Exception:
        # Fallback prompts
        prompts = [
            "Find events labeled malicious on July 4, 2017",
            "Show TCP traffic on port 443",
            "Find intrusion attempts in the last hour",
            "Query for SSH connections from external IPs",
            "Show all attack events with high severity"
        ]
    
    return prompts

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Performance benchmarking suite")
    parser.add_argument("--test-type", choices=["query", "load", "all"], default="query",
                       help="Type of benchmark to run")
    parser.add_argument("--iterations", type=int, default=10,
                       help="Number of iterations per test")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4],
                       help="Concurrency levels to test")
    parser.add_argument("--models", nargs="+", default=["llama3.1:latest"],
                       help="Models to benchmark")
    parser.add_argument("--output", default="artifacts/performance_results",
                       help="Output directory for results")
    
    args = parser.parse_args()
    
    async def main():
        benchmark = PerformanceBenchmark()
        test_prompts = load_test_prompts()
        
        print(f"Starting {args.test_type} benchmark with {len(test_prompts)} prompts")
        
        if args.test_type in ["query", "all"]:
            print("Running query generation benchmarks...")
            await benchmark.benchmark_query_generation(
                prompts=test_prompts,
                models=args.models,
                concurrency_levels=args.concurrency,
                iterations_per_test=args.iterations
            )
        
        if args.test_type in ["load", "all"]:
            print("Running load testing benchmarks...")
            benchmark.benchmark_load_testing(
                base_prompt=test_prompts[0],
                load_levels=[1, 2, 4, 8],
                duration_seconds=30  # Shorter for testing
            )
        
        # Generate report
        benchmark.generate_performance_report(args.output)
        print(f"Benchmark complete! Results saved to {args.output}")
    
    asyncio.run(main())

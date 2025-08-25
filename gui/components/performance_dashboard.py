#!/usr/bin/env python3
"""Performance monitoring dashboard for GUI"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

def render_performance_dashboard():
    """Render the performance monitoring dashboard"""
    
    st.header("🚀 Performance Dashboard")
    st.markdown("Real-time performance monitoring and optimization insights")
    
    # Performance overview tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Real-time Metrics", 
        "🔄 Load Balancing", 
        "💾 Cache Performance", 
        "📈 Benchmarks"
    ])
    
    with tab1:
        render_realtime_metrics()
    
    with tab2:
        render_load_balancing_view()
    
    with tab3:
        render_cache_performance()
    
    with tab4:
        render_benchmark_results()

def render_realtime_metrics():
    """Render real-time performance metrics"""
    st.subheader("Real-time System Performance")
    
    # Get current performance data
    try:
        from src.performance.caching import get_cache_stats
        cache_stats = get_cache_stats()
    except Exception as e:
        st.error(f"Could not load cache statistics: {e}")
        cache_stats = {}
    
    # System metrics overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Mock data - would come from distributed service
        st.metric(
            "Queries/Second", 
            "2.3",
            delta="0.4",
            help="Current query generation throughput"
        )
    
    with col2:
        st.metric(
            "Avg Response Time", 
            "1.2s",
            delta="-0.3s",
            help="Average query generation latency"
        )
    
    with col3:
        cache_hit_rate = cache_stats.get('overall_hit_rate', 0)
        st.metric(
            "Cache Hit Rate", 
            f"{cache_hit_rate:.1f}%",
            delta="5.2%",
            help="Percentage of requests served from cache"
        )
    
    with col4:
        st.metric(
            "Success Rate", 
            "97.8%",
            delta="1.2%",
            help="Percentage of successful query generations"
        )
    
    st.markdown("---")
    
    # Performance charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Response Time Distribution")
        
        # Mock response time data
        response_times = pd.DataFrame({
            'Time': pd.date_range('2025-01-01', periods=24, freq='H'),
            'P50': [1200, 1150, 1100, 1250, 1300, 1180, 1220, 1350, 1400, 1300, 1250, 1200,
                   1180, 1220, 1260, 1240, 1300, 1380, 1420, 1350, 1280, 1240, 1200, 1180],
            'P95': [2800, 2750, 2600, 2900, 3100, 2850, 2950, 3200, 3400, 3100, 2900, 2800,
                   2750, 2900, 3050, 2980, 3100, 3300, 3500, 3200, 2950, 2850, 2800, 2750],
            'P99': [4200, 4100, 3900, 4300, 4600, 4250, 4400, 4800, 5100, 4600, 4300, 4200,
                   4100, 4300, 4550, 4480, 4600, 4900, 5200, 4800, 4400, 4250, 4200, 4100]
        })
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=response_times['Time'],
            y=response_times['P50'],
            mode='lines',
            name='P50 (Median)',
            line=dict(color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=response_times['Time'],
            y=response_times['P95'],
            mode='lines',
            name='P95',
            line=dict(color='orange')
        ))
        
        fig.add_trace(go.Scatter(
            x=response_times['Time'],
            y=response_times['P99'],
            mode='lines',
            name='P99',
            line=dict(color='red')
        ))
        
        fig.update_layout(
            title="Response Time Percentiles (24h)",
            xaxis_title="Time",
            yaxis_title="Response Time (ms)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Throughput Over Time")
        
        # Mock throughput data
        throughput_data = pd.DataFrame({
            'Time': pd.date_range('2025-01-01', periods=24, freq='H'),
            'Queries_Per_Second': [1.8, 2.1, 1.9, 2.3, 2.7, 2.4, 2.6, 3.1, 3.4, 3.2, 2.8, 2.5,
                                  2.3, 2.6, 2.8, 2.7, 3.0, 3.3, 3.5, 3.2, 2.9, 2.6, 2.3, 2.1],
            'Success_Rate': [97.5, 98.1, 97.8, 98.3, 97.9, 98.2, 97.6, 98.0, 97.8, 98.1, 98.3, 97.9,
                            98.2, 97.8, 98.0, 98.4, 97.7, 98.1, 97.9, 98.2, 98.0, 97.8, 98.1, 97.9]
        })
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(
                x=throughput_data['Time'],
                y=throughput_data['Queries_Per_Second'],
                mode='lines+markers',
                name='Queries/Sec',
                line=dict(color='blue')
            ),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(
                x=throughput_data['Time'],
                y=throughput_data['Success_Rate'],
                mode='lines',
                name='Success Rate %',
                line=dict(color='green')
            ),
            secondary_y=True,
        )
        
        fig.update_xaxes(title_text="Time")
        fig.update_yaxes(title_text="Queries per Second", secondary_y=False)
        fig.update_yaxes(title_text="Success Rate (%)", secondary_y=True)
        
        fig.update_layout(
            title="System Throughput & Reliability",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

def render_load_balancing_view():
    """Render load balancing and worker status"""
    st.subheader("Load Balancing & Worker Status")
    
    # Mock worker data - would come from distributed service
    workers_data = [
        {
            "Worker ID": "ollama-worker-1",
            "Type": "Ollama Local",
            "Status": "🟢 Healthy",
            "Load": "45%",
            "Avg Response": "1.2s",
            "Success Rate": "98.5%",
            "Requests": 1847,
            "Models": "llama3.1:latest, deepseek-r1:14b"
        },
        {
            "Worker ID": "ollama-worker-2", 
            "Type": "Ollama Local",
            "Status": "🟡 Degraded",
            "Load": "78%",
            "Avg Response": "2.1s",
            "Success Rate": "96.2%",
            "Requests": 2156,
            "Models": "llama3.1:latest, gpt-oss:20b"
        },
        {
            "Worker ID": "external-api-1",
            "Type": "External API",
            "Status": "🔴 Offline",
            "Load": "0%",
            "Avg Response": "N/A",
            "Success Rate": "N/A",
            "Requests": 0,
            "Models": "gpt-4, claude-3"
        }
    ]
    
    workers_df = pd.DataFrame(workers_data)
    
    st.dataframe(
        workers_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Load distribution chart
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Load Distribution")
        
        load_data = [45, 78, 0]
        worker_names = ["Worker 1", "Worker 2", "Worker 3"]
        
        fig = go.Figure(data=[
            go.Bar(
                x=worker_names,
                y=load_data,
                marker_color=['green', 'orange', 'red']
            )
        ])
        
        fig.update_layout(
            title="Current Worker Load (%)",
            yaxis_title="Load Percentage",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Request Distribution")
        
        request_counts = [1847, 2156, 0]
        
        fig = go.Figure(data=[
            go.Pie(
                labels=worker_names,
                values=request_counts,
                hole=0.3
            )
        ])
        
        fig.update_layout(
            title="Total Requests Handled",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Worker configuration
    st.subheader("Worker Configuration")
    
    with st.expander("Add New Worker"):
        col1, col2 = st.columns(2)
        
        with col1:
            worker_type = st.selectbox(
                "Worker Type",
                ["Ollama Local", "External API", "Hybrid"]
            )
            
            endpoint = st.text_input(
                "Endpoint",
                placeholder="http://localhost:11434"
            )
        
        with col2:
            max_capacity = st.number_input(
                "Max Capacity",
                min_value=1,
                max_value=20,
                value=4
            )
            
            models = st.text_area(
                "Supported Models",
                placeholder="llama3.1:latest, deepseek-r1:14b"
            )
        
        if st.button("Add Worker"):
            st.success("Worker configuration saved! (Note: This is a demo)")

def render_cache_performance():
    """Render cache performance metrics"""
    st.subheader("Cache Performance & Optimization")
    
    try:
        from src.performance.caching import get_cache_stats
        cache_stats = get_cache_stats()
        
        # Cache overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            hit_rate = cache_stats.get('overall_hit_rate', 0)
            st.metric(
                "Overall Hit Rate",
                f"{hit_rate:.1f}%",
                help="Percentage of requests served from cache"
            )
        
        with col2:
            memory_cache = cache_stats.get('memory_cache', {})
            memory_utilization = memory_cache.get('utilization_percent', 0)
            st.metric(
                "Memory Cache",
                f"{memory_utilization:.1f}%",
                help="Memory cache utilization"
            )
        
        with col3:
            disk_cache = cache_stats.get('disk_cache', {})
            disk_utilization = disk_cache.get('utilization_percent', 0)
            st.metric(
                "Disk Cache",
                f"{disk_utilization:.1f}%",
                help="Disk cache utilization"
            )
        
        with col4:
            total_hits = cache_stats.get('total_hits', 0)
            st.metric(
                "Total Cache Hits",
                f"{total_hits:,}",
                help="Total number of cache hits"
            )
        
        st.markdown("---")
        
        # Detailed cache statistics
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Memory Cache Details")
            
            if memory_cache:
                memory_df = pd.DataFrame([
                    {"Metric": "Hits", "Value": memory_cache.get('hits', 0)},
                    {"Metric": "Misses", "Value": memory_cache.get('misses', 0)},
                    {"Metric": "Hit Rate", "Value": f"{memory_cache.get('hit_rate', 0):.1f}%"},
                    {"Metric": "Size (MB)", "Value": f"{memory_cache.get('size_mb', 0):.1f}"},
                    {"Metric": "Entries", "Value": memory_cache.get('entry_count', 0)},
                    {"Metric": "Evictions", "Value": memory_cache.get('evictions', 0)}
                ])
                
                st.dataframe(memory_df, use_container_width=True, hide_index=True)
            else:
                st.info("Memory cache statistics not available")
        
        with col2:
            st.subheader("Disk Cache Details")
            
            if disk_cache:
                disk_df = pd.DataFrame([
                    {"Metric": "Hits", "Value": disk_cache.get('hits', 0)},
                    {"Metric": "Misses", "Value": disk_cache.get('misses', 0)},
                    {"Metric": "Hit Rate", "Value": f"{disk_cache.get('hit_rate', 0):.1f}%"},
                    {"Metric": "Size (MB)", "Value": f"{disk_cache.get('size_mb', 0):.1f}"},
                    {"Metric": "Entries", "Value": disk_cache.get('entry_count', 0)},
                    {"Metric": "Evictions", "Value": disk_cache.get('evictions', 0)}
                ])
                
                st.dataframe(disk_df, use_container_width=True, hide_index=True)
            else:
                st.info("Disk cache statistics not available")
        
        # Cache management controls
        st.subheader("Cache Management")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Clear Memory Cache"):
                try:
                    from src.performance.caching import get_global_cache
                    cache = get_global_cache()
                    cache.memory_cache.clear()
                    st.success("Memory cache cleared!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing cache: {e}")
        
        with col2:
            if st.button("Cleanup Expired"):
                try:
                    from src.performance.caching import get_global_cache
                    cache = get_global_cache()
                    memory_cleaned = cache.memory_cache.cleanup_expired()
                    disk_cleaned = cache.disk_cache.cleanup_expired()
                    st.success(f"Cleaned {memory_cleaned + disk_cleaned} expired entries")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error cleaning cache: {e}")
        
        with col3:
            if st.button("Refresh Stats"):
                st.rerun()
        
    except ImportError:
        st.error("Cache performance module not available")
    except Exception as e:
        st.error(f"Error loading cache statistics: {e}")

def render_benchmark_results():
    """Render benchmark results and performance analysis"""
    st.subheader("Performance Benchmarks")
    
    # Check for benchmark results
    benchmark_file = Path("artifacts/performance_results/benchmark_results.json")
    
    if benchmark_file.exists():
        try:
            with open(benchmark_file) as f:
                benchmark_data = json.load(f)
            
            st.success(f"Loaded {len(benchmark_data)} benchmark results")
            
            # Convert to DataFrame for analysis
            df_data = []
            for result in benchmark_data:
                df_data.append({
                    "Test Name": result.get("test_name", "Unknown"),
                    "Operations/Sec": result.get("operations_per_second", 0),
                    "Avg Latency (ms)": result.get("avg_execution_time_ms", 0),
                    "P95 Latency (ms)": result.get("p95_execution_time_ms", 0),
                    "Success Rate (%)": result.get("success_rate_percent", 0),
                    "Peak Memory (MB)": result.get("peak_memory_usage_mb", 0),
                    "Total Operations": result.get("total_operations", 0)
                })
            
            if df_data:
                benchmark_df = pd.DataFrame(df_data)
                
                # Summary metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    max_throughput = benchmark_df["Operations/Sec"].max()
                    st.metric("Max Throughput", f"{max_throughput:.1f} ops/sec")
                
                with col2:
                    min_latency = benchmark_df["Avg Latency (ms)"].min()
                    st.metric("Best Avg Latency", f"{min_latency:.1f}ms")
                
                with col3:
                    avg_success_rate = benchmark_df["Success Rate (%)"].mean()
                    st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")
                
                st.markdown("---")
                
                # Detailed results table
                st.subheader("Benchmark Results")
                st.dataframe(benchmark_df, use_container_width=True, hide_index=True)
                
                # Performance visualization
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Throughput vs Latency")
                    
                    fig = px.scatter(
                        benchmark_df,
                        x="Avg Latency (ms)",
                        y="Operations/Sec",
                        size="Total Operations",
                        hover_name="Test Name",
                        title="Performance Trade-off Analysis"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("Success Rate Distribution")
                    
                    fig = px.bar(
                        benchmark_df,
                        x="Test Name",
                        y="Success Rate (%)",
                        title="Reliability Across Configurations"
                    )
                    
                    fig.update_xaxes(tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error loading benchmark results: {e}")
    
    else:
        st.info("No benchmark results found. Run benchmarks to see performance data.")
        
        # Benchmark runner controls
        st.subheader("Run New Benchmarks")
        
        col1, col2 = st.columns(2)
        
        with col1:
            benchmark_type = st.selectbox(
                "Benchmark Type",
                ["Query Generation", "Load Testing", "Full Suite"]
            )
            
            concurrency_levels = st.multiselect(
                "Concurrency Levels",
                [1, 2, 4, 8, 16],
                default=[1, 2, 4]
            )
        
        with col2:
            iterations = st.number_input(
                "Iterations per Test",
                min_value=5,
                max_value=100,
                value=10
            )
            
            models = st.multiselect(
                "Models to Test",
                ["llama3.1:latest", "deepseek-r1:14b", "gpt-oss:20b"],
                default=["llama3.1:latest"]
            )
        
        if st.button("Start Benchmark"):
            with st.spinner("Running benchmarks... This may take several minutes."):
                try:
                    # This would trigger the actual benchmark
                    st.info("Benchmark started! (Note: This is a demo - actual implementation would run benchmarks)")
                    
                    # In real implementation:
                    # import subprocess
                    # subprocess.run([
                    #     "python", "src/performance/benchmarking.py",
                    #     "--test-type", benchmark_type.lower().replace(" ", ""),
                    #     "--iterations", str(iterations),
                    #     "--concurrency"] + [str(c) for c in concurrency_levels] +
                    #     ["--models"] + models
                    # )
                    
                except Exception as e:
                    st.error(f"Benchmark failed: {e}")

def get_performance_data():
    """Get current performance data from various sources"""
    try:
        # This would collect data from:
        # - Distributed service metrics
        # - Cache statistics
        # - System resource usage
        # - Recent benchmark results
        
        return {
            "current_throughput": 2.3,
            "avg_response_time": 1200,
            "cache_hit_rate": 45.2,
            "success_rate": 97.8,
            "worker_count": 2,
            "active_requests": 5
        }
    except Exception:
        return {}

if __name__ == "__main__":
    # For testing the dashboard components
    render_performance_dashboard()

# Performance Benchmark Report
Generated: 2025-08-26 01:38:20

## Overall Summary
- Total Operations: 6
- Successful Operations: 6
- Overall Success Rate: 100.0%

## Top Performers
- **Best Throughput**: query_gen_llama3.1:latest_2c_3i (0.1 ops/sec)
- **Best Latency**: query_gen_llama3.1:latest_1c_3i (13756.6ms avg)
- **Best Reliability**: query_gen_llama3.1:latest_1c_3i (100.0% success)

## Detailed Results

| Test Name | Ops/Sec | Avg Latency (ms) | P95 Latency (ms) | Success Rate (%) | Peak Memory (MB) |
|-----------|---------|------------------|------------------|------------------|------------------|
| query_gen_llama3.1:latest_2c_3i | 0.1 | 26659.6 | 37194.6 | 100.0 | 21.0 |
| query_gen_llama3.1:latest_1c_3i | 0.1 | 13756.6 | 16661.0 | 100.0 | 61.0 |

## Performance Recommendations
- **Latency**: P95 latency exceeds 10 seconds in some configurations. Consider timeout optimization.
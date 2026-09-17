# Performance and Benchmark Methodology

**Status:** Architecture / Specification Phase  
**Important:** No benchmark results or performance claims exist yet.

## Measurements

Measure API throughput and p50/p95/p99 latency, queue latency, processing latency, end-to-end latency, failure rate, retry rate, worker utilization, provider latency, and resource usage.

## Protocol

Record commit/version, environment, OS, CPU, memory, dependency versions, topology, configuration, workload type, payload size, model/provider (mock or external), concurrency, job count, duration, warm-up, and sampling method. Use the mock provider for deterministic baseline measurements. Repeat runs and report variability; do not compare unlike environments.

## Scenarios

At minimum: submission-only, one worker, multiple workers, transient failures with bounded retries, duplicate delivery, and increasing concurrency until a defined saturation signal. Results belong in versioned benchmark artifacts and may be summarized in README/resume only after review.


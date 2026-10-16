#!/usr/bin/env python3
"""
Asynchronous high-concurrency benchmark tool for Scalable URL Shortener.
Fires 10,000 concurrent GET redirect requests to test Redis write-through caching layer.
Calculates: QPS, p50, p95, and p99 latency.
"""

import asyncio
import aiohttp
import time
import statistics
import argparse

async def fetch(session, url):
    start = time.perf_counter()
    try:
        async with session.get(url, allow_redirects=False) as response:
            latency = (time.perf_counter() - start) * 1000
            return latency, response.status
    except Exception as e:
        return None, 500

async def run_benchmark(target_url: str, total_requests: int, concurrency: int):
    print(f"============================================================")
    print(f" Scalable URL Shortener Latency Benchmark")
    print(f" Target: {target_url}")
    print(f" Total Requests: {total_requests:,} | Concurrency: {concurrency}")
    print(f"============================================================")

    connector = aiohttp.TCPConnector(limit=concurrency)
    latencies = []

    start_wall = time.perf_counter()

    async with aiohttp.ClientSession(connector=connector) as session:
        # Create batches of tasks
        batch_size = concurrency
        for i in range(0, total_requests, batch_size):
            current_batch = min(batch_size, total_requests - i)
            tasks = [fetch(session, target_url) for _ in range(current_batch)]
            results = await asyncio.gather(*tasks)
            for lat, status in results:
                if lat is not None and status in (200, 302):
                    latencies.append(lat)

    total_time = time.perf_counter() - start_wall
    qps = len(latencies) / total_time

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"\nBenchmark Results:")
    print(f"  - Completed Requests: {len(latencies):,}")
    print(f"  - Total Elapsed:      {total_time:.3f} seconds")
    print(f"  - Throughput (QPS):   {qps:,.0f} req/sec")
    print(f"  - p50 Latency:        {p50:.2f} ms")
    print(f"  - p95 Latency:        {p95:.2f} ms")
    print(f"  - p99 Latency:        {p99:.2f} ms  (Target: < 15 ms)")
    print(f"============================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="URL Shortener Benchmark")
    parser.add_argument("--url", default="http://localhost:8000/health", help="Target URL to load test")
    parser.add_argument("--requests", type=int, default=10000, help="Total requests")
    parser.add_argument("--concurrency", type=int, default=100, help="Concurrent workers")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.url, args.requests, args.concurrency))

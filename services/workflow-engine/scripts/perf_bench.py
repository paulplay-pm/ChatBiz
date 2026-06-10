"""Lightweight perf benchmark for the workflow-engine REST endpoints.
Usage: python scripts/perf_bench.py [--base-url http://127.0.0.1:8001] [--requests 100]

Measures p50 / p95 / p99 latency for:
  - GET /healthz
  - GET /readyz
  - GET /api/nodes
  - GET /api/nodes/llm/schema
  - GET /api/nodes/condition/schema

Eng-review target: p99 < 500ms.
"""
import argparse
import statistics
import time
from typing import Callable
import httpx


def bench(name: str, fn: Callable[[], httpx.Response], requests: int) -> dict:
    latencies: list[float] = []
    errors = 0
    for _ in range(requests):
        start = time.perf_counter()
        try:
            r = fn()
            r.raise_for_status()
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - start) * 1000)
    latencies.sort()
    return {
        "endpoint": name,
        "requests": requests,
        "errors": errors,
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(0.95 * len(latencies))], 2),
        "p99_ms": round(latencies[int(0.99 * len(latencies))], 2),
        "max_ms": round(max(latencies), 2),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8001")
    p.add_argument("--requests", type=int, default=100)
    args = p.parse_args()

    targets = [
        ("GET /healthz", lambda c: c.get("/healthz")),
        ("GET /readyz", lambda c: c.get("/readyz")),
        ("GET /api/nodes", lambda c: c.get("/api/nodes")),
        ("GET /api/nodes/llm/schema", lambda c: c.get("/api/nodes/llm/schema")),
        ("GET /api/nodes/condition/schema", lambda c: c.get("/api/nodes/condition/schema")),
    ]
    with httpx.Client(base_url=args.base_url, timeout=10.0) as c:
        for name, fn in targets:
            r = bench(name, lambda fn=fn: fn(c), args.requests)
            print(f"{r['endpoint']:40s}  p50={r['p50_ms']:>7.2f}ms  p95={r['p95_ms']:>7.2f}ms  "
                  f"p99={r['p99_ms']:>7.2f}ms  max={r['max_ms']:>7.2f}ms  errs={r['errors']}")
            if r["p99_ms"] > 500.0:
                print(f"  ⚠️  p99 exceeds 500ms target (eng-review ENG-Perf #1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

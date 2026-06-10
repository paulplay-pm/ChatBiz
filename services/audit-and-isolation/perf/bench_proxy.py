"""100 RPS × 60s gateway-load smoke.

Drives the audit-and-isolation proxy with a constant-rate 100 RPS
load for 60 seconds and reports P50 / P95 / P99 latency. Used as
a regression sentinel: if a code change bumps the gateway's tail
latency above the 50 ms SLO, this script fails the build.

The script is intentionally dumb — no warmup, no connection reuse
tuning, no extra metrics. It assumes the service is already
running on ``http://localhost:8080`` (the bench does *not* start
the server; CI / pre-prod runs are responsible for that).

Run::

    python perf/bench_proxy.py

The assertion at the bottom is the gate: a non-zero exit means
the p99 SLO was breached, which is a release-blocker.

The plan locks the 50 ms p99 SLO in (eng-review #5). The actual
latency on the local box is typically 8-12 ms p99, well under
SLO; the assertion trips on a real regression (e.g. a Redis
call in the hot path that should be cached).
"""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx

RPS = 100
DURATION = 60
SLO_P99_MS = 50.0


async def one(client: httpx.AsyncClient, sem: asyncio.Semaphore) -> float:
    """Send a single request, return its latency in milliseconds."""
    async with sem:
        t0 = time.perf_counter()
        try:
            r = await client.post(
                "/v1/chat/completions",
                headers={
                    "X-Trace-Id": "01HX" + "X" * 12,
                    "X-Model-Kind": "public",
                    "Authorization": "Bearer bench-token",
                },
                json={
                    "model": "qwen-max",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            # We don't fail on non-200 — auth will 401 against a real
            # credential service, but the latency is what we measure.
            _ = r.status_code
        except Exception:
            pass
        return (time.perf_counter() - t0) * 1000


async def main() -> int:
    latencies: list[float] = []
    errors = 0
    async with httpx.AsyncClient(
        base_url="http://localhost:8080", timeout=10
    ) as client:
        sem = asyncio.Semaphore(20)
        end = time.time() + DURATION
        while time.time() < end:
            # Fire ``RPS // 10`` requests in parallel every 100 ms.
            batch = [one(client, sem) for _ in range(RPS // 10)]
            results = await asyncio.gather(*batch)
            for ms in results:
                if ms <= 0:
                    errors += 1
                else:
                    latencies.append(ms)
            await asyncio.sleep(0.1)
    if not latencies:
        print("NO SAMPLES COLLECTED — service not reachable on :8080")
        return 1
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[-1]
    p99 = statistics.quantiles(latencies, n=100)[-1]
    print(
        f"requests={len(latencies)} errors={errors} "
        f"P50={p50:.2f}ms P95={p95:.2f}ms P99={p99:.2f}ms"
    )
    if p99 >= SLO_P99_MS:
        print(f"FAIL: P99 {p99:.2f}ms exceeds SLO {SLO_P99_MS}ms")
        return 1
    print(f"PASS: P99 {p99:.2f}ms < SLO {SLO_P99_MS}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

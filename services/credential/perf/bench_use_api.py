"""Local performance microbench for the `use` API.

Spec §性能基线 (Requirement: 性能基线) sets P99 < 50ms at 100 RPS
for the use API. This script drives the equivalent load *in-process*
against a real Postgres (testcontainers) and reports P50 / P95 / P99
in milliseconds, plus pass/fail against the SLO.

This is NOT a substitute for the locustfile in `locust/locustfile.py`
(which drives HTTP through the running stack) — the locust run is the
canonical CI check (Task 11.3 / 15.2). This microbench exists so a
developer can verify the perf budget without bringing up the full
docker-compose stack; it exercises the same hot path (encrypt + decrypt
+ audit write) but skips the ASGI / TCP / event-loop hop.

Run:

    .venv/bin/python perf/bench_use_api.py

Output: P50 / P95 / P99 in ms + a final "PASS"/"FAIL" line. Exit
code is 0 on pass, 1 on fail (suitable for `make verify`).
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from collections.abc import Iterator

import pytest  # noqa: F401  — pytest not actually used here
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# Re-use the same fixture as the integration tests.
from app import crypto
from app.audit import write_audit
from app.models import Base
from app.services import CredentialService

# ---------------------------------------------------------------------------
# Bench parameters
# ---------------------------------------------------------------------------

#: P99 SLO per spec §性能基线.
P99_SLO_MS: float = 50.0

#: Equivalent of "100 RPS for 60s" — 6000 total ops is enough for a
#: stable P99 reading without taking minutes.
TOTAL_OPS: int = 6000

#: Concurrency — 100 in-flight requests (matches the locust profile).
CONCURRENCY: int = 100

#: Credential value size in bytes — keep it small to isolate DB+audit
#: overhead from AES cost (AES-256-GCM is ~5 GB/s, this won't dominate).
CREDENTIAL_VALUE_LEN: int = 64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        yield url


async def _seed_credential(
    factory: async_sessionmaker, master_key: bytes, workspace: str
) -> str:
    """Create one credential and return its id."""
    from app.schemas import CredentialCreateRequest, CredentialType

    payload = CredentialCreateRequest(
        name="perf-bench",
        type=CredentialType.API_KEY,
        value="x" * CREDENTIAL_VALUE_LEN,
        workspace_id=workspace,
    )
    async with factory() as s:
        async with s.begin():
            svc = CredentialService(session=s, master_key=master_key)
            resp = await svc.create(payload, user_id="u-perf-admin")
            return resp.id


async def _one_use(
    factory: async_sessionmaker, master_key: bytes, cred_id: str, workspace: str
) -> None:
    from app.schemas import CredentialUseRequest

    use_req = CredentialUseRequest(cap="perf-bench", purpose="microbench")
    async with factory() as s:
        async with s.begin():
            svc = CredentialService(session=s, master_key=master_key)
            await svc.use(
                cred_id,
                use_req,
                user_id="u-perf-caller",
                workspace_id=workspace,
            )


async def _drive(factory: async_sessionmaker, master_key: bytes, cred_id: str, workspace: str) -> list[float]:
    """Fire TOTAL_OPS requests at CONCURRENCY workers; return per-op latencies (ms)."""
    sem = asyncio.Semaphore(CONCURRENCY)
    latencies: list[float] = []

    async def _worker() -> None:
        nonlocal latencies
        while True:
            async with sem:
                start = time.perf_counter()
                await _one_use(factory, master_key, cred_id, workspace)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                latencies.append(elapsed_ms)

    workers = [asyncio.create_task(_worker()) for _ in range(CONCURRENCY)]
    # Run for TOTAL_OPS // CONCURRENCY * CONCURRENCY roughly; the workers
    # run until the total reaches the cap.
    try:
        # Wait until we have enough samples, then cancel.
        target = TOTAL_OPS
        while len(latencies) < target:
            await asyncio.sleep(0.01)
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    return latencies[:TOTAL_OPS]


def _pct(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    return statistics.quantiles(samples, n=100, method="inclusive")[int(q) - 1]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> int:
    print(f"perf-bench: TOTAL_OPS={TOTAL_OPS}, CONCURRENCY={CONCURRENCY}")
    pg_gen = _postgres_url()
    pg_url = next(pg_gen)
    try:
        engine = create_async_engine(pg_url, pool_size=CONCURRENCY + 5)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        master_key = crypto.generate_master_key()
        cred_id = await _seed_credential(factory, master_key, workspace="finance")
        print(f"perf-bench: seeded credential id={cred_id[:20]}...")

        # Warm up — run a few ops to JIT/warm Postgres plan cache.
        for _ in range(50):
            await _one_use(factory, master_key, cred_id, workspace="finance")

        latencies = await _drive(factory, master_key, cred_id, workspace="finance")
        await engine.dispose()
    finally:
        try:
            next(pg_gen)
        except StopIteration:
            pass

    latencies.sort()
    p50 = _pct(latencies, 50)
    p95 = _pct(latencies, 95)
    p99 = _pct(latencies, 99)
    print(f"perf-bench: P50={p50:.2f}ms  P95={p95:.2f}ms  P99={p99:.2f}ms")

    if p99 < P99_SLO_MS:
        print(f"perf-bench: PASS (P99 < {P99_SLO_MS}ms)")
        return 0
    print(f"perf-bench: FAIL (P99 {p99:.2f}ms >= {P99_SLO_MS}ms)")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

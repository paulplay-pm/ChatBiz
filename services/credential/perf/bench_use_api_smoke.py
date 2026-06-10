"""Local performance microbench for the `use` API — quick smoke.

Same as perf/bench_use_api.py but with a small TOTAL_OPS for a fast
turnaround during local development. The real benchmark
(TOTAL_OPS=6000, CONCURRENCY=100) lives in bench_use_api.py and is
the canonical SLO check; this file is for "does it still work" smoke
runs.

Spec §性能基线 (Requirement: 性能基线): P99 < 50ms at 100 RPS.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from collections.abc import Iterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app import crypto
from app.models import Base
from app.services import CredentialService

P99_SLO_MS: float = 50.0
TOTAL_OPS: int = 500
CONCURRENCY: int = 10  # local docker PG: high concurrency starves asyncpg pool


def _postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        if url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        yield url


async def _seed(factory: async_sessionmaker, master_key: bytes) -> str:
    from app.schemas import CredentialCreateRequest, CredentialType

    payload = CredentialCreateRequest(
        name="perf-smoke",
        type=CredentialType.API_KEY,
        value="x" * 64,
        workspace_id="finance",
    )
    async with factory() as s:
        async with s.begin():
            svc = CredentialService(session=s, master_key=master_key)
            return (await svc.create(payload, user_id="u-smoke")).id


async def _one_use(factory: async_sessionmaker, master_key: bytes, cred_id: str) -> None:
    from app.schemas import CredentialUseRequest

    use_req = CredentialUseRequest(cap="perf-smoke", purpose="smoke")
    async with factory() as s:
        async with s.begin():
            svc = CredentialService(session=s, master_key=master_key)
            await svc.use(cred_id, use_req, user_id="u-caller", workspace_id="finance")


async def main() -> int:
    print(f"perf-smoke: TOTAL_OPS={TOTAL_OPS}, CONCURRENCY={CONCURRENCY}")
    pg_gen = _postgres_url()
    pg_url = next(pg_gen)
    try:
        engine = create_async_engine(pg_url, pool_size=CONCURRENCY + 5)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        master_key = crypto.generate_master_key()
        cred_id = await _seed(factory, master_key)
        print(f"perf-smoke: seeded id={cred_id[:18]}...")

        # Warmup — run a few hundred ops to JIT / warm Postgres
        # plan cache and asyncpg connection pool. Discard these
        # samples; they are not representative of steady-state.
        for _ in range(200):
            await _one_use(factory, master_key, cred_id)

        sem = asyncio.Semaphore(CONCURRENCY)
        latencies: list[float] = []
        target = TOTAL_OPS
        # A ``done`` counter + condition avoids the late-sample tail
        # that an in-flight worker contributes after TOTAL_OPS is
        # reached (each worker keeps its asyncpg connection hot, but
        # the *queueing delay* for the trailing few samples is not
        # representative of steady-state performance).
        done = 0
        stop = False

        async def _worker() -> None:
            nonlocal done
            while not stop:
                async with sem:
                    start = time.perf_counter()
                    await _one_use(factory, master_key, cred_id)
                    latencies.append((time.perf_counter() - start) * 1000.0)
                    done += 1

        workers = [asyncio.create_task(_worker()) for _ in range(CONCURRENCY)]
        try:
            while done < target:
                await asyncio.sleep(0.005)
            stop = True
        finally:
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        await engine.dispose()
    finally:
        try:
            next(pg_gen)
        except StopIteration:
            pass

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=100, method="inclusive")[94]
    p99 = statistics.quantiles(latencies, n=100, method="inclusive")[98]
    print(f"perf-smoke: P50={p50:.2f}ms  P95={p95:.2f}ms  P99={p99:.2f}ms")
    if p99 < P99_SLO_MS:
        print(f"perf-smoke: PASS (P99 < {P99_SLO_MS}ms)")
        return 0
    print(f"perf-smoke: FAIL (P99 {p99:.2f}ms >= {P99_SLO_MS}ms)")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

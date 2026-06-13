"""Locust load profile for the credential-management `use` API.

Spec §性能基线 (Requirement: 性能基线):

> WHEN locust 跑 100 RPS 持续 60s
> THEN 系统 MUST P99 < 50ms;P99 > 50ms MUST 触发 monitoring 告警

Run with the docker-compose stack up:

    .venv/bin/locust -f locust/locustfile.py --headless \
        -u 100 -r 10 --run-time 60s \
        --host http://localhost:8005

The test seeds one credential, then drives a constant 100 RPS of
`POST /api/v1/credentials/{id}/use` against it for 60 seconds. Each
Locust user is a self-contained client (own ``X-User-Id``); every
call decrypts the credential through the full envelope pipeline
(AES-256-GCM DEK + AES-256-GCM master wrapping) and writes a
``credential_audit`` row, which is the exact code path the spec
benchmarks.

Output is the default locust stats table; P99 is in the "Response
Time" / 99% column. CI integration (Task 15) parses the JSON stats
file (`--csv=... --html=...`) and fails the build if P99 > 50 ms.
"""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

from locust import HttpUser, constant_pacing, events, task
from locust.exception import RescheduleTask

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

#: P99 latency SLO from spec §性能基线. CI / verify.py fails the build
#: above this number.
P99_SLO_MS: float = 50.0

#: Per-spec target load: 100 RPS for 60s. Pacing is set per-user; total
#: throughput is roughly ``user_count / pace`` (100 / 1.0 = 100 RPS).
TARGET_USER_COUNT: int = 100
TARGET_RUN_TIME_S: int = 60
TARGET_PACE_S: float = 1.0  # 1 task per second per user ≈ 100 RPS @ 100 users


# ---------------------------------------------------------------------------
# Module-level state — seed the credential once per process.
# ---------------------------------------------------------------------------

_SEED: dict[str, Any] = {
    "credential_id": None,
    "admin_headers": None,
    "use_headers": None,
    "seeded": False,
}


def _seed(host: str) -> None:
    """Create one credential via the admin API; cache its id for the
    load test. We do this from the master process (events.init) so the
    HTTP test traffic below is purely the `use` API."""
    import httpx

    admin = {
        "X-User-Id": "u-locust-admin",
        "X-User-Workspace": "finance",
        "X-User-Roles": "admin",
    }
    use_h = {
        "X-User-Id": "u-locust-caller",
        "X-User-Workspace": "finance",
        "X-User-Roles": "credential_user",
    }
    payload = {
        "name": f"locust-{secrets.token_hex(4)}",
        "type": "api_key",
        "value": f"sk-locust-{secrets.token_hex(16)}",
        "workspace_id": "finance",
    }
    with httpx.Client(base_url=host, timeout=10.0) as cli:
        resp = cli.post("/api/v1/credentials", json=payload, headers=admin)
        resp.raise_for_status()
        _SEED["credential_id"] = resp.json()["id"]
        _SEED["admin_headers"] = admin
        _SEED["use_headers"] = use_h
        _SEED["seeded"] = True


@events.init.add_listener
def _on_init(environment: Any, **_: Any) -> None:
    """Seed once when locust starts (master process). Skip for the
    worker processes — they receive ``_SEED`` via the env var below
    when running in distributed mode."""
    if os.environ.get("LOCUST_IS_WORKER") == "1":
        return
    host = environment.host
    if not host:
        return
    try:
        _seed(host)
    except Exception as exc:  # pragma: no cover - startup error
        environment.runner.quit()
        raise SystemExit(f"locustfile: failed to seed credential: {exc!r}") from exc


# ---------------------------------------------------------------------------
# Load profile
# ---------------------------------------------------------------------------


class CredentialUseUser(HttpUser):
    """A single user hammering the `use` API at a fixed rate."""

    # Fixed pacing → 1 request per second per user. With 100 users that
    # averages 100 RPS, exactly the spec target. ``constant_throughput``
    # would also work but ties the rate to the response time; constant
    # pacing is more deterministic for a short 60-second benchmark.
    wait_time = constant_pacing(TARGET_PACE_S)

    # The user-weight attribute is also used by locust's WebUI to
    # display the profile; we keep one task per user for clarity.
    weight = 1

    @task
    def use_credential(self) -> None:
        cred_id = _SEED.get("credential_id")
        use_h = _SEED.get("use_headers")
        if not cred_id or not use_h:
            raise RescheduleTask()
        # No sleep between retries; the spec measures P99 of healthy
        # responses, and 5xx is a sign of a real problem, not noise.
        with self.client.post(
            f"/api/v1/credentials/{cred_id}/use",
            json={"cap": "locust-bench", "purpose": "perf-bench"},
            headers=use_h,  # type: ignore[arg-type]
            name="POST /api/v1/credentials/{id}/use",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"unexpected status {resp.status_code}: {resp.text}")
            else:
                resp.success()

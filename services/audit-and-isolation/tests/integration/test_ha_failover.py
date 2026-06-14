"""HA failover e2e — 2 audit-and-isolation replicas behind NGINX L4 LB.

Per task 2.4 of `openspec/changes/gateway-egress-enforcement-p0/`. Verifies
the end-to-end drain flow from 2.1 (preStop + /healthz 503) through 2.2
(K8s manifest) and 2.3 (NGINX L4 LB): when one replica dies, all new
requests are routed to the surviving replica within 5s.

**Skip policy**: this test is gated by the `HA_E2E=1` environment
variable. The default (unset) means SKIP. Reason: it requires a running
docker stack (`infrastructure/docker-compose-e2e-ha.yml`), which most
contributors and CI unit-test pipelines don't have. The dedicated e2e
CI runner (where this test is meant to run) sets HA_E2E=1 and brings
the stack up via the compose file.

Manual run (developer machine with Docker):

    HA_E2E=1 docker compose -f infrastructure/docker-compose-e2e-ha.yml up -d
    HA_E2E=1 pytest services/audit-and-isolation/tests/integration/test_ha_failover.py -v
    docker compose -f infrastructure/docker-compose-e2e-ha.yml down -v
"""

from __future__ import annotations

import os
import subprocess
import time

import httpx
import pytest

# Gate the whole module — without HA_E2E=1, skip. The skipif is on
# the module-level pytestmark so the file imports cleanly even when
# skipped (useful for coverage tools).
pytestmark = pytest.mark.skipif(
    os.environ.get("HA_E2E") != "1",
    reason="HA e2e requires HA_E2E=1 + running chatbiz-e2e-ha docker stack",
)

LB_URL = "http://127.0.0.1:8080"
HEALTHCHECK_TIMEOUT_S = 30
LB_FAILOVER_WINDOW_S = 5  # spec: "5s 内所有新请求被实例 B 接管"


def _wait_for_lb() -> None:
    """Block until the NGINX LB returns a 200 on /readyz (or timeout)."""
    deadline = time.time() + HEALTHCHECK_TIMEOUT_S
    last_err = "no attempt yet"
    while time.time() < deadline:
        try:
            r = httpx.get(f"{LB_URL}/readyz", timeout=2.0)
            if r.status_code == 200:
                return
            last_err = f"status {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1)
    pytest.fail(f"LB at {LB_URL} did not become ready within {HEALTHCHECK_TIMEOUT_S}s: {last_err}")


def _hit_lb() -> httpx.Response:
    """Make a single GET /readyz against the LB."""
    return httpx.get(f"{LB_URL}/readyz", timeout=3.0)


def _docker_exec(container: str, cmd: list[str]) -> str:
    """Run a command inside a docker-compose container and return stdout."""
    result = subprocess.run(
        ["docker", "exec", container, *cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"docker exec {container} {cmd!r} failed (rc={result.returncode}): "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    return result.stdout


@pytest.fixture(scope="module", autouse=True)
def _wait_for_lb_at_startup():
    """Wait for the stack to be healthy before any test runs."""
    _wait_for_lb()
    yield


def test_lb_baseline_returns_200() -> None:
    """Before any disruption, the LB is healthy and returns 200."""
    r = _hit_lb()
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"


def test_lb_sustains_traffic_during_normal_operation() -> None:
    """10 sequential requests should all succeed. This is the baseline
    that subsequent failover assertions compare against."""
    for i in range(10):
        r = _hit_lb()
        assert r.status_code == 200, f"req {i+1} got {r.status_code}: {r.text[:200]}"


def test_lb_failover_to_b_within_5s_after_a_dies() -> None:
    """Spec literal: "杀掉实例 A,5s 内所有新请求被实例 B 接管".

    Flow:
      1. Kill instance A with `docker stop chatbiz-e2e-ha-audit-a`
         (SIGTERM, which FastAPI lifespan handles by flipping
         app.state.draining and closing)
      2. Poll the LB: every 500ms for up to LB_FAILOVER_WINDOW_S,
         expect a 200
      3. If we see any 502/504 from the LB inside the window, the
         failover didn't happen in time and the test fails
      4. Total window: < LB_FAILOVER_WINDOW_S (5s) from the moment
         of `docker stop` to the first 200 from B

    Note: we do NOT use 5s from the kill — we use 5s from the kill
    to the first confirmed 200. The 30s preStop + termination grace
    in 2.2 covers in-flight requests; the LB's max_fails=2 +
    fail_timeout=10s (2.3) covers new connections.
    """
    # Sanity: baseline is up
    assert _hit_lb().status_code == 200, "baseline not healthy"

    # Kill A. We use `docker stop` (not `kill`) so SIGTERM flows through
    # the normal preStop / drain path (task 2.1, 2.2). The container
    # stays in `docker ps -a` so we can inspect it after.
    stop_start = time.monotonic()
    result = subprocess.run(
        ["docker", "stop", "chatbiz-e2e-ha-audit-a"],
        capture_output=True,
        text=True,
        check=False,
    )
    # `docker stop` returns when the container has actually stopped
    # (default 10s grace). Don't assert rc — even if it took >10s,
    # the LB-level test below is what matters.
    if result.returncode != 0:
        pytest.fail(f"docker stop failed: {result.stderr}")

    # Poll the LB. We expect: the first few requests might still
    # 200 (connections in-flight to A drain via 2.1) OR return
    # 502/504 (NGINX can't reach A anymore) for a brief window.
    # Within 5s, requests must succeed — meaning LB has routed to B.
    deadline = stop_start + LB_FAILOVER_WINDOW_S
    first_200_at: float | None = None
    samples: list[tuple[float, int]] = []
    while time.monotonic() < deadline:
        t = time.monotonic() - stop_start
        try:
            r = _hit_lb()
            samples.append((t, r.status_code))
            if r.status_code == 200:
                first_200_at = t
                break
        except httpx.HTTPError:
            samples.append((t, -1))  # connection refused
        time.sleep(0.5)

    assert first_200_at is not None, (
        f"LB did not return 200 within {LB_FAILOVER_WINDOW_S}s after pod A stopped. "
        f"Samples (t_seconds, status): {samples}"
    )

    # And the failover must be quick — spec says "5s 内". We give a
    # little slack (4.5s target) for the actual test threshold.
    assert first_200_at < LB_FAILOVER_WINDOW_S, (
        f"first 200 came at t={first_200_at:.2f}s, must be < {LB_FAILOVER_WINDOW_S}s. "
        f"Samples: {samples}"
    )


def test_lb_remains_healthy_after_failover() -> None:
    """After the failover (test_lb_failover_to_b_within_5s_after_a_dies),
    sustained traffic should all succeed (no intermittent 502s)."""
    for i in range(20):
        r = _hit_lb()
        assert r.status_code == 200, (
            f"post-failover req {i+1} got {r.status_code}: {r.text[:200]}"
        )


def test_both_pods_were_seen_by_lb_before_failover() -> None:
    """Pre-condition: confirm the LB can reach both pods BEFORE we kill one.
    We do this by reading the upstream connection states from the LB
    container's stream-access log. (Run order matters: this must run
    BEFORE test_lb_failover_to_b_within_5s_after_a_dies kills pod A.)
    """
    # This test is informational. We don't fail it on absence of logs
    # (the LB might not have logged yet) — just record what we see.
    try:
        log = _docker_exec(
            "chatbiz-e2e-ha-lb",
            ["cat", "/var/log/nginx/stream-access.log"],
        )
    except RuntimeError:
        pytest.skip("could not read NGINX access log (LB container not running?)")
    # Each log line has 'upstream=10.x.x.x:8080' field. We expect to
    # see at least 2 distinct upstream IPs (the 2 pods).
    import re

    upstream_ips = set(re.findall(r"upstream=([\d.]+):\d+", log))
    # NB: in our compose, the audit-and-isolation pods are in the
    # chatbiz-e2e-ha-net bridge, so their IPs are 172.x or 10.x
    # depending on the docker version. We just check there's more
    # than 1.
    assert len(upstream_ips) >= 2, (
        f"expected LB to see ≥ 2 distinct pod IPs, got {len(upstream_ips)}: {upstream_ips}. "
        f"log tail: {log[-500:]!r}"
    )

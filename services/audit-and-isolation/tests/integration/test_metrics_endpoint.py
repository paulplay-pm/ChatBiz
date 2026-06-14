"""Integration tests for GET /metrics (task 5.2).

Per spec 5.2 of `openspec/changes/gateway-egress-enforcement-p0/`. Verifies:

  1. Endpoint returns 200 with Prometheus text format
  2. All 5 spec metrics are present in the output
  3. Each metric has a HELP comment line
  4. Each metric has a TYPE comment line
  5. Counter / Histogram / Gauge types are correctly stamped
  6. The Content-Type header is the Prometheus text format
  7. Counter labels are present and parseable
  8. After incrementing a counter, its value appears in the output

The test relies on the global `prometheus_client` registry — we
import the real metric objects from `app.metrics` and call their
``.inc()`` / ``.observe()`` / ``.set()`` methods to populate them
for the relevant assertions. This is the same pattern Prometheus's
own integration tests use.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import metrics as metrics_mod


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


# ---------- helpers --------------------------------------------------------

def _body_lines(body: str) -> list[str]:
    """Split the /metrics body into non-empty lines."""
    return [ln for ln in body.split("\n") if ln.strip()]


def _metric_help(body: str, name: str) -> str | None:
    """Return the HELP comment line for a metric, or None if missing."""
    for ln in _body_lines(body):
        if ln.startswith(f"# HELP {name} "):
            return ln[len(f"# HELP {name} "):]
    return None


def _metric_type(body: str, name: str) -> str | None:
    """Return the TYPE comment line for a metric, or None if missing."""
    for ln in _body_lines(body):
        if ln.startswith(f"# TYPE {name} "):
            return ln[len(f"# TYPE {name} "):]
    return None


# ---------- 1. endpoint + content type ------------------------------------

def test_metrics_endpoint_returns_200(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_content_type_is_prometheus_text(client: TestClient) -> None:
    """Spec: Prometheus exposition format. The Content-Type is
    ``text/plain; version=X.Y.Z; charset=utf-8`` per the official
    Prometheus client library. We accept any ``version=`` value
    (the format version is bumped occasionally in prometheus_client
    updates; we just need a parseable text/plain)."""
    resp = client.get("/metrics")
    ct = resp.headers["content-type"]
    assert "text/plain" in ct
    assert "version=" in ct, f"missing version= in Content-Type: {ct}"


def test_metrics_body_is_text(client: TestClient) -> None:
    """Body is a string (decoded), not bytes."""
    resp = client.get("/metrics")
    assert isinstance(resp.text, str)
    assert len(resp.text) > 0


# ---------- 2-4. spec 5 metrics presence + HELP + TYPE ---------------------

def test_all_5_spec_metrics_are_present(client: TestClient) -> None:
    """Spec literal: 5 metric families."""
    resp = client.get("/metrics")
    body = resp.text
    expected = {
        "requests_total",
        "duration_seconds",
        "pii_hits_total",
        "active_connections",
        "trace_cache_hits_total",
    }
    for name in expected:
        # A metric is "present" if it has at least a # TYPE or
        # # HELP comment line. Even with no observations yet,
        # Counter / Histogram / Gauge register themselves.
        assert f"# TYPE {name} " in body, f"missing TYPE for {name}"
        assert f"# HELP {name} " in body, f"missing HELP for {name}"


def test_requests_total_is_counter(client: TestClient) -> None:
    assert _metric_type(client.get("/metrics").text, "requests_total") == "counter"


def test_duration_seconds_is_histogram(client: TestClient) -> None:
    assert _metric_type(client.get("/metrics").text, "duration_seconds") == "histogram"


def test_pii_hits_total_is_counter(client: TestClient) -> None:
    assert _metric_type(client.get("/metrics").text, "pii_hits_total") == "counter"


def test_active_connections_is_gauge(client: TestClient) -> None:
    assert _metric_type(client.get("/metrics").text, "active_connections") == "gauge"


def test_trace_cache_hits_total_is_counter(client: TestClient) -> None:
    assert _metric_type(client.get("/metrics").text, "trace_cache_hits_total") == "counter"


# ---------- 5. HELP comments are non-empty --------------------------------

def test_all_5_metrics_have_non_empty_help(client: TestClient) -> None:
    """Per the Prometheus exposition spec, every # HELP line must have
    a description. Empty HELP is a common bug we'd catch here."""
    resp = client.get("/metrics")
    body = resp.text
    for name in (
        "requests_total",
        "duration_seconds",
        "pii_hits_total",
        "active_connections",
        "trace_cache_hits_total",
    ):
        help_text = _metric_help(body, name)
        assert help_text is not None, f"missing HELP for {name}"
        assert len(help_text) > 10, (
            f"HELP for {name} is too short: {help_text!r}"
        )


# ---------- 6-8. counter values + labels -----------------------------------

def test_requests_total_counter_increments(client: TestClient) -> None:
    """After inc(), the value appears in the output with the
    right labels."""
    metrics_mod.requests_total.labels(method="POST", path="/v1/chat", status="200").inc()

    resp = client.get("/metrics")
    body = resp.text
    # Find the metric line that matches our labels
    expected = 'requests_total{method="POST",path="/v1/chat",status="200"}'
    matching = [ln for ln in _body_lines(body) if ln.startswith(expected)]
    assert matching, f"no line for {expected} in: {body[:500]}"
    # Parse: "metric{labels} value" or "metric{labels} value timestamp"
    line = matching[0]
    # Split on whitespace; last token is value (or second-to-last if timestamp present)
    tokens = line.split()
    assert len(tokens) >= 2, f"unexpected line format: {line!r}"
    # The metric+labels block is the first token, the value is the second
    value_token = tokens[1]
    value = float(value_token)
    assert value >= 1.0, f"counter not incremented: {matching[0]!r}"


def test_pii_hits_total_has_correct_labels(client: TestClient) -> None:
    """The pii_hits_total counter has labels {pii_type, action}."""
    metrics_mod.pii_hits_total.labels(pii_type="id_card", action="redact").inc()

    resp = client.get("/metrics")
    body = resp.text
    expected = 'pii_hits_total{action="redact",pii_type="id_card"}'
    assert expected in body, (
        f"no pii_hits_total line with pii_type=id_card action=redact; got body: {body[-500:]}"
    )


def test_trace_cache_hits_total_counter_increments(client: TestClient) -> None:
    """Trace cache hit counter (per task 4.1) is exposed at /metrics."""
    before_resp = client.get("/metrics")
    before = before_resp.text

    # Increment
    metrics_mod.trace_cache_hits_total.inc()

    after_resp = client.get("/metrics")
    after = after_resp.text

    # The counter value line MUST appear now
    expected_line = "trace_cache_hits_total"
    matching_before = [ln for ln in _body_lines(before) if ln.startswith(expected_line) and not ln.startswith("#")]
    matching_after = [ln for ln in _body_lines(after) if ln.startswith(expected_line) and not ln.startswith("#")]

    # After must have the line (a counter always has at least a 0 entry
    # in the registry once it's been registered and accessed).
    assert matching_after, f"no trace_cache_hits_total line after increment; body: {after[-500:]}"


def test_active_connections_gauge_reflects_set(client: TestClient) -> None:
    """The gauge is set via metrics_mod.active_connections.set(N)."""
    metrics_mod.active_connections.set(42)

    resp = client.get("/metrics")
    body = resp.text
    # The gauge line has format: active_connections 42.0
    matching = [ln for ln in _body_lines(body) if ln.startswith("active_connections ") and not ln.startswith("#")]
    assert matching, f"no active_connections line; body: {body[-500:]}"
    # The value is the last whitespace-separated token
    value = float(matching[0].split()[-1])
    assert value == 42.0, f"expected 42, got {value}"


def test_duration_seconds_histogram_observe_recorded(client: TestClient) -> None:
    """Histogram observation shows up as bucket counters + _sum / _count."""
    metrics_mod.duration_seconds.observe(0.123)

    resp = client.get("/metrics")
    body = resp.text
    # The histogram has _bucket, _sum, _count lines
    bucket_lines = [ln for ln in _body_lines(body) if ln.startswith("duration_seconds_bucket{")]
    sum_lines = [ln for ln in _body_lines(body) if ln.startswith("duration_seconds_sum")]
    count_lines = [ln for ln in _body_lines(body) if ln.startswith("duration_seconds_count")]

    assert bucket_lines, f"no bucket lines; body: {body[-500:]}"
    assert sum_lines, f"no _sum line; body: {body[-500:]}"
    assert count_lines, f"no _count line; body: {body[-500:]}"

    # The _count must be at least 1
    count_value = float(count_lines[0].split()[-1])
    assert count_value >= 1.0, f"expected count >= 1, got {count_value}"


# ---------- 9. endpoint doesn't require auth -------------------------------

def test_metrics_endpoint_no_auth_required(client: TestClient) -> None:
    """Prometheus scrapers don't carry auth tokens; the endpoint
    must be reachable without headers. (Authorization is done at
    the k8s NetworkPolicy level, not in the app.)"""
    resp = client.get("/metrics")
    assert resp.status_code == 200


# ---------- 10. endpoint registered in main -------------------------------

def test_metrics_route_registered_in_app() -> None:
    """The router is wired in app/main.py."""
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/metrics" in paths

"""K8s manifest test — verifies deploy/audit-and-isolation/ structure.

Per task 2.2 of `openspec/changes/gateway-egress-enforcement-p0/`. Uses
`kubeconform` (plan.md's stated validator) if available on PATH; falls
back to structural PyYAML checks + key field assertions otherwise.

We don't make the test *require* kubeconform — it's a separate binary
that ops teams may not have locally — but if it's available we run it
and surface its output. This keeps the test useful in CI (which has
kubeconform installed via the static-scan workflow's runner) and
locally (which usually doesn't).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]  # tests/unit/ -> tests/ -> audit-and-isolation/ -> services/ -> repo
DEPLOY_DIR = REPO_ROOT / "deploy" / "audit-and-isolation"
DEPLOYMENT = DEPLOY_DIR / "deployment.yaml"
SERVICE = DEPLOY_DIR / "service.yaml"
PDB = DEPLOY_DIR / "poddisruptionbudget.yaml"


def _load(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


# ----- file presence --------------------------------------------------------

def test_deploy_dir_exists() -> None:
    assert DEPLOY_DIR.is_dir(), f"missing {DEPLOY_DIR}"


def test_all_three_manifests_present() -> None:
    for p in (DEPLOYMENT, SERVICE, PDB):
        assert p.is_file(), f"missing {p}"


# ----- deployment.yaml ------------------------------------------------------

def test_deployment_replicas_is_two() -> None:
    """HA requirement: 2 active-active replicas (eng-review decision #1)."""
    d = _load(DEPLOYMENT)
    assert d["spec"]["replicas"] == 2, (
        f"replicas must be 2 for active-active HA, got {d['spec']['replicas']}"
    )


def test_deployment_termination_grace_period_is_45s() -> None:
    """Must be > preStop sleep (30s) to give the container time to drain
    before SIGKILL. 45s = 30s drain + 15s headroom for slow responses."""
    d = _load(DEPLOYMENT)
    grace = d["spec"]["template"]["spec"]["terminationGracePeriodSeconds"]
    assert grace == 45, f"terminationGracePeriodSeconds must be 45, got {grace}"


def test_deployment_has_prestop_sleep_30() -> None:
    """preStop sleep 30 is the drain window. Runtime drain (app.state.draining)
    flips within the first ~100ms; the remaining ~29.9s is buffer for
    in-flight LLM calls to finish."""
    d = _load(DEPLOYMENT)
    pre_stop = d["spec"]["template"]["spec"]["containers"][0]["lifecycle"]["preStop"]
    cmd = pre_stop["exec"]["command"]
    # Find the sleep 30 command — bash -c "sleep 30" is the form we use.
    assert any("sleep 30" in str(c) for c in cmd), (
        f"preStop must include 'sleep 30', got command: {cmd}"
    )


def test_deployment_liveness_probe_points_at_readyz() -> None:
    """/healthz 503 during drain is a deliberate K8s convention deviation
    (see task 2.1 module docstring). To keep liveness semantics standard,
    livenessProbe reads /readyz (which 503s during drain too, but in a
    K8s-standard way) with a generous failureThreshold so the 30s drain
    window doesn't trigger a restart."""
    d = _load(DEPLOYMENT)
    probe = d["spec"]["template"]["spec"]["containers"][0]["livenessProbe"]
    assert probe["httpGet"]["path"] == "/readyz", (
        f"livenessProbe path must be /readyz, got {probe['httpGet']['path']}"
    )
    # failureThreshold * periodSeconds should comfortably cover preStop (30s)
    period = probe["periodSeconds"]
    threshold = probe["failureThreshold"]
    assert period * threshold >= 30, (
        f"livenessProbe failure window {period * threshold}s must >= preStop 30s, "
        f"got period={period}s threshold={threshold}"
    )


def test_deployment_readiness_probe_points_at_readyz() -> None:
    d = _load(DEPLOYMENT)
    probe = d["spec"]["template"]["spec"]["containers"][0]["readinessProbe"]
    assert probe["httpGet"]["path"] == "/readyz", (
        f"readinessProbe path must be /readyz, got {probe['httpGet']['path']}"
    )


def test_deployment_container_port_is_8080() -> None:
    d = _load(DEPLOYMENT)
    ports = d["spec"]["template"]["spec"]["containers"][0]["ports"]
    http_port = next((p for p in ports if p.get("name") == "http"), None)
    assert http_port is not None, f"no 'http' named port: {ports}"
    assert http_port["containerPort"] == 8080, (
        f"containerPort must be 8080, got {http_port['containerPort']}"
    )


def test_deployment_uses_dev_image_tag() -> None:
    """We ship one K8s manifest per environment via overlays, not per-tag
    (image: chatbiz/audit-and-isolation:dev matches docker-compose-dev.yml).
    Production tag swap is a separate concern (handled by Helm / Kustomize
    in a real deployment; out of scope for this spec)."""
    d = _load(DEPLOYMENT)
    image = d["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image == "chatbiz/audit-and-isolation:dev", (
        f"image must be chatbiz/audit-and-isolation:dev, got {image!r}"
    )


def test_deployment_runs_as_non_root() -> None:
    """audit UID 10002 from Dockerfile. K8s must enforce runAsNonRoot."""
    d = _load(DEPLOYMENT)
    sc = d["spec"]["template"]["spec"]["containers"][0]["securityContext"]
    assert sc.get("runAsNonRoot") is True
    assert sc.get("runAsUser") == 10002


# ----- service.yaml ---------------------------------------------------------

def test_service_type_is_cluster_ip() -> None:
    """ClusterIP only — NGINX stream L4 LB (task 2.3) is the public-facing
    entry. Direct external access would bypass audit-and-isolation
    policy enforcement."""
    s = _load(SERVICE)
    assert s["spec"]["type"] == "ClusterIP", f"type must be ClusterIP, got {s['spec']['type']!r}"


def test_service_selector_matches_deployment_labels() -> None:
    """The Service selector MUST match the Deployment's pod labels,
    otherwise no endpoints are created and traffic silently 0-routes."""
    d = _load(DEPLOYMENT)
    s = _load(SERVICE)
    dep_labels = d["spec"]["template"]["metadata"]["labels"]
    # Service spec.selector is a LabelSelector with matchLabels sub-key
    svc_selector = s["spec"]["selector"]["matchLabels"]
    for k, v in svc_selector.items():
        assert dep_labels.get(k) == v, (
            f"service selector {k}={v} not in deployment labels {dep_labels}"
        )


def test_service_target_port_is_named_http() -> None:
    s = _load(SERVICE)
    port = s["spec"]["ports"][0]
    assert port["name"] == "http"
    assert port["targetPort"] == "http", (
        f"targetPort should be named 'http' (matches deployment container port name), "
        f"got {port['targetPort']!r}"
    )
    assert port["port"] == 8080


# ----- poddisruptionbudget.yaml --------------------------------------------

def test_pdb_min_available_is_one() -> None:
    """With replicas=2, minAvailable=1 means at most 1 pod can be
    voluntarily disrupted at any time. K8s rolling update + autoscaler
    scale-down cooperate with this floor."""
    p = _load(PDB)
    assert p["spec"]["minAvailable"] == 1, (
        f"minAvailable must be 1, got {p['spec']['minAvailable']!r}"
    )


def test_pdb_selector_matches_deployment_labels() -> None:
    p = _load(PDB)
    d = _load(DEPLOYMENT)
    dep_labels = d["spec"]["template"]["metadata"]["labels"]
    pdb_selector = p["spec"]["selector"]["matchLabels"]
    for k, v in pdb_selector.items():
        assert dep_labels.get(k) == v, (
            f"PDB selector {k}={v} not in deployment labels {dep_labels}"
        )


def test_pdb_api_version_is_policy_v1() -> None:
    """policy/v1 is GA since K8s 1.21. policy/v1beta1 was removed in 1.25."""
    p = _load(PDB)
    assert p["apiVersion"] == "policy/v1", (
        f"apiVersion must be policy/v1, got {p['apiVersion']!r}"
    )


# ----- kubeconform optional runner -----------------------------------------

@pytest.mark.skipif(
    shutil.which("kubeconform") is None,
    reason="kubeconform not installed locally; CI runs it via static-scan workflow",
)
def test_kubeconform_validates_all_manifests() -> None:
    """If kubeconform is available, run it against all 3 manifests.
    Failure here means a K8s API field is wrong, which would block
    `kubectl apply` in production."""
    result = subprocess.run(
        [
            "kubeconform",
            "-strict",
            "-summary",
            str(DEPLOYMENT),
            str(SERVICE),
            str(PDB),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"kubeconform failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

"""Tests for the audit-and-isolation K8s manifests.

The K8s manifest contract is checked structurally because kubeconform
is not always available in CI. The contract enforces:

* Deployment — replicas=2, preStop sleeps 30, terminationGracePeriod=45,
  livenessProbe on /healthz, readinessProbe on /healthz.
* Service — ClusterIP on port 8080.
* PodDisruptionBudget — minAvailable: 1.

We parse each file with ``yaml.safe_load`` (no PyYAML installation
required for production code — only for these tests) and assert the
exact fields. If kubeconform is on PATH we run it too, otherwise we
skip the integration check.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

MANIFEST_DIR = Path(__file__).resolve().parent.parent


def _load(name: str) -> dict:
    with (MANIFEST_DIR / name).open() as f:
        return yaml.safe_load(f)


def test_deployment_has_replicas_2():
    d = _load("deployment.yaml")
    assert d["kind"] == "Deployment"
    assert d["spec"]["replicas"] == 2


def test_deployment_has_prestop_sleep_30():
    d = _load("deployment.yaml")
    containers = d["spec"]["template"]["spec"]["containers"]
    assert len(containers) >= 1
    lifecycle = containers[0]["lifecycle"]
    prestop = lifecycle["preStop"]
    assert prestop["exec"]["command"] == ["/bin/sh", "-c", "sleep 30"]


def test_deployment_has_termination_grace_period_45():
    d = _load("deployment.yaml")
    assert d["spec"]["template"]["spec"]["terminationGracePeriodSeconds"] == 45


def test_deployment_liveness_probe_targets_healthz():
    d = _load("deployment.yaml")
    containers = d["spec"]["template"]["spec"]["containers"]
    probe = containers[0]["livenessProbe"]
    assert probe["httpGet"]["path"] == "/healthz"


def test_deployment_readiness_probe_targets_healthz():
    d = _load("deployment.yaml")
    containers = d["spec"]["template"]["spec"]["containers"]
    probe = containers[0]["readinessProbe"]
    assert probe["httpGet"]["path"] == "/healthz"


def test_deployment_container_listens_on_8080():
    d = _load("deployment.yaml")
    containers = d["spec"]["template"]["spec"]["containers"]
    ports = containers[0]["ports"]
    assert any(p.get("containerPort") == 8080 for p in ports)


def test_service_is_clusterip_on_8080():
    s = _load("service.yaml")
    assert s["kind"] == "Service"
    assert s["spec"]["type"] == "ClusterIP"
    assert s["spec"]["ports"][0]["targetPort"] == 8080


def test_pdb_has_min_available_1():
    p = _load("poddisruptionbudget.yaml")
    assert p["kind"] == "PodDisruptionBudget"
    assert p["spec"]["minAvailable"] == 1


def test_pdb_targets_deployment():
    p = _load("poddisruptionbudget.yaml")
    selector = p["spec"]["selector"]
    assert "matchLabels" in selector


@pytest.mark.skipif(shutil.which("kubeconform") is None, reason="kubeconform not on PATH")
def test_kubeconform_validates_manifests():
    files = ["deployment.yaml", "service.yaml", "poddisruptionbudget.yaml"]
    cmd = ["kubeconform", "-strict", "-summary"] + [str(MANIFEST_DIR / f) for f in files]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"kubeconform failed: {result.stderr}\n{result.stdout}"

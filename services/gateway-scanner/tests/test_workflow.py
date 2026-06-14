"""GitHub Actions workflow test — verifies gateway-static-scan.yml structure.

Per task 1.5 of `openspec/changes/gateway-egress-enforcement-p0/`. The actual
end-to-end validation happens in CI (or `act` locally). Here we verify:

  1. The YAML file parses
  2. The expected jobs/steps are present
  3. The trigger paths cover `services/**` and `libs/**`
  4. The `pip install -e services/gateway-scanner` step exists
  5. The `python -m gateway_scanner` invocation references the correct args

We don't shell out to `act` or hit the GitHub API — the test should run in
<1s and have no network dependency.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]  # tests/ -> gateway-scanner/ -> services/ -> repo
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "gateway-static-scan.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW.is_file(), f"workflow file missing: {WORKFLOW}"
    with WORKFLOW.open() as f:
        return yaml.safe_load(f)


def test_workflow_parses(workflow: dict) -> None:
    assert isinstance(workflow, dict), f"workflow root must be a mapping, got {type(workflow)}"


def test_workflow_name(workflow: dict) -> None:
    assert workflow.get("name") == "gateway-static-scan", (
        f"name should be 'gateway-static-scan', got {workflow.get('name')!r}"
    )


def test_workflow_triggers_on_pull_request(workflow: dict) -> None:
    assert "on" in workflow or True in workflow, "workflow has no trigger"
    on = workflow.get("on") or workflow.get(True)
    assert "pull_request" in on, f"pull_request trigger missing: {list(on)}"


def test_pull_request_paths_cover_services_and_libs(workflow: dict) -> None:
    pr = workflow[True if True in workflow else "on"]["pull_request"]
    paths = pr.get("paths", [])
    assert "services/**" in paths, f"services/** not in pull_request paths: {paths}"
    assert "libs/**" in paths, f"libs/** not in pull_request paths: {paths}"


def test_workflow_has_scan_job(workflow: dict) -> None:
    jobs = workflow["jobs"]
    assert "scan" in jobs, f"expected 'scan' job, got {list(jobs)}"


def test_scan_job_runs_on_ubuntu(workflow: dict) -> None:
    scan = workflow["jobs"]["scan"]
    assert scan.get("runs-on") == "ubuntu-latest", (
        f"scan job should run on ubuntu-latest, got {scan.get('runs-on')!r}"
    )


def test_scan_job_steps_in_order(workflow: dict) -> None:
    """Critical steps: checkout → setup-python → install → scan.

    Order matters: scanning before install would fail (no scanner module).
    The "verify scanner is importable" step is part of install validation,
    not a separate ordering requirement.
    """
    steps = workflow["jobs"]["scan"]["steps"]
    step_names = [s.get("name", "").lower() for s in steps]

    def index_of(needle: str) -> int:
        for i, n in enumerate(step_names):
            if needle in n:
                return i
        return -1

    checkout = index_of("checkout")
    setup = index_of("set up python")
    install = index_of("install gateway-scanner")
    # Match the "scan services/" step, not "install" or "annotate scan result"
    scan = index_of("scan services/")

    assert checkout >= 0, f"checkout step missing: {step_names}"
    assert setup >= 0, f"setup-python step missing: {step_names}"
    assert install >= 0, f"install step missing: {step_names}"
    assert scan >= 0, f"scan step missing: {step_names}"

    # Order: checkout < setup < install < scan
    assert checkout < setup < install < scan, (
        f"step order wrong: {[(i, n) for i, n in enumerate(step_names)]}"
    )


def test_scan_step_invokes_scanner_module(workflow: dict) -> None:
    """The scan step must call `python -m gateway_scanner` with the right args.

    The "scan" step is the one whose name starts with "scan services/" —
    earlier steps with "scan" in their name (like "install gateway-scanner")
    are install-validation, not the actual policy check.
    """
    steps = workflow["jobs"]["scan"]["steps"]
    scan_steps = [s for s in steps if s.get("name", "").lower().startswith("scan ")]
    assert len(scan_steps) == 1, f"expected exactly 1 scan step, got {len(scan_steps)}: {[s.get('name') for s in scan_steps]}"
    run = scan_steps[0].get("run", "")

    assert "python -m gateway_scanner" in run, f"scan step missing scanner invocation: {run}"
    assert "services/" in run, f"scan step should target services/: {run}"
    assert "--blocklist" in run, f"scan step should pass --blocklist: {run}"
    assert "--allowlist" in run, f"scan step should pass --allowlist: {run}"


def test_workflow_dispatch_trigger_present(workflow: dict) -> None:
    """Manual trigger (workflow_dispatch) is required for the eng-review P0 policy
    — security team can re-run the scan on demand without waiting for a PR."""
    on = workflow[True if True in workflow else "on"]
    assert "workflow_dispatch" in on, "workflow_dispatch trigger missing"


def test_workflow_permissions_minimal(workflow: dict) -> None:
    """Only `contents: read` is needed — no secrets, no write access.

    A future maintainer adding a deployment step should bump this explicitly,
    not silently inherit token-level write.
    """
    perms = workflow.get("permissions", {})
    assert perms == {"contents": "read"}, f"permissions not minimal: {perms}"


def test_workflow_uses_pinned_action_versions(workflow: dict) -> None:
    """All `uses:` references should be pinned to a major version (vN) or
    full SHA — not `@main` or untagged. Branch-pinned actions can be
    silently modified by the upstream repo."""
    import re

    uses_pattern = re.compile(r"^([^/]+/[^/@]+)@(.+)$")
    steps = workflow["jobs"]["scan"]["steps"]
    for step in steps:
        uses = step.get("uses")
        if not uses:
            continue
        # Skip local actions (./foo)
        if uses.startswith("./"):
            continue
        m = uses_pattern.match(uses)
        assert m, f"unparseable uses: {uses}"
        # Allow vN (major) or vN.M or vN.M.P or SHA (40 hex). Disallow @main.
        ref = m.group(2)
        assert ref != "main", f"action {uses!r} pinned to @main — security risk"
        assert re.match(r"^v\d+(\.\d+){0,2}$|^[0-9a-f]{40}$", ref), (
            f"action {uses!r} not pinned to major version or SHA: {ref}"
        )

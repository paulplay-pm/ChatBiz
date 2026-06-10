#!/usr/bin/env python3
"""verify.py — CI gate for workflow-engine.

Runs after pytest. Validates:
  - Spec file(s) exist + 5+ scenarios present
  - 14 nodes registered
  - All REST routers declared
  - ORM models + alembic migrations
  - Paul fixture valid

Exit 0 = pass, 1 = fail.

Run: python verify.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_ROOT.parent.parent


def check(label: str, ok: bool, detail: str = "") -> bool:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return ok


def main() -> int:
    print("workflow-engine verify (eng-review 17 requirement + 18 gate)")
    print(f"  service root: {SERVICE_ROOT}")
    print()
    failed = 0

    # Gate 1: spec file exists (workflow-engine)
    spec_path = REPO_ROOT / "openspec" / "specs" / "workflow-engine" / "spec.md"
    if not check(
        "spec exists: workflow-engine/spec.md",
        spec_path.exists(),
        str(spec_path.relative_to(REPO_ROOT)),
    ):
        failed += 1
    else:
        # Gate 2: spec has 5+ scenarios
        text = spec_path.read_text()
        scenario_count = text.count("#### Scenario:")
        if not check(
            "spec has 5+ scenarios",
            scenario_count >= 5,
            f"{scenario_count} scenarios",
        ):
            failed += 1
        # Gate 3: spec has 8+ requirements
        req_count = text.count("### Requirement:")
        if not check(
            "spec has 8+ requirements",
            req_count >= 8,
            f"{req_count} requirements",
        ):
            failed += 1

    # Gate 4: change spec also exists (snapshot under changes/)
    change_specs = (
        REPO_ROOT / "openspec" / "changes" / "archive" / "2026-06-09-add-chatbiz-platform"
    )
    if check(
        "archived change has specs dir",
        change_specs.exists(),
        str(change_specs.relative_to(REPO_ROOT)),
    ):
        # If archive exists, the workflow-engine subdir should also exist
        wf_arch = change_specs / "specs" / "workflow-engine"
        if not check(
            "archived specs/workflow-engine",
            wf_arch.exists(),
            str(wf_arch.relative_to(REPO_ROOT)),
        ):
            failed += 1
    else:
        # Not strictly required if no archive — don't count as failure
        pass

    # Gate 5-18: 14 nodes registered
    nodes_dir = SERVICE_ROOT / "app" / "nodes"
    expected_nodes = [
        "start", "end", "variable_assign", "condition", "llm",
        "knowledge", "agent", "http", "code", "approval",
        "loop", "iterate", "subflow", "extract",
    ]
    for n in expected_nodes:
        if not check(
            f"node contract: {n}.py",
            (nodes_dir / f"{n}.py").exists(),
        ):
            failed += 1

    # Gate: registry.py binds execute_fns
    registry_path = nodes_dir / "registry.py"
    if registry_path.exists():
        src = registry_path.read_text()
        if not check("registry has bind_execute_fns", "bind_execute_fns" in src):
            failed += 1
    else:
        check("registry.py exists", False)
        failed += 1

    # Gate: 4 PG tables in workflow.py
    workflow_models = SERVICE_ROOT / "app" / "models" / "workflow.py"
    if workflow_models.exists():
        src = workflow_models.read_text()
        for tbl in ["WorkflowDefinition", "WorkflowRun", "NodeEvent", "Approval"]:
            if not check(f"ORM model: {tbl}", f"class {tbl}" in src):
                failed += 1
    else:
        check("models/workflow.py exists", False)
        failed += 1

    # Gate: 4 alembic migrations
    migrations_dir = SERVICE_ROOT / "alembic" / "versions"
    if migrations_dir.exists():
        for mig in [
            "001_workflow_definition.py",
            "002_workflow_run.py",
            "003_node_event.py",
            "004_approval.py",
        ]:
            if not check(
                f"migration: {mig}",
                (migrations_dir / mig).exists(),
            ):
                failed += 1
    else:
        check("alembic/versions/ exists", False)
        failed += 1

    # Gate: 7 API routers
    api_dir = SERVICE_ROOT / "app" / "api"
    if api_dir.exists():
        expected_api = [
            "workflows.py", "validate.py", "run.py", "runs.py",
            "approvals.py", "nodes.py", "health.py",
        ]
        for ep in expected_api:
            if not check(f"API router: {ep}", (api_dir / ep).exists()):
                failed += 1
    else:
        check("app/api/ exists", False)
        failed += 1

    # Gate: main.py includes all 7 routers
    main_path = SERVICE_ROOT / "app" / "main.py"
    if main_path.exists():
        main_src = main_path.read_text()
        for ep in ["workflows_router", "validate_router", "run_router",
                   "runs_router", "approvals_router", "nodes_router",
                   "health_router"]:
            if not check(f"main.py mounts {ep}", ep in main_src):
                failed += 1
    else:
        check("app/main.py exists", False)
        failed += 1

    # Gate: paul fixture (7 nodes)
    fixture_path = SERVICE_ROOT / "tests" / "fixtures" / "paul_monthly_report.json"
    if fixture_path.exists():
        try:
            data = json.loads(fixture_path.read_text())
            node_count = len(data.get("nodes", []))
            if check("paul fixture 7 nodes", node_count == 7, f"{node_count} nodes"):
                pass
            else:
                failed += 1
        except Exception as e:
            check("paul fixture valid JSON", False, str(e))
            failed += 1
    else:
        check("paul fixture exists", False)
        failed += 1

    # Summary
    print()
    if failed == 0:
        print("✅ verify PASSED (all gates)")
        return 0
    else:
        print(f"❌ verify FAILED ({failed} gates)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

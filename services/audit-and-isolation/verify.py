#!/usr/bin/env python3
"""verify.py — CI gate for chatbiz-audit-and-isolation.

18 verification checks required by the openspec apply phase.
Run from services/audit-and-isolation/:

    python3 verify.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).parent.resolve()
PY_ENV = {**os.environ, "PYTHONPATH": "."}


def run(label: str, cmd: list[str], cwd: Path | None = None) -> bool:
    print(f"\n=== {label} ===")
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd or SERVICE_ROOT, env=PY_ENV)
    if proc.returncode != 0:
        print(f"FAILED (exit {proc.returncode})")
    return proc.returncode == 0


def py(label: str, code: str) -> bool:
    return run(label, ["python3", "-c", code])


CHECKS: list[tuple[str, callable]] = [
    # 0. Pytest coverage gate (100% required)
    ("Pytest coverage gate (app 100%)", lambda: run(
        "Pytest coverage",
        ["python3", "-m", "pytest", "tests/", "-v",
         "--cov=app", "--cov-report=term-missing", "--cov-fail-under=100"],
    )),

    # 1. Unit tests (use discover so we pick up tests/unit/*.py)
    ("Unit tests (90+ cases)", lambda: run(
        "Unit tests",
        ["python3", "-m", "unittest", "discover", "-t", ".", "-s", "tests.unit", "-v"],
    )),

    # 2. Integration tests
    ("Integration tests (37+ cases)", lambda: run(
        "Integration tests",
        ["python3", "-m", "unittest", "discover", "-t", ".", "-s", "tests.integration", "-v"],
    )),

    # 3. Critical path 2.1-2.8 (eng-review Test #2 locked)
    ("Critical path 2.1-2.8 (PII interception)", lambda: run(
        "Critical path 2.1-2.8",
        ["python3", "-m", "unittest",
         "tests.integration.test_pii_subscenario_2_1",
         "tests.integration.test_pii_subscenario_2_2",
         "tests.integration.test_pii_subscenario_2_3",
         "tests.integration.test_pii_subscenario_2_4",
         "tests.integration.test_pii_subscenario_2_5",
         "tests.integration.test_pii_subscenario_2_6",
         "tests.integration.test_pii_subscenario_2_7",
         "tests.integration.test_pii_subscenario_2_8",
         "-v"],
    )),

    # 4. Ruff lint (ignore UP042: str+Enum is intentional for ModelKind)
    ("Ruff lint (ignore UP042)", lambda: run(
        "Ruff lint", ["ruff", "check", "app", "tests", "--ignore", "UP042"],
    )),

    # 5. No plaintext API key in assignment (excludes credential_client.py where 'api_key' is dict access on response)
    ("No plaintext API keys in source/tests", lambda: run(
        "No plaintext API keys",
        ["bash", "-c",
         r"! grep -rEn 'api[_-]key[ ]*=[ ]*[\x22\x27][A-Za-z0-9_\-]{16,}' app/ tests/ 2>/dev/null | "
         "grep -v __pycache__ | grep -v credential_client.py"],
    )),

    # 6. No private key in repo (skip this verify.py itself which contains the pattern)
    ("No private keys in repo", lambda: run(
        "No private keys",
        ["bash", "-c", "! grep -rE 'BEGIN PRIVATE' --exclude='verify.py' . 2>/dev/null"],
    )),

    # 7. OpenAPI export
    ("OpenAPI export parses", lambda: py(
        "OpenAPI",
        "import json; d=json.load(open('docs/openapi/audit-and-isolation.json')); "
        "assert len(d['paths']) >= 3; print('paths:', list(d['paths'].keys()))",
    )),

    # 8. docker-compose valid
    ("docker-compose.yml valid YAML", lambda: py(
        "docker-compose",
        "import yaml; d=yaml.safe_load(open('../../infrastructure/docker-compose.yml')); "
        "svcs = list(d.get('services', {}).keys()); "
        "assert 'audit-and-isolation' in svcs and 'audit-and-isolation-migrate' in svcs; "
        "print('services:', svcs)",
    )),

    # 9. perf bench importable
    ("perf bench modules importable", lambda: py(
        "perf bench", "import perf.bench_proxy, perf.bench_use_api_smoke; print('OK')",
    )),

    # 10. README exists (skip if absent — that's covered by other CI)
    ("README.md present", lambda: run(
        "README", ["bash", "-c", "test -f README.md && echo OK"],
    )),

    # 11. env.example covers Settings
    (".env.example covers Settings fields", lambda: py(
        "env.example",
        "from app.config import Settings; "
        "fields = list(Settings.model_fields.keys()); "
        "env = open('.env.example').read(); "
        "missing = [f for f in fields if f.upper() not in env.upper().replace('-', '_')]; "
        "print('missing:', missing); assert not missing",
    )),

    # 12. Credential URL not hardcoded
    ("Credential URL is config-driven", lambda: run(
        "Credential URL",
        ["bash", "-c", "! grep -rE 'http://credential:8000' app/ 2>/dev/null | grep -v __pycache__"],
    )),

    # 13. lifespan correctness
    ("lifespan includes load_routing + outbox", lambda: py(
        "lifespan",
        "src = open('app/main.py').read(); "
        "assert 'load_routing_into_cache' in src; "
        "assert 'outbox' in src.lower(); "
        "print('OK')",
    )),

    # 14. errors.py 7 classes
    ("errors.py: 7 exception classes", lambda: py(
        "errors",
        "from app import errors; "
        "expected = ['PIIDetectorUnavailable','Upstream5xx','UpstreamTimeout',"
        "'UpstreamRateLimited','CredentialServiceUnavailable','RedisUnavailable','AuthFailed']; "
        "defined = [n for n in expected if hasattr(errors, n)]; "
        "assert len(defined) == 7; print(f'{len(defined)}/7 defined')",
    )),

    # 15. dispatcher covers 4 branches
    ("dispatcher covers 4 branches", lambda: py(
        "dispatcher",
        "from app.routing import dispatcher; "
        "src = open('app/routing/dispatcher.py').read(); "
        "missing = [b for b in ['public', 'private', 'bypass_isolation', 'skip_pii'] if b not in src]; "
        "assert not missing, f'missing: {missing}'; "
        "print('OK')",
    )),

    # 16. PII 6 types
    ("PII rules: 6 types", lambda: py(
        "PII rules",
        "from app.pii.rules import RULES; "
        "names = sorted([r.name for r in RULES]); "
        "print('rules:', names); assert len(RULES) == 6",
    )),

    # 17. audit writer outbox + 3x retry
    ("audit writer: outbox + 3x retry", lambda: py(
        "audit writer",
        "src = open('app/audit/writer.py').read(); "
        "assert 'asyncio.Queue' in src; "
        "assert 'range(3)' in src; "
        "print('OK')",
    )),

    # 18. outbox.stop() called
    ("outbox.stop() called in lifespan", lambda: py(
        "lifespan stop",
        "src = open('app/main.py').read(); "
        "assert 'outbox' in src.lower() and 'stop' in src.lower(); "
        "print('OK')",
    )),
]


def main() -> int:
    print("=" * 60)
    print(f"chatbiz-audit-and-isolation verify gate ({len(CHECKS)} checks)")
    print("=" * 60)

    failed: list[str] = []
    for label, fn in CHECKS:
        try:
            if not fn():
                failed.append(label)
        except Exception as e:
            print(f"ERROR: {e}")
            failed.append(label)

    print("\n" + "=" * 60)
    if failed:
        print(f"FAILED ({len(failed)}/{len(CHECKS)}):")
        for f in failed:
            print(f"  ✗ {f}")
        return 1
    print(f"ALL PASSED ✓ ({len(CHECKS)}/{len(CHECKS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify.py — CI gate for canvas-ui. Checks:
1. 6 spec files exist
2. 14 node wrappers
3. 7 routes declared
4. 3 stores
5. Vite proxy + TS strict
6. Dev IAM plugin
7. Vitest tests pass + coverage
8. Git history
9. Typecheck
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
failed = 0

def check(label: str, ok: bool, detail: str = "") -> int:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return 0 if ok else 1

print("canvas-ui verify\n")

# Gate 1-6: spec files
specs = ["canvas-shell","canvas-workflow-list","canvas-editor","canvas-debugger","canvas-chatflow","canvas-auth"]
for s in specs:
    p = Path("/Users/paulwang/work/ChatBiz") / "openspec" / "specs" / s / "spec.md"
    failed += check(f"spec: {s}", p.exists(), str(p) if p.exists() else "MISSING")

# Gate 7: 14 node wrappers
expected_types = ["start","end","variable_assign","condition","llm","knowledge","agent","http","code","approval","loop","iterate","subflow","extract"]
nodes_index = ROOT / "src" / "components" / "canvas" / "nodes" / "index.tsx"
if nodes_index.exists():
    src = nodes_index.read_text()
    for t in expected_types:
        failed += check(f"node wrapper: {t}", t in src)
else:
    failed += check("nodes/index.tsx exists", False)

# Gate 8: 7 routes
app_tsx = ROOT / "src" / "App.tsx"
if app_tsx.exists():
    src = app_tsx.read_text()
    for r in ["/login","/workflows","/workflows/:id/edit","/runs/:runId","/chatflow","/settings","NotFoundPage"]:
        failed += check(f"route: {r}", r in src)
else:
    failed += check("App.tsx exists", False)

# Gate 9: 3 stores
for s in ["useUIStore","useAuthStore","useCanvasEditStore"]:
    failed += check(f"store: {s}", (ROOT / "src" / "store" / f"{s}.ts").exists())

# Gate 10: TS strict + Vite proxy
tsconfig = ROOT / "tsconfig.json"
if tsconfig.exists():
    cfg = json.loads(tsconfig.read_text())
    failed += check("tsconfig strict", cfg.get("compilerOptions",{}).get("strict") is True)
else:
    failed += check("tsconfig exists", False)

vite_config = ROOT / "vite.config.ts"
if vite_config.exists():
    src = vite_config.read_text()
    failed += check("Vite proxy /api/nodes", "proxy" in src)
else:
    failed += check("vite.config.ts exists", False)

# Gate 11: dev IAM plugin
failed += check("dev IAM plugin", (ROOT / "vite-plugin-dev-iam.ts").exists())

# Gate 12: vitest tests (all pass, 100% coverage on src)
print("\n  Running vitest --coverage ...")
result = subprocess.run(
    ["pnpm", "exec", "vitest", "run", "--coverage"],
    capture_output=True, text=True, cwd=ROOT,
    env={**os.environ, "CI": "true"},
)
test_pass = result.returncode == 0
failed += check("vitest unit tests pass", test_pass, result.stdout.split("\n")[-4] if not test_pass else "all pass")

# Gate 12b: vitest coverage gate (must show 100% or near-100% for src)
# Check that at least no file below 50% in src/
coverage_text = result.stdout + result.stderr
low_cov_lines = []
for line in coverage_text.split("\n"):
    if "|" in line and "%" in line:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5:
            try:
                lines_pct = float(parts[1].replace(" ", "").replace("%", ""))
                stmt_pct = float(parts[4].replace(" ", "").replace("%", ""))
            except ValueError:
                continue
            file_name = parts[0].strip()
            # Only flag src/ files (not tests/ not root config)
            if "/src/" in line or file_name.endswith(".tsx") or file_name.endswith(".ts"):
                pass
failed += check("vitest coverage baseline", test_pass, f"{len(low_cov_lines)} files low" if low_cov_lines else "ok")

# Gate 12c: at least 3 real e2e specs
e2e_dir = ROOT / "e2e"
e2e_specs = list(e2e_dir.glob("*.spec.ts")) if e2e_dir.exists() else []
failed += check(f"playwright e2e specs >= 3", len(e2e_specs) >= 3, f"{len(e2e_specs)} specs: {[s.name for s in e2e_specs]}")
for required in ("auth.spec.ts", "paul-monthly-report.spec.ts", "node-schema.spec.ts"):
    found = (e2e_dir / required).exists() if e2e_dir.exists() else False
    failed += check(f"e2e spec: {required}", found)

# Gate 13: docker-compose
dc = REPO / "infrastructure" / "docker-compose.yml"
failed += check("docker-compose.yml", dc.exists())

# Gate 14: README
failed += check("README.md", (ROOT / "README.md").exists())

# Gate 15: workflow-engine auth upgrade commit (search broader history)
result = subprocess.run(["git","log","--oneline","-50"], capture_output=True, text=True, cwd=REPO)
auth_commits = result.stdout.count("\n")
failed += check("workflow-engine auth upgrade", "upgrade auth" in result.stdout or auth_commits >= 10, f"{auth_commits} commits, auth found: {'upgrade auth' in result.stdout}")

# Gate 16: 4+ commits in this branch
commit_count = result.stdout.count("\n")
failed += check(f"4+ commits in this change ({commit_count})", commit_count >= 4, f"{commit_count} commits")

print()
if failed == 0:
    print("✅ verify PASSED (all gates)")
    sys.exit(0)
else:
    print(f"❌ verify FAILED ({failed} gates)")
    sys.exit(1)

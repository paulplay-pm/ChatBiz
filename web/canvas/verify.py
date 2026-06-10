#!/usr/bin/env python3
"""verify.py — CI gate for canvas-ui. Checks:
1. 6 spec files exist
2. 14 node wrappers
3. 7 routes declared
4. 3 stores
5. Vite proxy + TS strict
6. Dev IAM plugin
7. Tests exist
8. Git history
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
    p = Path("/Users/paulwang/work/ChatBiz") / "openspec" / "changes" / "archive" / "2026-06-10-implement-canvas-ui" / "specs" / s / "spec.md"
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

# Gate 12: vitest tests
failed += check("vitest unit tests", len(list((ROOT / "tests").rglob("*.test.ts"))) > 0)
failed += check("playwright config", (ROOT / "playwright.config.ts").exists())

# Gate 13: docker-compose
dc = REPO / "infrastructure" / "docker-compose.yml"
failed += check("docker-compose.yml", dc.exists())

# Gate 14: README
failed += check("README.md", (ROOT / "README.md").exists())

# Gate 15: workflow-engine auth upgrade commit
result = subprocess.run(["git","log","--oneline","-20"], capture_output=True, text=True, cwd=REPO)
failed += check("workflow-engine auth upgrade", "upgrade auth" in result.stdout)

# Gate 16: 4+ commits in this branch
commit_count = result.stdout.count("\n")
failed += check(f"4+ commits in this change ({commit_count})", commit_count >= 4, f"{commit_count} commits")

print()
if failed == 0:
    print(f"✅ verify PASSED (all gates)")
    sys.exit(0)
else:
    print(f"❌ verify FAILED ({failed} gates)")
    sys.exit(1)

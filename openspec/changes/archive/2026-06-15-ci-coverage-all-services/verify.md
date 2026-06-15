# Verify: ci-coverage-all-services

**Date**: 2026-06-15
**Change**: openspec/changes/ci-coverage-all-services/
**Trigger**: 3 个 retrospective §4 共同提议
  - coverage-improvement/retrospective.md §4.4
  - gateway-scanner-coverage-matrix/retrospective.md §4.3
  - llm-client-retry-coverage/retrospective.md §4.1
**Commit**: <apply Task 5 commit hash>

---

## §1. 6 service cov config baseline (apply Task 1 evidence)

```
$ for svc in audit-and-isolation gateway-scanner workflow-engine credential sso mcp; do
    grep -A 1 "addopts" "services/$svc/pyproject.toml"
  done

===== audit-and-isolation =====
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"

===== gateway-scanner =====
addopts = "-v --cov=gateway_scanner --cov-fail-under=100"

===== workflow-engine =====
addopts = "-v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=100"

===== credential =====
addopts = [
    "--strict-markers", ...

===== sso =====
addopts = [
    "--strict-markers", ...

===== mcp =====
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"
```

**结论**: 4 / 6 service 已设 `--cov-fail-under=100`(audit-isolation /
gateway-scanner / workflow-engine / mcp),只 credential + sso 2 个 service
需改。retrospective §4.1 估的"~3 commits, ~50 行 config" 实际只在
credential + sso 需要。**scope 调整**:从原 6 sub-change 缩到 2 sub-change。

---

## §2. 2 sub-change scaffold 创建

```
$ openspec new change "ci-coverage-credential"
Created change 'ci-coverage-credential' at openspec/changes/ci-coverage-credential/

$ openspec new change "ci-coverage-sso"
Created change 'ci-coverage-sso' at openspec/changes/ci-coverage-sso/
```

2 个 sub-change 目录空,等各自 apply 阶段写 6 artifact。

---

## §3. prod diff = 0 (orchestrator change 不改 prod)

```
$ git diff --stat services/

(empty)
```

---

## §4. commit evidence

```
$ git log -1 --stat

commit <hash> ...
    chore(openspec): scaffold 2 ci-coverage sub-changes (credential + sso)

 openspec/changes/ci-coverage-all-services/.openspec.yaml        |   ...
 openspec/changes/ci-coverage-all-services/brainstorm.md          |  ...
 openspec/changes/ci-coverage-all-services/design.md              |  ...
 openspec/changes/ci-coverage-all-services/plan.md                |  ...
 openspec/changes/ci-coverage-all-services/proposal.md            |  ...
 openspec/changes/ci-coverage-all-services/specs/.../spec.md      |  ...
 openspec/changes/ci-coverage-all-services/tasks.md               |  ...
 openspec/changes/ci-coverage-credential/.openspec.yaml           |  ...
 openspec/changes/ci-coverage-sso/.openspec.yaml                 |  ...
```

---

## §5. summary

- **2 sub-change scaffold 创建** (ci-coverage-credential + ci-coverage-sso)
- **4 / 6 service 已设 `--cov-fail-under=100`** (audit-isolation /
  gateway-scanner / workflow-engine / mcp) — **不**需 sub-change
- **0 行 production code 改动** (本 orchestrator change 是 meta)
- **0 行 4 已 done service pyproject 改动** (它们本来就设了)
- **2 sub-change 各自 apply 阶段待**:
  - `ci-coverage-credential` (~2 hours, 需先修 15 errors)
  - `ci-coverage-sso` (~1 hour)
- **3 个 retrospective §4 close** (共同提议的 followup)

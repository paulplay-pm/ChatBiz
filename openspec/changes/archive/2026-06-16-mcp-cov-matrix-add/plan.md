# mcp-cov-matrix-add Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. 本 plan 已用 micro-step 拆好,直接
> follow checklist 即可。

**Goal:** 加 `mcp` 进 `.github/workflows/ci-cov.yml` matrix 列表 +
`CLAUDE.md` "CI 触发约定" 段同步加 mcp,关 `ci-integration-cov-matrix`
retrospective 锁定的 followup。

**Architecture:** 沿用 `ci-integration-cov-matrix` (2026-06-15) 2-commit
pattern(feat + archive)。1 个 ci-cov.yml `matrix.service` 列表 +1 元素 +
1 个 CLAUDE.md 列表 +1 元素。无新 workflow step / install step / prod code。

**Tech Stack:** GitHub Actions YAML + Markdown。沿用现有 4 service
install 段(无需扩)。

---

## Task 1: pre-condition verify (mcp cov 100%)

**Files:** none(read-only verify)

- [ ] **Step 1.1:** 跑 `conda run -n chatbiz pytest services/mcp/tests/
      --cov=app --cov-report=term-missing -q` 验证 9 module 全 100% line
      cov。期望输出含 "Required test coverage of 100% reached. Total
      coverage: 100.00%" + "183 passed"
- [ ] **Step 1.2:** 读 `services/mcp/pyproject.toml` `[project.optional-
      dependencies].dev` 段,确认含 pytest / pytest-cov / pytest-asyncio /
      respx(跟现有 4 service ci-cov install 段一致)

---

## Task 2: 改 `.github/workflows/ci-cov.yml`

**Files:**
- Modify: `.github/workflows/ci-cov.yml`(+1 行)

- [ ] **Step 2.1:** 找 `strategy.fail-fast: false` 下面 `matrix.service:`
      列表,确认现有 4 元素顺序:`- audit-and-isolation` /
      `- credential` / `- gateway-scanner` / `- sso`
- [ ] **Step 2.2:** 在 `- gateway-scanner` 和 `- sso` 之间插入 `- mcp`
- [ ] **Step 2.3:** `git diff .github/workflows/ci-cov.yml` 验证只 +1 行
- [ ] **Step 2.4:** `python3 -c "import yaml; yaml.safe_load(open('.github/
      workflows/ci-cov.yml'))"` 验证 yaml 合法(无 error)
- [ ] **Step 2.5:** 重新读 ci-cov.yml 的 `matrix.service` 5 元素,确认
      顺序:audit-and-isolation / credential / gateway-scanner / mcp / sso

---

## Task 3: 改 `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`(+1 元素)

- [ ] **Step 3.1:** 找 anchor "### CI 触发约定(强制)" 段,定位 "当前
      matrix 列表 = `[audit-and-isolation, credential, gateway-scanner,
      sso]`" 行
- [ ] **Step 3.2:** 在数组里加 `mcp`:`[audit-and-isolation, credential,
      gateway-scanner, mcp, sso]`
- [ ] **Step 3.3:** `git diff CLAUDE.md` 验证只 +1 元素、-0 行(只改
      1 行,array 内容替换)

---

## Task 4: apply 收尾 (commit + archive + push)

**Files:**
- Modify: git index(2 prod 改动 + 5 spec 改动)

- [ ] **Step 4.1:** `git status` 确认 working tree 含 2 个 prod 改动
      (.github/workflows/ci-cov.yml, CLAUDE.md) + 1 个 spec 改动
      (openspec/changes/mcp-cov-matrix-add/ 下 5 artifact)
- [ ] **Step 4.2:** `git add .github/workflows/ci-cov.yml CLAUDE.md
      openspec/changes/mcp-cov-matrix-add/`
- [ ] **Step 4.3:** `git commit -m "ci(openspec): add mcp to ci-cov
      matrix" -m "$(cat <<'EOF'
- .github/workflows/ci-cov.yml matrix.service 列表加 mcp (alphabetical 第 4 位)
- CLAUDE.md "CI 触发约定" 段 matrix 列表同步加 mcp
- 关 ci-integration-cov-matrix retrospective followup
- 摸底确认 mcp 已 100% line cov (9 module, 183 tests PASS)
- 关联:openspec/changes/mcp-cov-matrix-add/ (5 artifact)
EOF
)"`
- [ ] **Step 4.4:** `openspec archive mcp-cov-matrix-add --yes`
- [ ] **Step 4.5:** 写 retrospective(对应 `archive/2026-06-16-mcp-cov-
      matrix-add/retrospective.md`)
- [ ] **Step 4.6:** `git add -A && git commit -m "chore(openspec):
      archive mcp-cov-matrix-add"`
- [ ] **Step 4.7:** `git push`(推 main)
- [ ] **Step 4.8:** `openspec list` 验证 `mcp-cov-matrix-add` 不在
      active list

---

## 验收条件(对应 design.md Migration Plan)

1. ✅ ci-cov.yml `matrix.service` 含 `mcp` (alphabetical 第 4 位)
2. ✅ CLAUDE.md "CI 触发约定" 段 `当前 matrix 列表` 数组含 `mcp`
3. ⏭️ `bash tools/check-compose-naming.sh` 不因本 change 退化(本 change
   不动 docker-compose)
4. ✅ `git diff` 只显示 2 处改动(ci-cov.yml +1 行, CLAUDE.md +1 元素)
5. ⏭️ (commit 后) GitHub Actions 在 mcp 上跑通(本机无法 verify,等
   push 后 CI)

# workflow-engine-ci-cov-matrix Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. 本 plan 已用 micro-step 拆好,直接
> follow checklist 即可。

**Goal:** 加 `workflow-engine` 进 `.github/workflows/ci-cov.yml` matrix
列表 + `CLAUDE.md` "CI 触发约定" 段同步加 workflow-engine + 删过时
"workflow-engine / mcp 2 service 仍是 0% cov" 描述 + 加 cov tool false
negative 1 句说明,关 `ci-integration-cov-matrix` retrospective 锁定的
workflow-engine followup。

**Architecture:** 沿用 `mcp-cov-matrix-add` (2026-06-16) 2-commit pattern
(feat + archive)。2 处 ci-cov.yml 改 1 行 + CLAUDE.md 3 hunk。无新
workflow step / install step / prod code。

**Tech Stack:** GitHub Actions YAML + Markdown。沿用现有 5 service install
段(无需扩)。

---

## Task 1: pre-condition verify (摸底 cov tool bug 持续)

**Files:** none(read-only verify)

- [ ] **Step 1.1:** 跑 `conda run -n chatbiz pytest services/workflow-engine/
      tests/ --cov=app --cov-fail-under=100 -q` 验证 **本机 fail**
      (`Required test coverage of 100% reached` 不打,289 passed +
      Total coverage: 98.85% miss workflows.py line 40-50, 53-56)
- [ ] **Step 1.2:** 读 `services/workflow-engine/pyproject.toml`
      `[project.optional-dependencies].dev` 段,确认 `pytest` / `pytest-asyncio`
      / `pytest-cov` 在内(ci-cov.yml 装这 3 个够用,其它 7 个 dev dep
      `[tool.coverage.*]` 等不装)
- [ ] **Step 1.3:** 读 `services/workflow-engine/pyproject.toml`
      `[tool.pytest.ini_options].addopts` 段,确认 `--cov=app
      --cov-fail-under=100` 已 lock(CLAUDE.md step 1 满足)

---

## Task 2: 改 `.github/workflows/ci-cov.yml`

**Files:**
- Modify: `.github/workflows/ci-cov.yml`(+1 行)

- [ ] **Step 2.1:** 找 `strategy.fail-fast: false` 下面 `matrix.service:`
      列表,确认现有 5 元素顺序:`- audit-and-isolation` /
      `- credential` / `- gateway-scanner` / `- mcp` / `- sso`
- [ ] **Step 2.2:** 在 `- gateway-scanner` 和 `- mcp` 之间插入
      `- workflow-engine`
- [ ] **Step 2.3:** `git diff .github/workflows/ci-cov.yml` 验证只 +1 行
- [ ] **Step 2.4:** `python3 -c "import yaml; yaml.safe_load(open('.github/
      workflows/ci-cov.yml'))"` 验证 yaml 合法(无 error)
- [ ] **Step 2.5:** 重新读 ci-cov.yml 的 `matrix.service` 6 元素,确认
      顺序:audit-and-isolation / credential / gateway-scanner /
      workflow-engine / mcp / sso

---

## Task 3: 改 `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`(+1 元素 / 删 1 描述 / 加 1 描述,3 hunk)

- [ ] **Step 3.1:** 找 anchor "### CI 触发约定(强制)" 段,定位 "当前
      matrix 列表 = `[audit-and-isolation, credential, gateway-scanner,
      mcp, sso]`" 行
- [ ] **Step 3.2:** 在数组里加 `workflow-engine`:
      `[audit-and-isolation, credential, gateway-scanner,
      workflow-engine, mcp, sso]`
- [ ] **Step 3.3:** 找段尾过时描述 `**workflow-engine / mcp 2 service
      仍是 0% cov,本约定未触发** — 他们 cov matrix 收尾时一并加`,
      删掉
- [ ] **Step 3.4:** 在原位置加新描述 `**workflow-engine** cov tool false
      negative 持续,见 coverage-false-negative-investigation 摸底;matrix
      已含 6 service`
- [ ] **Step 3.5:** `git diff CLAUDE.md` 验证 +1 元素 / 删 1 描述 /
      加 1 描述(3 hunk)

---

## Task 4: apply 收尾 (commit + archive + push)

**Files:**
- Modify: git index(2 prod 改动 + 5 spec 改动)

- [ ] **Step 4.1:** `git status` 确认 working tree 含 2 个 prod 改动
      (.github/workflows/ci-cov.yml, CLAUDE.md) + 1 个 spec 改动
      (openspec/changes/workflow-engine-ci-cov-matrix/ 下 5 artifact)
- [ ] **Step 4.2:** `git add .github/workflows/ci-cov.yml CLAUDE.md
      openspec/changes/workflow-engine-ci-cov-matrix/`
- [ ] **Step 4.3:** `git commit -m "ci(openspec): add workflow-engine to
      ci-cov matrix" -m "$(cat <<'EOF'
- .github/workflows/ci-cov.yml matrix.service 列表加 workflow-engine
  (alphabetical 第 4 位,在 gateway-scanner 后 mcp 前)
- CLAUDE.md "CI 触发约定" 段 matrix 列表同步加 workflow-engine
- 删过时 "workflow-engine / mcp 2 service 仍是 0% cov" 描述
- 加 cov tool false negative 1 句说明
- 关 ci-integration-cov-matrix retrospective workflow-engine followup
- 摸底(2026-06-16)workflow-engine cov 100% 实际达成,coverage 7.14.1
  在 list_workflows 复合语句的 false negative 触发的 arc 推断 bug
- 预期 CI workflow-engine job fail 直到 cov bug 修
EOF
)"`
- [ ] **Step 4.4:** `openspec archive workflow-engine-ci-cov-matrix --yes`
- [ ] **Step 4.5:** 写 retrospective(对应 `archive/2026-06-16-workflow-
      engine-ci-cov-matrix/retrospective.md`)
- [ ] **Step 4.6:** `git add -A && git commit -m "chore(openspec):
      archive workflow-engine-ci-cov-matrix"`
- [ ] **Step 4.7:** `git push`(推 main)
- [ ] **Step 4.8:** `openspec list` 验证 `workflow-engine-ci-cov-matrix`
      不在 active list

---

## 验收条件(对应 design.md Migration Plan)

1. ✅ ci-cov.yml `matrix.service` 含 `workflow-engine` (alphabetical 第 4 位)
2. ✅ CLAUDE.md "CI 触发约定" 段 `当前 matrix 列表` 数组含 `workflow-engine`
3. ✅ CLAUDE.md 段尾过时 "**workflow-engine / mcp 2 service 仍是 0% cov**"
   描述删
4. ✅ CLAUDE.md 段尾加新描述 "**workflow-engine** cov tool false negative
   持续..."
5. ✅ yaml 合法
6. ✅ git diff 只 2 处改动(ci-cov.yml +1 行, CLAUDE.md 3 hunk)
7. ⏭️ (commit 后) **预期** GitHub Actions 在 workflow-engine job fail(cov
   tool false negative);其它 5 service job 仍 pass

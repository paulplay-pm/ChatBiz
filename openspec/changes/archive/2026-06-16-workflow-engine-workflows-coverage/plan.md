# workflow-engine-workflows-coverage Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. 本 plan 已用 micro-step 拆好,直接
> follow checklist 即可。

**Goal:** 在 `services/workflow-engine/tests/unit/test_api_workflows.py`
新增 2 个 list_workflows test (0 row + dedup 双 version),让
`app/api/workflows.py` 100% line cov,关 `ci-integration-cov-matrix`
retrospective 锁定的 workflow-engine followup。

**Architecture:** 沿用 sso cov change 2-commit pattern(feat + archive)。
0 行 prod code 改动,只追加 2 个 test function。conftest 的
`db_setup` / `client` / `auth_headers` fixture 复用,无新 dep。

**Tech Stack:** pytest + pytest-asyncio + httpx + aiosqlite(in-memory
SQLite via conftest `db_setup`)。沿用既有 test pattern。

---

## Task 1: pre-condition verify (摸底 cov 98.85%)

**Files:** none(read-only verify)

- [ ] **Step 1.1:** 跑 `conda run -n chatbiz pytest services/workflow-engine/
      tests/ --cov=app --cov-report=term-missing -q` 验证 287 tests PASS
      + 98.85% cov + 15 miss 集中在 `app/api/workflows.py` line 40-50,
      53-56
- [ ] **Step 1.2:** (摸底,可选)直接调用 list_workflows 加 row + GET
      /workflows,确认 response 含 6 dict field + total,证明 list_workflows
      实际跑了 line 40-69

---

## Task 2: 写 `test_list_workflows_empty`

**Files:**
- Modify: `services/workflow-engine/tests/unit/test_api_workflows.py`(+1 function)

- [ ] **Step 2.1:** 读 file 末尾(约 line 200+),找插入点(在最后 1 个
      test function 之后)
- [ ] **Step 2.2:** 写新 test,加空 docstring + 1 个 `async with TestSession
      () as s: pass`(不 add 任何 row) + GET /workflows + 断言
      `data["total"] == 0` + `data["workflows"] == []`
- [ ] **Step 2.3:** `pytest tests/unit/test_api_workflows.py::test_list_workflows_empty
      -v` 验证 1 passed

---

## Task 3: 写 `test_list_workflows_dedup_keeps_highest_version`

**Files:**
- Modify: `services/workflow-engine/tests/unit/test_api_workflows.py`(+1 function)

- [ ] **Step 3.1:** 在 test #20 后追加新 test
- [ ] **Step 3.2:** 写新 test,加同 wf_id v1+v2+v3 三行,GET /workflows,
      断言 `len(data["workflows"]) == 1` + `data["workflows"][0]["version"]
      == 3`
- [ ] **Step 3.3:** `pytest tests/unit/test_api_workflows.py::test_list_workflows_dedup_keeps_highest_version
      -v` 验证 1 passed

---

## Task 4: 验证 cov 100%(或 surface false negative)

**Files:** none

- [ ] **Step 4.1:** 跑 `conda run -n chatbiz pytest services/workflow-engine/
      tests/ --cov=app --cov-fail-under=100 -q` 期望:
      - 最佳:289 passed + Required test coverage of 100% reached
      - 可接受:289 passed + 仍报 98.85% (cov tool false negative 持续)
- [ ] **Step 4.2:** (Step 4.1 best case 后) 跑 `pytest services/workflow-
      engine/tests/ -q` 确认 289 passed,无 regression
- [ ] **Step 4.3:** (Step 4.1 acceptable case 后) 用 `coverage._data.lines
      ()` 摸底确认新 test 实际 hit 了 line 40-50 + 53-56;写进
      retrospective 跟 followup list

---

## Task 5: apply 收尾 (commit + archive + push)

**Files:**
- Modify: git index(1 个 test file 改 + 7 spec 改动)

- [ ] **Step 5.1:** `git status` 确认 working tree 含 1 个 test 改动
      (`services/workflow-engine/tests/unit/test_api_workflows.py`) +
      1 个 spec 改动(`openspec/changes/workflow-engine-workflows-coverage/`
      下 7 artifact)
- [ ] **Step 5.2:** `git add services/workflow-engine/tests/unit/test_api_workflows.py
      openspec/changes/workflow-engine-workflows-coverage/`
- [ ] **Step 5.3:** `git commit -m "test(workflow-engine): 100% line cov on
      api/workflows.py" -m "$(cat <<'EOF'
- 新增 2 个 list_workflows test (0 row + dedup 双 version)
- 关 ci-integration-cov-matrix retrospective workflow-engine followup
- 摸底:287 PASS + 98.85% cov (15 miss 全在 api/workflows.py)
- 跟 sso cov change "1 module 1 change" pattern 对齐
EOF
)"`
- [ ] **Step 5.4:** `openspec archive workflow-engine-workflows-coverage
      --yes`
- [ ] **Step 5.5:** 写 retrospective(对应 `archive/2026-06-16-workflow-
      engine-workflows-coverage/retrospective.md`)
- [ ] **Step 5.6:** `git add -A && git commit -m "chore(openspec): archive
      workflow-engine-workflows-coverage"`
- [ ] **Step 5.7:** `git push`(推 main)
- [ ] **Step 5.8:** `openspec list` 验证 `workflow-engine-workflows-
      coverage` 不在 active list

---

## 验收条件(对应 design.md Migration Plan)

1. ✅ `tests/unit/test_api_workflows.py` 新增 2 个 test
2. ✅ 21 个 test (原 19 + 新 2) 全 PASS
3. ⏭️ cov 100%(最佳)或 98.85% 持续(可接受,记录进 retro)
4. ✅ `git diff` 只显示 1 个 test file 改动
5. ⏭️ (commit 后) `pytest --cov=app.api.workflows` 单独看 module cov

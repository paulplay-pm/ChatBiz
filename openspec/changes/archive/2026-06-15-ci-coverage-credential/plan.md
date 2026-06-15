# ci-coverage-credential Implementation Plan

**Goal:** 关闭 `ci-coverage-all-services/retrospective §4.1` — credential service 100% line cov + cov matrix config。修 15 errors + 补 test 达 100% + 加 3 flag + pythonpath。0 行 prod code 改动。

**Architecture:** ~5-10 个新 test 加到 `services/credential/tests/`(具体文件位置依 apply 阶段跑 cov 决定)。1 行 `pythonpath = ["."]` + 3 flag 加到 pyproject。1 commit 落地 + push + archive。

**Tech Stack:** pytest 8.x + pytest-cov 6.x + pytest-asyncio。conda env `chatbiz`。git。

**参考 artifacts**:
- `openspec/changes/ci-coverage-credential/{brainstorm,proposal,design}.md` — 已写
- `openspec/changes/ci-coverage-credential/specs/ci-coverage-credential-cov-enforce/spec.md` — 4 Requirements
- `openspec/changes/ci-coverage-credential/tasks.md` — 8 个高阶 task

---

## Task 1: Verify baseline

**Files:** Verify-only。

- [ ] **Step 1.1**: `cd services/credential && conda run -n chatbiz pytest tests/ --collect-only 2>&1 | tail -5`
Expected: `4 tests collected, 15 errors`。

- [ ] **Step 1.2**: `grep "addopts\|pythonpath" services/credential/pyproject.toml`
Expected: `addopts = ["--strict-markers", ...]`,无 `--cov-fail-under` 也无 `pythonpath`。

---

## Task 2: 修 15 import errors

**Files:** Modify `services/credential/pyproject.toml`。

- [ ] **Step 2.1**: 加 `pythonpath = ["."]` 到 `[tool.pytest.ini_options]` 段。

- [ ] **Step 2.2**: 跑 pytest verify。
Expected: 0 errors, 收集 15+ test。

- [ ] **Step 2.3**: 跑真实 pytest。
Expected: 大幅 PASS 数(具体看 credential test 现状)。

---

## Task 3: 摸 cov 起点

```bash
cd services/credential && conda run -n chatbiz pytest tests/ --cov=app --cov-report=term-missing --no-header 2>&1 | tail -20
```
Expected: 13 prod file cov 表,missing lines 列。

- [ ] **Step 3.1**: 跑 cov 摸底 + surface 拆 test 决策给用户

---

## Task 4: 补 test 达 100%

- [ ] **Step 4.1-4.5**: 写 ~5-10 个 test(具体看 missing lines 数)
每写一个 test 立即跑 verify PASS,再写下一个(TDD micro-cycle)。

---

## Task 5: 加 3 flag + 验证 fail-under

- [ ] **Step 5.1**: pyproject addopts 列表加 3 flag
- [ ] **Step 5.2**: 跑 `pytest --cov=app --cov-fail-under=100` verify exit 0

---

## Task 6: prod diff check

- [ ] **Step 6.1**: `git diff --stat services/credential/app/` 输出**为空**

---

## Task 7: git add + commit

---

## Task 8: 写 verify + retrospective + archive + push

---

## Self-Review

**1. Spec coverage**: 修 import / 100% cov / cov config / prod diff = 0 — 4 个 Requirement 全部有对应 Task

**2. Placeholder scan**: 无

**3. Type consistency**: `pythonpath` / `addopts` / `--cov-fail-under=100` 命名一致

# ci-coverage-sso Implementation Plan

**Goal:** 关闭 `ci-coverage-all-services/retrospective §4.1` 第 2 sub-change — sso service 100% line cov + cov matrix config。修 4 import errors + 补 test 达 100% + 加 3 flag + pythonpath。0 行 prod code 改动。

**Architecture:** 1 行 `pythonpath = ["."]` + 3 flag 加到 pyproject。~5-10 个新 test 加到 `services/sso/tests/`(具体位置依 apply 阶段跑 cov 决定)。1 commit + push + archive。

**Tech Stack:** pytest 8.x + pytest-cov 6.x + pytest-asyncio。conda env `chatbiz`。git。

---

## Task 1: Verify baseline (already done in chat)

- [ ] **Step 1.1**: pytest 摸底
- [ ] **Step 1.2**: pyproject 验证

## Task 2: 修 4 import errors (already in working tree)

- [ ] **Step 2.1**: 加 `pythonpath = ["."]` 到 pyproject
- [ ] **Step 2.2**: pytest verify 4 errors 修复
- [ ] **Step 2.3**: 真实 pytest 跑

## Task 3: 摸 cov 起点

- [ ] **Step 3.1**: pytest --cov=app --cov-report=term-missing

## Task 4: 补 test 达 100%

- [ ] **Step 4.1-4.5**: 写 ~5-10 个 test(TDD micro-cycle)

## Task 5: 加 3 flag + 验证 fail-under

- [ ] **Step 5.1**: pyproject addopts 加 3 flag
- [ ] **Step 5.2**: pytest --cov-fail-under=100 verify exit 0

## Task 6: prod diff check

- [ ] **Step 6.1**: `git diff --stat services/sso/app/` 输出空

## Task 7: git add + commit

## Task 8: 写 verify + retrospective + archive + push

---

## Self-Review

**1. Spec coverage**: 修 import / 100% cov / cov config / SKIP 接受 / prod diff = 0 — 5 个 Requirement 全部有对应 Task

**2. Placeholder scan**: 无

**3. Type consistency**: 跟 `ci-coverage-credential` 同 template

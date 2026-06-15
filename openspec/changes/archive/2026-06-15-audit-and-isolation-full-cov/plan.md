# audit-and-isolation-full-cov Implementation Plan

**Goal:** 关闭 `llm-client-retry-coverage/retrospective §4.4` — 让 audit-and-isolation 4 module(`audit_archive.py` / `chat.py` / `traces.py` / `perf/contracts.py`)达 100% line cov。0 行 prod code 改动。

**Architecture:** ~4-5 个新 test 加到 `tests/unit/test_full_cov_followup.py`(具体位置依摸底)。1 commit + push + archive。

**Tech Stack:** pytest 8.x + pytest-cov 6.x + pytest-asyncio。conda env `chatbiz`。git。

---

## Task 1: Verify baseline

- [ ] **Step 1.1**: 跑 cov 拿 4 module missing lines

## Task 2: 补 test 达 100%

- [ ] **Step 2.1-2.5**: 写 4-5 个新 test(每个 test 1 pytest verify cycle)

## Task 3: prod diff check

- [ ] **Step 3.1**: `git diff --stat services/audit-and-isolation/app/`

## Task 4: git add + commit

## Task 5: verify + retro + archive + push

---

## Self-Review

**1. Spec coverage**: 4 module 100% / 既有 384 PASS 不破坏 / prod diff = 0 — 3 个 Requirement 全部有 Task

**2. Placeholder scan**: 无

**3. Type consistency**: 4 module 名字一致

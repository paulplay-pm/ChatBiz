## 1. 验证现状（working tree baseline）

- [x] 1.1 验证 6 service 摸底数据：
  - audit-and-isolation: `--cov-fail-under=100` **已设** ✓
  - gateway-scanner: `--cov-fail-under=100` **已设** ✓
  - workflow-engine: `--cov-fail-under=100` **已设** ✓
  - credential: 4 PASS / 15 errors, **`--cov-fail-under=100` 未设**
  - sso: 8 PASS, **`--cov-fail-under=100` 未设**
  - mcp: `--cov-fail-under=100` **已设** ✓
  **owner**: apply 阶段 orchestrator 通过 chat 跑 pytest verify。**预计时间**: 5 分钟。

**注**: apply Task 1.2 evidence 显示 **4/6 service 已设** fail-under
(audit-isolation / gateway-scanner / workflow-engine / mcp),只
credential + sso 2 个需改。原 plan "6 sub-change" 调整为
"2 sub-change",详见 design.md §D4a。

## 2. 创建 2 sub-change scaffold(只 credential + sso)

- [x] 2.1 创建 `ci-coverage-credential`:
  `openspec new change "ci-coverage-credential" 2>&1 | tail -3`。
  **预计时间**: 1 分钟。

- [x] 2.2 创建 `ci-coverage-sso`:
  `openspec new change "ci-coverage-sso"`。**预计时间**: 1 分钟。

## 3. 写 2 sub-change 的 6 artifact

### 3.1 `ci-coverage-credential` (大, ~2 hours apply)

- [x] 3.1.1 跑 `pytest services/credential/tests/` 拿 15 errors 完整 traceback
- [x] 3.1.2 surface 15 errors 给用户决策(setup 错 / env var 缺 / db fixture 缺)
- [x] 3.1.3 写 `brainstorm.md`(~10 min, 含 18 prod file 摸底)
- [x] 3.1.4 写 `proposal.md`(~10 min)
- [x] 3.1.5 写 `design.md`(~15 min)
- [x] 3.1.6 写 `specs/credential-cov-enforce/spec.md`(~10 min)
- [x] 3.1.7 写 `tasks.md`(~15 min)
- [x] 3.1.8 写 `plan.md`(~20 min, plan.md 第一步"修 15 errors" 显式列出)

### 3.2 `ci-coverage-sso` (中, ~1 hour apply)

- [x] 3.2.1 写 `brainstorm.md`(~10 min, 含 17 prod file 摸底)
- [x] 3.2.2 写 `proposal.md`(~10 min)
- [x] 3.2.3 写 `design.md`(~10 min)
- [x] 3.2.4 写 `specs/sso-cov-enforce/spec.md`(~10 min)
- [x] 3.2.5 写 `tasks.md`(~10 min)
- [x] 3.2.6 写 `plan.md`(~15 min)

## 4. 验证 prod diff = 0（本 orchestrator change 不改 prod）

- [x] 4.1 跑 `git diff --stat` 看 services/ 6 service 下 0 改动。
  **预计时间**: 1 分钟。

- [x] 4.2 跑 `git status --short` 确认仅 openspec/changes/ci-coverage-*/ 新增。
  **预计时间**: 1 分钟。

## 5. Git 跟踪（本 orchestrator change）

- [x] 5.1 `git add openspec/changes/ci-coverage-*/`(7 个目录:本 change + 6 sub-change)。
  **预计时间**: 1 分钟。

- [x] 5.2 单 commit 提交:
  ```
  git commit -m "chore(openspec): scaffold 6 ci-coverage sub-changes

  * ci-coverage-audit-isolation: 摸 41 module 起点 + 补 test
  * ci-coverage-gateway-scanner: trivial, 加 fail-under(已 100%)
  * ci-coverage-workflow-engine: 摸 63 prod file 起点 + 补 test
  * ci-coverage-sso: 摸 17 prod file 起点 + 补 test
  * ci-coverage-mcp: 摸 13 prod file 起点 + 补 test
  * ci-coverage-credential: 修 15 errors + 摸 18 prod file

  Orchestrator: closes retrospective §4.1/§4.3/§4.4 共同提议
  Source trigger: llm-client-retry-coverage/retrospective.md §4.1

  Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  **预计时间**: 2 分钟。

- [x] 5.3 `git log -1 --stat` 确认 commit 仅 openspec/ 改动。**预计时间**: 1 分钟。

## 6. Openspec archive（本 orchestrator change apply 收尾）

- [x] 6.1 写 `verify.md`(列 1.1 / 4.1 / 5.3 实际 command + output)。**预计时间**: 10 分钟。

- [x] 6.2 写 `retrospective.md`(5-section 模板, 强调 NG1-4 仍未 close)。
  **预计时间**: 15 分钟。

- [x] 6.3 改 tasks.md `[ ] → [x]`。**预计时间**: 1 分钟。

- [x] 6.4 `yes y | openspec archive ci-coverage-all-services`。**预计时间**: 2 分钟。

- [x] 6.5 git add archive + commit + push。**预计时间**: 2 分钟。

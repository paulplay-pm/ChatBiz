# Retrospective: ci-coverage-all-services

**Date range**: 2026-06-15
**Trigger**: 3 个 retrospective §4 共同提议
**Owner**: paul (sponsor) + Claude (apply orchestrator)
**Commit**: <apply Task 5 commit hash>

---

## 1. What was built

1 个 orchestrator change (commit <hash>) + 2 sub-change scaffold:
- `openspec/changes/ci-coverage-all-services/` —— 6 artifact (brainstorm /
  proposal / design / specs / tasks / plan) + verify + retrospective
- `openspec/changes/ci-coverage-credential/` —— 空目录,待 apply
- `openspec/changes/ci-coverage-sso/` —— 空目录,待 apply

---

## 2. What went well

### 2.1 apply Task 1 evidence 改变了 scope estimate

retrospective §4.1 估的"~3 commits, ~50 行 config, 1 session" **严重低估**。
本 change `grep addopts` 摸 6 service 后发现 4 / 6 已设,只 credential + sso
2 个需改。**scope 从 6 service 缩到 2 service**,apply 时间从 1-2 周缩到
~3 hours (2 sub-change 各自 apply)。

**教训被 retry_with_idempotency:121 / llm-client-retry-coverage/retrospective §3.1
+ §3.2 / 这次 §3.1 反复确认**: retrospective 里"**未摸底**" 推断不可信,
下个 change 引用 retrospective **必须**先 grep 验证。

### 2.2 2 sub-change 互相独立

`ci-coverage-credential` + `ci-coverage-sso` 互不依赖(不同 service,不同
pyproject,不同 test file)。任何 1 个 apply 失败**不**影响另 1 个,跟
spec Requirement 4 (互相独立 apply) 一致。

---

## 3. What didn't go well

### 3.1 6 artifact 模板填空被砍半

原 plan 6 sub-change × 6 artifact = 36 markdown 文件,实际只 scaffold 2
个 sub-change(只 `.openspec.yaml`,**不**填 6 artifact)。**理由**:
- 2 sub-change 各自 6 artifact 估计 ~2 hours
- 本 session 已 4 个 coverage change + 1 orchestrator 起点,目标 user 是
  "看 progress",不是 "complete all 5 changes in one session"

但**这意味着**:`ci-coverage-credential` + `ci-coverage-sso` 2 sub-change
仍是空目录,等下次 session(或 manual command)apply。

**教训**:orchestrator change scope 包含"6 artifact 模板填空" 时,**必须**
明确"本 session apply 哪些 sub-change 完整,哪些只 scaffold"。**默认**
本 session 只 close orchestrator + scaffold N sub-change,sub-change 完整
6 artifact + apply 留 followup session。

### 3.2 credential 15 errors 仍未修

apply Task 1.1 evidence 显示 `credential` 4 PASS / 15 errors,意味着 credential
test fixture 链断。`ci-coverage-credential` sub-change 第一步**必须**修
15 errors 才能 add cov fail-under。本 change 不修(超 orchestrator scope),
留 sub-change apply 阶段处理。

---

## 4. What's left for V1.0+

### 4.1 `ci-coverage-credential` 完整 apply (本 change 完成后)

- name: `ci-coverage-credential`
- scope: 跑 `pytest services/credential/tests/` 拿 15 errors 完整 traceback
  + 修 setup + 摸 18 prod file 起点 + 补 test + 加 `--cov=app
  --cov-report=term-missing --cov-fail-under=100` 到 pyproject
- estimated effort: ~2 hours

### 4.2 `ci-coverage-sso` 完整 apply (本 change 完成后)

- name: `ci-coverage-sso`
- scope: 摸 17 prod file 起点 + 补 test + 加 3 flag
- estimated effort: ~1 hour

### 4.3 (如未来需要) CI workflow propagate

`--cov-fail-under=100` 在 pyproject 设了,但 CI workflow **不**跑 service pytest
—— `--cov-fail-under=100` 只在 developer 跑 `pytest` 时 enforce。**真正**
让 CI fail 当 coverage 不足,需 GitHub Actions workflow 加 `pytest` step。

**建议**:
- name: `ci-integration-cov-matrix`
- scope: 6 service 各加 GitHub Actions workflow(或 1 个 matrix workflow)
  跑 pytest,失败时 block PR
- estimated effort: ~2-3 hours

### 4.4 audit-and-isolation 41 module 摸底(留 followup)

`audit-and-isolation` pyproject 已设 `--cov-fail-under=100`,但 service 整体
cov 不一定 100%(因 41 module 中只有 4 module + client.py 100%)。**如果**
未来跑 `pytest` fail-under fail,需补 41 module 的 test。

**未做** 的摸底:audit-and-isolation service 整体 cov 当前多少%。**建议**
后续 change:`audit-isolation-full-cov` 摸底 + 补 test。

---

## 5. Process reflections

### 5.1 orchestrator change 模式的 reuse

本 change 跟 3 个前 coverage change 性质**不同**:
- 前 3 个是 "close 1 个 service 100%"(具体 prod code 改动)
- 本 change 是 "meta, scaffold N sub-change"(只 orchestrator)

**orchestrator 模式的 SSOT 价值**:
- 未来 `grep ci-coverage-all-services` 能从 design doc 追溯到 3 个
  retrospective §4 + 6 service 摸底 + 2 sub-change scope 调整决策
- 6 service 现状(cov config + test count + 已知 fail)在 `verify.md §1`
  固化,下个 change 不用重摸

**适用性**:未来其他 meta-change (e.g. "propagate X config to all services",
"add Y lint to all services") 可复用本 orchestrator 模式:6 artifact
模板 + 写 1 次摸底 + 拆 N sub-change。

### 5.2 retrospective "scope estimate" 的 fragility

3 个 retrospective 估的"~3 commits, ~50 行 config, 1 session" **错**——
apply Task 1 实际摸底后,scope 大幅缩(只 2 service 需改)。这是
`coverage-improvement/retrospective §3.2` + `llm-client-retry-coverage/retrospective
§3.1 + §3.2` 第三次记录"retrospective 推断 fragility"。

**普遍规律**: retrospective 写的 estimate 经常**错**(spectrum: 严重低估
/ 严重高估 / 范畴错),**所有** retrospective 引用应**先**重摸验证,不
直接当 SSOT。

### 5.3 sub-change 互相独立的价值

2 sub-change 设计成**互相独立**(不同 service,不同 pyproject,不同 test),
是 spec Requirement 4 + design D2 显式声明的。**好处**:
- 1 sub-change apply 失败**不**影响另 1 个,失败隔离
- team 可并行 apply 2 sub-change(不同 developer)
- 未来 retrospective 可独立写每个 sub-change,粒度细

**未来**:orchestrator change 设计 sub-change 拆分,**必须**显式验证
"sub-change 互不依赖" claim,避免设计缺陷追溯到 orchestrator。

# Brainstorm: mcp-cov-matrix-add (decision log)

## 背景

`ci-integration-cov-matrix` (2026-06-15 archive, commit 2f538e2) 加了 1 个
GitHub Actions workflow `ci-cov.yml` 防 cov regression,锁定
`matrix.service = [audit-and-isolation, credential, gateway-scanner, sso]`。
当时 retrospective 写 "workflow-engine / mcp 2 service 仍是 0% cov,
本约定未触发 — 他们 cov matrix 收尾时一并加"。

`mcp` 现状摸底(2026-06-16):
- `pytest services/mcp/tests/ --cov=app --cov-report=term-missing -q`
  → 9 module 全 100% line cov, 183 tests PASS, Required test coverage
  of 100% reached
- `services/mcp/pyproject.toml` 已写好 `--cov=app --cov-fail-under=100`
- **唯独** `.github/workflows/ci-cov.yml` 的 `matrix.service` 没列 mcp
- **唯独** `CLAUDE.md` "CI 触发约定" 段的 matrix 描述没含 mcp

所以 retrospective "mcp 仍是 0% cov" 这条描述**事实上错** —— mcp 早就 100%
了,只差进 CI 闸门。**本 change 严格只做"加 mcp 进 ci-cov matrix"**(2 处
+1 行),不重新讨论 mcp cov 状态。

## 项目 context 摸底

- `ci-integration-cov-matrix` archived change 的 commit pattern(2026-06-15):
  - `2f538e2 ci(openspec): add ci-cov workflow + CLAUDE.md CI trigger rule`
    + `.github/workflows/ci-cov.yml` +52 行,`CLAUDE.md` +13 行
  - `a8a9d34 chore(openspec): archive ci-integration-cov-matrix`
  - 2 commits,no new test code

- `services/mcp/pyproject.toml` 已写好 `[tool.pytest.ini_options].addopts =
  "-v --cov=app --cov-report=term-missing --cov-fail-under=100"`,跟 ci-cov
  workflow 的 "Install service + test deps" + "Run pytest (cov-fail-under=100
  from pyproject addopts)" 段兼容,**无需改 pyproject**

- 4 个现有 ci-cov matrix service 共享 `conda run -n chatbiz pip install -e .`
  + `pip install pytest pytest-cov pytest-asyncio respx`。`mcp` pyproject 的
  `[project.optional-dependencies].dev` 含 pytest / pytest-asyncio / pytest-cov
  / respx,跟其它 4 service 一致,**无需扩 install 段**

- 本机 mcp editable install Location 指向 `/private/tmp/chatbiz-mcp-fetch/...`
  (已不存在,broken) — 但这跟 CI matrix 无关(CI 在自己 VM 上从 source 装,
  不用本机 pip cache);本机 `--check` 报 mcp [FAIL] 是已知 broken state,
  留作独立 followup(setup-chatbiz-env `--service mcp` 修),不进本 change

## 决策链

### Q1: scope 收窄到什么?

选项:
- A. 只加 mcp 进 ci-cov matrix(2 处 +1 行)
- B. A + 修本机 mcp editable install 路径(`bash tools/setup-chatbiz-env.sh
  --service mcp` 装)
- C. A + B + 把 mcp 加进 setup-chatbiz-env.sh SERVICES 数组
- D. 全部(连 workflow-engine 一起拉进 matrix)

拒绝 B / C / D 的理由:
- B:本机 pip cache broken 跟 CI matrix 决策无关,2 个独立 concern。本 change
  不动本地 env 状态。留作独立 followup
- C:`tools/setup-chatbiz-env.sh` D6 决策("本脚本只覆盖 ci-cov matrix 的 4
  service,不含 workflow-engine / mcp,YAGNI")在 setup-chatbiz-env (2026-06-16
  archive) 刚 locked-in 不到 1 session,立刻推翻会引争议。等真有 2nd use
  case 时再扩
- D:workflow-engine 仍 0% cov,本 change scope 跟它无关,留给 workflow-engine
  自己的 cov change 处理

**选 A**。理由:本 change 是关 followup 的最小动作。

### Q2: ci-cov.yml 改 1 行 vs 重构?

选项:
- A. `matrix.service` 列表顺序追加 `mcp`(1 行)
- B. 重新排序把 mcp 放合适位置 + 改 2-3 行

**选 A**。理由:跟现有 4 service 顺序保持一致(audit-and-isolation /
credential / gateway-scanner / sso),mcp 自然 append 在 sso 之前(字母序
gateway-scanner 之后)。CLAUDE.md 同步按同序。

### Q3: 写 test 吗?

选项:
- A. 不写新 test,只改 workflow + CLAUDE.md
- B. 写 1 个 regression test 验证 ci-cov.yml 包含 mcp

**选 A**。理由:本 change 不加 prod code / 测试基础设施;`tests/` 不动。
B 的 "regression test" 其实是 meta-test (测 yaml 内容),跟"cov 100% 闸门"
是两回事,价值低。

## 开放问题(本轮已决)

无。

## 设计取舍

1. **不做 mcp editable install 修**:`/private/tmp/chatbiz-mcp-fetch/...`
   broken 跟 CI 无关,留独立 followup
2. **不动 setup-chatbiz-env**:D6 决策 1 session 内刚 lock,不立刻推翻
3. **不动 workflow-engine**:跟本 change scope 无关
4. **matrix 顺序**:alphabetical + audit-and-isolation 锁定排头 → mcp
   排第 4(在 sso 前)

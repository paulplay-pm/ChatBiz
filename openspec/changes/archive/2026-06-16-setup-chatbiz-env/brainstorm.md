<!--
Raw capture of superpowers:brainstorming output for setup-chatbiz-env.

本档原样捕捉 brainstorming skill 的产出。skill 的自然产出是 decision log
格式(背景 → 决策链 Q1-Qn → 设计取舍)。

design.md 从本档萃取并重新整理为结构化设计文件。
不要将本档的内容复制到 design.md — design.md 是独立的重组产物,两者互补但不重叠。
-->

# Brainstorm: setup-chatbiz-env (decision log)

## 背景

ChatBiz 当前阶段:**pre-build**,`docs/architecture.md` + `docs/prd.md` 已冻结,
eng-review 12 个工程决策已 locked-in。最近 4 周集中把 4 service (audit-and-isolation /
credential / gateway-scanner / sso) 推到 100% line cov,加 ci-cov workflow。
13 个 openspec change 全 archive。

本轮新需求(来自 ci-integration-cov-matrix retrospective,2026-06-15 收尾时 surface):

> ✅ scaffold-cleanup + setup-chatbiz-env — 杂点清理

即"新开发者入职第一步,需要在 README / CLAUDE.md 之外,有 1 个能跑的 1-shot
脚本把 chatbiz conda env + 4 service dev deps 全部装好"。memory
[[conda-chatbiz-env]] 锁定了"必须用 chatbiz conda env,禁止 base / uv",但
没有脚本支撑 — 当前是口头约定。

上一轮 followup 探查还发现 "scaffold-cleanup" 部分是 0 work(没 openspec-specs-*.md
遗留、没 nested 空目录、`scripts/` 目录不存在),所以本 change scope 收窄为
**只做 setup-chatbiz-env**,scaffold-cleanup 0 work 在本 change 里**不**展开
(用户确认选 "只做 setup-chatbiz-env" 选项)。

## 项目 context 摸底

- `tools/check-compose-naming.sh` 是现成的同 pattern 单文件 shell script:
  - 头部 docstring 写决策背景 + Usage + Exit codes
  - `set -euo pipefail`
  - bash 4+ / macOS BSD awk 兼容(用 `[^[:space:]]` 替代 `\S`)
  - `chmod +x` 后 git-tracked
  - `--strict` / `--show-baseline` flags 模式

- 4 service pyproject 全部 PEP 621 + setuptools.build_meta(credential / sso
  有更全的 metadata 段但 build 模式一致):
  - `[project.dependencies]` 走运行时
  - `[project.optional-dependencies].dev` 走 dev(测试 + lint)
  - **无 Poetry lock**,所以 deps 安装统一 `pip install -e ".[dev]"` 即可

- `chatbiz` conda env 在 /opt/anaconda3/envs/chatbiz 存在(本机已装);4 service
  中 audit-and-isolation / gateway-scanner 已 editable install 在 main 仓库路径。
  credential / sso 还没装(它们对应的 retrospective cov 是 13 commits 期间完成
  的,装 deps 在 sso-routers-coverage / sso-jwt-utils-coverage 那些 change 里
  没显式登记,只跑了 pytest)。

- 工作流要求:CI 触发约定锁定的 matrix = `[audit-and-isolation, credential,
  gateway-scanner, sso]`,workflow-engine / mcp 收尾时再加。本脚本只覆盖这 4
  service,不预先扩到 workflow-engine / mcp(避免 YAGNI)。

## 决策链

### Q1: 单一 shell script vs Makefile / taskipy / hatch env?

选项:
- A. `tools/setup-chatbiz-env.sh` 单文件 shell(沿用 check-compose-naming pattern)
- B. Makefile 包装 shell(`make setup`)
- C. root `pyproject.toml` + `[tool.taskipy]`
- D. 用 `hatch env create`

拒绝 B / C / D 的理由:
- B — 仓库现状**无** Makefile(CLAUDE.md "Commands" 段明说"没有 build / lint / test
  命令"),为 1 个 setup 引入破例,跟"零框架"约定冲突。
- C — 仓库**无** root pyproject.toml;且 taskipy 要装进某个 env,setup 行为本身
  在调 conda + pip,shell 最直接。
- D — hatch 是 build tool,本仓库 build 用 setuptools.build_meta;且 hatch env
  create 跟"必须用 conda"锁定冲突。

**选 A**。理由:沿用既有 `tools/` 单文件 shell 模式,零依赖,跟项目"零 build
框架"约定一致。

### Q2: `--check` 模式怎么实现?

初版用 `python -c "import jose"` 之类 import probe — 失败。**根因**:同 env 内
多个 service 的 deps 互相覆盖,`jose` 被 audit-and-isolation 装上后,即使
sso 没装,`import jose` 也成功 → 假阳性。

修正:用 `pip show <pkg-name>` 拿 `Location` 字段,跟 `services/<name>/` 实际
路径精确比对。**worktree 路径 ≠ main 路径 → FAIL**,这是正确信号(提示
"this service 还没在这个 worktree 装,跑 `--service <name>` 装")。

**选 Location 比对**。

### Q3: 真装 vs 干跑区分?

- 全量装:`conda create` (if env not exists) + `pip install -e ".[dev]"` × 4
  service
- 干跑:`--check` 只做 conda env existence + editable install location 校验,
  **不调 pip upgrade / install**
- 单 service:加 deps 改 pyproject 后 `--service <name>` 重装

`--check` 不调 `pip install --upgrade pip wheel setuptools`,因为那是
modification。改完后 `pip install` 在 [1/3] 段被 gate 在 `MODE != "check"`。

### Q4: 把 `chatbiz` env 写死还是参数化?

- 写死(env name = `chatbiz`):跟 memory[[conda-chatbiz-env]] 锁定一致
- 参数化(`--env-name <name>`):YAGNI — 本仓库没理由多 env

**写死**,参数化留给未来真有需求时再加。

## 开放问题(本轮已决)

无。

## 设计取舍

1. **PEP 621 双 mode 是错的**:4 service 全 PEP 621,setup script 简化掉 Poetry 分支
2. **worktree 路径 ≠ main 路径**:`--check` 应 FAIL 而不是 silent pass — 这是
   "service 还没 editable install 在 worktree 路径下" 的精确信号
3. **shell 不用 Python**:`pip show | awk` 拿 Location 字段 1 行就够,引入 Python
   import 反而把 setup 的依赖膨胀
4. **不动 workflow-engine / mcp**:本脚本只覆盖 ci-cov matrix 的 4 service,
   YAGNI 原则。等它们收尾时再扩。

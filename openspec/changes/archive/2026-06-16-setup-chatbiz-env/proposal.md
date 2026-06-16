# setup-chatbiz-env — Proposal

## Why

memory [[conda-chatbiz-env]] 锁定"Python 后端必须用 `chatbiz` conda env,禁止
anaconda3 base / uv"(2026-06-11 P2 回归时 base 缺 jose / langgraph 触发),但
当前**没有 1-shot 脚本支撑这条约束** —— 新开发者入职是口头约定,4 service dev
deps 各自手工 `pip install -e ".[dev]"`,易遗漏。

ci-integration-cov-matrix retrospective (2026-06-15) 收尾时把
"setup-chatbiz-env + scaffold-cleanup" 列为 followup,后者经摸底确认是 0 work
(没 openspec-specs-*.md 遗留、没 nested 空目录、`scripts/` 目录不存在),本
change scope 收窄为**只做 setup-chatbiz-env**。

预期收益:
1. 新开发者 1 条命令从 0 到能跑 `pytest`
2. CI pre-flight hook 可调 `--check` 精确校验 4 service editable install 路径
3. 仓库"零 build 框架"约定不动(沿用 `tools/check-compose-naming.sh` 模式)

## What Changes

**新开发者入职流程**
- From:口头约定 `conda activate chatbiz` + 手工 `cd services/<x> && pip install -e ".[dev]"` × 4
- To:`bash tools/setup-chatbiz-env.sh` 1-shot 完成 env + 4 service dev deps
- Reason:消除口头约定的隐式知识 + 减遗漏
- Impact:non-breaking;既有开发者不受影响(本机 env 仍 work)

**CI pre-flight 校验**
- From:无可用脚本判断"某 service 在某路径是否 editable install"
- To:`bash tools/setup-chatbiz-env.sh --check` 用 `pip show <pkg> | Location` 精确校验
- Reason:避免 import probe 假阳性(实测 sso 没装时 `import jose` 仍成功,因 audit-and-isolation 装了)
- Impact:non-breaking;新能力

**CLAUDE.md 文档**
- From:无 setup 指引段
- To:加 1 段 "Python 后端环境设置(强制)" 11 行
- Reason:跟既有"CI 触发约定" / "前端目录约定" 同模式
- Impact:non-breaking;纯文档

## Capabilities

### New Capabilities
- `dev-env-setup`: `tools/setup-chatbiz-env.sh` 4 mode (full / `--check` / `--env-only` / `--service <name>`),自动装 `chatbiz` conda env + 4 service (audit-and-isolation / credential / gateway-scanner / sso) 全部 dev deps。`--check` 模式用 `pip show <pkg> | Location` 精确校验 editable install 在 `services/<name>/` 实际路径。

### Modified Capabilities
无。本 change 不触及任何现有 spec 的 REQUIREMENT 改动 —— 纯新增工具脚本 + 1 段 CLAUDE.md。

## Impact

- **新增文件**:`tools/setup-chatbiz-env.sh`(144 行,chmod +x,git-tracked)
- **修改文件**:`CLAUDE.md` +1 段(11 行,引用 `tools/setup-chatbiz-env.sh`)
- **触及文档**:`openspec/changes/setup-chatbiz-env/{brainstorm,design,proposal,specs,tasks,plan}.md`
- **不触及**:任何 service 代码 / pyproject.toml / docker-compose / GitHub workflow / 端口表 / 前端 / 数据库
- **eng-review 决策引用**:
  - 不触及 12 个 eng-review 锁定决策(eng-review 决策都是关于"运行时架构"如 Lead Agent、4 错误边界、数据隔离网关等,跟 dev tooling 不重叠)
  - 跟 CI 触发约定(`[audit-and-isolation, credential, gateway-scanner, sso]` matrix)对齐 —— 本脚本装 deps 的 4 service = CI matrix 4 service
- **FUTURE-IMPLEMENTATION**:不适用(本 change 是 dev tooling,不是产品功能)
- **前端范围**:无前端改动(纯 Python 后端 dev tooling)
- **后端范围**:新增 1 个 dev-only shell script,不进运行时
- **豁免前端理由**:纯 dev tooling,跟 UI / SPA / 浏览器无关
- **3 个具名用户(paul / leo / anny)**:不触及(本 change 是工程 dev tooling,不是用户功能)
- **非目标**:
  - 不引入 Makefile / taskipy / hatch(项目"零 build 框架"约束)
  - 不装 workflow-engine / mcp 2 个 0% cov service(YAGNI)
  - 不做 env 卸载 / 重建
  - 不处理 conda 自身安装
  - 不替代 `docs/architecture.md` / `docs/prd.md`

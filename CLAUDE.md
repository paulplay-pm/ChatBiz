# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**ChatBiz** — enterprise AI agent 平台,正在从 0 研发。当前状态:**设计已冻结,代码尚未开始**。

### 工作产物

- `docs/architecture.md` — 70 KB 中文技术架构文档,对比了 7 个 AI Agent 平台(DeerFlow / OpenClaw / Hermes / Dify / n8n / LangChain / LangGraph),设计了"ChatBiz Agent Platform"的 6 层企业级架构,包括 Lead Agent / Sub Agent 的运行时设计、LangGraph StateGraph 编译路径、12 类工作流节点、4 层记忆系统等。
- `docs/prd.md` — 166 KB 产品需求文档(v1.5),8 个章节覆盖 6 个核心模块(工作流 / Agent / 知识库 / 插件 / 模型 / 系统)、4 类用户、3 个使用场景(智能客服 / 数据分析 / 合同审核),有 MVP / V1.0 / V1.5 / V2.0 的 4 阶段里程碑。
- `docs/prototype.html` — 370 KB / 4562 行 HTML 原型,展示产品的 UI 形态。
- `openspec/` — OpenSpec 工作流,默认 schema 为 `superpowers-bridge`(中文 + 严格测试/审计/标签规则)。
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` — **已批准的 design doc**(office-hours + plan-eng-review 2 轮对抗式评审,12 个 finding 全部 locked-in),所有 12 个 implementation tasks 落地在 `tasks-eng-review-20260610-001717.jsonl`。
- `LICENSE` (MIT), `.gitignore`, single commit "Initial commit" on `main`。

**设计事实的最终来源 = `docs/architecture.md` + `docs/prd.md` + 那个 design doc(3 件合起来)**,不要只引用其中一个。

### 项目身份(用户在这次 init 里明确的)

- Lead Agent / Sub Agent 模式:见 `docs/architecture.md` §4.3.2(基于 LangGraph StateGraph 实现的 Lead + Sub-Agent 委派)
- Workflow 引擎:见 `docs/architecture.md` §4.3.1(自研画布 + 自研节点 + LangGraph 编译)
- 整体设计:见 `docs/architecture.md` §4

## Conventions from `openspec/config.yaml` (强制)

所有 OpenSpec 变更产物必须遵守:

- **语言**: 所有产出物 + 模型回复用简体中文
- **Source of truth 顺序**:`docs/architecture.md` > `docs/prd.md` > design doc。任何 spec 跟这三者冲突,先回到源头改,再写 spec
- **Future-implementation tag**:`[FUTURE-IMPLEMENTATION]`(仓库目前 0 行源代码,任何 spec 触及 API/DB/前端 都要标)
- **Tech stack consistency**:`design.md` 的技术选型必须与 `docs/architecture.md` §4.4 一致;偏离需要书面理由 + `architecture.md` 更新提案
- **Spec language**: Requirement 用 `SHALL` / `MUST`;每个 Requirement 至少一个 `#### Scenario:`(WHEN/THEN)
- **Task discipline**: 任务 ≤ 2h;编码任务配对验证任务;不允许"先实现后补测试"
- **测试覆盖率** (per config): 单元 ≥100% / 接口 100% / 安全全覆盖
- **后端规范** (per config): Python 走 SQLAlchemy ORM + 异步 + 审计埋点
- **前端规范** (per config): React 组件化 + TypeScript 严格 + Hooks + 状态隔离

完整规则在 `openspec/config.yaml` —— 写新 change 之前先读。

[FUTURE-IMPLEMENTATION] `docs/architecture.md` §4.3.Y PII 规则集段落即将在 `gateway-egress-enforcement-p0` apply 阶段补全,引用 `services/audit-and-isolation/app/pii/{rules,detector,redactor,reverser}.py` 作为权威实现。

## 已锁定的工程决策(eng-review 2026-06-10,12 finding 全部 approved)

来自 design doc `## GSTACK REVIEW REPORT`,**不要再重新讨论**:

1. **数据隔离网关 = egress 强制点**(不是 ingress)。2 实例 HA + 健康检查 + 跨网关 trace-id 关联。失败 = 所有 LLM 调用挂,这是 P0 单点
2. **12 个节点类型共享一份 Node Contract**(TypedDict)。同一份代码生成:画布 UI 组件 + StateGraph 节点函数 + I/O schema + 验证函数。12 × 4 = 48 个组件从 1 个源生成
3. **四层记忆**(工作 / 短期 Redis / 长期 PostgreSQL / 语义 Milvus),见 `docs/architecture.md` §4.3.X(eng-review 决定补的小节)
4. **Workflow + Chatflow 都用同一个 LangGraph StateGraph**,Chatflow 是 Workflow 的 "loop back" 变体
5. **MVP 包含 MCP 集成**(filesystem / fetch / postgres 三个核心 server)
6. **人工审批节点**:LangGraph Checkpointer 到 PostgreSQL + 通知渠道(企微/邮件/站内信 至少 1 个) + 审批人 web UI 重新进入 + 24h 默认超时
7. **代码生成 Node Contract**:4 份代码从 1 份 dataclass schema 生成
8. **状态双层**:PostgreSQL(workflow state, source of truth)+ Redis(画布实时状态,event sourcing)
9. **错误处理 4 边界**:canvas drag-loop / runtime(LLM 5xx / timeout / 限额)/ user(参数不全)/ security(未授权凭证)
10. **3 层测试 + LLM eval**:pytest 单元 + 集成(LangGraph e2e)+ Playwright E2E + 50 paul 财务月报 LLM eval 基线
11. **4 个 critical path 100% 覆盖**:paul 财务月报 end-to-end / 网关 PII 拦截 / 人工审批中断续接 / 插件加载降级
12. **5 个存储量预估**:audit log 780GB/3mo / workflow state 500MB / Milvus 100GB(1B chunks)/ canvas JSON 500MB / MinIO 文档 10TB/year

## 团队 + 时间线(已锁定)

- **总周期**:9-12 月(C-level sponsor 承诺)
- **FTE**:5-7 人(month 1-9);month 10-12 收尾 2-3 人
- **MVP**:month 2-3 数据隔离网关 + 自研画布 + paul 财务月报 workflow + 基础审计
- **里程碑**:月 2-3 MVP / 月 6 完整数据隔离 + 基础画布 / 月 9 完整版
- **3 个具名用户**:paul(财务运营)/ leo(基础服务)/ anny(增值服务)
- **关键稀缺角色**:LangGraph 后端 × 1、React Flow / X6 资深前端 × 2、Month 1 必须到位

## Commands

**没有** build / lint / test 命令 —— 仓库 0 行源代码,没有 `package.json` / `pyproject.toml` / `Makefile` / CI。**不要试图跑一个。**

唯一 CLI 是 `openspec`(全局装好):

- `openspec schemas` — 列出可用的 change schemas
- `openspec schema validate [name]` — 验证 schema(默认 `superpowers-bridge`)
- `openspec new change <kebab-name>` — 脚手架新 change
- `openspec instructions <artifact> --change <name> --json` — 取下一个 artifact 的指令 + 模板
- `openspec status --change <name>` — artifact 进度 + 是否 apply-ready
- `openspec list` — 列出活跃 changes

实现期真正会用的命令(预计):`pytest`, `uv run`, `pnpm dev`, `kubectl`, `docker compose`(都没装,因为没代码)。

## 项目约定

- **Source of truth = `docs/architecture.md`**(注意小写 a)+ `docs/prd.md` + `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md`。任何 spec 跟其中之一冲突,先 surface,再回到源头改。
- 所有 spec/change 走 `openspec/` schemas。不要在 repo 根创建 ad-hoc 设计文档。
- 默认 schema = **`superpowers-bridge`**(`openspec/config.yaml` 设的)。schema 内部依赖 superpowers plugin 的 `brainstorming` skill。
- `openspec/` 整个目录在 `.gitignore` 第 181 行(下推到本机配置)。如果要 schema/spec 改动入库,改 `.gitignore` 加 `!openspec/schemas/` 之类白名单,且**先问用户**。
- AI-tool 配置目录(`.claude/`、`.codex/`、`.opencode/`)都在 `.gitignore` —— 是 per-developer,不是团队的。
- 仓库根 `CLAUDE.md` 是这个文件 —— 跟 `openspec/config.yaml` 配合使用,**两者都遵循**。

## Working here (按当前阶段给指南)

### 如果用户问"实现 X"

仓库 0 行代码。**先开一个 `openspec new change`** 而不是直接开写代码。Change 走 `superpowers-bridge` 流程:**brainstorm → proposal → design → specs → tasks → plan → apply → verify → retrospective**。design 阶段对照 `docs/architecture.md` §4 和已锁定的 12 个 eng-review 决策,避免重写。

### 如果用户问"加一段 architecture"

**99% 的情况** 是应该改 `docs/architecture.md`,不是写 code。改之前先 surface 在 `CLAUDE.md` / openspec change / 直接的 chat 里 —— 至少在 design doc / eng-review report 里留个引用。

### 如果用户问"加 build / test / 框架"

这是**重大 scope 变更**。需要先确认:这是真的要把仓库从设计态推到实现态,还是只是一个针对某个 service 的轻量 build(比如 sandbox 实验)?

如果是真的推到实现态:先开一个 `openspec new change <feat>` 走完整流程。

### Superpowers 依赖

`superpowers-bridge` schema 依赖 `superpowers@claude-plugins-official` plugin。技能 `brainstorming` / `writing-plans` / `using-git-worktrees` / `subagent-driven-development` / `finishing-a-development-branch` / `test-driven-development` 都装好了。**不要去 stub 这些技能**,直接用。

### OpenSpec 命令命名空间

OpenSpec CLI 用 `openspec-*`(`openspec-propose` / `openspec-explore` / `openspec-apply-change` / `openspec-archive-change`)。upstream `superpowers-bridge` README 引用 `/opsx:*` —— 这些 slash command 跟已装的 CLI 不是 1:1 映射。**优先用已装 CLI 的实际命令名**。

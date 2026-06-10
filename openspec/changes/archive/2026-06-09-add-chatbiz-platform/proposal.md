## Why

企业内部存在 AI 工具滥用与重复劳动两类并行问题。paul/leo/anny 三个具名团队成员目前用公网 AI 工具(ChatGPT、文心等)分析内部文档、整理数据,导致内部数据流入公网 AI 训练管线 —— 这是合规红线,而非想象的威胁。现在仓库 docs/ 三件套(架构 + PRD + 原型)已冻结、eng-review 12 个工程决策已锁定,正是从设计推到实施契约的时机;先生成完整 OpenSpec 规范,再开实施 change。

## What Changes

**OpenSpec 规范创建**
- From: 仓库 0 行代码,无 OpenSpec 规范契约。
- To: 9 个核心 capability + 3 个横切 capability 的 spec,作为后续实施的契约基础。
- Reason: 跨 change 实施时需要"做什么"的统一参考;没有 spec,各 change 会冲突。
- Impact: non-breaking。仓库当前无代码,本 change 纯文档产物。

**[FUTURE-IMPLEMENTATION]** 本 change **不实现任何代码**。它是规范定义,不是实现 change。后续每个 capability 的实施将开新 change(走 openspec-apply)。

## Capabilities

### New Capabilities

(全部 9 核心 + 3 横切 = 12 个新 capability,按 PRD §3 + Arch §4 真实模块边界)

**9 核心(对应 PRD §3 框图 + Arch §4.3 关键组件):**
- `workflow-engine`: 可视化工作流编排(画布 + 12 节点 + LangGraph 编译),对应 PRD §4.1 / Arch §4.3.1。
- `agent-runtime`: Lead Agent + Sub Agent 委派,基于 LangGraph StateGraph,对应 PRD §4.2 / Arch §4.3.2。
- `knowledge-base`: 知识库管理 + RAG 配置,对应 PRD §4.3 / Arch §4.3.4 (RAG Engine)。
- `plugin-market`: 工具扩展(MCP 集成 + 自定义插件),对应 PRD §4.4 / Arch §4.3.5 (Tool Registry)。[ENG-Arch #5] MVP 含 3 个核心 MCP server。
- `model-management`: 模型配置 + 路由 + 限流,对应 PRD §4.5。
- `system-management`: 用户/角色/部门/权限管理 + 多租户,对应 PRD §4.6 / Arch §4.2 (Workspace 隔离 + RBAC)。
- `channel-management`: 通道管理(Web/钉钉/企微/飞书),对应 PRD §4.6 + Arch §4.1 接入层。
- `credential-management`: 凭证创建 + 加密存储 + API Key 管理,对应 PRD §8.2 MVP P0。
- `skill-management`: 技能浏览 + 安装 + 创建 + 绑定 Agent,对应 PRD §8.3 V1.0 P1。

**3 横切(覆盖 eng-review 锁定的平台级 concern):**
- `audit-and-isolation`: 数据隔离网关(egress 强制点) + 审计日志 + 跨网关 trace 关联,对应 [ENG-Arch #1] + [ENG-Perf #1] + [ENG-Quality #3] 4 错误边界。
- `monitoring`: 基础监控面板 + 执行日志 + 告警配置 + 链路追踪,对应 PRD §8.2 MVP P0 + §8.3 V1.0 P1。
- `api-gateway`: API 服务 + 自动生成 API + API Key 鉴权 + MCP Server 暴露,对应 PRD §8.3 V1.0 P1。

### Modified Capabilities

(无 — 仓库目前无既有 capability。)

## Impact

**Affected artifacts:**
- `docs/architecture.md` §4 — 实施时按此 spec 推进
- `docs/prd.md` §3 + §4 + §8 — 实施时按此 spec 推进
- `openspec/schemas/superpowers-bridge/` 已装 schema — 12 个 cap 全部走此 schema

**Affected services (per Arch §4.5 部署):**
- Web Frontend (React SPA) — 工作流画布、Agent 配置、监控面板
- API Gateway (Kong/Nginx) — 12 个 cap 全部通过此暴露
- Workflow Engine + Agent Runtime + Tool Executor + RAG Service + Model Proxy + Sandbox + Auth + Audit + Notification — 9 核心 + 3 横切的 12 个服务

**Affected eng-review decisions (12 个全部 locked-in,本 spec 必须遵守,引用 [ENG-#N] 即可,不在 spec 内复述):**
- 4 critical path 100% 覆盖:paul 财务月报 / 网关 PII 拦截 / 人工审批中断续接 / 插件降级 [ENG-Test #2]
- 3 层测试金字塔 + LLM eval [ENG-Test #1]
- Node Contract 驱动 12 节点类型 [ENG-Arch #2, Quality #1]
- 数据隔离网关 = egress 强制点 + HA + trace [ENG-Arch #1]
- MCP 集成 MVP 必含 [ENG-Arch #5]
- 状态双层 PostgreSQL + Redis [ENG-Quality #2]

**Non-goals (明确不做):**
- Mobile / Flutter 通道 [推迟 V2.0+ per ENG-Out of Scope]
- 插件市场第三方开发者生态 [推迟 V2.0+]
- 多租户 SaaS 化(本 spec system cap 只做单租户 + RBAC,不做 SaaS)
- 智能音箱 / 邮件集成通道 [V2.0+]
- 复杂 Agent 自治 / LangGraph 图计算深度用法 [V2.0+]
- 跨平台 SSO / SAML / OIDC [V1.0+ 用企微/钉钉扫码]
- 海外模型合规审批 [MVP+ 用国内模型]
- i18n 国际化 [MVP 不做]
- 7+ 节点类型(LangGraph 高级、HTTP、代码执行、人工审批、子流程、参数提取、变量赋值) — MVP 只覆盖 PRD §8.2 列的 8 个 P0,其余 V1.0+ 补
- `verify` + `retrospective` artifacts — 这些是 post-apply 的,不在本 change 范围

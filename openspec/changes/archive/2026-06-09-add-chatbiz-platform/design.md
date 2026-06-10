## Context

**当前状态:** 仓库 0 行源代码,处于 pre-build 阶段。

**已冻结的 3 件源:**
- `docs/architecture.md` §4(技术架构,中文,约 980 行)
- `docs/prd.md` v1.5(产品需求,中文,8 章节 + 4 阶段里程碑)
- `docs/prototype.html`(HTML 原型,4562 行)

**已锁定的工程决策:** eng-review 12 个 finding,详见 `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` 的 `## GSTACK REVIEW REPORT`。本设计文档必须遵守这些决策,以 `[ENG-#N]` 引用之,不重提。

**Stakeholders:**
- 3 个具名内部用户:paul(财务运营)、leo(基础服务)、anny(增值服务)
- C-level sponsor(9-12 月预算承诺)
- 5-7 FTE 实施团队(1 后端网关 + 1 后端 LangGraph + 2 前端画布 + 1 全栈 + 0.5 运维)

**本 change 的本质:** OpenSpec 规范定义,不是实现 change。后续每个 capability 的实施将开新 change。

## Goals / Non-Goals

**Goals:**
- 为 9 核心 + 3 横切 capability 提供完整的 OpenSpec 规范(spec.md + SHALL/MUST 表述 + Scenario)
- 引用 eng-review 12 个锁定决策,确保实施时不会重新讨论
- 标识 3 个具名用户场景的"必中 wedge"和 4 个 critical path 100% 覆盖
- 描述 capability 间的依赖关系(workflow→agent、workflow→knowledge 等)
- 严格遵循 [FUTURE-IMPLEMENTATION] 标注,所有触及代码的 spec 标为此类(本 change 不实现代码)

**Non-Goals:**
- 不实现任何代码 —— 本 change 纯规范定义
- 不修改 `docs/architecture.md` —— 设计事实源已冻结
- 不创建工作流或 agent 的具体实现 —— 这些由后续 change 实施
- 不集成第三方 LLM 服务的实际凭证 —— 凭证管理是 capability,不在本 change 范围
- 不做 i18n 国际化 [MVP 不做]
- 不做 Mobile/Flutter 通道 [V2.0+]
- 不做多租户 SaaS 化 [本 spec 仅单租户 + RBAC]
- 不做插件市场生态 [V2.0+]
- 不做 verify + retrospective artifacts —— post-apply 阶段产物

## Decisions

### D1: Capability 划分 (9 核心 + 3 横切 = 12 个)
- **选择:** 按 PRD §3 模块边界 + Arch §4.3 关键组件,9 个核心 capability + 3 个横切 capability。
- **理由:** 6 个不够细(把 credential/channel/skill/monitoring/audit/api-gateway 塞进 system 会变 god module),12 个刚好每个有清晰 single responsibility,符合 openspec 的 spec-driven 哲学(每 cap 一个 spec 文件)。
- **已考虑 alternative:** 拆 6 个 — 拒绝理由:god module + spec 难以独立 review。

### D2: 数据隔离网关 = 横切 capability (`audit-and-isolation`)
- **选择:** 网关独立成 `audit-and-isolation` capability,跨所有 LLM 调用边界。
- **理由:** 网关是平台级 concern,只属于任何一个模块都会导致 spec 间不一致。[ENG-Arch #1] 锁定为 egress 强制点 + HA + trace 关联。
- **已考虑 alternative:** 塞进 workflow 或 agent —— 拒绝理由:网关跨越所有 LLM 边界,scope 不匹配。

### D3: Node Contract 写 design.md 不写 spec
- **选择:** Node Contract(TypedDict 驱动 12 节点 4 份代码生成)是设计决定,写进 design.md §Decisions,引用 `[ENG-Arch #2, Quality #1]`,不进 spec。
- **理由:** spec 是"做什么"契约,Node Contract 是"怎么做"实现选择。spec 不锁实现。
- **已考虑 alternative:** Node Contract 写 spec requirement —— 拒绝理由:污染 spec,锁定实现。

### D4: critical path 写在 verify 不写 spec
- **选择:** 4 个 critical path(paul 财务月报 / 网关 PII 拦截 / 人工审批中断续接 / 插件降级)作为 verify artifact 的产物,引用 `[ENG-Test #2]`。
- **理由:** critical path 是"如何证明做到"的工具,不是 spec 的契约。
- **已考虑 alternative:** 4 个 critical path 写 spec requirement —— 拒绝理由:让 spec 变测试驱动,污染意图。

### D5: Workflow + Chatflow 复用同一 LangGraph StateGraph
- **选择:** workflow-engine cap 内 spec 一个 `mode: workflow|chatflow` 参数,runtime 复用同一 StateGraph,chatflow 是 workflow 的 "loop back" 变体。
- **理由:** [ENG-Arch #4] 锁定。
- **已考虑 alternative:** 两个独立 runtime —— 拒绝理由:60% 代码重复 + 调度路径多 1 倍。

### D6: MVP 范围按 PRD §8.2 1-2 月 8 个 P0,不全栈自研
- **选择:** MVP 仅交付 PRD §8.2 列的 8 个 P0(画布基础节点 + LLM 节点 + 知识库 + 模型管理 + 凭证管理 + 系统管理 + 监控 + 通道管理)。workflow-engine cap 内的 12 节点只 MVP 必含的 4-5 个,其余 7+ V1.0+ 补。
- **理由:** PRD 是产品需求,1-2 月 MVP 是产品方认可的范围;eng-review 的 9-12 月全栈自研是工程评估,不是 spec 范围。
- **已考虑 alternative:** 全部 12 节点 + 9 核心 cap 都在 MVP —— 拒绝理由:超出 PRD §8.2 MVP 范围,9-12 月是实施估算,不是规范定义。

### D7: 所有 cap 引用 eng-review 12 决策,不复述
- **选择:** 每个 spec 顶部列 `eng-review-refs: [ENG-#N1, ENG-#N2, ...]`,不复制决策内容。
- **理由:** DRY + 单一 source of truth(设计 doc 的 ## GSTACK REVIEW REPORT)。
- **已考虑 alternative:** 每个 spec 复制相关决策段落 —— 拒绝理由:DRY 违反 + 容易跟 design doc 不一致。

### D8: Capability 依赖关系只 mention,不 require
- **选择:** 在 spec.md 顶部列 `depends_on: [other-cap, ...]`,不写具体调用语义(具体语义在 design.md)。
- **理由:** spec 之间不互相 require → 可独立 review;实施时要读所有 spec 才能拼装。
- **已考虑 alternative:** 在 spec 内用 SHALL 写跨 cap 行为 —— 拒绝理由:god-spec,跨 12 cap 行为交织难以维护。

### D9: Channel MVP 只做 Web,其他 V1.0+
- **选择:** channel-management cap 包含 Web/钉钉/企微/飞书 4 个通道的实现 spec,但 MVP 阶段仅实现 Web 通道,其他 3 个在 V1.0+ 补。
- **理由:** 3 个具名用户(paul/leo/anny)目前都在 PC + Web 工作流,Mobile IM 通道非 MVP 必需。
- **已考虑 alternative:** 4 个通道都做 MVP —— 拒绝理由:增加 1-2 月工作量,与 PRD §8.2 1-2 月 MVP 冲突。

### D10: 系统管理 = 单租户 + RBAC,不做多租户 SaaS
- **选择:** system-management cap 内 spec 描述 Workspace 隔离(逻辑隔离)+ RBAC,物理部署是单租户内网。
- **理由:** 仓库目标是内网部署企业 AI 平台,不是 to-B SaaS。
- **已考虑 alternative:** system cap 内做多租户 SaaS —— 拒绝理由:scope mismatch,推迟到 V2.0+。

### D11: 数据隔离网关 = egress 强制点(不 ingress)
- **选择:** 网关部署在 API Gateway 与外部 LLM API 之间,所有出站 LLM 请求经此。[ENG-Arch #1]。
- **理由:** 信任边界 = LLM 提供方,网关 = 强制执行点。
- **已考虑 alternative:** 网关在 ingress 拦截入站 —— 拒绝理由:入站控制 = WAF/API Gateway,出站 LLM 审计 = 数据隔离,scope 不同。

### D12: 3 层测试金字塔 + LLM eval 是 spec 验收条件
- **选择:** 每个 cap 的 spec 内 Requirement 包含测试要求(单元 / 集成 / E2E / LLM eval 视情况),引用 `[ENG-Test #1]`。
- **理由:** spec 是契约,验收条件是契约的一部分。"做到"必须可证。
- **已考虑 alternative:** 测试要求只在 verify 阶段写 —— 拒绝理由:实施时容易遗漏测试,spec 内强制更稳。

## Risks / Trade-offs

- **[Risk] 12 个 capability 太多,spec 维护负担大** → Mitigation: 每个 cap spec ≤ 200 行,跨 cap 引用用 `[cap-name]` 简写,不展开。
- **[Risk] 跨 cap 依赖(workflow→agent、workflow→knowledge)实施时容易耦合** → Mitigation: 实施时 worktree-per-cap 隔离,跨 cap 集成在 plan 阶段用 [ENG-#N] 引用锁定决策。
- **[Risk] PRD §8.2 MVP 范围(1-2 月)与 eng-review 9-12 月不匹配** → Mitigation: 实施时按 eng-review 时间线,spec 按 PRD MVP 内容,中间差距由 plan 阶段处理。
- **[Risk] Node Contract 在 design.md 但 spec 引用,在实施时工程师可能绕过** → Mitigation: tasks.md 把 Node Contract 作为前置任务。
- **[Risk] 数据隔离网关 HA 单点(2 实例)是 P0,实施中如果只跑 1 实例就上线** → Mitigation: tasks.md 把"HA 部署"作为部署阶段的强制验收项。
- **[Risk] 3 个具名用户的工作流场景在 spec 阶段描述不清,实施时跟实际场景偏差** → Mitigation: verify 阶段把 3 个具名用户跑 4 critical path 100% 覆盖,任何偏差在 verify 时 surface。
- **[Trade-off] 12 cap 拆分使 spec 间一致性变难维护** → 接受理由:god module 是更大的反模式,跨 cap 引用 + design.md 单一来源是接受的代价。
- **[Trade-off] 不实现 i18n 限制了未来海外子公司使用** → 接受理由:MVP 是内网中国企业,海外不是当前目标;V2.0+ 再考虑。

## Migration Plan

N/A — 本 change 不涉及部署变更(纯 OpenSpec 规范定义,无代码、无服务、无 endpoint、无 DB schema)。

实施迁移由后续每个 capability 的 change 负责(走 openspec-apply + subagent-driven-development + finishing-a-development-branch)。

## Open Questions

1. **MVP 范围冲突**: PRD §8.2 写 1-2 月 MVP / 8 个 P0,eng-review 写 9-12 月全栈自研。**本 spec 按 PRD MVP 范围(8 个 P0)落地,实施时按 eng-review 时间线。**这个 gap 接受吗?
   - 默认:**接受**,因为 openspec change 的范围应该跟产品文档(MVP 定义)对齐,而不是跟工程估算(实施时间)对齐。
2. **12 cap 拆得过细?** 是否应该合并 credential / skill / channel 进 system?
   - 默认:**不合并**,因为每个 cap 有清晰边界(凭证管理 = 加密 + 轮换、技能管理 = 浏览/安装、通道管理 = IM 集成),合并会变 god module。
3. **3 个横切 cap (audit-and-isolation / monitoring / api-gateway) 的归属?** 应该独立成 cap,还是某个 cap 的子模块?
   - 默认:**独立**,因为它们跨所有 LLM/数据/服务边界,scope 跨多 cap。
4. **prototype.html 怎么用?** PRD §6 列了 30+ 屏幕的原型。spec 是否需要为每屏写一个 Requirement?
   - 默认:**不每屏写**,spec 写 cap 级别的能力(例如"工作流画布支持拖拽节点"),UI 细节在 prototype 里。verify 阶段用 Playwright 对照 prototype 截图做 e2e。
5. **数据隔离网关的"凭证加密"细节** (KMS? Vault? 自研?):**留到实施 change**,spec 只说"凭证 MUST 加密存储",不锁实现。
6. **聊天记忆的"短期 Redis"具体 TTL?** 默认 24h,实施时调。

## References (锁定决策)

- eng-review 12 finding 摘要见 `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` 的 `## GSTACK REVIEW REPORT`
- openspec config.yaml 的 `eng-review-decisions` 块已落地 12 finding 摘要
- 9 核心 + 3 横切 capability 的 spec 在 `specs/<cap>/spec.md`
- 实施时按 9-12 月里程碑(MVP 2-3 月 / V1.0 5-6 月 / V1.5 8-9 月 / V2.0 11-12 月)

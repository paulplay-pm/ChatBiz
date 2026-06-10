<!--
Raw capture of superpowers:brainstorming output for the ChatBiz platform change.

Captured 2026-06-10 during /openspec-propose (one-shot generation; no back-and-forth dialogue).
The user invoked this with: "根据 docs/ 目录下的 PRD、架构、原型,为ChatBiz平台生成OpenSpec规范".

This file records the design exploration. design.md reorganizes this into structured sections
(Context, Goals, Decisions, Risks, Migration); do not copy content verbatim.
-->

# Brainstorm: ChatBiz 平台 OpenSpec 规范

## 背景

仓库当前状态:
- 3 个文档已冻结:`docs/architecture.md`(技术架构)、`docs/prd.md` v1.5(产品需求)、`docs/prototype.html`(HTML 原型)
- eng-review 12 个工程决策已 locked-in,写在 design doc 的 `## GSTACK REVIEW REPORT`
- 0 行源代码,pre-build 阶段
- openspec 默认 schema = `superpowers-bridge`,context + rules 块已针对本仓库状态做过调优

用户本次要的不是"实现代码",而是**从 3 个文档反向生成完整 OpenSpec 规范**,作为后续实施的契约基础。

## 决议链

### Q1: 范围
- **决议**:这个 change = **整个 ChatBiz Agent Platform 的规范定义**,不是某个具体 feature。
- **理由**:用户的请求是"为 ChatBiz 平台生成 OpenSpec 规范",且 docs/ 三件套本身已经覆盖了平台全貌。一次生成比拆成 12 个 feature changes 更符合用户意图(否则需要 12 次 openspec-propose,效率低且规范间难以交叉引用)。
- **被拒方案**:拆成 12 个 feature changes (workflow-only / agent-only / ...)。拒绝理由:OpenSpec 不擅长跨 change 的依赖管理,且同一仓库 12 个并行 change 会冲突。

### Q2: 包含什么 capability(规格)
- **决议**:按 PRD §3 + Architecture §4.3 的真实模块边界,**9 个核心 capability + 3 个横切 capability**。
- **9 个核心** (PRD §3 列出):workflow / agent / knowledge / plugin / model / system / channel / credential / skill
- **3 个横切**:monitoring / audit / api-gateway
- **被拒方案**:只写 6 个 PRD §1.3 列的"价值主张模块" — 那 4 个不是真正的模块,是营销框架。拒绝理由:OpenSpec 的 capability 必须对应可独立 spec 化的功能域,营销话语不适合作为 capability。

### Q3: 与现有 eng-review 决策的关系
- **决议**:每个 spec **必须引用** 12 个 eng-review 决策里相关的 finding 编号(`[ENG-#N]`),不重提。
- **理由**:openspec config.yaml 的 `eng-review-decisions` 块已经把这 12 条落地,spec 作者再写一遍是浪费 + 可能写错。
- **被拒方案**:把 12 条决策完整复述到每个 spec 里。拒绝理由:DRY 违反、容易跟 design doc 不一致。

### Q4: 数据隔离网关在哪一层 spec
- **决议**:网关不进任何 capability spec,作为**横切 concern**写在 `audit-and-isolation` capability(对应 eng-review Arch #1)里。
- **理由**:网关是平台级 concern,不是某个模块的内部细节。但它需要专门 spec 因为 P0 单点故障。
- **被拒方案**:塞进 workflow 或 agent 的 spec。拒绝理由:网关跨越所有 LLM 调用边界,只属于任何一个模块都会导致 spec 间不一致。

### Q5: Node Contract 怎么落
- **决议**:Node Contract **不进 spec**,作为 design.md §Decisions 的一条(引用 `[ENG-Arch #2]`);在 `node-contract` capability 里只 spec 它的**外部行为**(从 1 份 schema 生成 12 节点类型的 4 份代码),不 spec 内部实现。
- **理由**:spec 是契约,不是实现说明。Node Contract 本身是 eng-review #2 的"已锁定的设计选择",不该作为 requirement。
- **被拒方案**:把 Node Contract 写成一个 requirement "系统 MUST 用 Node Contract"。拒绝理由:这是实现决定,不是用户可观察的契约。

### Q6: 4 个 critical path 测试
- **决议**:critical path 写在 `verify` artifact(plan-eng-review Test #1+Test #2 的产物),不进 specs。
- **理由**:spec 是"做什么",verify 是"如何证明做到了"。critical path 是 verify 的工具,不是 spec 的 requirement。
- **被拒方案**:4 个 critical path 写成 spec requirements。拒绝理由:让 spec 变得"测试驱动",污染"做什么"和"如何测"。

### Q7: 中文规格还是英文
- **决议**:中文(openspec config.yaml 强制 + 仓库 convention)。
- **理由**:不重提。openspec config 已设。

## 设计取捨

### T1: Capability 数量
**选了 12 个 capability**(9 核心 + 3 横切)而不是 6 个。

理由:
- 6 个 = 把 credential / channel / skill / monitoring / audit / api-gateway 塞进 system,会变成 god module
- 12 个 = 每个 cap 有清晰的 single responsibility,符合 openspec 的 spec-driven 哲学(每个 cap 一个 spec 文件)

但 12 个 cap 的代价:spec 数量多,阅读负担大,跨 cap 的引用复杂。接受这个代价,因为实施时本来就要按 12 个模块组织。

### T2: 跨 cap 依赖怎么表达
- workflow → agent(workflow 可调用 agent)
- workflow → knowledge(workflow 可调用 RAG)
- workflow → plugin(workflow 可调用工具)
- agent → plugin(agent 调工具)
- agent → knowledge(agent 调 RAG)
- agent → skill(agent 加载技能)
- 所有 cap → credential(都需要凭证)
- 所有 cap → audit(都需要审计)
- 所有 cap → monitoring(都需要埋点)
- 所有 cap → api-gateway(都通过网关暴露)

**决策**:在每个 cap 的 spec 顶部**列出 depends_on**,但不写具体调用语义(具体语义在 design.md 里)。spec 之间不互相 require,只互相 mention。这样 spec 可以独立 review,但实施时要读所有 spec。

### T3: 文档的 source of truth 优先级
- docs/architecture.md = 技术事实(最高优先)
- docs/prd.md = 产品需求
- docs/prototype.html = UI 形态参考(非规范性)
- design doc (gstack) = 已锁定的 eng-review 决策
- openspec config.yaml = 工作流 + 项目约定

如果 spec 跟其中之一冲突,**先 surface,再回到源头改**。不接受"spec 写新版本"绕过源。

## Open Questions

1. **MVP 范围的具体边界**:PRD §8.2 列了 8 个 P0 功能项,但 eng-review 建议 5-7 FTE / 9-12 月,远超 PRD 的 1-2 月 MVP。**这个 spec 应该按 PRD 的 1-2 月 MVP 范围,还是 eng-review 推荐的 9-12 月全栈自研范围?**
   - 影响:如果按 PRD MVP 范围,spec 只覆盖 8 个 P0 项的 1-2 月交付;按 eng-review 范围,spec 覆盖 9-12 月全栈。
   - 默认:**按 PRD 的 1-2 月 MVP 范围**,因为 PRD 是产品需求,eng-review 是工程评估。实施时再切到 eng-review 范围。
2. **Channel 8+ 通信渠道(钉钉/企微/飞书/web)**:MVP 阶段是否需要全部 4 个,还是先 1-2 个?
   - 默认:**MVP 只做 Web 通道**,其余 V1.0+ 补。
3. **Mobile / Flutter 通道**:arch §4.1 列了 Flutter,eng-review Out of Scope 推到 V2.0。**这个 spec 不包含 Mobile**。
4. **国际化(i18n)**:PRD 没提。中文 + 英文是双语的"AI agent 平台"通常需要 i18n。**默认:不做 i18n,所有 UI 文本中文**。
5. **多租户 SaaS 化**:arch §4.2 列了"Workspace 隔离 + RBAC",eng-review Out of Scope 推到 V2.0+。**这个 spec 的 system cap 只做单租户 + RBAC,不做 SaaS 多租户**。

## What was already known (不需要重提)

- 4 层记忆(工作 / 短期 Redis / 长期 PostgreSQL / 语义 Milvus):`[ENG-Arch #3]`,在 arch §4.3.X 补详细设计
- 数据隔离网关 = egress 强制点 + HA + trace:`[ENG-Arch #1]`
- Node Contract (TypedDict) 驱动 12 节点类型:`[ENG-Arch #2, Quality #1]`
- Workflow + Chatflow 复用同一 LangGraph StateGraph:`[ENG-Arch #4]`
- MVP 包含 MCP 集成(filesystem / fetch / postgres):`[ENG-Arch #5]`
- 人工审批 = LangGraph Checkpointer + 通知 + 24h 超时:`[ENG-Arch #6]`
- 状态双层 PostgreSQL + Redis:`[ENG-Quality #2]`
- 错误处理 4 边界:`[ENG-Quality #3]`
- 3 层测试金字塔 + LLM eval:`[ENG-Test #1]`
- 4 critical path 100% 覆盖:`[ENG-Test #2]`
- 网关 3 性能项(缓存 / 限流 / 批处理):`[ENG-Perf #1]`
- 5 存储量预估:`[ENG-Perf #2]`

## 待 OpenSpec 后续 artifact 落地的内容

- **proposal.md**:Why(数据泄露 + 3 具名用户)/ What Changes(12 cap 新增) / Capabilities(列出 12 cap)/ Impact([ENG-#N] 引用)
- **design.md**:Context / Goals / Decisions(对应 9 core + 3 cross-cutting)/ Risks / Migration
- **specs/<12 caps>/spec.md**:每个 cap 一个 spec 文件,Requirement 列表 + Scenario
- **tasks.md**:实施步骤,按 9-12 月里程碑组织(MVP / V1.0 / V1.5 / V2.0)
- **plan.md**:执行策略(worktree 分配 + subagent-driven-development)

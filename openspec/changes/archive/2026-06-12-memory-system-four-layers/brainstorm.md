<!--
Raw capture of superpowers:brainstorming output for change `memory-system-four-layers`.
设计来源:eng-review 2026-06-10 锁定的 Arch #3(已 locked-in,不再重新讨论)。
eng-review 原始 finding(逐字引用):
> Arch #3 (P1, 7/10) — "Four-layer memory architecture" (工作/短期/长期/语义) listed in §4.2 but not designed in §4.3.
> Resolution: 补 §4.3.X 详细设计. Add §4.3.X 记忆系统 section: working memory (in-context),
> short-term (Redis, session-scoped), long-term (PostgreSQL, user-scoped), semantic
> (Milvus, topic-scoped). Explicit call sites with Agent/Workflow runtime.
-->

# Brainstorm:4 层记忆系统 §4.3.X 详细设计

## 背景(来自 eng-review 报告)

eng-review 2026-06-10 锁定的 12 个工程决策中,Arch #3 明确"§4.2 列出 4 层记忆
架构,但 §4.3 没有详细设计"。本次 change **不再讨论要不要做**,只落实 §4.3.X
段的**详细设计**:4 层记忆的 call sites(谁写谁读)、写入策略(何时写、写什么格式、
保留多久)、读取策略(检索触发、相关性评分)、容量预估(每层存储上限)、与
Agent/Workflow runtime 的集成点。

仓库现状:§4.3.3 已有 4 层记忆架构图(简要,L1/L2/L3/L4 各 1 段),但 call sites
/ 写入策略 / 读取策略 / 容量预估 / 集成点全部空白。本次 change 在 §4.3.3
**之后**新增 §4.3.X 段(eng-review 报告里已预留 §4.3.X 占位)。

## 决策链(已知,user 已在 eng-review 锁定,本段不需 user 确认)

### Q1:范围边界

- **选项 A** 纯 §4.3.X 段补全 + 交叉引用,不实现新代码 ← **本 spec 选 A**
- B:同时实现 4 层记忆的 service / API / schema
- C:实现一个最小 PoC 验证

**选 A 理由:** eng-review Arch #3 明确"补 §4.3.X 详细设计",不是"补 4 层记忆实现"。
4 层记忆的实现分散在 多个 service(working in LangGraph / short-term Redis(已有
audit-and-isolation 用 Redis)/ long-term PG(已有 audit_log)/ semantic Milvus
待 spec 实施),跨多个 team 推进,本 spec 不抢。

### Q2:与 §4.3.3 关系

- §4.3.3 = 已有,**简要 4 层图**(本次不动)
- §4.3.X = **新增**,§4.3.3 的详细设计补充(eng-review 报告里已预留)

### Q3:spec capability 列表

- 1 个新 capability `memory-system-design`(文档 spec)

### Q4:与 §4.3.Y(PII 规则集,刚由 gateway-egress-enforcement-p0 spec 补)关系

- **并列**。§4.3.Y 描述 PII 处理,§4.3.X 描述 4 层记忆
- 交叉引用:§4.3.X 中 L3 长期记忆可能含 PII,引用 §4.3.Y 的 PII 拦截规则

### Q5:实施约束

- **文档 spec**,不写代码
- verify 是 `grep` 验证 §4.3.X 段存在
- 不创建新 capability 实现,只创建 1 个 `memory-system-design` capability 锁定 §4.3.X 段存在

## 4 层记忆详细设计要点(eng-review #3 锁定范围)

### L1 工作记忆 (Working Memory)
- **存储**:in-context(LLM prompt 内),无外部持久化
- **生命周期**:单次 LLM 调用 / 单次 workflow step 内
- **call site**:LangGraph StateGraph 的 state 字段 / `langgraph.runtime.context`
- **写入策略**:每次 node 执行后自动累积到 state;LangGraph 自带 state propagation
- **读取策略**:下个 node 的 `state` 参数;无显式 retrieval
- **容量上限**:由 LLM context window 限制(8K-128K tokens),无明确存储数字

### L2 短期记忆 (Short-term Memory)
- **存储**:Redis,key prefix `chatbiz:mem:short:{user_id}:{session_id}`
- **生命周期**:session 结束 + N 小时(默认 24h,env 可配)
- **call site**:`agent-runtime` 完成 1 个 user turn 后 / `workflow-engine` 完成 1 个 step 后
- **写入策略**:append-only,最近 N 轮对话历史(N=50,env 可配);压缩策略:超 N 触发 LLM 摘要
- **读取策略**:新 session 启动时拉最近 N 轮作为 initial context;**不**做语义检索
- **容量预估**:50 user × 10 turns/天 × 2KB/turn × 30 天 = 30MB(全公司,30 天保留),Redis 9.0 GB 内存绰绰有余

### L3 长期记忆 (Long-term Memory)
- **存储**:PostgreSQL + 向量字段(`pgvector` 扩展),表 `chatbiz_memory_long`
- **生命周期**:永久(用户偏好/历史事实),不主动删除
- **call site**:`agent-runtime` 检测到用户偏好(明确表达"我喜欢...")/ 历史事实("上次你说...")
- **写入策略**:每次 user turn 末尾,LLM 提取 1-3 条记忆候选 + user 确认(可选);写 PG
- **读取策略**:每个新 turn 启动时,embedding 检索 top-K(默认 5)相关记忆,注入 context
- **容量预估**:1000 user × 100 memory/人 × 1KB/memory = 100MB(全公司,3 年保留),PG 5GB 表空间

### L4 语义记忆 (Semantic Memory)
- **存储**:Milvus / Weaviate(eng-review Tech stack 锁定),collection `chatbiz_knowledge`
- **生命周期**:文档入知识库时建索引,删除文档时同步删索引
- **call site**:`knowledge-base` 服务,RAG 检索;paul 月报工作流的"知识检索"节点
- **写入策略**:文档上传 → chunk(512 token,overlap 50)→ embedding → upsert Milvus
- **读取策略**:向量相似度 top-K(K=10,rerank top-3)+ metadata filter(用户部门、文档时间)
- **容量预估**:eng-review Perf #2 #3 锁定 100GB(1B chunks × 1KB/chunk)
- **PII 处理**:引用 §4.3.Y PII 规则,文档上传前先 PII 扫描(继承 gateway-egress-enforcement-p0 的 PII policy)

### Memory Middleware(eng-review #3 提到)
- 4 层透明切换:`read(query) -> List[MemoryHit]`(按相关性合并 4 层)
- 写入策略:agent/runtime 调用 `write(memory)`,middleware 决定写到 L2/L3
- 溢出淘汰:L2 超 N 自动摘要到 L3;L3 永久保留

## 设计取捨

| 取捨点 | 选 A | 选 B | 我们选 | 理由 |
|---|---|---|---|---|
| L3 向量字段 | pgvector | 独立 Milvus | pgvector | 简化部署,4 层中 1-3 层都用 PG;L4 才用独立向量 |
| L2 摘要策略 | LLM 摘要 | 滑动窗口 | LLM 摘要 | 用户偏好是抽象概念,滑动窗口会丢失早期偏好 |
| L4 rerank | 不用 | Cross-encoder | 不用 | MVP 阶段 cosine 相似度足够;cross-encoder 留 V1.0+ |
| L1 持久化 | 不持久 | 落 Redis | 不持久 | L1 是 working context,不需要跨调用保留 |

## 被拒方案

1. **L1 落 Redis** —— eng-review 明确 "in-context",持久化是 L2 职责
2. **L3 独立 Milvus** —— 重复部署;pgvector 足够 MVP 阶段
3. **L4 用 OpenSearch** —— 锁定 Milvus(eng-review Tech stack);OpenSearch 留 V1.0+
4. **跨 user 共享 L3 记忆** —— 隐私红线;L3 严格 per-user

## 触发 wedge 场景

- **paul 财务月报**:L2 短期(最近几次月报讨论)+ L3 长期(paul 偏好"先看营收再砍费用")
- **leo 数据查询**:L2(最近查询历史)+ L4(企业 schema metadata)
- **anny 文档审核**:L4 为主(上传文档进知识库),L1 临时(LLM 解析中转)

## 跨 spec 依赖

| 后续 spec | 怎么引用本 spec §4.3.X |
|---|---|
| T2 Node Contract | "知识检索节点" 引用 L4 semantic memory |
| T7 Workflow + Chatflow | state machine 引用 L1 working memory |
| T11 4 错误边界 | L1 写入失败 → user boundary;L4 检索失败 → runtime boundary |
| (新) L2 短期记忆 spec | 继承 §4.3.X L2 段 |
| (新) L3 长期记忆 spec | 继承 §4.3.X L3 段 |
| (新) L4 知识库 spec | 继承 §4.3.X L4 段 + §4.3.Y PII 拦截 |
| (新) Memory Middleware | 继承 §4.3.X middleware 段 |

## Open Questions(交给 apply 阶段)

- **OQ1:** L3 pgvector 索引参数(`ivfflat` vs `hnsw`)→ spike task 验证
- **OQ2:** L2 摘要的 LLM 选型(Qwen vs 内部 vLLM)→ 与 LLM 路由表一致
- **OQ3:** L4 rerank 模型选型 → MVP 跳过,V1.0+ 再选

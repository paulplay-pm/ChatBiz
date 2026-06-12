# Design:4 层记忆系统 §4.3.X 详细设计

## Context

`docs/architecture.md` §4.3 已有 §4.3.1(工作流引擎)/ §4.3.2(Agent 运行时)/ §4.3.3(记忆管理系统——**简要 4 层图**)/ §4.3.4(工具与扩展系统)/ §4.3.5(企业安全与权限)/ §4.3.Y(PII 规则集,刚由 gateway-egress-enforcement-p0 spec 补)。eng-review Arch #3 锁定"补 §4.3.X 详细设计",eng-review 报告里**已预留 §4.3.X 占位段**。本 spec 在 §4.3.3(简要图)之后新增 §4.3.X(详细设计)段,不动其他段。

仓库 0 行新代码(纯文档 spec)。L1/L2/L3/L4 4 层记忆的**实际实现**分散在多个 spec:工作记忆 in LangGraph state(L1)/ short-term Redis spec(TBD)/ long-term PG+pgvector spec(TBD)/ semantic Milvus spec(TBD)/ Memory Middleware spec(TBD)。本 spec **只补设计文档**,不抢实现。

## Goals

- **G1:** §4.3.X 段存在,内容覆盖 4 层 + Middleware 5 大要点
- **G2:** §4.3.X 引用 §4.3.3(简要图)+ §4.3.Y(PII 规则集)+ §4.4(技术栈)
- **G3:** §4.3.X 标注每层是"已实现"或"[FUTURE-IMPLEMENTATION]"(为后续 spec 铺路)
- **G4:** CLAUDE.md 同步 surface `[FUTURE-IMPLEMENTATION]`
- **G5:** 文档目录条目加 §4.3.X 链接

## Decisions

| ID | 决策 | 出处 |
|---|---|---|
| D1 | 4 层定义:L1 working(in-context)/ L2 short-term(Redis, 24h TTL)/ L3 long-term(PG+pgvector, 永久)/ L4 semantic(Milvus, 永久) | eng-review Arch #3 |
| D2 | L3 用 `pgvector` 扩展,**不**用独立 Milvus | 4 层中 1-3 层都用 PG,简化部署 |
| D3 | L2 摘要策略:超 N(N=50)轮自动 LLM 摘要到 L3 | 抽象概念早期偏好滑动窗口会丢失 |
| D4 | L4 PII 处理:文档上传前先 PII 扫描(引用 §4.3.Y) | 数据合规 |
| D5 | Memory Middleware:`read(query) -> List[MemoryHit]` 透明合并 4 层 | eng-review Arch #3 提到 |
| D6 | §4.3.X 内容形态:**纯设计文档**,不写代码;每层标注"[EXISTING]" / "[FUTURE-IMPLEMENTATION]" 状态 | 本 spec 是文档 spec,不是代码 spec |
| D7 | §4.3.X 引用 §4.3.3 简要图(已有),**不**复制 4 层图 | 避免重复 |
| D8 | §4.3.X 容量预估数字要明确,且与 eng-review Perf #2 #3(100GB Milvus / 1B chunks)对齐 | eng-review 锁定 |

## 与 source of truth 的对应关系

- `docs/architecture.md` §4.3.3 简要 4 层图 —— **本 spec 不动**,§4.3.X 引用
- `docs/architecture.md` §4.3.Y PII 规则集 —— **本 spec 引用**(L4 PII 处理)
- `docs/architecture.md` §4.4 技术栈 —— **本 spec 引用**(Milvus / pgvector / Redis / PG)
- `docs/architecture.md` §4.5 部署架构 —— 不引用
- eng-review Arch #3 —— 本 spec 是它锁定的设计文档
- eng-review Perf #2 #3(100GB Milvus, 1B chunks)—— D8 引用

## Risks

- **R1:** §4.3.X 容量预估数字(L2 30MB / L3 100MB / L4 100GB)基于假设,实际可能漂移 → 缓解:数字后注"基于估算,实际由容量监控 + T12 storage-estimates spec 校准"
- **R2:** §4.3.X 标注的"[FUTURE-IMPLEMENTATION]" 状态可能被后续 spec 改变 → 缓解:每个 [FUTURE-IMPLEMENTATION] 标注对应 spec name
- **R3:** §4.3.X 与 §4.3.3 重复 —— D7 明确 §4.3.X 引用 §4.3.3,不复制图
- **R4:** §4.3.X 与 L2/L3/L4 后续 spec 内容脱节 —— 缓解:每层都标 "[FUTURE-IMPLEMENTATION: see openspec/changes/<L2/L3/L4-spec>/]"

## 跨 spec 依赖图

```
T3 (本 spec) ─┬─→ T2 Node Contract 知识检索节点引用 L4
              ├─→ T7 Workflow + Chatflow 引用 L1 working memory
              ├─→ T11 4 错误边界 引用 L1/L2/L4 失败模式
              ├─→ T12 5 存储预估 引用 L2 30MB / L3 100MB / L4 100GB
              └─→ (新) L2 / L3 / L4 / Middleware spec 各自继承本 spec §4.3.X
```

## Migration

不适用。本 spec 是文档增量,不动现有代码。

## Open Questions(交给 apply 阶段)

- **OQ1:** L3 pgvector 索引参数(`ivfflat` vs `hnsw`)→ L3 spec 验证
- **OQ2:** L2 摘要的 LLM 选型 → 与 LLM 路由表一致(在 audit-and-isolation 已有)
- **OQ3:** L4 rerank 模型选型 → MVP 跳过,V1.0+ 再选

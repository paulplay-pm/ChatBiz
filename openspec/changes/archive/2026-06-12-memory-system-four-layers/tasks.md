# Tasks: memory-system-four-layers

## 1. 文档调研与素材准备(1h 内,2 个 task)

- [ ] 1.1 读 `docs/architecture.md` §4.3.3(已有 4 层简要图)完整内容,标出 §4.3.X 段需要**补充**的 5 大要点(call sites / 写入策略 / 读取策略 / 容量预估 / Middleware 集成点)
- [ ] 1.2 读 `docs/architecture.md` §4.3.Y(PII 规则集)和 §4.4(技术栈)确认交叉引用锚点;读 eng-review #3 锁定决策确认 4 层定义

## 2. §4.3.X 段撰写(2h 内,1 个 task)

- [ ] 2.1 写 `docs/architecture.md` §4.3.X 段(目标 200-300 行),内容结构:
  - **引子**:eng-review Arch #3 锁定;4 层是 §4.2 列出,§4.3.3 简要图,本段是详细设计
  - **L1 工作记忆**:存储(in-context)/ 生命周期(单次 LLM 调用)/ call site(LangGraph state)/ 写入策略(自动累积)/ 读取策略(下个 node 的 state 参数)/ 容量(LLM context window 限制,8K-128K tokens,无明确数字)
  - **L2 短期记忆**:存储(Redis, key prefix `chatbiz:mem:short:{user_id}:{session_id}`)/ 生命周期(session 结束 + 24h)/ call site(`agent-runtime` 完成 1 user turn 后)/ 写入策略(append-only, N=50, 超 N 触发 LLM 摘要)/ 读取策略(新 session 启动时拉最近 N 轮)/ 容量预估(50 user × 10 turns × 2KB × 30 天 = 30MB)
  - **L3 长期记忆**:存储(PG+pgvector, 表 `chatbiz_memory_long`)/ 生命周期(永久)/ call site(`agent-runtime` 检测偏好)/ 写入策略(每 turn 末尾 LLM 提取 1-3 条 + 可选 user 确认)/ 读取策略(embedding top-K=5 注入 context)/ 容量预估(1000 user × 100 memory × 1KB = 100MB)
  - **L4 语义记忆**:存储(Milvus, collection `chatbiz_knowledge`)/ 生命周期(随文档)/ call site(`knowledge-base` 服务, paul 月报"知识检索"节点)/ 写入策略(文档 → chunk 512 + overlap 50 → embedding → upsert)/ 读取策略(向量相似度 top-K=10, rerank top-3)/ 容量预估(eng-review Perf #2 #3 锁定 100GB, 1B chunks × 1KB)/ PII 处理(引用 §4.3.Y)
  - **Memory Middleware**:4 层透明切换 / `read(query) -> List[MemoryHit]` / `write(memory)` 决定写哪层 / 溢出淘汰(L2 超 N → L3 摘要)
  - **call sites 与 Agent/Workflow runtime 集成**:每层标注 [EXISTING] / [FUTURE-IMPLEMENTATION]
  - **交叉引用**:§4.3.3 简要图 / §4.3.Y PII 规则集 / §4.4 技术栈
  - **eng-review 决策引用**:Arch #3 / Perf #2 #3
  - **下游 spec 引用**:T2 / T7 / T11 / T12 / (新) L2 / (新) L3 / (新) L4 / (新) Middleware
- [ ] 2.2 验证 `docs/architecture.md` 内容总长度仍合理(Markdown 渲染 < 2000 行),目录条目加 §4.3.X 链接

## 3. CLAUDE.md surface 同步(30min 内,1 个 task)

- [ ] 3.1 在 `CLAUDE.md` §4.3 描述段后、`## 已锁定的工程决策` 之前,加 1 行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.X 4 层记忆详细设计即将在 memory-system-four-layers apply 阶段补全,引用 §4.3.3 简要图 + §4.3.Y PII 规则集 + §4.4 技术栈`
- [ ] 3.2 验证 `CLAUDE.md` 内容仍合理(总长度 < 300 行),surface 标记位置正确

## 4. verify 验证(30min 内,1 个 task)

- [ ] 4.1 写 `services/audit-and-isolation/tests/test_architecture_md.py`(沿用 gateway-egress spec 的命名约定,虽然这是 memory spec,但用统一测试)—— **不**,改为更轻量:写一个独立 `tests/test_architecture_md.py` 在仓库根(可能用 `openspec/changes/memory-system-four-layers/tests/` 路径,或仓库根 tests/),用 grep 验证 §4.3.X 段存在 + 含 5 大要点关键词(call sites / 写入 / 读取 / 容量 / Middleware)+ 引用 §4.3.3 / §4.3.Y / §4.4 + 含 L1-L4 + Middleware 4 关键词
- [ ] 4.2 跑 `python -m pytest tests/test_architecture_md.py -v` 验证

## 5. 收尾(15min 内,2 个 task)

- [ ] 5.1 写 `verify.md`:列 §4.3.X 段验证结果 + 5 大要点覆盖 + 交叉引用 OK + CLAUDE.md surface OK
- [ ] 5.2 写 `retrospective.md`:本 spec 是纯文档 spec 的反思(用时 vs 价值 / 与 §4.3.3 关系 / 下游 spec 引用是否清晰)+ 后续 L2/L3/L4/Middleware 4 个 spec 的衔接建议

---

**总计 7 个 task,5 个文档/同步 + 2 个收尾**。每个 task ≤ 2h,无编码任务(全文档)。

**配对验证:**
- task 2.1 ↔ task 4.1(test 验证)
- task 3.1 ↔ task 4.1(同一 test 验证)
- task 5.1 ↔ task 4.1(spec 完成判定)

无孤儿。任务粒度全部 ≤ 2h。

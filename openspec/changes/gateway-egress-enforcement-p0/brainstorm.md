<!--
Raw capture of superpowers:brainstorming output for change `gateway-egress-enforcement-p0`.
本檔原樣捕捉 brainstorming skill 的產出,不做結構化重排(那是 design.md 的工作)。
设计来源:eng-review #1 (locked-in 12 个工程决策中的第 1 个)。
-->

# Brainstorm:数据隔离网关(egress 强制点,P0)

## 背景(来自 eng-review 报告)

ChatBiz 是企业内 AI Agent 平台。共同根因:内部用户(paul / leo / anny)用公网 AI 工具处理内部数据 = 合规红线。eng-review 在 2026-06-10 锁定 12 个工程决策,其中 **#1 数据隔离网关 = egress 强制点**(不是 ingress),被标记为 **P0 单点**:失败 = 所有 LLM 调用挂。HA 拓扑、健康检查、跨网关 trace-id 关联是必含项。本次 brainstorm 不再讨论"要不要做",只 surface 范围边界和 2 个未决小问题。

**eng-review 原始 finding(逐字引用):**
> 数据隔离网关 = egress 强制点(不是 ingress)。2 实例 HA + 健康检查 + 跨网关 trace-id 关联。失败 = 所有 LLM 调用挂,这是 P0 单点。

## 决策链

### Q1:范围边界(eng-review #1 没明说 PII / 限流 / 缓存是否归本 spec)

**选项:**
- (A) 纯 HA + trace 关联 —— 我推荐
- (B) HA + trace + PII 拦截
- (C) HA + trace + PII + 性能(全包)

**用户选择:(C) 全包**。本 spec 范围扩大到 4 项:HA + trace + PII + 性能(限流 / 缓存 / 批处理)。

**代价与缓解:**
- superpowers-bridge config 规定 task ≤ 2h,编码任务配对验证任务。4 项功能会膨胀到 20+ task
- **缓解方案:**本 spec 不交付 PII / 限流 / 缓存 / 批处理的实现细节,只交付 **(1) HA + trace 关联的骨架 + (2) `egress.Hook` 协议 + (3) `gateway.HA.Pair` 协议 + (4) PII/限流/缓存的 4 个 contract 单元测试桩**。具体实现留给后续 spec(reopen 本 change 的 PR)
- proposal.md 的"非目标"和"影响面"会显式声明这一点

### Q2:状态后端 / 跨实例 trace 关联(eng-review #8 双层设计如何映射到 gateway)

**选项:**
- (A) PostgreSQL 为主,Redis 缓存(eng-review 锁定)
- (B) Redis 为主,PG 备
- (C) PG + Redis + Raft/etcd 三层

**用户选择:(A) PostgreSQL 为主,Redis 缓存**。Redis 在 gateway 内部做跨实例 trace cache(短 TTL 5min),PostgreSQL 是审计落地和 source of truth(超 5min 也能从 PG 反查)。

**契约:**
- trace-id 写 PG 的同时写 Redis,5min 滑动 TTL
- Redis 挂了不阻塞,降级为"直接查 PG"
- PG 是合规真源,Redis 是性能优化层

### Q3:egress 强制的具体含义(eng-review "egress 强制点(不是 ingress)"有歧义)

**选项:**
- (A) **设置 LLM 依赖黑名单**(我推荐)—— 任何代码不允许直接 import `openai` / `anthropic` SDK,必须经过 gateway client
- (B) 只限 agent / workflow,plugin 灵活
- (C) 纯 IP / 域名白名单

**用户选择:(A) 设置 LLM 依赖黑名单**。在 CI 阶段用 `import-linter` 或自制 AST 扫描阻止直连 import。运行时二次兜底:网关侧检查 `X-Gateway-Signature` header,缺失则拒绝。

**双重防御:**
- 编译期:静态扫描(主防御)
- 运行期:`X-Gateway-Signature` HMAC(兜底,防止绕过静态扫描的动态 import)

## 表面未决问题(必须列,不能藏)

### Q4 (OPEN):HA 切换时正在飞行的 LLM 请求如何处理?

**我的默认值(待 user 确认):** 客户端 SDK 识别 `503 HA_FAILOVER` 后幂等重试;网关侧在切换前 30s 拒绝新连接(`Connection: close` + `Retry-After`),让旧实例上的 in-flight 请求自然完成。

**理由:** LLM 调用通常 5-60s,需要时间让旧实例排空。Kubernetes `preStop hook` + `terminationGracePeriodSeconds=60` 是成熟模式。

**风险:** 客户端必须实现幂等重试(每条 LLM 请求带 `Idempotency-Key`)。本 spec 需在 client SDK 中提供重试器,否则 P99 会飙高。

### Q5 (OPEN):PII 拦截到底几档 / 哪些字段

**我的默认值:**
- **block 档(强拦截):** 身份证号、银行卡号、统一社会信用代码 → 直接拒,返回 422,日志告警
- **mask 档(脱敏放行):** 手机号、邮箱、地址 → 替换为 `138****1234`,LLM 收到脱敏版本,审计记录原文 hash
- **log-only 档(记账):** 内部员工编号、内部项目代号 → 原文放行,审计记录命中位置

**理由:** 三档分治,既不阻断 paul 月报工作流(财务月报含大量手机号 / 员工编号,block 就跑不起来了),又不放过高敏感 PII(身份证 / 银行卡)。

**风险:** 阈值漂移。`docs/architecture.md` 还没写 PII 规则集,需要 T1 落地时同步补充到 architecture.md §4.3.Y 章节(eng-review 已经预留 §4.3.X 给我们用了)。

## 设计取捨(整体)

| 取捨点 | 选 A | 选 B | 我们选 | 理由 |
|---|---|---|---|---|
| HA 粒度 | 进程级(active-passive) | 实例级(active-active) | active-active 双实例 | eng-review 锁定 2 实例,active-active 利用率更高 |
| 共享存储 | PG only | PG + Redis | PG + Redis | eng-review #8 锁定双层 |
| 客户端协议 | HTTP/JSON | gRPC | HTTP/JSON | 简单、LangGraph Python SDK 现成支持 |
| 加密 | mTLS only | mTLS + 应用层加密 | mTLS | 内部网络,信任边界在网关上 |
| 健康检查 | TCP ping | HTTP /health + 主动 LLM ping | HTTP /health | TCP 假阳,LLM ping 误杀频繁 |

## 被拒方案

1. **纯 ingress 拦截(NGINX + JWT 鉴权)** —— eng-review 明确否决,理由:LLM 调用常在 worker 内部,ingress 拦不到
2. **service mesh 拦截(Istio sidecar)** —— 拒绝,理由:增加运维复杂度,langgraph 不在 mesh 里
3. **运行时网络策略(Kubernetes NetworkPolicy)** —— 拒绝,理由:粒度太粗,无法区分 LLM 和普通 HTTP
4. **provider 端白名单(在 OpenAI 后台限制 IP)** —— 拒绝,理由:依赖 vendor,MVP 时间线不允许

## 触发 wedge 场景(必中)

- **paul 财务月报工作流:** 月度报表含员工手机号 / 身份证 / 银行卡,网关必须 mask 身份证但不阻断工作流
- **leo 基础服务数据查询:** 查询请求里不能含 PII,触发 block 档时返回 422 + 审计记录
- **anny 增值服务文档审核:** 上传文档到 MinIO 不走网关(只走 DLP),但 LLM 解析时走网关,触发 PII 扫描

## 跨任务耦合(影响后续 spec)

| 后续 spec | 怎么依赖本 spec |
|---|---|
| T2 Node Contract | 12 节点类型的 LLM 调用全部走 `egress.Hook` 协议 |
| T4 测试架构 | 集成测试套件必须含 `gateway failover e2e` |
| T5 4 critical path | "网关 PII 拦截"是 4 路径之一,需在本 spec 后立即续做 |
| T6 性能优化 | 缓存 / 限流 / 批处理 的 contract 在本 spec 给,实现留 T6 |
| T11 错误边界 | 4 错误边界中"security"边界 = 网关 PII 拦截 |
| T12 存储预估 | audit log 780GB/3mo 包含 PII mask 后的原文 hash |

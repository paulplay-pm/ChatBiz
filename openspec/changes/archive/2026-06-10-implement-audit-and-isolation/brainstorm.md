<!--
Raw capture of superpowers:brainstorming output.

本檔原樣捕捉 brainstorming skill 的產出,不強制結構。
Skill 的自然產出是 decision log 格式(背景 → 決議鏈 Q1-Qn → 設計取捨)。

design.md 從本檔萃取並重新整理為結構化設計文件。
兩者互補但不重疊。
-->

# Brainstorm — chatbiz-audit-and-isolation

> 触发: openspec new change implement-audit-and-isolation
> 模式: superpowers-bridge (brainstorm → proposal → design → specs → tasks → plan → apply → verify → retrospective)
> 日期: 2026-06-10

## 背景

**eng-review 锁定(12 finding 全部 approved,不再重议)**:
- Arch #1 (P1, 9/10) — 数据隔离网关 = **egress 强制点**(非 ingress)。2 实例 HA + 健康检查 + 跨网关 trace-id 关联。失败 = 所有 LLM 调用挂,P0 单点
- Perf #1 (P1, 8/10) — 网关 P99 < 500ms,需要 cache(频繁 prompt / credentials / model routing)+ rate limit + batch
- Test #2 (P1, 7/10) — 4 个 critical path 100% 覆盖,其中 **#2 = 数据隔离网关 PII 拦截**

**design doc 术语定义**(approved):
> "数据隔离网关" = 部署在 LLM egress 路径上的 sidecar 代理,所有出站 LLM 请求必须经过它,执行 PII 脱敏、审计记录、内部模型路由。**信任边界 = LLM 提供方**,网关 = 强制执行点。

**架构定位**:
```
调用方 (agent-runtime / workflow-engine / canvas)
        ↓ OpenAI-compatible API
audit-and-isolation (Python FastAPI)
        ↓ httpx 异步透传
上游 LLM (public: Qwen/DeepSeek/文心/通义 | private: 内部 vLLM)
```

**MVP 时间窗**: month 2-3,与 credential service(已落地)形成上下游依赖链。

---

## 决策链

### Q1 — PII 检测器失败时的姿态

**选项**:
- (A) Fail-Closed: 检测器挂 → 阻断出站 + 503
- (B) Fail-Open + 告警: 检测器挂 → 放行 + WARN 审计 + 人工复检
- (C) 混合: 默认 Fail-Closed,allowlist 例外

**决定**: **(B) Fail-Open + 告警**

**理由**:
- 企业内业务连续性优先(paul 月报跑不出来 > 偶尔漏 PII)
- 通过 audit + 告警补足可见性,ops 能在 15 min 内发现 detector 异常
- 完全 Fail-Closed 把"detector 健康"变成所有 LLM 可用性的单点(违背 HA 初衷)

**拒绝 (A) 的理由**: 把 PII 检测器变成业务可用性单点,违背"2 实例 HA"的初衷
**拒绝 (C) 的理由**: MVP 阶段过度工程;allowlist 配置会变成新的安全漏洞

---

### Q2 — PII 检测方式

**选项**:
- (A) 正则规则集(中国手机/身份证/银行卡/邮箱/统一社会信用代码/营收金额)
- (B) 正则 + 静态人名词典
- (C) 云厂商敏感词 API(阿里云内容安全等)
- (D) 本地微调小 LLM(Qwen-Guard)

**决定**: **(A) 正则规则集**

**理由**:
- 延迟 < 1ms,完全满足 P99 < 500ms 目标
- 6 类企业内最常见 PII 100% 覆盖
- 无外部依赖(企业内网不允许连公网)
- 测试可重现(无 LLM 概率性)

**拒绝 (B) 的理由**: 人名词典维护成本高(每夜热更新)且企业内准确率提升有限
**拒绝 (C) 的理由**: 又调一个公网 API,跟"数据隔离"初心冲突
**拒绝 (D) 的理由**: 延迟 200-500ms 撞破 P99 目标;MVP 阶段不必要

---

### Q3 — 脱敏动作

**选项**:
- (A) 类型化占位符(REPLACE)
- (B) 硬删除
- (C) 整请求阻断
- (D) 可配置(Agent 自选)

**决定**: **(A) 类型化占位符**

**理由**:
- 上下文语义保留(LLM 知道"有个人身份证被脱敏了")
- 可逆(Q14 决定)
- Agent 后续多轮调用占位符前后一致

**拒绝 (B) 的理由**: 语义损失(LLM 误以为语法错)
**拒绝 (C) 的理由**: Agent 不知道发生了什么;V1.0+ 考虑作为 strict 模式
**拒绝 (D) 的理由**: MVP 阶段不增加 Agent 复杂度

---

### Q4 — 模型路由决策

**选项**:
- (A) 透传(调用方定)
- (B) 策略路由(脱敏状态驱动)
- (C) 动态选优(latency/cost/quality)

**决定**: **(A) 透传**

**理由**:
- MVP 简化决策,网关只做"保安"不做"调度"
- 把模型选择权留给 agent-runtime(更懂业务上下文)
- 网关 P99 500ms 预算主要给 PII 扫描,不留给路由计算

**拒绝 (B) 的理由**: 复杂度高,需 model→kind 表 + 路由决策树
**拒绝 (C) 的理由**: 实现最重,且需要实时 metric,违背 MVP 简洁

---

### Q5 — 限流策略

**选项**(可多选):
- (A) Per-User 滑窗 60/min
- (B) Per-Workflow-Instance 30/min
- (C) Per-User-Token-Budget/day
- (D) 不限,只计数

**决定**: **(D) 不限,只计数**

**理由**:
- MVP 阶段不阻塞业务
- 计数本身是审计的副产品(已经在 Q6 audit 里)
- 真正的限流由上游 LLM provider 自己的 quota 控制

**拒绝 (A/B/C 的理由**: MVP 阶段无证据表明需要;V1.0+ 业务跑起来后再加

---

### Q6 — 审计粒度

**选项**:
- (A) Metadata-Only(trace_id / user_id / model / 脱敏后 prompt 摘要 hash / token / latency / PII 结果)
- (B) Full-Payload(冷存储)
- (C) 混合(按风险存)

**决定**: **(A) Metadata-Only**

**理由**:
- 满足合规"每条 LLM 调用可追溯"
- 占空间小(MVP 3 个月预估 < 50GB,远低于 780GB/3mo 阈值)
- 不存脱敏后/原文 → 减少"审计库本身被攻破"的二次泄露面

**拒绝 (B) 的理由**: 780GB/3mo 已经在 eng-review 标了"冷存储"成本,不合算
**拒绝 (C) 的理由**: 实现复杂 + 风险判定阈值无标准

---

### Q7 — HA 拓扑

**选项**:
- (A) 2 实例 + L4 LB active-active(eng-review 锁定)
- (B) 2 实例 + Redis-sticky(同 trace 路由同实例)
- (C) 单实例

**决定**: **(A) 2 实例 + L4 LB active-active**

**理由**:
- eng-review Arch #1 明确锁定
- active-active 比 sticky 简单,Redis 共享状态已经够用
- 跨实例 trace 一致性由"Redis 共享 map"保证(Q15)

**拒绝 (B) 的理由**: 引入 session affinity 复杂度,且 Redis 已经是事实共享存储
**拒绝 (C) 的理由**: 违背 P0 单点防护

---

### Q8 — 凭证调用

**选项**:
- (A) 调 credential 服务(已落地)
- (B) 环境变量注入
- (C) 本服务不接触凭证

**决定**: **(A) 调 credential 服务**

**理由**:
- credential service 已实现 17 个 Requirements,`use_credential` API 完备
- 凭证轮转(30 天)由 credential 服务管,本服务不重复
- audit trace 跨服务关联(Q9 + 调 credential 的 service token)

**拒绝 (B) 的理由**: 违反"凭证不落代码/不落环境"原则
**拒绝 (C) 的理由**: 模型选择权在调用方(Q4),但调用方需从本服务拿 API key,本服务是必经之路

---

### Q9 — trace-id 来源

**选项**:
- (A) 调用方传入(Header `X-Trace-Id`)
- (B) 本服务生成
- (C) 不关联

**决定**: **(A) 调用方传入**

**理由**:
- 业务主导:agent-runtime 已有自己的 trace context(W3C Trace Context 风格)
- 本服务不重复造 ID
- 跨服务 trace 关联成为可能(workflow → gateway → LLM provider)

**拒绝 (B) 的理由**: 调用方需反查关联,关联弱
**拒绝 (C) 的理由**: 违背 eng-review Arch #1 "跨网关 trace-id 关联"

---

### Q10 — Redis 缓存内容

**选项**:
- (A) 仅模型路由表
- (B) 路由 + prompt + 凭证 list
- (C) 全量(含 response cache)

**决定**: **(A) 仅模型路由表**

**理由**:
- 路由表 < 1KB,改一次不频繁,缓存收益最大(每次调用都查)
- prompt templates 不在热路径(workflow 编译时已注入,运行时不再查)
- 凭证有 TTL,credential 服务自己 cache

**拒绝 (B) 的理由**: prompt 和 credential list 不是每调用热路径,缓存收益小
**拒绝 (C) 的理由**: response cache 有 freshness 问题,且增加审计复杂度

---

### Q11 + Q12 — 上游网络拓扑 + Bypass 机制

**选项**:
- (A) 全部公网
- (B) 全部内网私有
- (C) 混合
- (C.1) 真路由分流(本服务按 model_kind 路由)
- (C.2) 调用方 header 声明(本服务按 header 决定)
- (C.3) 退回公网

**决定**: **(C.2) 调用方 header 声明 + 本服务调用**

**调和 Q4 (透传)**: 模型选择是调用方定的(在 body.model 里),本服务读 header 决定"是否脱敏 + 走哪个 base_url"

**Header 约定**:
- `X-Model-Kind: public | private`(必填)
- `X-Bypass-Isolation: true`(可选;声明后跳过 PII 脱敏,需 X-Model-Kind=private)

**理由**:
- 与 Q4 "透传"调和:本服务不决策模型,只读 header 决定路径
- 给 private 留口子(企业内部 vLLM 不需要 PII 脱敏,节省 CPU)
- 显式声明降低误用风险(developer 必须知道自己在做什么)

**拒绝 (A) 的理由**: 企业内已有内部 vLLM(leo 用),MVP 阶段必须支持
**拒绝 (B) 的理由**: MVP Qwen/DeepSeek 是公网 API
**拒绝 (C.1) 的理由**: 增加 routing 模块复杂度
**拒绝 (C.3) 的理由**: V1.0 内部 LLM 是已确认需求,延后 = 返工

---

### Q13 — 实现语言

**选项**:
- (A) Python (FastAPI)
- (B) Go
- (C) Node.js / TypeScript

**决定**: **(A) Python**

**理由**:
- 跟 credential service 一致,团队上手零成本
- FastAPI 异步 + httpx 异步 P99 < 50ms 已验证(credential P99=6.74ms)
- PII 正则(Python `re` 引擎)< 1ms/请求,无 CPU 压力

**拒绝 (B) 的理由**: QPS < 100,Go 优势不显著;团队成本高
**拒绝 (C) 的理由**: 企业内 Python 团队多,Node 需补人

---

### Q14 — 脱敏可逆性

**选项**:
- (A) 可逆脱敏(map 存 Redis)
- (B) 单向(只脱敏上行)
- (C) 加密可逆

**决定**: **(A) 可逆脱敏**

**理由**:
- 体验:员工看到的是原值(表现跟未脱敏一样),LLM 拿到的是占位符
- 上下文:agent 多步调用能保持 PII 一致
- 安全:map TTL 30min,过期自动清空,降低长期泄露风险

**拒绝 (B) 的理由**: LLM 响应里全是 `[身份证_xxxx]`,员工看了就放弃用
**拒绝 (C) 的理由**: 实现复杂,响应侧逆推一旦 cache miss 会出错

---

### Q15 — 脱敏 map 粒度

**选项**:
- (A) Per-Trace
- (B) Per-User
- (C) Per-Workflow

**决定**: **(A) Per-Trace**

**理由**:
- 同一 trace 多次 LLM 调用共享,典型 agent 场景(规划→工具→总结,3-5 次 LLM)能正常还原
- TTL 30min 足以覆盖大多数 agent 任务
- 不同 trace 隔离 → 不存在跨会话泄露风险

**拒绝 (B) 的理由**: 跨 workflow 泄露风险(workflow A 的手机号被 workflow B 还原)
**拒绝 (C) 的理由**: 跟 Per-Trace 几乎一样,但 workflow 边界比 trace 边界粗,跨 step 隔离弱

---

### Q16 — 测试范围

**选项**:
- (A) 100% PII 拦截覆盖(eng-review Test #2 #2)
- (B) + 50 paul 财务月报 LLM eval
- (C) + 透传保真性测试

**决定**: **(A) 100% PII 拦截覆盖**

**理由**:
- eng-review Test #2 锁定
- eval (B) 需要外部 LLM API,MVP 阶段不必要
- 透传保真性 (C) 是 V1.0+ 关注

**拒绝 (B) 的理由**: MVP 阶段不必要,留 V1.0
**拒绝 (C) 的理由**: eng-review 没要求,优先级低

---

### Q17 — egress 强制点位置

**选项**:
- (A) 独立 LLM proxy 服务(OpenAI-compatible)
- (B) Sidecar(同 pod)
- (C) SDK 拦截(in-process)

**决定**: **(A) 独立 LLM proxy 服务**

**理由**:
- 调用方改 base_url 一行代码:`https://api.openai.com` → `http://audit-and-isolation:8080`
- 部署简单(独立 deployment,K8s service 暴露)
- 容易审计(所有 LLM 流量集中经过一个 service,易接 ELK)
- 跟 eng-review 隐含方案一致(egress 强制点 = 独立 service)

**拒绝 (B) 的理由**: 每个 agent-runtime / workflow-engine pod 多 1 个 container,部署复杂;sidecar 不能"拒绝同 namespace 内绕过"(同 pod 两 container 可互调)
**拒绝 (C) 的理由**: "developer 不绕过 SDK 直接 httpx.post(qwen-api)" 难防;需 lint + code review + 运行时防绕过(实现难)

---

## 设计总览(交付给 design.md 的核心)

### 5.1 架构
```
调用方 → audit-and-isolation (Python FastAPI :8080)
  ├─ Ingress (鉴权 + trace/model_kind 提取)
  ├─ PII Detector (6 类正则) → Redactor (类型化占位符)
  ├─ Routing (Redis-cached model_routing table)
  ├─ Upstream Caller (httpx 异步)
  ├─ Reverser (响应侧占位符还原)
  └─ Audit Writer (outbox 异步落 PostgreSQL)
        ↓
上游 LLM (public Qwen/DeepSeek | private vLLM)
```

### 5.2 组件
20+ 文件,主要模块:
- `app/pii/`(detector, rules, redactor, reverser)
- `app/routing/`(table, dispatcher)
- `app/llm/`(client, streaming)
- `app/audit/`(writer, hash)
- `app/auth.py`(service token)
- `app/main.py` + `app/lifespan.py`

### 5.3 数据流
4 个场景:public + PII / private + bypass / HA 切换 / detector fail-open

### 5.4 错误处理
10 类错误,Fail-Open on PII / Fail-Closed on auth+credential

### 5.5 测试
- 单元 100% + 集成(testcontainers)+ perf bench
- critical path #2 100% 覆盖
- P99 < 50ms 网关层 + P99 < 500ms 端到端

---

## Open Questions

无。所有关键决策都已落地,无未决问题。

---

## Rejected Alternatives 汇总

| 选项 | 拒绝理由 |
|------|----------|
| Fail-Closed on PII | 把 detector 健康变成所有 LLM 单点 |
| 正则 + 人名词典 | 维护成本高,准确率提升有限 |
| 云厂商敏感词 API | 又调公网,违背数据隔离 |
| 本地微调小 LLM | 延迟 200-500ms 撞破 P99 目标 |
| 硬删除 / 整请求阻断 | 语义损失 / 体验差 |
| 可配置脱敏动作 | MVP 阶段过度 |
| 策略路由 / 动态选优 | 复杂度高,MVP 留给 V1.0+ |
| 限流(PPL/Token) | MVP 阶段无证据需要 |
| Full-Payload audit | 780GB/3mo 成本 + 二次泄露面 |
| 单实例 / Redis-sticky | 违背 HA 锁定 / 引入复杂度 |
| 环境变量凭证 | 违反"凭证不落代码" |
| 本服务生成 trace-id | 违背跨服务 trace 关联 |
| 缓存 prompt / response cache | 不在热路径 / freshness 问题 |
| 真路由分流(C.1) | 增加 routing 模块 |
| 退回公网(C.3) | V1.0 内部 LLM 是已确认需求 |
| Go / Node.js | 团队成本 / QPS < 100 |
| 加密可逆脱敏 | 实现复杂,cache miss 会出错 |
| Per-User / Per-Workflow map | 跨会话泄露 / 边界粗 |
| 50 paul LLM eval | MVP 不必要,V1.0+ |
| 透传保真性测试 | eng-review 没要求 |
| Sidecar | 部署复杂 / 同 pod 互调绕过 |
| SDK 拦截 | 防绕过难 |

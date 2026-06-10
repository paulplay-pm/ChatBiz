# Design — chatbiz-audit-and-isolation

> 模式: superpowers-bridge
> 阶段: design (从 brainstorm.md 重组)
> 承接: `brainstorm.md`(17 个 Q 决策全 locked,无 Open Questions)
> 日期: 2026-06-10

---

## Context

**ChatBiz 平台定位**:企业级 AI Agent 智能体平台(Lead Agent / Sub Agent + 工作流引擎 + 内网 AI + 数据隔离网关)。MVP 时间窗 month 2-3。

**eng-review 锁定决策**(本设计受以下 4 条 finding 约束,见设计 doc `## GSTACK REVIEW REPORT`):

| Finding | 锁定内容 |
|---------|----------|
| **Arch #1 (P1)** | 数据隔离网关 = **egress 强制点**(非 ingress)。2 实例 HA + 健康检查 + 跨网关 trace-id 关联。失败 = 所有 LLM 调用挂 |
| **Perf #1 (P1)** | 网关 P99 < 500ms,需 cache + rate limit + batch |
| **Quality #3 (P2)** | 4 个错误边界:canvas drag / runtime / user / security |
| **Test #2 (P1)** | 4 个 critical path 100% 覆盖,其中 **#2 = 数据隔离网关 PII 拦截** |

**架构定位**(对应 `docs/architecture.md` §4.1 网关层 + §4.3.5 企业安全与权限):

```
调用方 (agent-runtime / workflow-engine / canvas)
        ↓ OpenAI-compatible API
chatbiz-audit-and-isolation (Python FastAPI :8080)
        ↓ httpx 异步透传
上游 LLM (public: Qwen/DeepSeek/文心/通义 | private: 内部 vLLM)
```

**stakeholders**:
- 业务侧(paul/leo/anny):体验上"脱敏透明" + 响应保真
- 平台侧(agent-runtime / workflow-engine):只需改 base_url,无侵入
- 安全合规(内部 audit team):每条 LLM 调用 metadata 可追溯
- 运维(平台 SRE):2 实例 HA + 告警 + 降级路径

**下游依赖**:credential service(已落地,17 Reqs) — 本服务通过 service token 调其 `use_credential` API 拿 LLM provider API key。

---

## Goals / Non-Goals

### Goals

1. **强制 egress 拦截**:agent-runtime / workflow-engine 所有出站 LLM 调用经本服务
2. **PII 自动脱敏 + 可逆**:6 类企业内 PII 100% 命中,员工看到原值
3. **Metadata-Only 审计**:每条 LLM 调用留痕,支持合规追溯(trace_id / user_id / model / token / latency / PII 结果)
4. **跨服务 trace-id 关联**:X-Trace-Id 由调用方传入,本服务透传到上游 + 写入 audit
5. **2 实例 HA**:任一实例挂,流量自动切到另一实例,业务不中断
6. **P99 网关层 < 50ms**(P99 端到端含 LLM < 500ms):对齐 eng-review Perf #1
7. **可降级**:PII detector 异常时 Fail-Open + WARN 审计 + 告警,不阻断业务

### Non-Goals(本 change 不做)

- **模型路由决策**:模型选择权在调用方(Q4 透传)
- **限流**:MVP 只计数不限流(Q5)
- **Full-Payload 审计**:只存 metadata(Q6)
- **公网 API 反向代理**:本服务只代理企业内 egress,不代理公网到企业内
- **多租户 SaaS**:单租户内部部署(eng-review 锁定)
- **海外模型合规**:MVP 用国产模型(eng-review NOT in scope)
- **Plugin Marketplace / 3rd-party 开发者生态**:V2.0+(eng-review NOT in scope)
- **可视化画布 / agent-runtime / workflow-engine 本身**:本服务只是它们的依赖

---

## Decisions

> 17 个 Q 决策,从 brainstorm.md 重组而来,补充 finding 编号 + architecture.md 引用。

### D1: 部署形态 — 独立 LLM proxy 服务

- **选择**:独立 Python FastAPI 服务,OpenAI-compatible API(POST /v1/chat/completions)
- **理由**:调用方改 base_url 一行代码即可;部署简单;所有 LLM 流量集中易接 ELK
- **对应 finding**:Arch #1
- **已考虑 alternative**:
  - Sidecar — 多 1 container / 同 pod 互调可绕过,否决
  - SDK 拦截(in-process)— 防绕过难(developer 可直接 httpx.post),否决

### D2: PII 检测器失败姿态 — Fail-Open + 告警

- **选择**:detector 抛异常 → 不脱敏 + WARN 审计 + metric counter + PagerDuty 告警
- **理由**:企业内业务连续性 > 偶尔漏 PII;通过 audit + 告警补足可见性
- **对应 finding**:Arch #1(HA 不应被 detector 单点拖累)
- **已考虑 alternative**:
  - Fail-Closed — 把 detector 健康变成所有 LLM 单点,否决
  - 混合(allowlist)— MVP 过度工程,否决

### D3: PII 检测方式 — 正则规则集(6 类)

- **选择**:6 类正则,中国本地化
  - 身份证(18 位 + 校验位 + 末位 X)
  - 手机(11 位 1[3-9] 开头)
  - 银行卡(16-19 位 Luhn 校验)
  - 邮箱(RFC 5322 简化)
  - 统一社会信用代码(18 位)
  - 营收金额(中文 "营收 1,234,567.89 元" 风格)
- **理由**:延迟 < 1ms,满足 P99 < 500ms 目标;无外部依赖;测试可重现
- **对应 finding**:Perf #1(性能预算)
- **已考虑 alternative**:
  - 正则 + 静态人名词典 — 维护成本高,否决
  - 云厂商敏感词 API — 又调公网,违背数据隔离,否决
  - 本地微调小 LLM — 延迟 200-500ms 撞破 P99 目标,否决

### D4: 脱敏动作 — 类型化占位符(可逆)

- **选择**:原值 → `[类型_xxxx]`,map 存 Redis;响应侧反向还原
- **理由**:LLM 看到占位符(语义保留);员工看到原值(体验跟未脱敏一样);agent 多步调用占位符前后一致
- **对应 finding**:无直接对应(Q3 业务决策)
- **已考虑 alternative**:
  - 硬删除 — 语义损失,否决
  - 整请求阻断 — Agent 不知道发生了什么,否决
  - 可配置(Agent 自选)— MVP 过度,否决

### D5: 脱敏 map 粒度 — Per-Trace (TTL 30min)

- **选择**:key = trace_id,TTL = 1800s
- **理由**:同一 trace 多次 LLM 调用共享;不同 trace 隔离(跨会话零泄露);TTL 防止长期泄露
- **对应 finding**:Arch #1(跨网关 trace-id 关联)
- **已考虑 alternative**:
  - Per-User — 跨 workflow 泄露风险,否决
  - Per-Workflow — 边界粗,跟 Per-Trace 几乎一样但隔离弱,否决

### D6: 模型路由 — 透传(调用方定)

- **选择**:body.model 字段直传上游;网关不决策模型
- **理由**:MVP 简化;Agent 业务上下文更懂;网关 P99 预算主要给 PII 扫描
- **对应 finding**:无直接对应(Q4 业务决策)
- **已考虑 alternative**:
  - 策略路由(脱敏状态驱动)— 复杂度高,V1.0+ 考虑
  - 动态选优(latency/cost/quality)— 实现最重,V1.0+ 考虑

### D7: 上游网络拓扑 — 混合(public + private),header 声明

- **选择**:调用方在 header 里声明:
  - `X-Model-Kind: public | private`(必填)
  - `X-Bypass-Isolation: true`(可选;声明后跳过 PII 脱敏,需 X-Model-Kind=private)
- **理由**:调和 D6 透传(本服务不决策模型,只读 header 决定路径);给 private vLLM 留口子(节省 CPU);显式声明降低误用
- **对应 finding**:无直接对应(Q11+Q12)
- **已考虑 alternative**:
  - 全部公网 — MVP 必须支持内部 vLLM,否决
  - 全部内网 — Qwen/DeepSeek 是公网 API,否决
  - 真路由分流(本服务决策)— 增加 routing 模块复杂度,否决

### D8: HA 拓扑 — 2 实例 + L4 LB active-active

- **选择**:2 个 audit-and-isolation 实例 + 前面 Nginx upstream(K8s service 也可);healthcheck fail → 踢出
- **理由**:eng-review 锁定;active-active 比 sticky 简单;跨实例 trace 一致性由 Redis 共享 map 保证
- **对应 finding**:Arch #1(P0 单点防护)
- **已考虑 alternative**:
  - 2 实例 + Redis-sticky — 引入 session affinity 复杂度,Redis 已共享,否决
  - 单实例 — 违背 P0 防护,否决

### D9: 凭证调用 — 调 credential 服务(已落地)

- **选择**:本服务持有 service token 调 credential service 的 `use_credential` API 拿 LLM provider API Key;缓存 5min
- **理由**:credential service 已实现 17 Reqs;凭证轮转 30 天由其管理;跨服务 trace 关联成可能
- **对应 finding**:无直接对应(Q8);依赖 credential service
- **已考虑 alternative**:
  - 环境变量注入 — 违反"凭证不落代码",否决
  - 本服务不接触凭证 — 调用方需从本服务拿 API key,本服务是必经之路,实际做不到,否决

### D10: trace-id 来源 — 调用方传入

- **选择**:Header `X-Trace-Id`(必填,MVP 强制);本服务写 audit + 透传上游
- **理由**:业务主导(agent-runtime 已有 W3C Trace Context);跨服务 trace 关联;本服务不造 ID
- **对应 finding**:Arch #1(跨网关 trace-id 关联)
- **已考虑 alternative**:
  - 本服务生成 — 调用方反查关联,关联弱,否决
  - 不关联 — 违背 eng-review,否决

### D11: Redis 缓存内容 — 仅模型路由表

- **选择**:key = model_name,value = upstream base_url / path / timeout;TTL 60s(可配置)
- **理由**:路由表 < 1KB,改一次不频繁,缓存收益最大;prompt / credential list 不在热路径
- **对应 finding**:Perf #1(性能)
- **已考虑 alternative**:
  - 路由 + prompt + 凭证 list — 不在热路径,收益小,否决
  - 全量(含 response cache)— freshness 问题,否决

### D12: 限流策略 — 不限,只计数

- **选择**:每条请求只 audit 计数,不做限流
- **理由**:MVP 阶段无证据需要;计数已是 audit 副产品;真正 quota 由上游 LLM provider 控制
- **对应 finding**:Perf #1(rate limit 是 3 个 perf 项之一,但 MVP 可降级)
- **已考虑 alternative**:
  - Per-User / Per-Workflow / Token-Budget — MVP 不必要,V1.0+ 业务跑起来再加

### D13: 审计粒度 — Metadata-Only

- **选择**:每条 LLM 调用 audit 写 14 个字段(trace_id / user_id / workflow_id / model / model_kind / bypass_isolation / pii_detected_types / pii_redacted_count / prompt_hash / token_in / token_out / latency_ms / upstream_status / error_class)
- **理由**:合规可追溯;MVP 3 个月预估 < 50GB;不存脱敏后/原文 → 减少二次泄露面
- **对应 finding**:Perf #2(5 个存储量预估之一)
- **已考虑 alternative**:
  - Full-Payload(冷存储)— 780GB/3mo 成本 + 二次泄露面,否决
  - 混合(按风险存)— 风险判定阈值无标准,否决

### D14: 实现语言 — Python (FastAPI)

- **选择**:Python 3.12 + FastAPI + uvicorn + httpx + SQLAlchemy[asyncio] + asyncpg + alembic + redis + pydantic v2
- **理由**:跟 credential service 一致,团队上手零成本;P99 = 6.74ms 已验证(credential 实测)
- **对应 finding**:无直接对应(技术栈对齐 architecture.md §4.4)
- **已考虑 alternative**:
  - Go — QPS < 100 不需要;团队成本高
  - Node.js — 需补人;Python 团队多

### D15: 测试范围 — 100% PII 拦截覆盖(eng-review Test #2 #2)

- **选择**:4 个 critical path 中本服务 = #2,子场景全部覆盖
  - 2.1 身份证脱敏
  - 2.2 手机/银行卡脱敏(不脱敏位数不足的)
  - 2.3 邮箱/信用代码/营收金额
  - 2.4 响应侧还原(同 trace 多轮调用)
  - 2.5 PII detector fail-open
  - 2.6 上游 timeout
  - 2.7 credential down
  - 2.8 trace 跨实例
- **理由**:eng-review 锁定
- **已考虑 alternative**:
  - + 50 paul LLM eval — MVP 不必要,V1.0+
  - + 透传保真性 — eng-review 没要求,优先级低

---

## Risks / Trade-offs

### R1: Fail-Open on PII detector

- **[Risk]** PII detector 异常期间,原始 PII 数据会发到公网 LLM
- → **Mitigation**: WARN 审计(每条都打)+ PagerDuty 告警(15 min 内响应)+ metric counter(dashboard 监控)
- → **Trade-off 接受理由**:企业内业务连续性优先;detector 健康间门可观察

### R2: 模型路由表缓存 60s,变更生效延迟

- **[Risk]** 管理员改了 model_routing 表 → 最多 60s 后才生效
- → **Mitigation**:K8s ConfigMap watch + Redis pub/sub 主动失效;紧急情况 reload endpoint
- → **Trade-off 接受理由**:MVP 阶段路由表改一次不频繁

### R3: 脱敏 map 跨实例依赖 Redis

- **[Risk]** Redis 挂 → 脱敏 map 写失败 → 本请求不脱敏
- → **Mitigation**:Redis 写失败 → 降级"不脱敏 + WARN 审计 + 告警";路由表读失败 → 用启动时载入的内存 copy
- → **Trade-off 接受理由**:Redis HA(2 实例 + 哨兵)由基础设施保障;本服务不重新实现

### R4: credential service 是下游依赖

- **[Risk]** credential service 不可用 → 本服务无法拿 LLM provider API key → 503
- → **Mitigation**:1 次重试 + 仍失败 → 503 + ERROR 审计 + 告警
- → **Trade-off 接受理由**:credential service 已 HA(2 实例);503 透传 = 调用方知道是基础设施问题

### R5: 4 个错误边界(eng-review Quality #3)

- **[canvas drag-loop]** N/A — 本服务不涉及画布(画布是 workflow-engine)
- **[runtime]** D2(D4 失败降级) + R3(Redis 失败降级) + R4(credential 失败) 全部覆盖
- **[user]** body 解析失败 → 422;trace_id 缺失 → 422;body > 1MB → 413
- **[security]** service token 校验失败 → 401 + 写 audit;**Fail-Closed**(不 Fail-Open)

### R6: 测试覆盖 PII 6 类规则的 false positive

- **[Risk]** 误杀"010-12345"这种不带手机号的业务号,导致 LLM 收到无意义占位符
- → **Mitigation**:每类规则都有"位数不足不命中"边界;集成测试覆盖 20+ 边界 case
- → **Trade-off 接受理由**:MVP 阶段误杀 < 1% 业务可接受;V1.0+ 收集业务样本优化正则

### R7: P99 网关层 < 50ms 需每次调用都 < 50ms

- **[Risk]** PII 正则扫描 + Redis 写 + httpx 透传 + 响应还原,链路较长
- → **Mitigation**:PII 正则编译缓存 + Redis 客户端连接池 + httpx keep-alive + perf bench 必跑
- → **Trade-off 接受理由**:credential service 已验证 P99 = 6.74ms,本服务架构同构

---

## Migration Plan

### 部署步骤

1. **阶段 0 — DB 准备**(apply 流程内)
   - alembic upgrade head → 创建 `audit_log` / `model_routing` 表
   - 插入初始 model_routing 种子数据(Qwen/DeepSeek/内部 vLLM)

2. **阶段 1 — 镜像构建 + 推送**
   - `services/audit-and-isolation/Dockerfile` 多阶段 build
   - CI: pytest / ruff / bandit / no-plaintext grep 全部通过

3. **阶段 2 — K8s 部署**
   - Deployment: 2 replicas
   - Service: ClusterIP,port 8080
   - HPA:CPU > 70% 时扩到 4 replicas(预留 buffer)
   - L4 LB:K8s Service 自动 round-robin 2 replicas
   - healthcheck:GET /healthz 返 200

4. **阶段 3 — 调用方切换**(分批)
   - 第一批:agent-runtime(week 1)— base_url 改 `http://audit-and-isolation:8080`
   - 第二批:workflow-engine(week 2)— 同上
   - 第三批:canvas(week 3)— 直接调用场景少,放最后

5. **阶段 4 — 验证**
   - perf bench:100 RPS × 60s,P99 < 50ms
   - critical path 2.1-2.8 全部跑过
   - 1 周灰度(只读 10% 流量),观察 audit 数据
   - 2 周全量

### Rollback 策略

- **触发条件**:P99 > 200ms 持续 / 5xx > 1% / 漏 PII > 0 容忍
- **步骤**:
  1. K8s 切回旧 base_url(调用方保留 fallback env var)
  2. 本服务 Deployment 缩到 0(不删,留作调查)
  3. audit_log 表保留(合规需要)
  4. 24h 内出 RCA report

### 验收条件

- 4 个 critical path 子场景(2.1-2.8)100% 通过
- 性能:P99 网关层 < 50ms,端到端 < 500ms
- HA:1 实例挂,K8s healthcheck 30s 内踢出,LB 切流量
- 告警:Fail-Open / Redis 挂 / credential 挂 3 类告警 15 min 内到
- audit:每条 LLM 调用都有 metadata 入库(用 paul 财务月报真实 workflow 验证)

---

## Open Questions

无。所有 17 个 Q 决策已 locked,本设计无未决问题。

---

## 引用(给后续阶段)

- `brainstorm.md` — 17 个 Q 的 raw 决策链
- `docs/architecture.md` §4.1 网关层 + §4.3.5 企业安全与权限 + §4.4 技术栈选型
- 设计 doc `## GSTACK REVIEW REPORT` — Arch #1 / Perf #1 / Quality #3 / Test #2
- 下一个 change:`implement-agent-runtime`(workflow-engine 完成后)
- 下游依赖:credential service(已落地,17 Reqs)

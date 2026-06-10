# Proposal — chatbiz-audit-and-isolation

> 模式: superpowers-bridge
> 阶段: proposal (基于 brainstorm.md + design.md)
> 承接: design.md 15 个 D 决策
> 日期: 2026-06-10

## Why

ChatBiz 平台核心护城河 = 内网部署 + 数据隔离 + 审计 + 自研画布 4 项合一。MVP 阶段(month 2-3)如果数据隔离网关不落地,paul 财务月报 workflow 拿不到 sponsor 可见进度,3 个具名用户(paul/leo/anny)就回退到"用 ChatGPT 贴内部数据"的违规模式。eng-review 12 finding 中 Arch #1 / Perf #1 / Test #2 / Quality #3 四条直接绑定本服务,缺一不可。

## What Changes

**数据隔离网关实现**
- From: 0 行代码;LLM 调用直连公网 provider,无 PII 拦截,无 audit
- To: 独立 Python FastAPI 服务(:8080),OpenAI-compatible API,所有出站 LLM 调用经此网关
- Reason: eng-review Arch #1 锁定;数据不出域 = 合规红线
- Impact: 破坏性 — 调用方(agent-runtime / workflow-engine)必须改 base_url

**PII 脱敏(Fail-Open + 类型化占位符 + 可逆)**
- From: 无 PII 防护
- To: 6 类正则(身份证/手机/银行卡/邮箱/统一社会信用代码/营收金额),`[类型_xxxx]` 占位符,Redis Per-Trace map(TTL 30min)存映射
- Reason: D2/D3/D4/D5 决策;detector 异常时 Fail-Open + WARN 审计(企业内业务连续性优先)
- Impact: 非破坏性(新增能力)

**Metadata-Only 审计(替代 Full-Payload)**
- From: 无 audit
- To: 每条 LLM 调用写 14 字段 metadata(trace_id/user_id/workflow_id/model/model_kind/bypass/pii_types/pii_count/prompt_hash/token_in/token_out/latency_ms/upstream_status/error_class)
- Reason: D13 决策;降低 780GB/3mo 冷存储成本 + 减少二次泄露面
- Impact: 非破坏性

**跨服务 trace-id 关联**
- From: 无关联
- To: 调用方传 `X-Trace-Id`,本服务透传上游 + 写 audit + 跟 credential service 联动
- Reason: Arch #1 锁定;故障排查必需
- Impact: 破坏性 — 调用方必须传 trace_id(否则 422)

**模型路由透传 + Bypass 机制**
- From: N/A
- To: 调用方传 `X-Model-Kind: public|private` + 可选 `X-Bypass-Isolation: true`(后者跳过 PII)
- Reason: D7 决策;支持企业内部 vLLM(节省 CPU)
- Impact: 非破坏性(默认值 = public + 不 bypass)

**2 实例 HA(active-active)**
- From: 0 实例
- To: K8s Deployment × 2 replicas + L4 LB + Redis 共享状态
- Reason: Arch #1 P0 单点防护
- Impact: 非破坏性(部署侧)

## Capabilities

### New Capabilities
- `llm-egress-gateway`: OpenAI-compatible proxy 服务(PII 脱敏 + 透传 + audit + 限流计数 + 模型路由 + HA)

### Modified Capabilities
- `audit-and-isolation` (openspec/specs/audit-and-isolation/spec.md 已存在占位): Requirements 全部重写,从"9 个 placeholder Req"改为对齐 D1-D15 的 17 个 Req
  - 主要冲突:占位 spec 第 5 个 Req "审计日志" 写"明文 prompt/response 完整记录",与 D13 Metadata-Only 冲突
  - 主要冲突:占位 spec 第 1 个 Req "网关失败阻断" 写"网关不可用 → 阻断所有 LLM 调用",与 D2 PII detector Fail-Open 不完全冲突(网关整体挂确实要 Fail-Closed,detector 挂才 Fail-Open)
  - 主要冲突:占位 spec 第 7 个 Req "限流 60 RPM" 与 D12 不限流冲突
  - 上述冲突在 proposal 阶段 surface,**冲突解决方式**:本 change 的 specs/ 重新定义需求,archive 时 delta spec 会自动合并到 openspec/specs/audit-and-isolation/spec.md

## Impact

**新增代码**:
- `services/audit-and-isolation/`(新 service,~ 25 文件,~ 5,000 行 Python + 测试)
  - app/pii/(detector/rules/redactor/reverser)
  - app/routing/(table/dispatcher)
  - app/llm/(client/streaming)
  - app/audit/(writer/hash)
  - app/auth.py
  - app/main.py + app/lifespan.py
  - tests/(unit/integration/perf)
  - Dockerfile
  - pyproject.toml
- `infrastructure/docker-compose.yml` 追加 3 个容器(本服务 + migrate + 留位)
- `infrastructure/k8s/` 追加 Deployment/Service/HPA([FUTURE-IMPLEMENTATION] — V1.0 完整 K8s manifest, MVP 阶段用 docker-compose)

**修改代码**:
- `openspec/specs/audit-and-isolation/spec.md`(archive 时 delta 合并,占位 spec 重写)

**新 API 端点**:
- `POST /v1/chat/completions` — OpenAI-compatible
- `POST /v1/completions` — OpenAI-compatible(legacy)
- `GET /v1/models` — OpenAI-compatible
- `GET /healthz` — K8s healthcheck
- `GET /readyz` — K8s readiness
- `GET /admin/model-routing` — 管理员查路由表 [FUTURE-IMPLEMENTATION]
- `POST /admin/model-routing/reload` — 管理员强制 reload [FUTURE-IMPLEMENTATION]

**下游依赖**:
- credential service(已落地,17 Reqs)— `use_credential` API
- PostgreSQL 16+(`audit_log` / `model_routing` 表)
- Redis 7+(脱敏 map + 路由表 cache)

**新 PII 规则**:
- 6 类正则,内置 + 启动时从 DB 加载(预置 Qwen / DeepSeek 凭据路由)

**eng-review 锁定决策引用**:
- Arch #1 (P1) — 数据隔离网关 = egress 强制点 + 2 实例 HA + 跨网关 trace-id 关联 ✅
- Perf #1 (P1) — P99 < 500ms + cache + rate limit + batch(cache ✅,限流降级为"只计数",batch V1.0+ 考虑)
- Quality #3 (P2) — 4 错误边界 ✅
- Test #2 (P1) — 4 critical path 100% 覆盖(本服务 = #2 PII 拦截)✅

**非目标**(Non-Goals,本 change 不做):
- 模型路由决策(透传,调用方定)
- 限流(只计数,不限)
- Full-Payload 审计
- K8s 完整 manifest(MVP 用 docker-compose)
- 海外模型合规(国产模型)
- 50 paul 财务月报 LLM eval
- 透传保真性测试
- Plugin Marketplace / 3rd-party 生态
- 多租户 SaaS

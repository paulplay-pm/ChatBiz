# audit-and-isolation Specification (Delta — MODIFIED)

> 模式: superpowers-bridge
> 阶段: specs
> 类型: MODIFIED Requirements(覆盖占位 spec 的 3 个 Req)
> 关联 proposal: `proposal.md` → Modified Capabilities → `audit-and-isolation`
> 关联 design: `design.md` → D2/D12/D13 决策覆盖占位 spec
> 日期: 2026-06-10
> 状态: [FUTURE-IMPLEMENTATION] — 仓库当前 0 行源代码,本 spec 触及 API/DB/前端

## 冲突说明

本 change 的 design.md 已锁定 3 个与 openspec/specs/audit-and-isolation/spec.md(占位 spec)冲突的决策。archive 时,以下 MODIFIED sections 会替换占位 spec 的对应 Requirement。

| 占位 spec Req | 占位 spec 原意 | 本 change 决定 | 冲突原因 |
|---------------|---------------|----------------|----------|
| 审计日志 | 明文 prompt/response 完整记录 | Metadata-Only | D13 决策 + 780GB/3mo 成本 + 二次泄露面 |
| 缓存 + 限流 + 批处理 [ENG-Perf #1] | 60 RPM 限流 + 超限写 audit | 不限流,只计数 | D12 决策 + MVP 简化 |
| 4 critical path 测试 [ENG-Test #2] | 1 个 change 覆盖 4 个 path | 本 change 仅覆盖 #2 PII 拦截 | Test #2 跨 4 service 协调,不应在 1 个 change |

---

## MODIFIED Requirements

### Requirement: 审计日志
系统 MUST 完整记录所有 LLM 调用 + 凭证访问 + 权限变更 + 异常;日志含 trace_id / user_id / cap / workflow_id / model / model_kind / bypass_isolation / pii_detected_types / pii_redacted_count / prompt_hash / token_in / token_out / latency_ms / upstream_status / error_class(共 15 字段;Metadata-Only,**MUST NOT** 含明文 prompt 或 response)。eng-review Test #2 + D13 决策。

#### Scenario: 完整审计 metadata
- **WHEN** 任何 LLM 调用完成
- **THEN** 系统 MUST 写入 audit_log(append-only,不可修改):全部 15 字段;**MUST NOT** 含明文 prompt 或 response(grep "110101" 在 audit_log 必须为 0 行)

#### Scenario: 审计查询(管理员)
- **WHEN** 管理员按 (user_id, time_range) 查询审计
- **THEN** 系统 MUST 返回 metadata(无明文);响应 < 2s;支持按 trace_id 聚合查询

#### Scenario: prompt_hash 还原(管理员)
- **WHEN** 管理员想看某次调用的 prompt 内容
- **THEN** 系统 MUST 提供 "audit_log + 重放 prompt_hash" 接口:① 重放脱敏后 prompt 给上游 ② 拿 response 但仍不存明文 ③ 仅给管理员使用,写 access audit

---

### Requirement: 缓存 + 限流 + 批处理 [ENG-Perf #1]
网关 MUST 实现 3 个性能优化(eng-review Perf #1):① 缓存(模型路由表 Redis-cached,TTL 60s);② 限流降级为"只计数,不阻断"(MVP 阶段;V1.0+ 引入真限流);③ 批处理留待 V1.0+(MVP 不实现)。

#### Scenario: 模型路由表缓存
- **WHEN** 同 model_name 1 分钟内 100 次查询
- **THEN** 系统 MUST 第 1 次从 PG 加载到 Redis,后续 99 次从 Redis 拿;Redis 不可达 MUST 降级到内存 fallback copy

#### Scenario: 单用户高频调用不阻断(MVP 不限流)
- **WHEN** 同一 user_id 1 分钟内 100 次 LLM 调用
- **THEN** 系统 MUST 全部 100 次都正常处理(不限流);audit 记 100 条;count 字段用于后续计费

#### Scenario: 限流 V1.0+ 引入
- **WHEN** V1.0 业务跑起来后,管理员配置 limit_policy
- **THEN** 系统 MUST 引入限流(超限返 429);**本 change 不实现**

---

### Requirement: 4 critical path 测试 [ENG-Test #2]
本系统涉及 4 个 critical path 之一(数据隔离网关 PII 拦截);测试 MUST 100% 覆盖 8 个子场景。eng-review Test #2 锁定。其他 3 个 critical path(paul 财务月报 end-to-end / 人工审批中断续接 / 插件加载降级)由对应 service 负责。

#### Scenario: PII 拦截 8 子场景全过
- **WHEN** 测试套件运行(子场景 2.1 身份证 / 2.2 手机银行卡 / 2.3 邮箱信用代码营收 / 2.4 响应还原 / 2.5 Fail-Open / 2.6 upstream timeout / 2.7 credential down / 2.8 trace 跨实例)
- **THEN** 8 个子场景 MUST 100% 通过;任何失败 MUST 阻断 release

#### Scenario: 其他 3 个 critical path 协调
- **WHEN** paul 财务月报 / 人工审批 / 插件加载 相关 service 落地
- **THEN** 对应 service MUST 负责自己的 critical path 测试(跨 service 测试通过 workflow-engine / agent-runtime / plugin-market 的 e2e 套件);本 change 不实现

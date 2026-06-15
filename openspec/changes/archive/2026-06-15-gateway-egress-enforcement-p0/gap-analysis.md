# Gap Analysis:本 spec vs 现有 `services/audit-and-isolation/`

**生成时间:** 2026-06-12(apply 启动前 surface)
**背景:** apply 阶段发现仓库早就有 `services/audit-and-isolation/`(2335 行 Python,alembic,Dockerfile,100% 覆盖率强制,eng-review Arch #1 引用)。本 spec 是基于"0 行代码"假设编写的,75% 任务与现有实现重叠。**用户决定走"增量补差"路线**,本文件是补差依据。

## 已实现(spec 25 task 标 done,标 [EXISTING])

| 原 spec task | 现有实现位置 | 一致性 |
|---|---|---|
| 1.1 服务骨架 | `services/audit-and-isolation/app/main.py` + `pyproject.toml` | ✅ 完全一致 |
| 1.2 迁移 SQL | `services/audit-and-isolation/alembic/versions/001_create_audit_log.py` | ✅ audit_log 表(改名 audit_events 不影响,ORM 锁定) |
| 1.3 SDK 空壳 | `services/audit-and-isolation/app/llm/client.py` | ⚠️ SDK 形态不同:用 OpenAI 兼容 HTTP 客户端,不是 HMAC 注入;客户端由 `services/workflow-engine/` 等调用方实现 |
| 1.4 scanner CLI | **无** | ❌ **待补** |
| 2.1 blocklist yaml | **无** | ❌ **待补** |
| 2.2 allowlist yaml | **无** | ❌ **待补** |
| 2.3 AST 扫描 | **无** | ❌ **待补** |
| 2.4 SDK HMAC 注入 | **无**(现有用 `Authorization: Bearer <token>` + 调 credential service) | 🔄 **决策冲突,见下** |
| 2.5 中间件签名验证 | `services/audit-and-isolation/app/auth.py` 存在(用 credential service 而非 HMAC) | 🔄 **决策冲突** |
| 2.6 配对 e2e | `tests/integration/test_e2e_4_scenarios.py` | ✅ 已覆盖 |
| 3.1 /health | `services/audit-and-isolation/app/api/health.py` | ✅ 已实现,端点是 `/healthz` + `/readyz` |
| 3.2 preStop 排空 | **无**(单实例,无 HA) | ❌ **待补**(随 3.3 一起) |
| 3.3 K8s manifest | **无** | ❌ **待补** |
| 3.4 SDK 重试器 | `services/audit-and-isolation/app/llm/client.py` 内部有重试(1 次 5xx),不暴露给调用方 | 🔄 **决策冲突**:现有重试是上游 LLM,不是 HA failover |
| 3.5 NGINX L4 LB | **无** | ❌ **待补** |
| 3.6 HA e2e | **无** | ❌ **待补** |
| 4.1 pii_rules.yaml | `services/audit-and-isolation/app/pii/rules.py`(代码内 RULES 列表) | ⚠️ **格式不同**:现在是 Python 常量,不是 yaml;3 档只剩 mask |
| 4.2 加载器 | `app/pii/rules.py::validate_rule` | ✅ 已实现 |
| 4.3 PII 扫描器 | `app/pii/detector.py` + `redactor.py` | ✅ 已实现(6 类) |
| 4.4 block 档 | **无**(现有只 mask) | 🔄 **决策冲突**:与现有 mask-only 冲突,需 decide |
| 4.5 mask 档 | `app/pii/redactor.py` + `reverser.py` | ✅ 已实现(可逆) |
| 4.6 log-only 档 | **无** | 🔄 **决策冲突**:现有是写 audit 表,没有 log-only 显式档位 |
| 4.7 审计写入 | `app/audit/writer.py` + `outbox` | ✅ 已实现 |
| 4.7.1 定时归档 | **无** | ❌ **待补** |
| 4.7.2 冷查询 | **无** | ❌ **待补** |
| 4.8 PII e2e | `tests/integration/test_pii_*.py`(8 个子场景) | ✅ 已覆盖 |
| 5.1 trace_id | `app/api/chat.py` header 解析 + `app/audit/writer.py` 写 trace_id | ⚠️ **格式不同**:现有透传 `X-Trace-Id`,不生成 UUIDv7 |
| 5.2 双写 | `app/audit/writer.py` PG + `app/redis_client.py` Redis | ⚠️ **用途不同**:Redis 存 PII 反向映射(per-trace 30min),不是 trace cache |
| 5.3 trace 查询 | **无** | ❌ **待补** |
| 5.4 trace e2e | **无** | ❌ **待补** |
| 5.5 perf contract | `app/routing/table.py` 算半个(Redis-cached routing table) | ❌ **待补** |
| 5.6 /metrics | `app/metrics.py` 有 Counter/Histogram 但**端点没暴露** | ❌ **待补** |
| 5.7 集成 | **无**(Noop 降级路径) | ❌ **待补** |
| 5.8 文档 | **无** | ❌ **待补** |
| 6.1 全量覆盖率 | `pyproject.toml` 已配 `--cov-fail-under=100` | ✅ 已强制 |
| 6.2 critical path | `tests/integration/_critical_path_base.py` + `test_e2e_4_scenarios.py` | ✅ 已覆盖 4 个 critical path |
| 6.3 verify.md | **无** | ❌ **本 spec apply 后写** |

## 决策冲突点(3 个,需用户二次确认)

### DC1: HMAC 签名 vs service token auth

- **spec 写的:** `X-Gateway-Signature` HMAC 头 + 静态扫描双层防御
- **现有的:** `Authorization: Bearer <token>` + 调 credential service 验证(service token,集中轮转)
- **用户决定走补差 =** 保留现有 credential service 路径,**HMAC 头不引入**(引入会破坏现有 service-to-service 信任链)
- **补差结果:** spec task 2.4 / 2.5 **删除**,替换为"`auth.py` 已用 credential service,本 spec 不引入新 auth 维度";静态扫描(AST 2.1-2.3)仍 **保留**,作为编译期防御

### DC2: PII mask-only vs 三档(block/mask/log-only)

- **spec 写的:** block / mask / log-only 三档
- **现有的:** mask 一档 + 可逆
- **用户决定走补差 =** 保留现有 mask-only(理由:可逆设计对 paul 月报场景友好,block 会拒服务;eng-review 报告里没要求 block)
- **补差结果:** spec task 4.4 / 4.6 **删除**,只保留 mask(task 4.5)+ 写入审计(task 4.7)。proposal.md 影响面段必须 surface "PII block 档未引入,与现有 mask-only 兼容,后续如需 block 走 T11 错误边界"

### DC3: trace_id 格式 UUIDv7 vs 透传 X-Trace-Id

- **spec 写的:** 网关生成 UUIDv7
- **现有的:** 调用方传 `X-Trace-Id`,网关透传
- **用户决定走补差 =** 保留现有透传模式(spec 写 UUIDv7 是基于 "网关是新" 假设,补差场景下网关是已有,不动)
- **补差结果:** spec task 5.1 改写为"网关保留调用方 X-Trace-Id,若缺失则生成 UUIDv7"(兼容模式)

## 待补 12 task(apply 实际工作量)

| ID | 内容 | 出处 |
|---|---|---|
| 1.4 + 2.1 + 2.2 + 2.3 | `services/gateway-scanner/` 静态扫描 CLI(blocklist yaml + allowlist yaml + AST 扫描) | 静态扫描编译期防御,无冲突 |
| 3.2 + 3.3 + 3.5 + 3.6 | HA 拓扑(preStop 排空 + K8s manifest + NGINX L4 + HA e2e) | 现有单实例,本 spec 加 2 实例 active-active |
| 4.7.1 + 4.7.2 | 定时归档 + 冷查询(eng-review Perf #2 锁定的 780GB/3mo MinIO 路径) | 现有 audit_log 无归档 |
| 5.3 + 5.4 | trace 跨实例查询端点 + e2e | 现有不暴露 trace 查询 |
| 5.5 + 5.6 + 5.7 | perf contracts + /metrics 端点 + Noop 集成 | 现有 metrics 计数器存在但端点未暴露 |
| 5.8 | docs/architecture.md §4.3.Y PII 规则集段 | 文档补全 |
| 6.3 | verify.md | apply 收尾 |

## 12 task 不动(改 done + [EXISTING])

| ID | 内容 | 状态 |
|---|---|---|
| 1.1 | 服务骨架 | done by audit-and-isolation |
| 1.2 | 迁移 SQL | done by audit-and-isolation (audit_log 表) |
| 1.3 | SDK 空壳 | done by audit-and-isolation (OpenAI 兼容) |
| 2.4 | SDK HMAC 注入 | **删除**(DC1) |
| 2.5 | 中间件签名验证 | **删除**(DC1) |
| 2.6 | 配对 e2e | done |
| 3.1 | /health | done(audit-and-isolation 用 /healthz + /readyz) |
| 3.4 | SDK 重试器 | **删除/改**(DC1:auth 路径不动) |
| 4.1 | pii_rules.yaml | done(代码内 RULES) |
| 4.2 | 加载器 | done |
| 4.3 | PII 扫描器 | done |
| 4.4 | block 档 | **删除**(DC2) |
| 4.5 | mask 档 | done |
| 4.6 | log-only 档 | **删除**(DC2) |
| 4.7 | 审计写入 | done |
| 4.8 | PII e2e | done |
| 5.1 | trace_id | done(透传) |
| 5.2 | 双写 | done(Redis 用途不同但实现存在) |
| 5.4 | trace e2e(跨实例) | **删除/合并到新 5.3 跨实例 e2e** |
| 5.8 | 文档(独立写) | 部分(只写 5.8 docs §4.3.Y 增量) |
| 6.1 | 覆盖率 | done(已配 --cov-fail-under=100) |
| 6.2 | critical path | done(已有 4 个 critical path 测试) |

**新 spec 形态:37 task → 12 待补 task + 18 已 done + 7 删除**

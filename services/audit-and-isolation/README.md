# chatbiz-audit-and-isolation

> ChatBiz 数据隔离网关 — egress 强制点。所有出站 LLM 调用 MUST 经此。
> eng-review Arch #1 (P1) 锁定。

## What it does

OpenAI-compatible 代理层(`POST /v1/chat/completions`),在调用方(agent-runtime / workflow-engine / canvas)与上游 LLM 之间做 4 件事:

1. **PII 自动检测与脱敏**(6 类正则,可逆):身份证 / 手机 / 银行卡 / 邮箱 / 统一社会信用代码 / 营收金额 → `[类型_xxxx]` 类型化占位符,响应侧反向还原
2. **Metadata-Only 审计**:每条调用 14 字段写入 PG(trace_id / user_id / model / token / latency / pii_types / ...),明文 prompt/response **不入库**
3. **跨服务 trace-id 关联**:调用方传 `X-Trace-Id`,透传上游 + 写 audit
4. **模型路由**:按 `X-Model-Kind: public|private` + 可选 `X-Bypass-Isolation: true` 决定 PII 是否跳过

## Architecture

```
调用方 (agent-runtime / workflow-engine)
        ↓ OpenAI-compatible API
chatbiz-audit-and-isolation :8080
  ├─ 鉴权 (service token, 调 credential service)
  ├─ PII Detector (6 类正则) → Redactor → Redis map (Per-Trace, TTL 30min)
  ├─ Routing (Redis-cached model_routing table)
  ├─ Upstream Caller (httpx async)
  ├─ Reverser (响应侧还原)
  └─ Audit Writer (outbox 异步落 PG)
        ↓
上游 LLM (public: Qwen/DeepSeek | private: 内部 vLLM)
```

## Tech Stack

| 层 | 技术 |
|---|------|
| Language | Python 3.12 |
| Web | FastAPI + uvicorn + httpx async |
| DB | PostgreSQL 16 + SQLAlchemy 2.0 async + asyncpg + Alembic |
| Cache | Redis 7(脱敏 map + 路由表) |
| Test | pytest + unittest + fakeredis + respx |
| Lint | ruff + bandit |
| HA | 2 实例 + L4 LB(K8s service) |

## 关键设计决策

| 决策 | 选择 | 引用 |
|------|------|------|
| Egress 强制点 | 独立 OpenAI-compatible proxy 服务 | eng-review Arch #1 |
| PII detector 失败姿态 | Fail-Open + WARN 审计 + PagerDuty 告警 | D2(brainstorm Q1) |
| PII 检测 | 6 类正则(< 1ms) | D3 |
| 脱敏动作 | 类型化占位符 `[类型_xxxx]`,可逆 | D4 + D14 |
| 脱敏 map 粒度 | Per-Trace,TTL 30min | D5 |
| 模型路由 | 调用方定(透传)+ Header `X-Model-Kind` 控制 PII | D6 + D7 |
| HA | 2 实例 + L4 LB active-active | D8 |
| 凭证 | 调 credential service `use_credential` API | D9 |
| trace-id | 调用方传入 `X-Trace-Id`(必填) | D10 |
| Redis cache | 仅模型路由表(TTL 60s) | D11 |
| 限流 | 不限,只计数 | D12 |
| 审计 | Metadata-Only(14 字段) | D13 |

详见 `openspec/changes/archive/2026-06-10-implement-audit-and-isolation/{brainstorm,design}.md`。

## Quick start

### 本地开发

```bash
cd services/audit-and-isolation
pip install -e ".[dev]"

# 起 PG + Redis + credential
cd ../../infrastructure
docker compose up postgres redis credential -d

# alembic migration + seed
cd ../services/audit-and-isolation
DATABASE_URL=postgresql+asyncpg://chatbiz:chatbiz@localhost:5432/audit_isolation \
  alembic upgrade head

# 启动 service
uvicorn app.main:app --port 8080 --reload
```

### 用 docker-compose 一把起

```bash
cd infrastructure
docker compose up audit-and-isolation -d
docker compose logs -f audit-and-isolation
```

3 容器:`chatbiz-audit-isolation`(主)+ `chatbiz-audit-isolation-migrate`(一次性)+ 已有的 postgres/redis/credential。

## Testing

```bash
cd services/audit-and-isolation
PYTHONPATH=. python3 -m unittest discover -t . -s tests -v
```

测试矩阵:
- **单元测试** (90+): `tests/unit/test_*.py`
- **集成测试** (37+): `tests/integration/test_*.py`,用 fakeredis + respx mock 上游
- **Critical path 2.1-2.8** (8 个 e2e): `tests/integration/test_pii_subscenario_2_*.py` — eng-review Test #2 锁定

跑 CI gate:

```bash
python3 verify.py
```

18 项检查全部通过才算 release-ready。

## Performance budget

- **P99 网关层延迟** < 50ms(不含上游 LLM,100 RPS 压测下)
- **P99 端到端**(含 LLM 透传)< 500ms — eng-review Perf #1 锁定

跑 bench:

```bash
# 100 RPS × 60s 透传压测
PYTHONPATH=. python3 perf/bench_proxy.py

# In-process smoke(不需要起 server)
PYTHONPATH=. python3 perf/bench_use_api_smoke.py
```

## API 端点

| 端点 | 用途 |
|------|------|
| `POST /v1/chat/completions` | OpenAI-compatible 主端点 |
| `POST /v1/completions` | OpenAI-compatible legacy |
| `GET /v1/models` | 列已启用的 model_routing |
| `GET /healthz` | K8s liveness |
| `GET /readyz` | K8s readiness(检查 PG / Redis / credential / 路由表) |

完整 OpenAPI:`docs/openapi/audit-and-isolation.{yaml,json}`(从 `app.main:app` 自动导出)。

## 安全规约(CLAUDE.md 全局)

- ✅ 主密钥 / 凭证明文 **不入** commit / log / audit / test fixture
- ✅ LLM provider API Key 走 credential service,**不**硬编码 / 不进 env
- ✅ audit_log 表只存 prompt_hash(SHA-256),**不存**明文
- ✅ Service token 鉴权 fail-closed(401 + 不继续)
- ✅ PII detector fail-open(Fail-Open + 告警,业务连续性优先,**不**阻断)

## 4 个错误边界(eng-review Quality #3)

| 边界 | 处理 |
|------|------|
| **security** | service token 验证失败 → 401(fail-closed) |
| **runtime** | upstream 5xx/timeout / Redis 挂 / credential 挂 → 重试或降级 |
| **user** | body 解析错 / trace_id 缺失 / body > 1MB → 422/413 |
| **canvas drag-loop** | N/A(本服务不涉及画布) |

## Spec & change

- **Spec**: `openspec/specs/audit-and-isolation/spec.md`
- **Change archive**: `openspec/changes/archive/2026-06-10-implement-audit-and-isolation/`
- **eng-review locked**: Arch #1 / Perf #1 / Quality #3 / Test #2(全部对齐)

## 下游依赖

- `chatbiz-credential` service(已落地,17 Reqs)— `POST /v1/credentials/use` 拿 LLM API Key
- PostgreSQL 16(audit_log + model_routing 两表)
- Redis 7(脱敏 map + 路由表 cache)

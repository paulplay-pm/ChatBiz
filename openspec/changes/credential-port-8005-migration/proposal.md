# credential-port-8005-migration — Proposal

## Why

`infrastructure/docker-compose.yml` 把 `credential` 服务的 host port 映射为 `8000:8000`。本机 Trae IDE (PID 7703) 占着 `0.0.0.0:8000` (IPv6),导致本机 `docker compose -p chatbiz up` 必 fail 在 credential 容器 bind 阶段。

`web-integration-test-suite` 与 `fix-production-compose` 两个 change 都把 "7-service 端到端 up 验证" 标 BLOCKED 在本机。要让 7-service 端到端在本机也能跑通,必须换 host port。

不改: 本机任何 dev 阶段测试 production compose 必 fail; 后续 CI 接入 (eng-review Test #1) 无法做端到端冒烟。

改: 把 credential host port 从 8000 迁到 8005,container-internal port 8000 保持不动 (audit-and-isolation / workflow-engine / credential Dockerfile healthcheck 都消费 `credential:8000` DNS)。

参考基线:
- `CLAUDE.md` 端口表 "8005+ (未来) 可用,新 service 从 8005 开始往后分配" — 8005 是第一个合规的"未来"端口
- `infrastructure/docker-compose.yml` line 91: `"8000:8000"` (待改)
- `infrastructure/README.md` line 52: `curl http://localhost:8000/healthz` (待改)
- `services/credential/locust/locustfile.py` line 12: `--host http://localhost:8000` (待改)
- `CLAUDE.md` 端口表 (待改 8000 行 + 加 8005 行)

## What Changes

- **修改** `infrastructure/docker-compose.yml`: `credential.ports: "8000:8000"` → `"8005:8000"`
- **修改** `infrastructure/README.md`: `curl http://localhost:8000/healthz` → `curl http://localhost:8005/healthz`
- **修改** `services/credential/locust/locustfile.py`: `--host http://localhost:8000` → `--host http://localhost:8005`
- **修改** `CLAUDE.md` 端口表: 8000 行标"已迁移到 8005" + 注释; 新增 8005 行标"credential (migrated from 8000)"

**不** 改:
- Container-internal port 8000 (audit-and-isolation / workflow-engine / Dockerfile healthcheck 都不动)
- `infrastructure/docker-compose-test.yml` (test stack 本就不暴露 host 8000)
- `services/workflow-engine/.env.example` 的 `CREDENTIAL_SERVICE_URL=http://credential:8000` (container-internal, 不变)
- `services/workflow-engine/tests/...` 所有 respx mock 用 `credential-test:8000` (test mock hostname, 不变)
- 任何 service 业务代码

## Capabilities

### New Capabilities

- `credential-port-migration`: credential host port 8000 → 8005 迁移的 capability。**前端范围** = N/A (纯基础设施, 零 UI/业务/协议场景); **后端范围** = `infrastructure/docker-compose.yml` + `infrastructure/README.md` + `services/credential/locust/locustfile.py` + `CLAUDE.md`; **豁免前端** = 纯基础设施层。

### Modified Capabilities

无。

## Impact

- **代码层**:
  - `infrastructure/docker-compose.yml` (改, 1 行)
  - `infrastructure/README.md` (改, 1 行)
  - `services/credential/locust/locustfile.py` (改, 1 行)
  - `CLAUDE.md` (改, 端口表)
- **依赖**: 无新增
- **CLAUDE.md 端口表**: 8000 行标"已迁移到 8005"; 新增 8005 行 "credential (migrated from 8000)"。8000 行不删 (审计追踪)。
- **openspec/config.yaml §apply.rules**:
  - "MUST: 端口从 CLAUDE.md 端口分配表选用" — **满足** (8005 标"未来", CLAUDE.md "新 service 从 8005 开始往后分配" 明文允许)
  - "MUST: 服务容器在 infrastructure/docker-compose.yml 注册" — **满足** (本 change 改的就是该文件)
  - "MUST: 健康检查用 HTTP GET" — 满足 (既有 healthcheck 不动)

## Non-goals

- **不** 改 container-internal port 8000
- **不** 改 audit-and-isolation / workflow-engine 的 CREDENTIAL_SERVICE_URL env (它们消费 `credential:8000` 容器内端口, 不动)
- **不** 改 test stack (`docker-compose-test.yml` 本身就不暴露 host 8000)
- **不** 改既有 mock test (用 `credential-test:8000` mock hostname, 不变)
- **不** 删 CLAUDE.md 8000 行 (保留审计追踪)
- **不** 重排 CLAUDE.md 端口表 (仅改 8000 行 + 加 8005 行)

## Open Questions

- **OQ1**: 本机 `docker compose -p chatbiz up --wait` 改后能否跑通 7-service? **答**: 应能 (8005 free + fix-production-compose 三个 compose bug 已修)。verify 阶段直接跑。
- **OQ2**: Locust 性能测试改 `--host` 后能否在生产 dev 跑? **答**: 1 行改动, 风险面 0。

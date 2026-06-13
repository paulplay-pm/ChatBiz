# credential-port-migration

**Frontend Scope: N/A — 纯基础设施层（infrastructure compose + 文档），无 UI / 业务 / 协议场景**

**Backend Scope: 含后端**（`infrastructure/docker-compose.yml` + `infrastructure/README.md` + `services/credential/locust/locustfile.py` + `CLAUDE.md`）

**Impact**（被谁消费）：
- 解 `web-integration-test-suite` 和 `fix-production-compose` 两个 change 在本机的 BLOCKED 验证项
- 后续 CI 接入（eng-review Test #1）需要 7-service 端到端 up
- 任何 dev 阶段 `docker compose -p chatbiz up` 在本机（Trae IDE 占 8000 的环境）

## ADDED Requirements

### Requirement: credential host port 8000 → 8005

`infrastructure/docker-compose.yml` 的 `credential.ports` MUST 从 `"8000:8000"` 改为 `"8005:8000"`。Container-internal port 8000 MUST 保持不变（其他 service 仍消费 `credential:8000` DNS）。MUST NOT 改 audit-and-isolation / workflow-engine 的 `CREDENTIAL_SERVICE_URL` env。

#### Scenario: credential 容器在本机能 bind 8005
- **WHEN** 本机 `lsof -i :8005` 确认 free
- **AND** `docker compose -p chatbiz up credential` 跑
- **THEN** 容器日志 MUST NOT 含 `bind: address already in use`
- **AND** `docker compose -p chatbiz ps` 显示 credential 状态 `running`

#### Scenario: credential 容器内仍监听 8000
- **WHEN** `docker exec chatbiz-credential sh -c "ss -tlnp | grep 8000"` 执行
- **THEN** MUST 含 `:8000` 监听行 (uvicorn 在容器内仍 bind 8000)
- **AND** `localhost:8000` 在容器内可达

#### Scenario: host 上 curl 8005 拿到 credential health
- **WHEN** `curl http://localhost:8005/healthz` 在 host 执行
- **THEN** MUST 返回 200
- **AND** body 来自 credential 容器 (响应 shape 包含 `{"status": "ok"}` 或类似)

### Requirement: README 与 Locust 同步 8005

`infrastructure/README.md` 的 `curl http://localhost:8000/healthz` MUST 改为 `curl http://localhost:8005/healthz`。`services/credential/locust/locustfile.py` 的 `--host http://localhost:8000` MUST 改为 `--host http://localhost:8005`。

#### Scenario: README 文档示例
- **WHEN** `grep -n "localhost:8000" infrastructure/README.md` 执行
- **THEN** MUST 输出 0 行（全部 8000 → 8005）

#### Scenario: Locust 启动 host
- **WHEN** `grep -n "host http://localhost" services/credential/locust/locustfile.py` 执行
- **THEN** MUST 含 `localhost:8005` 1 行
- **AND** MUST NOT 含 `localhost:8000`

### Requirement: CLAUDE.md 端口表更新

`CLAUDE.md` 端口表 8000 行 MUST 标"已迁移到 8005 (2026-06-13)" + 备注"见 change credential-port-8005-migration"。新增 8005 行 MUST 标"credential" + 备注"migrated from 8000"。**保留** 8000 行不删。

#### Scenario: 端口表 8000 行保留
- **WHEN** `grep -n "^\| 8000 \|" CLAUDE.md` 执行
- **THEN** MUST 含 1 行含 "8000" 且状态列含"已迁移"

#### Scenario: 端口表 8005 行新增
- **WHEN** `grep -n "^\| 8005 \|" CLAUDE.md` 执行
- **THEN** MUST 含 1 行含 "8005" 且状态列含"已分配" 且服务列含"credential"

### Requirement: 端到端 7-service up 验证

干净 dev 机（本机 Trae 不占 8005）`docker compose -p chatbiz down -v && docker compose -p chatbiz up --wait` MUST 跑通 7 service 全部 healthy（postgres / redis / credential / audit-and-isolation / mcp / workflow-engine / web）。

#### Scenario: 7 service 全 healthy
- **WHEN** `docker compose -p chatbiz ps` 执行
- **THEN** 7 service MUST 全部 `State: healthy`
- **AND** `docker compose -p chatbiz up --wait` 退出码 0

#### Scenario: 跨 service 链路通
- **WHEN** 7 service 都 healthy 后
- **THEN** `curl http://localhost:8005/healthz` 200 (credential)
- **AND** `curl http://localhost:8080/healthz` 200 (audit-and-isolation, 它内部连 credential:8000 容器端口)
- **AND** `curl http://localhost:8001/healthz` 200 (workflow-engine, 它内部连 credential:8000 容器端口)

#### Scenario: inter-service 调用工作（audit → credential）
- **WHEN** 7 service 都 healthy 后
- **AND** 调 audit-and-isolation 的任意需要 credential 验证的 endpoint
- **THEN** MUST NOT 收到 502/503/504 (audit 无法连 credential)
- **AND** audit-and-isolation 容器日志 MUST 不含 "credential service unavailable"

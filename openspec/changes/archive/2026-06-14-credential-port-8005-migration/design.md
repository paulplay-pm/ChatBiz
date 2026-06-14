# credential-port-8005-migration — Design

## Context

`infrastructure/docker-compose.yml` 把 `credential` 服务的 host port 映射为 `8000:8000`。本机 Trae IDE (PID 7703) 占 `0.0.0.0:8000` (IPv6),导致本机 `docker compose -p chatbiz up` 必 fail 在 credential 容器 bind 阶段。

`web-integration-test-suite` 与 `fix-production-compose` 两个 change 都把 "7-service 端到端 up 验证" 标 BLOCKED 在本机。本 change 是解此 BLOCKED 的最小改动: 把 credential host port 迁到 8005 (CLAUDE.md "未来" 范围第一个端口)。

**关键约束**:
- Container-internal port 8000 **不能动**: audit-and-isolation / workflow-engine / Dockerfile healthcheck 都消费 `credential:8000` 容器内 DNS + 端口
- 8005 在 CLAUDE.md "8005+ (未来) 可用" 范围,合规
- 本机 8005 free (lsof 已验)

**eng-review 锁定决策**:
- **Test #1** (P1): 3 层测试金字塔 — 解阻塞 7-service 端到端 up
- **Test #2** (P1): 4 critical path — 解阻塞 ① paul 完整链路 (前两 change 已落代码)

**stakeholder**: devops (compose 维护 1 人)

## Goals / Non-Goals

**Goals**:
- `infrastructure/docker-compose.yml` `credential.ports: "8000:8000"` → `"8005:8000"`
- `infrastructure/README.md` `localhost:8000` → `localhost:8005`
- `services/credential/locust/locustfile.py` `--host localhost:8000` → `localhost:8005`
- `CLAUDE.md` 端口表 8000 行标"已迁移到 8005" + 注释; 新增 8005 行
- 改后本机 `docker compose -p chatbiz up --wait` 7-service 全 healthy
- Container-internal 8000 保持, audit-and-isolation / workflow-engine / Dockerfile healthcheck 零改动

**Non-Goals**:
- 改 container-internal port 8000
- 改 audit-and-isolation / workflow-engine 的 CREDENTIAL_SERVICE_URL env
- 改 test stack (docker-compose-test.yml 本就不暴露 host 8000)
- 改既有 mock test (用 `credential-test:8000` mock hostname)
- 删 CLAUDE.md 8000 行
- 重排 CLAUDE.md 端口表

## Decisions

### D1: 选 8005 (CLAUDE.md "未来" 范围第一个)

**选择**: 8005 = CLAUDE.md 端口表"8005+ (未来) 可用,新 service 从 8005 开始往后分配"的第一个。

**理由**:
- 合规: CLAUDE.md 明文允许
- 本机 free (lsof 已验)
- 8 开头段跟 8000/8001/8004 视觉一致 (同段)

**已考虑 alternative**:
- **A. 8006 / 8007+** — 拒绝: 没理由跳 8005, 它是 "未来" 范围第一个
- **B. 9000+** — 拒绝: 跳出常用 dev 段, dev 工具(IDE / debug)常用 9000 段
- **C. 删 host port mapping** (类似 test stack) — 拒绝: 失去直接调试 + Locust 需要 host 访问

### D2: Container-internal port 8000 保持

**选择**: 容器内 FastAPI app 仍监听 8000; 仅 host → container 映射端口改 8005 → 8000。

**理由**:
- `CREDENTIAL_SERVICE_URL=http://credential:8000` 既是 compose DNS 又是容器内端口, audit-and-isolation / workflow-engine 引用不动
- Dockerfile healthcheck `http://127.0.0.1:8000/healthz` 是容器 loopback, 不动
- 容器内 0 改动,风险面最小

### D3: 只改 4 个 host-side reference

**选择**: 3 文件 + 1 CLAUDE.md 端口表行, 不动 container-internal / mock test。

**理由**:
- 范围最小, 风险面最小
- 其他 `localhost:8000` 都是 mock test (respx) 或文档示例, 不影响

**已考虑 alternative**:
- **A. 同步改所有 `localhost:8000` 文档** — 拒绝: 风险面变大, 收益小; 用户文档/curl 示例可后续 PR 修

### D4: CLAUDE.md 8000 行不删, 标记"已迁移"

**选择**: 8000 行保留, 状态列填"已迁移到 8005 (2026-06-13)", 备注列加"见 change credential-port-8005-migration"。

**理由**:
- 审计追踪: 未来 reader 知道这个端口历史, 不是凭空消失
- 防止未来 service 误把 8000 当"空闲"
- 新增 8005 行状态列"已分配", 备注列"credential (migrated from 8000)"

## Risks / Trade-offs

**[Risk] 远端 CI 8005 被占** — lsof 本机 8005 free; 但远端 CI 跑同一份 compose 需确认。**Mitigation**: verify 步骤显式 `lsof -i :8005`; CI 跑失败时改 8006/8007 (同 CLAUDE.md "未来" 范围)。

**[Risk] 既有 user 脚本访问 `localhost:8000` credential** — 改后失效。**Mitigation**: change commit message 显式列 "BREAKING: credential host port 8000 → 8005"; release notes 同步。

**[Risk] Locust 性能测试 CI 跑** — 改 --host 后 CI 需要对应改 perf 入口。**Mitigation**: `services/credential/locust/locustfile.py` 是唯一 reference, 1 行改完。

**[Trade-off] 8000 行不删** — 接受 (审计追踪)。

**[Trade-off] 不动 container-internal** — 接受 (风险面最小, 零 service 业务代码改动)。

## Migration Plan

**本 change 不涉及数据迁移**, 仅改 host port + 文档。

**部署顺序**:
1. 改 4 文件
2. 本机 `lsof -i :8005` 确认 free
3. 本机 `docker compose -p chatbiz down -v` 清空 (因为 fix-production-compose 改过 init, 需要 fresh start)
4. 本机 `docker compose -p chatbiz up --wait` 验证 7-service healthy
5. `curl http://localhost:8005/healthz` 验证 credential
6. `curl http://localhost:8080/healthz` 验证 audit-and-isolation (它内部仍连 credential:8000 容器端口, 验证 inter-service 链路)

**rollback**:
- revert commit 即可 (无数据迁移)
- 既有 CI / user 脚本访问 8000 改回 work

## Open Questions

- **OQ1**: 本机 7-service up 验证? **答**: 跑。
- **OQ2**: Locust 改后能否跑? **答**: 1 行改, 风险 0。

# credential-port-8005-migration — Tasks

> **Scope**：把 credential 服务 host port 从 8000 迁到 8005，container-internal port 保持。改 3 文件 + CLAUDE.md 端口表。
>
> **不** 改：container-internal 8000 / audit-and-isolation / workflow-engine 的 CREDENTIAL_SERVICE_URL / test stack / 既有 mock test (用 `credential-test:8000` 不变) / 任何 service 业务代码。
>
> **前置门**：`fix-production-compose` change merged (本机 docker compose 3 个 compose bug 已修); `infrastructure/postgres-init-test/` workaround 保留。

## 0. 前置门

- [ ] 0.1 验 `docker --version >= 24` + `lsof -i :8005` 输出空（本机 8005 free）。验：`docker -v` + `lsof -i :8005`。

## 1. 改 3 个 host-side reference

- [ ] 1.1 修改 `infrastructure/docker-compose.yml` `credential.ports`: `"8000:8000"` → `"8005:8000"`。**编码规范**：格式与既有一致。**安全清单**：用 `${VAR:-default}` 不需要。验：`grep -n "8005:8000" infrastructure/docker-compose.yml` 输出 1。
- [ ] 1.2 修改 `infrastructure/README.md` `localhost:8000/healthz` → `localhost:8005/healthz`。**编码规范**：注释 + curl 示例。**安全清单**：仅 1 行。验：`grep -n "localhost:8000" infrastructure/README.md` 输出 0。
- [ ] 1.3 修改 `services/credential/locust/locustfile.py` `--host http://localhost:8000` → `--host http://localhost:8005`。**编码规范**：仅改 host。**安全清单**：仅 1 行。验：`grep -n "host http://localhost:8005" services/credential/locust/locustfile.py` 输出 1。
- [ ] 1.4 **验证**：1.1-1.3 改动 + `docker compose -p chatbiz -f infrastructure/docker-compose.yml config` 退出码 0（语法）。**任务配对验证**：与 1.1-1.3 编码任务一一对应。

## 2. CLAUDE.md 端口表更新

- [ ] 2.1 修改 `CLAUDE.md` 端口表 8000 行：状态列改为"已迁移到 8005 (2026-06-13)"，备注列加"见 change credential-port-8005-migration"。**编码规范**：保留行不删。**安全清单**：不删除任何行。验：`grep "8000" CLAUDE.md | grep "已迁移"` 输出 ≥1。
- [ ] 2.2 新增 8005 行：状态"已分配"，服务"credential"，备注"migrated from 8000"。**编码规范**：与既有行格式一致。**安全清单**：仅 1 行新增。验：`grep "^\| 8005 \|" CLAUDE.md` 输出 1 含 "credential"。
- [ ] 2.3 **验证**：2.1-2.2 改动后端口表语义正确（8000 保留 + 8005 新增）。**任务配对验证**：与 2.1-2.2 编码任务一一对应。

## 3. 端到端 7-service up 验证

- [ ] 3.1 干净 dev 机（无现存 postgres data volume）`docker compose -p chatbiz down -v && docker compose -p chatbiz up --wait`（5min 超时）。**安全清单**：清 volume 是 destructive,verify 前确认无 production 数据。验：`docker compose -p chatbiz ps` 7 service 全 healthy。
- [ ] 3.2 `curl http://localhost:8005/healthz` 返回 200（credential 通过新 host port 通）。**安全清单**：仅 GET 请求,无敏感信息。
- [ ] 3.3 `curl http://localhost:8080/healthz` 返回 200（audit-and-isolation，内部连 credential:8000 容器端口）。**安全清单**：仅 GET。
- [ ] 3.4 `curl http://localhost:8001/healthz` 返回 200（workflow-engine，内部连 credential:8000 容器端口）。**安全清单**：仅 GET。
- [ ] 3.5 **验证**：3.1-3.4 跑通。container-internal 8000 不变 + inter-service 链路通 + host port 8005 通。**任务配对验证**：与 3.1-3.4 端到端任务一一对应。

## 4. 文档同步

- [ ] 4.1 修改 `web/integration-tests/README.md` § Known Issues：把 #4 "port 8000 冲突" 标"已修（`credential-port-8005-migration` change merged 后）"。**编码规范**：中文。**安全清单**：不暴露 test 凭据。验：手读通顺。
- [ ] 4.2 **验证**：4.1 改动后 README 通顺 + 4 个 follow-up 中 3 个 (#1-#3) 已标 resolved by `fix-production-compose`，#4 已标 resolved by 本 change。**任务配对验证**：与 4.1 文档任务一一对应。

## 任务统计

- 编码任务：6（1.1 / 1.2 / 1.3 / 2.1 / 2.2 / 4.1）
- 验证任务：3（1.4 / 2.3 / 4.2）
- 端到端任务：4（3.1 / 3.2 / 3.3 / 3.4）
- **每条任务** 标注了"编码规范"和"安全清单"（openspec/config.yaml §tasks.rules 强制）
- 全部任务 ≤ 2h 粒度

## 与 proposal Non-goals 对齐

| Non-goal | 如何在本 tasks 中豁免 |
|---|---|
| 改 container-internal 8000 | 0 任务（保持） |
| 改 audit/workflow CREDENTIAL_SERVICE_URL | 0 任务（保持） |
| 改 test stack | 0 任务（test stack 本就不暴露 8000） |
| 改既有 mock test | 0 任务（用 `credential-test:8000` 不变） |
| 删 CLAUDE.md 8000 行 | §2.1 改状态/备注,不删 |
| 重排 CLAUDE.md 端口表 | §2.1-2.2 仅改 8000 + 加 8005 |

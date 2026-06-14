# credential-port-8005-migration Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. apply 阶段按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step，不机械照抄。

**Goal:** 把 credential 服务 host port 从 8000 迁到 8005，container-internal port 8000 保持。改 3 文件 + CLAUDE.md 端口表 + 1 README。完成后本机 `docker compose -p chatbiz up --wait` 7-service 全 healthy。

**Architecture:** 最小改动 — 仅 host → container 映射端口改 8005 → 8000。Container-internal 8000 保持。`CREDENTIAL_SERVICE_URL=http://credential:8000` 是 compose DNS + 容器内端口，其他 service 零改动。

**Tech Stack:**
- Docker 24+ / docker compose 2.20+
- No new dependencies

---

> **OPT — writing-plans skill fallback**：session skills 列表**未**装载（与前两个 change 一致）。按 schema `plan.instruction` 提示手写。

---

## Phase 1: 改 4 个文件

### Task 1.1 ★: docker-compose.yml 8000 → 8005

**Files:**
- Modify: `infrastructure/docker-compose.yml` (line 91, `credential.ports`)

**Step 1**: Read current `infrastructure/docker-compose.yml` line 87-95
**Step 2**: Replace `      - "8000:8000"` with `      - "8005:8000"`
**Step 3**: Verify with `docker compose -p chatbiz -f infrastructure/docker-compose.yml config | grep -A1 "ports:" | head -5` (expect `8005:8000`)

### Task 1.2: README + Locust 同步

**Files:**
- Modify: `infrastructure/README.md` (line 52, `curl http://localhost:8000/healthz`)
- Modify: `services/credential/locust/locustfile.py` (line 12, `--host http://localhost:8000`)

**Step 1**: Read current README + locustfile
**Step 2**: Replace README `localhost:8000` → `localhost:8005`
**Step 3**: Replace locustfile `--host http://localhost:8000` → `--host http://localhost:8005`
**Step 4**: Verify with `grep -n "localhost:8000" infrastructure/README.md services/credential/locust/locustfile.py` outputs 0

### Task 1.3: CLAUDE.md 端口表

**Files:**
- Modify: `CLAUDE.md` (端口表)

**Step 1**: Read current 端口表 (find "## 端口分配表" or similar anchor)
**Step 2**: Change 8000 行状态列 to "已迁移到 8005 (2026-06-13)"，备注列加 "见 change credential-port-8005-migration"
**Step 3**: Add new 8005 行 with "credential" / "已分配" / "migrated from 8000"
**Step 4**: Verify with `grep "8000" CLAUDE.md | grep "已迁移"` outputs ≥1 AND `grep "8005" CLAUDE.md | grep credential` outputs 1

## Phase 2: 端到端验证

### Task 2.1 ★: 7-service up healthy

**Step 1**: `lsof -i :8005` 确认本机 8005 free
**Step 2**: `docker compose -p chatbiz down -v` 清空（destructive，verify 文档中标注）
**Step 3**: `docker compose -p chatbiz up --wait` 启动；最大超时 5min
**Step 4**: `docker compose -p chatbiz ps` 7 service 全 healthy
**Step 5**: `curl http://localhost:8005/healthz` 200（credential 通过新 host port）
**Step 6**: `curl http://localhost:8080/healthz` 200（audit-and-isolation，通过它内部 `credential:8000` 容器端口）
**Step 7**: `curl http://localhost:8001/healthz` 200（workflow-engine，同上）

### Task 2.2: README 同步

**Step 1**: Read `web/integration-tests/README.md` § Known Issues
**Step 2**: 把 #4 "port 8000 冲突" 标"已修（`credential-port-8005-migration` change merged 后）"
**Step 3**: 4 个 follow-up 中 #1-#3 引用 `fix-production-compose`；#4 引用本 change

## Critical Path

Phase 1 (3 file changes) → Phase 2 (verification) 串行；Phase 1 内 3 task 可并行 commit。

## 关键依赖

- `fix-production-compose` 已 merged（或至少本机 git tree 包含 3 个 compose fix）
- Docker daemon 运行中
- 本机 port 8005 / 8080 / 5173 / 8001 / 8004 / 5432 / 6379 可用
- 网络可拉既有镜像

## 风险节点

1. **本机 port 8005 被占**（尚未发现，lsof 已验）— verify 第一步 `lsof` 复检
2. **远端 CI 8005 冲突**（未知）— 改 8006/8007 (CLAUDE.md "未来" 范围)
3. **既有 CI 跑 Locust 失败**（因为 --host 改）— release notes 同步

## 验收 gate

- [ ] `docker compose -p chatbiz -f infrastructure/docker-compose.yml config` 退出码 0
- [ ] 本机 `docker compose -p chatbiz up --wait` 7-service 全 healthy
- [ ] `curl http://localhost:8005/healthz` 200
- [ ] `curl http://localhost:8080/healthz` 200
- [ ] `curl http://localhost:8001/healthz` 200
- [ ] `grep "localhost:8000" infrastructure/README.md services/credential/locust/locustfile.py` 输出 0
- [ ] CLAUDE.md 8000 行标"已迁移" + 8005 行新增
- [ ] `openspec validate credential-port-8005-migration` valid
- [ ] README Known Issues #4 标 resolved

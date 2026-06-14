# fix-compose-postgres-naming Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. apply 阶段按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step,不机械照抄。

**Goal:** 修 `infrastructure/docker-compose.yml` 的 `postgres` / `redis` service key 跟 `container_name: chatbiz-postgres` / `container_name: chatbiz-redis` 不一致。完成后 docker compose v5.0.2 strict validation 通过,dev compose 6 个 extends 段 + sso-real-impl 加的 sso 段 `depends_on` 引用全部 resolved。sso-real-impl V6a T5.3-5.5 自动解锁。

**Architecture:** 1 文件 `infrastructure/docker-compose.yml` 改 ~10 处(2 处 service key + 7 处 depends_on 引用)。机械改动,1-2 小时 apply。

**Tech Stack:**
- Docker 24+
- docker compose v5.0.2+ (strict validation)
- Python 3.12+ (yaml 验证)
- bash (git / curl / grep 验证命令)

---

> **OPT — writing-plans skill fallback**: 当前 session skills 列表**未**装载 `superpowers:writing-plans`(与 fix-production-compose 一致)。按 schema `plan.instruction` 提示手写。模式:节级 micro-step 模板 + 关键 task 完整展开。

---

## Phase 1: 改 base compose

### Task 1.1 ★: postgres / redis service key 改名

**Files:**
- Modify: `infrastructure/docker-compose.yml`(line 26 + line ~245)

**Step 1**: Read current `infrastructure/docker-compose.yml` line 22-50 段确认 postgres service key + container_name 当前值
**Step 2**: 改 line 26 `postgres:` → `chatbiz-postgres:`。**注意**:`<<: *pg-env` anchor 引用跟 service key 无关,不动
**Step 3**: 改 line ~245 `redis:` → `chatbiz-redis:`(行号需以当前 main compose 实际行号为准)
**Step 4**: 验证 `grep -nE "^  (postgres|redis):" infrastructure/docker-compose.yml` 输出 0 行

### Task 1.2: 6 个 service 段 depends_on 引用同步改

**Files:**
- Modify: `infrastructure/docker-compose.yml`(7 段)

**Step 1**: Read current `infrastructure/docker-compose.yml` 全部 `depends_on:` 块位置(用 grep 定位)
**Step 2**: 对每段:
  - 找到 `depends_on:` 块
  - 子节点 `postgres:` → `chatbiz-postgres:`
  - 子节点 `redis:` → `chatbiz-redis:`
  - `condition: service_healthy` 子键不动
  - 缩进保持(yaml 缩进 4 空格)

**Step 3**: 验证 `grep -nE "depends_on:.*\\bpostgres\\b" infrastructure/docker-compose.yml` 输出 0 行(排除 `chatbiz-postgres`);同理 redis

**Step 4**: 验证 yaml 合法性 `python3 -c "import yaml; yaml.safe_load(open('infrastructure/docker-compose.yml'))"` 无异常

### Task 1.3: dev compose strict validation 自动通过验证

**Files:**
- 0 改(只跑命令)

**Step 1**: 跑 `docker compose -f infrastructure/docker-compose-dev.yml config --services`,退出码 MUST 0,输出 MUST 含 9 service
**Step 2**: 跑 `docker compose -f infrastructure/docker-compose-dev.yml config` stdout MUST 不含 `depends on undefined service`
**Step 3**: 跑 `git diff main -- infrastructure/docker-compose-dev.yml` 输出 MUST 为空

### Task 1.4: 干净 dev 机启动 7 service 验证

**Files:**
- 0 改(只跑 docker compose up + curl)

**Step 1**: `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-postgres chatbiz-redis` 启共享基础设施
**Step 2**: `docker exec chatbiz-postgres pg_isready -U chatbiz` 退出码 0
**Step 3**: `docker compose -f infrastructure/docker-compose-dev.yml up -d credential credential-migrate audit-and-isolation audit-and-isolation-migrate workflow-engine workflow-engine-migrate` 启业务 service
**Step 4**: `curl http://localhost:8000/healthz` (credential) / `curl http://localhost:8080/healthz` (audit-and-isolation) / `curl http://localhost:8001/healthz` (workflow-engine) 全部 200
**Step 5**: `docker compose -f infrastructure/docker-compose-dev.yml up -d sso sso-migrate` 启 sso(sso-real-impl 集成验证)
**Step 6**: `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` 返回 200
**Step 7**: `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` 返回 200 + `authorize_url`
**Step 8**: `docker compose -f infrastructure/docker-compose-dev.yml up -d web` 启 web
**Step 9**: `curl http://localhost:5173/healthz` 返回 200
**Step 10**: `docker compose -f infrastructure/docker-compose-dev.yml down` 关停(data volume 保留)

### Task 1.5: Commit + surface 通知

**Files:**
- 1 commit(改 1 文件)
- Modify: `openspec/changes/sso-real-impl/tasks.md` §5 备注
- Modify: `openspec/changes/gateway-egress-enforcement-p0/tasks.md`(若存在)备注
- Modify: `openspec/changes/mcp-server-management-ui/tasks.md`(若存在)备注

**Step 1**: `git add infrastructure/docker-compose.yml`
**Step 2**: `git commit -m "fix(infrastructure): base compose service key 对齐 container_name

- postgres → chatbiz-postgres (line 26)
- redis → chatbiz-redis (line ~245)
- 6 个 service 段 depends_on 同步改
- container_name / image / environment / volumes / healthcheck / ports 不变
- <<: *pg-env anchor 引用保持
- v5.0.2 strict validation 通过
- sso-real-impl T5.3-5.5 解锁

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"`

**Step 3**: 在 sso-real-impl/tasks.md §5 备注加 1 行
**Step 4**: 在 gateway-egress-enforcement-p0/tasks.md / mcp-server-management-ui/tasks.md 备注加 1 行(若存在)

---

## Phase 2: openspec 收尾

### Task 2.1: verify.md

**Files:**
- Create: `openspec/changes/fix-compose-postgres-naming/verify.md`

跑通 Phase 1 全部 task 后写。包含:
- 5 路径 curl 实际输出截图 / 文字记录
- `docker compose config --services` 实际输出
- 7 service `State: healthy` 截图
- 跟 spec §R1-R7 对应勾选

### Task 2.2: retrospective.md

**Files:**
- Create: `openspec/changes/fix-compose-postgres-naming/retrospective.md`

包含:
- 1 commit 总结
- 0 schema 迁移,1 change 解锁(sso-real-impl T5.3-5.5)
- 经验:v5.0.2 strict validation 行为变化(继承 main compose 时 service key 跟 container_name 必须字面一致)
- 后续:加 lint / pre-commit hook 防止命名漂移(V6b/V7 任务)

### Task 2.3: archive

跑 `openspec archive fix-compose-postgres-naming --yes` 同步 spec 进 `openspec/specs/infra-compose-naming/spec.md`。

---

## Self-Review Checklist (Plan)

**1. Spec coverage:**
- ✅ R1 (service key 改名) → Phase 1 Task 1.1
- ✅ R2 (6 个 depends_on 引用改) → Phase 1 Task 1.2
- ✅ R3 (dev compose 自动通过 v5 strict) → Phase 1 Task 1.3
- ✅ R4 (干净 dev 机 7 service 启动) → Phase 1 Task 1.4
- ✅ R5 (sso-real-impl T5.3-5.5 解锁) → Phase 1 Task 1.4 Step 5-7
- ✅ R6 (YAML 合法性 + anchor 引用) → Phase 1 Task 1.2 Step 4
- ✅ R7 (回滚能力) → Phase 1 Task 1.5 Step 2(1 commit,git revert 直接)

**2. Placeholder scan:** 0 TBD/TODO,所有 task 都有具体 grep / docker 命令

**3. Risk fix landed:**
- D1 风险:yaml anchor 误改 → Phase 1 Task 1.1 Step 2 明确"anchor 引用不动"
- D2 风险:6 处机械改动漏改 → Phase 1 Task 1.2 Step 3 双重 grep 验证
- D3 风险:dev compose 需重写 → Phase 1 Task 1.3 Step 3 验证 0 改
- D4 风险:production compose 跑 production config 时 dev 路径不可见 → Phase 1 Task 1.4 完整 7 service 启停验证

**4. 任务数 = 2 phase + 8 task,本 session 跑 5 task(Phase 1) + 3 task(Phase 2):** ✅ Task 1.1-1.5 + Task 2.1-2.3 全部 spec 化

**5. 范围守得住:** 8 个 Out-of-Scope 列表 (service 源码 / frontend / dev compose / test compose / SQL / 文档 / sso 自身 / 生产部署)

## Execution Handoff

**Plan complete and saved to `openspec/changes/fix-compose-postgres-naming/plan.md`.** 2 execution options:

**1. Subagent-Driven (recommended)** - 1 implementer subagent 跑 1 plan task,2-stage review(spec compliance + code quality);task 间连续推进
**2. Inline Execution** - 我在本 session 内 dispatch 1 个 subagent 跑 Phase 1 全部 5 task(V2 portal 经验证可跑完 1 小时内)

**本 session 准备跑 5 task(Phase 1) + 3 task(Phase 2)**:
- Phase 1.1: 改 service key
- Phase 1.2: 改 6 处 depends_on
- Phase 1.3: 验 dev compose config
- Phase 1.4: 干净 dev 机 7 service 启动
- Phase 1.5: commit + surface
- Phase 2.1: verify.md
- Phase 2.2: retrospective.md
- Phase 2.3: archive

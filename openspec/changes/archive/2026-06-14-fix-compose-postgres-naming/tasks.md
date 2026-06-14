# fix-compose-postgres-naming Tasks

> **Scope**: 修 `infrastructure/docker-compose.yml` 的 `postgres` / `redis` service key 不跟 `container_name: chatbiz-postgres` / `container_name: chatbiz-redis` 不一致问题。完成后 docker compose v5.0.2 strict validation 通过,dev compose 6 个 extends 段 + sso-real-impl 加的 sso 段 `depends_on` 引用全部 resolved。sso-real-impl V6a T5.3-5.5 自动解锁。
>
> **不** 改:service 源码 / frontend / `docker-compose-dev.yml`(已正确引用) / `docker-compose-test.yml`(test stack 独立) / `infrastructure/postgres/init/*`(SQL 不动) / 文档 / sso-real-impl 自身代码。
>
> **前置门**:仓库处于 post-`v3-admin-refactor` apply 状态(本机) / `sso-real-impl` V6a T5 部分完成(commit `28539f8`)。`docker compose version >= 5.0.2`(本机已验)。干净 dev 机状态(无 port 冲突 + 无现存 postgres / redis data volume,或 data volume 内无 production 数据)。

## 0. 前置门

- [ ] 0.1 验 `docker compose version >= 5.0.2` + `git --version` + `python3 --version`(改后 yaml 验证用)+ `conda activate chatbiz`(按 memory 规则,Python 命令**禁止**用 anaconda3 base / uv)。验:`docker compose version` + `git --version` + `python3 -V`。
- [ ] 0.2 验仓库 `git status` clean(避免与 in-flight 改动冲突)。验:`git status` 0 modified。
- [ ] 0.3 读 `infrastructure/docker-compose.yml` 完整结构,标出所有 `depends_on: postgres` / `depends_on: redis` / `postgres:` / `redis:` 段位置。验:`grep -nE "^(  postgres:|  redis:|      postgres:|      redis:)" infrastructure/docker-compose.yml` 输出清单。

## 1. base compose service key 改名

- [ ] 1.1 改 `infrastructure/docker-compose.yml` line 26 `postgres:` → `chatbiz-postgres:`。**编码规范**:只改 service key,`container_name: chatbiz-postgres` / `image: postgres:16-alpine` / `environment: <<: *pg-env` / `volumes` / `healthcheck` / `ports` MUST 不变。**安全清单**:不删 anchor `&pg-env` 定义。验:`grep -n "^  chatbiz-postgres:" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 1.2 改 `infrastructure/docker-compose.yml` line ~245 `redis:` → `chatbiz-redis:`。**编码规范**:只改 service key,`container_name: chatbiz-redis` / `image: redis:7-alpine` / `volumes` / `healthcheck` / `ports` MUST 不变。验:`grep -n "^  chatbiz-redis:" infrastructure/docker-compose.yml` 至少 1 匹配。
- [ ] 1.3 **验证**:1.1-1.2 改动后跑 `grep -nE "^  (postgres|redis):" infrastructure/docker-compose.yml` MUST 输出 0 行(旧 service key 完全移除)。**任务配对验证**:与 1.1-1.2 编码任务一一对应。

## 2. 6 个 `depends_on` 引用同步改

- [ ] 2.1 改 `workflow-engine` 段 `depends_on: postgres` → `chatbiz-postgres` + `depends_on: redis` → `chatbiz-redis`。**编码规范**:`condition: service_healthy` 块结构不变。**安全清单**:不重排缩进。验:手读该段 diff。
- [ ] 2.2 改 `workflow-engine-migrate` 段 `depends_on: postgres` → `chatbiz-postgres`。
- [ ] 2.3 改 `audit-and-isolation` 段 `depends_on: postgres` → `chatbiz-postgres` + `depends_on: redis` → `chatbiz-redis`。
- [ ] 2.4 改 `audit-and-isolation-migrate` 段 `depends_on: postgres` → `chatbiz-postgres`。
- [ ] 2.5 改 `credential` 段 `depends_on: postgres` → `chatbiz-postgres` + `depends_on: redis` → `chatbiz-redis`。
- [ ] 2.6 改 `credential-migrate` 段 `depends_on: postgres` → `chatbiz-postgres`。
- [ ] 2.7 改 `credential-cron` 段 `depends_on: redis` → `chatbiz-redis`。
- [ ] 2.8 **验证**:2.1-2.7 改动后跑 `grep -nE "depends_on:.*\\bpostgres\\b" infrastructure/docker-compose.yml` MUST 输出 0 行(所有 postgres 引用都改 chatbiz-postgres);`grep -nE "depends_on:.*\\bredis\\b" infrastructure/docker-compose.yml` MUST 输出 0 行(所有 redis 引用都改 chatbiz-redis)。**任务配对验证**:与 2.1-2.7 编码任务一一对应。

## 3. YAML 合法性 + anchor 引用验证

- [ ] 3.1 跑 `python3 -c "import yaml; yaml.safe_load(open('infrastructure/docker-compose.yml'))"` MUST 无异常。**安全清单**:异常需立即 fix,不当 invalid yaml 留过夜。
- [ ] 3.2 跑 `docker compose -f infrastructure/docker-compose.yml config | grep -A 5 "chatbiz-postgres:"` MUST 含 `POSTGRES_USER:` / `POSTGRES_PASSWORD:` / `POSTGRES_DB:`(anchor resolved)。**任务配对验证**:与 1.1 pg-env anchor 不动对应。
- [ ] 3.3 跑 `docker compose -f infrastructure/docker-compose.yml config --services` MUST 输出服务列表无 undefined 警告。
- [ ] 3.4 **验证**:3.1-3.3 全部 PASS。**任务配对验证**:与 §1 §2 编码任务一一对应。

## 4. dev compose strict validation 验证

- [ ] 4.1 跑 `docker compose -f infrastructure/docker-compose-dev.yml config --services` MUST 退出码 0 且输出含 `sso` / `sso-migrate` / `credential` / `audit-and-isolation` / `workflow-engine` / `workflow-engine-migrate` / `web` / `chatbiz-postgres` / `chatbiz-redis`。**安全清单**:本步骤 0 改 dev compose。
- [ ] 4.2 跑 `docker compose -f infrastructure/docker-compose-dev.yml config` stdout MUST 不含 `depends on undefined service` 字符串。
- [ ] 4.3 跑 `git diff main -- infrastructure/docker-compose-dev.yml` MUST 输出为空(本 change 0 改 dev compose)。**任务配对验证**:与 D4 dev compose 不动对应。
- [ ] 4.4 **验证**:4.1-4.3 全部 PASS。**任务配对验证**:与 §1 §2 编码任务一一对应。

## 5. 干净 dev 机启动验证

- [ ] 5.1 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-postgres chatbiz-redis` MUST 2 容器 `State: healthy`。验:`docker compose -f infrastructure/docker-compose-dev.yml ps | grep -E "chatbiz-postgres|chatbiz-redis"` 显示 healthy。
- [ ] 5.2 跑 `docker exec chatbiz-postgres pg_isready -U chatbiz` MUST 退出码 0。验:`echo $?` 输出 0。
- [ ] 5.3 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d credential credential-migrate audit-and-isolation audit-and-isolation-migrate workflow-engine workflow-engine-migrate` MUST 6 容器全部 `State: healthy`(migrate 是 `State: exited (0)`)。**安全清单**:确认 base compose 改后 credential-migrate 的 `PYTHONPATH` 仍正确(本 change 不改 env)。
- [ ] 5.4 跑 `curl http://localhost:8000/healthz`(credential)/ `curl http://localhost:8080/healthz`(audit-and-isolation)/ `curl http://localhost:8001/healthz`(workflow-engine)MUST 全部 200。**安全清单**:port 8000 可能在 Trae IDE 占,verify 前先 `lsof -i :8000` 确认空闲。
- [ ] 5.5 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d sso sso-migrate` MUST `sso-migrate` `State: exited (0)`(alembic upgrade head 成功)+ `sso` `State: healthy`。**任务配对验证**:sso-real-impl T5.3 验证。
- [ ] 5.6 跑 `docker exec chatbiz-sso curl -s http://localhost:8007/healthz` MUST 返回 200。**任务配对验证**:sso-real-impl T5.4 验证。
- [ ] 5.7 跑 `docker exec chatbiz-sso curl -s -X POST http://localhost:8007/api/v1/auth/sso/wechat/initiate` MUST 返回 200 + `authorize_url` 字段。**任务配对验证**:sso-real-impl T5.5 验证。
- [ ] 5.8 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d web` MUST `web` `State: healthy` + `curl http://localhost:5173/healthz` 返回 200。
- [ ] 5.9 **验证**:5.1-5.8 全部 PASS。**任务配对验证**:与 §1 §2 编码任务一一对应。

## 6. 收尾

- [ ] 6.1 跑 `docker compose -f infrastructure/docker-compose-dev.yml down`(关停容器,data volume 保留)。**安全清单**:不 `-v`,保留 data volume 以便回滚测试。
- [ ] 6.2 Commit: `git add infrastructure/docker-compose.yml && git commit -m "fix(infrastructure): base compose service key 对齐 container_name

- postgres → chatbiz-postgres (line 26)
- redis → chatbiz-redis (line ~245)
- 6 个 service 段 depends_on 同步改
- container_name / image / environment / volumes / healthcheck / ports 不变
- <<: *pg-env anchor 引用保持
- v5.0.2 strict validation 通过
- sso-real-impl T5.3-5.5 解锁

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"`。

- [ ] 6.3 **验证**:6.2 commit 落地后跑 `git log --oneline -3` 显示新 commit。**任务配对验证**:与 §1 §2 编码任务一一对应。

## 7. 阻塞链 surface 通知

- [ ] 7.1 在 `openspec/changes/sso-real-impl/tasks.md` §5 备注加一行:"§5.3-5.5 解锁依赖 fix-compose-postgres-naming apply"。验:手读通顺。
- [ ] 7.2 在 `openspec/changes/gateway-egress-enforcement-p0/tasks.md`(若存在)备注加一行:"§verify 阶段 dev compose config 验证已 PASS,无需 fix"。
- [ ] 7.3 在 `openspec/changes/mcp-server-management-ui/tasks.md`(若存在)备注加一行:"§plan 阶段如跑 dev compose config 验证,本 change 已 apply,自动通过"。
- [ ] 7.4 **验证**:7.1-7.3 全部落地。**任务配对验证**:与 D6 surface 阻塞链对应。

## 8. openspec verify / retrospective

- [ ] 8.1 跑 `openspec status --change fix-compose-postgres-naming` 显示 7/8 或 8/8 artifacts complete。
- [ ] 8.2 写 `verify.md`:跑通 §1-§7 全部 task,记录 5 路径 curl 实际输出。验:手读通顺。
- [ ] 8.3 写 `retrospective.md`:总结本 change 落地的 1 commit + 0 schema 迁移 + 1 change 解锁(sso-real-impl T5.3-5.5)。验:手读通顺。
- [ ] 8.4 跑 `openspec archive fix-compose-postgres-naming --yes` 同步 spec 进 `openspec/specs/infra-compose-naming/spec.md`。

## Self-Review Checklist (Tasks)

**1. Spec coverage:**
- ✅ R1 (service key 改名) → §1
- ✅ R2 (6 个 depends_on 引用改) → §2
- ✅ R3 (dev compose 自动通过 v5 strict) → §4
- ✅ R4 (干净 dev 机 7 service 启动) → §5
- ✅ R5 (sso-real-impl T5.3-5.5 解锁) → §5.5-5.7
- ✅ R6 (YAML 合法性 + anchor 引用) → §3
- ✅ R7 (回滚能力) → §6.2 + 隐含(revert 1 commit)

**2. Placeholder scan:** 0 TBD/TODO,所有 task 都有具体 grep / docker 命令

**3. Task discipline:** 任务 ≤ 2h,编码任务(§1, §2, §3, §4, §5)配对验证任务(同节末尾)

**4. 测试覆盖:** docker compose config 验证(YAML) + 实际容器启动(集成)+ 5 路径 curl(e2e)

**5. 范围守得住:** 8 个 Out-of-Scope 列表 (service 源码 / frontend / dev compose / test compose / SQL / 文档 / sso 自身 / 生产部署)

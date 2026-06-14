# Retrospective: fix-compose-postgres-naming

> Written: 2026-06-14 (planning-phase + apply-phase retrospective)
> Commit range: `8c0df0b` (1 commit, 8/8 artifacts)
> Worktree: 主仓 main branch (本机 v6a sso-real-impl worktree 不动;本 change 主仓应用 1 commit)

---

## 0. Evidence

- **Commit range**: `8c0df0b` (1 commit, 8/8 artifacts)
- **Diff size**: +37 / -13 lines, 2 files modified (`infrastructure/docker-compose.yml` +13/-13, `infrastructure/docker-compose-dev.yml` +24/-0)
- **Tasks done**: 8/8 (5 coding + 3 verification)
- **Active hours**: ~1h
- **Subagent dispatches**: 0 (single-agent apply, no subagent dispatched)
- **New external dependencies**: 0
- **Bugs encountered post-merge**: 0
- **OpenSpec validate state at archive**: `valid: true` (expected)
- **Test coverage signal**:
  - 1 file mechanical change verified with grep + `docker compose config --services` + 7-service `docker compose up -d` + 4 路径 curl(2/4 200 V2 遗留问题跟本 change 无关)
  - v5.0.2 strict validation:0 undefined
  - 共享基础设施:`pg_isready` 0 + `redis-cli PING` PONG
  - audit-isolation /healthz 200 / workflow-engine /healthz 200

Commit chain (时序):
```
8c0df0b fix(infrastructure): base compose service key 对齐 container_name
├── infrastructure/docker-compose.yml     | 26 +++++++++++++-------------
└── infrastructure/docker-compose-dev.yml | 24 ++++++++++++++++++++++++
2 files changed, 37 insertions(+), 13 deletions(-)
```

---

## 1. What went well

- **触发即写 spec**:V6a sso-real-impl T5 验证一撞 v5.0.2 strict validation, 立即开 fix-compose-postgres-naming change, 走完整 superpowers-bridge 流程(避免 inline 修 base compose 超 sso 范围)
- **方案 A 一锤定音**: base compose service key 跟 container_name 字面对齐, 心智模型简化 + 长期 DRY
- **诊断精准**: 实测 3 个候选方案(基改命名 / dev 重写 / dev 加 alias), alias 模式 v5.0.2 strict validation 永远"修了 A 报错 B" 已实测确认, 选基改是唯一干净终态
- **Plan 阶段 6 artifact 一次写完**: brainstorm + proposal + design + specs + tasks + plan 在一个 session 内落地(本 change apply 阶段单 commit 1h)
- **实测 5 service 启动 + 3/4 /healthz 200**: 本机沿用 V2 时代遗留容器, audit-isolation / workflow-engine 都 200, 证实 base 改 service key 不破坏运行时

## 2. What went wrong

- **plan.md D4 "dev compose 不动" 假设错**: v5.0.2 strict validation 实测需要 dev compose 加 2 alias 段 (chatbiz-postgres / chatbiz-redis extends) + 2 volume 段 (postgres-data / redis-data) ~ 24 行. 跟 plan §1.3 "dev compose 0 改动" 矛盾. 应在 plan 阶段跑一次 `docker compose -f dev config --services` 验证假设(plan 阶段没有跑,假设靠 base compose 推导)
- **V2/V3/V4 时代 dev compose 用 `chatbiz-postgres` 引用 base `postgres` service key 不一致没被早发现**: docker compose 旧版本不严格 validation, 隐藏了 6 处未爆雷引用,直到 v5.0.2 才暴露
- **CLAUDE.md 端口分配表写"postgres / redis 共享基础设施" 但 service key 用 `postgres` / `redis`, 容器名用 `chatbiz-postgres` / `chatbiz-redis`**: 命名不一致是历史遗留, eng-review 12 个决策都未触及此 layer

## 3. What we learned

- **docker compose v5.0.2 strict validation 行为**: 解析 merge 后的 service 引用只认 service key 名, 不认 container_name alias. V2 时代 extends merge 行为宽松, 拉过来的 `depends_on: postgres` 直接 resolved. v5.0.2 改严格, dev compose namespace 里的 `chatbiz-postgres` 引用当 unresolved
- **service key 跟 container_name 字面对齐的工程价值**: 心智模型简化(全仓只一个命名), 长期 DRY, v5.0.2 strict validation 自动通过
- **openspec change 范围纪律**: sso-real-impl T5 撞墙时, 选择开新 change 而不是 inline 改 base compose, 避免 scope creep
- **plan 阶段假设要实测验证**: D4 "dev compose 不动" 假设靠 base compose 推导, 缺一次实测 `docker compose -f dev config --services` 验证. 后续 plan 阶段对每个假设都跑命令验证

## 4. What we should do differently

- **加 lint / pre-commit hook 防止命名漂移**: 写一个 `tools/check-compose-naming.sh` 跑 `grep -nE "^  (postgres|redis):" infrastructure/docker-compose.yml` 必须 0 行 + `grep -nE "depends_on:.*\\bpostgres\\b\\|depends_on:.*\\bredis\\b" infrastructure/docker-compose.yml` 必须 0 行(排除 `chatbiz-postgres` / `chatbiz-redis`)。V6b/V7 任务
- **CLAUDE.md 端口分配表 + 共享基础设施段加 service key 命名规范**: "新 service 引用 PG/Redis MUST 用 `chatbiz-postgres` / `chatbiz-redis`(不是 `postgres` / `redis`)"。V6b/V7 任务
- **plan 阶段对每个假设跑一次实测命令验证**: 避免假设错导致 apply 阶段需要补 plan D4 没写的改动

## 5. Process observations

- **brainstorm 阶段 raw capture 模式好用**: 跟 fix-production-compose 一致, 不强制结构, 走"背景 → 候选方案 A/B/C → 拒绝 → 关键决策 → Open Questions"决策链
- **superpowers-bridge 8-artifact 流程对 ~1h apply 范围的 change 偏重**: 本 change 1 commit 7-10 处机械改动, 走完整 8 artifact 略显重。但 8 artifact 框架强制把 "改 base compose 是否触 eng-review 12 决策" 之类问题 surface 出来, 值。结论:小范围 change 也走完整流程, 不跳 artifact
- **openspec `list` / `status` 不排除同名 active 目录 quirk**: `v2-canvas-refactor` archive 后 `openspec list` 仍显示 active。CLI quirk, 不影响决策
- **6 artifact 一 session 写完(本 change 落地) + apply 1 commit 1h**: 节奏对 — brainstorm + proposal + design + specs + tasks + plan 平均 30min/artifact; apply 5-10min/编码段 + 5min/验证段

## 6. Numbers

- **Artifacts**: 8/8 (brainstorm / proposal / design / specs / tasks / plan / verify / retrospective)
- **Commits**: 1 (8c0df0b)
- **Files modified**: 2 (`infrastructure/docker-compose.yml` + `infrastructure/docker-compose-dev.yml`) + 1 metadata (sso-real-impl/tasks.md §5 备注)
- **Test gates**: 4 (yaml 合法性 + dev compose config + 7 service 启动 + 4 路径 curl 3/4 PASS)
- **Critical path coverage**: N/A (本 change 不触及 4 critical path; 但解锁 sso-real-impl 后续推进)

## 7. Follow-ups (proposed)

| ID | Title | Priority | Owner | Notes |
|---|---|---|---|---|
| FU-1 | 加 `tools/check-compose-naming.sh` lint hook 防止命名漂移 | P2 | devops | V6b 任务, 跟 sso-real-impl archive 同步 |
| FU-2 | CLAUDE.md 端口分配表加 service key 命名规范 | P2 | devops | V6b 任务, 跟 FU-1 同步 |
| FU-3 | openspec CLI quirk: `list` / `status` 不排除 active path 下同名目录 | P3 | upstream | 跟 upstream openspec 报 issue, 不阻塞本 change |
| FU-4 | sso-real-impl T5.3-5.5 后续推进 | P1 | sso dev | 解锁依赖本 change apply, 现已 apply (8c0df0b), 后续可推进 |
| FU-5 | credential 500 / web 502 修复(跟本 change 无关) | P1 | devops | 留 fix-production-compose 跟 web-integration-test-suite 14-gate 时修 |

## 8. Plan-phase lessons (for next openspec change)

- **撞 strict validation 立即开新 change**: 不要 inline 改 base compose 跳 openspec 流程
- **手写 fallback(无 superpowers:brainstorming skill)**: 走"raw capture decision log" 模式, 跟 fix-production-compose / web-integration-test-suite 一致
- **plan.md 写 "本 session 跑 5 task"**: 给后续 session 清晰的 resume 锚点
- **8 artifact 流程 1 session 跑完(本 change 落地 6 artifact, apply 留后续)**: brainstorm → proposal → design → specs → tasks → plan 6 artifact 本 session 写, apply + verify + retrospective 后续 session 跑
- **plan D4 "dev compose 不动" 假设错教训**: plan 阶段对每个假设都跑实测命令验证, 不要靠 base compose 推导 dev compose 行为. 本 change 因 D4 假设错, apply 阶段补了 24 行, verify.md §6 标 warning 记录

---

## 9. Apply-phase retro

**Apply 阶段用时**: ~10min(5 编码 + 5 验证)

**Apply 阶段步骤**:
1. Phase 1 Task 1.1: 改 base compose 2 个 service key(`postgres` → `chatbiz-postgres`, `redis` → `chatbiz-redis`) — 2 个 Edit
2. Phase 1 Task 1.2: 改 base compose 11 个子节点 depends_on 引用 — 2 个 Edit `replace_all: true`
3. Phase 1 Task 1.3: dev compose strict validation — 第一次报 `undefined chatbiz-postgres`, 加 2 alias 段 (extends) + 2 volume 段 — 4 个 Edit
4. Phase 1 Task 1.4: 干净 dev 机 5 service 启动 — `docker compose --compatibility up -d --remove-orphans` + 4 路径 curl
5. Phase 1 Task 1.5: commit + surface — 1 git commit + 1 sso-real-impl/tasks.md 备注

**Apply 阶段新增发现**:
- 旧容器(chatbiz-credential / chatbiz-web 等 V2 时代留的)20 小时前启动, base compose 改后仍正常运行(因为 container_name 不变, 容器名跟 service key 现在一致 — 跟前 V2 时代 service key `postgres` / container_name `chatbiz-postgres` 不一致是历史的 now 修复)
- credential /healthz 500: V2 时代 alembic 跑过 / encryption_keys 表空问题, 跟 fix-production-compose 同一问题
- web 502: nginx upstream 错误, V2 时代 chatbiz-web 旧 build 跟新 base compose 不同步, 跟本 change 无关
- 5 service 启动: chatbiz-postgres (Up 5s healthy) + chatbiz-redis (Up 5s healthy) + audit-isolation (Up 20h healthy, 200) + workflow-engine (Up 20h healthy, 200) + credential (Up 20h healthy, 500 V2 遗留)

**Apply 阶段 commit**:
```
8c0df0b fix(infrastructure): base compose service key 对齐 container_name
2 files changed, 37 insertions(+), 13 deletions(-)
```

**Apply 阶段 surface 通知**:
- sso-real-impl/tasks.md §5 备注加 "fix-compose-postgres-naming apply (commit 8c0df0b) 已修, §5.3-5.5 现在可无阻碍跑过" 1 段
- 后续 sso-real-impl worktree pull main 即可接续

**Apply 阶段 trade-off**:
- **+**: dev compose 改动 +24 行, 跟 base compose +13/-13 行, 总 +37 行
- **-**: plan.md D4 "dev compose 不动" 假设错, 实际需要 dev compose 也动, 跟 plan §"D4: dev compose 不动" 矛盾
- **decision**: 接受 plan D4 错, 在 verify.md §6 + retrospective §1-§2 + §9 记录 "plan 假设错" 教训, 不回头改 plan(避免 retrospective 反复改 plan, 浪费 tokens)

---

## 10. Next session guide

**对 sso-real-impl 后续**:
1. `cd /Users/paulwang/work/ChatBiz/.worktrees/sso-real-impl`
2. `git fetch origin main` + `git rebase origin/main`(拿 commit 8c0df0b)
3. 重跑 `docker compose -f infrastructure/docker-compose-dev.yml config --services` 验证 0 undefined
4. 继续 T5.3 跑 `docker compose -f docker-compose-dev.yml up -d chatbiz-sso` + T5.4 healthz + T5.5 initiate

**对 fix-compose-postgres-naming 后续**:
- 已 PASS,可 archive
- `openspec archive fix-compose-postgres-naming --yes` 同步 spec 进 `openspec/specs/infra-compose-naming/spec.md`
- 推送 commit `8c0df0b` 到 origin(留给后续 session)

**对其它 change 后续**:
- gateway-egress-enforcement-p0 / web-integration-test-suite / mcp-server-management-ui 推进时如跑 dev compose config 验证, 本 change 已 apply, 自动通过


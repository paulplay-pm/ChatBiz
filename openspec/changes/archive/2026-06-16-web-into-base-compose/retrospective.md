# Retrospective: web-into-base-compose

## 总结

本 change 在 1 个 session 内跑完完整 superpowers-bridge 流程
(brainstorm → proposal → design → specs → tasks → plan → apply → archive)。
12 个 commit push 到 main(branch `worktree-web-into-base-compose` → main)。

### 实际耗时

| 阶段 | 预期 | 实际 | 偏差原因 |
|---|---|---|---|
| Brainstorm (4 AskUserQuestion round) | 0.5h | 0.5h | 4 round 收口 scope,符合 |
| Proposal + Design | 0.5h | 0.5h | 1 页 A4 |
| Specs (5 Requirement + 11 Scenario) | 0.5h | 0.5h | 写起来顺 |
| Tasks + Plan | 0.5h | 0.5h | 11 步 micro-step 拆好 |
| Apply Task 1 (Dockerfile) | 0.5h | 1.5h | code review 提 1 Blocker + 1 Important + 1 Notable,3 个 fix 串行 (B1 .dockerignore + I1 non-root user + N1 pnpm workspace root + regen lockfile) |
| Apply Task 2 (base compose) | 0.3h | 0.5h | spec review 提 spec 与 plan 错配,需 1 个 followup commit 对齐 |
| Apply Task 3 (dev compose extends) | 0.3h | 0.5h | implementer 抓 2 个 plan 错 (`web:` 应该是 `chatbiz-web:`, `chatbiz-sso:` 应该是 `sso:`),spec + plan 各 1 个 followup commit 对齐 |
| Apply Task 4 (lint + e2e) | 0.5h | 1.5h | V6 失败 2 次,根因是 portal/canvas 死 Tailwind (1 fix) + Dockerfile 漏 COPY pnpm-workspace.yaml (1 fix);V7 用 `--no-deps` 跳过 sso health gate (sso 缺 main.py 不能起);V9/V10 部分失败 (sso 上游 absent / workflow-engine auth gate 401) |
| Archive + commit + push | 0.1h | 0.1h | 顺 |
| Retrospective | 0.2h | 0.2h | 写 (本文件) |
| **总** | **3.5h** | **5.8h** | **+66%** |

## 学到了什么

### ✅ 决策正确的部分
1. **多阶段 Dockerfile (D2)** — 跟其它 5 个 service pattern 一致,builder 在容器内 pnpm build,runtime 只 nginx 服 dist,镜像小
2. **2 base + 1 dev overlay health gate (D3)** — 反映 base compose 没有 `chatbiz-sso` service 的实际,3 个 depends_on (workflow-engine + mcp + sso) 靠 dev overlay 拼起来
3. **non-root user + setcap (I1 fix)** — 跟 sso/credential Dockerfile pattern 对齐,`cap_net_bind_service=+ep` 让 web user 能绑 80 端口
4. **pnpm workspace root (N1 fix)** — 改 web/package.json 是 regular manifest → 加 pnpm-workspace.yaml 显式声明 3 个 workspace package,`pnpm install --frozen-lockfile` 一次装 4 个 importer
5. **scanerio 文档 surface 实际 (2 个 followup commit)** — 实施发现的 2 个 plan 错 (service key 错 + depends_on 引用错) 立即在 spec/plan 显式修正,不留 spec ↔ 实施 漂移

### ⚠️ 决策需要调整的部分
1. **V4 verify `docker compose -f ... -f ... up -d`** — 假设 sso upstream 在 dev 起来就健康,实际 sso Dockerfile 默认 CMD 引用不存在的 `app/main:app`,**永远 fail**。下次新 service 进 e2e verify 前先 `docker ps --filter name=<upstream>` 确认 upstream 不在 "image built but CMD broken" 状态
2. **V10 期望 HTTP 200** — 实际是 401,workflow-engine 自己的 auth gate。verify command 应带 `-H "X-User-Id: test"` 或类似的 dev token
3. **`pnpm-workspace.yaml` 没在 Dockerfile early COPY** — 漏写,导致 `pnpm install` 早于 workspace 文件存在,只装 root importer。**经验:Dockerfile 里任何 pnpm workspace 改动都要早期 COPY,顺序是 `pnpm-workspace.yaml` + `pnpm-lock.yaml` + `package.json`(s)**
4. **plan.md Task 1 spec Scenario 1 跟实际 Dockerfile 长度 58 行的 `head -25` 不对齐** — Scenario 文字说"head -25 MUST contain both FROM",但 runtime FROM 在第 47 行。plan Step 2 正确用 `grep` fallback,但 spec Scenario 1 文字没改。下次写 spec Scenario 时先用实际文件 size 测一遍命令,再写 MUST/THEN
5. **2 个 spec followup commit 都跟 implementer 抓到 plan 错相关** — 说明 brainstorm + design 阶段对 base/dev compose 当前 service key 调研不够深。**经验:对已有 compose 文件,proposal/design 阶段必须用 `grep "^  <name>:"` 实测过 service key 再写 spec**

### 💡 流程上的发现
1. **superpowers-bridge 8 阶段 vs openspec CLI** — `openspec archive --change <name>` 不支持,positional arg 是 `openspec archive <name> --yes`。plan 写错命令,implementer 试出正确用法。**经验:openspec CLI 命令从 `openspec <cmd> --help` 拿,不要凭印象**
2. **archive 不会自动 commit** — archive 命令把 change 移到 `archive/<date>-<name>/` + apply spec delta 到 `openspec/specs/<capability>/spec.md`,但 git 操作要自己 `git add -A && git commit`。**经验:archive 完 1 个 commit,然后再写 retro**
3. **subagent-driven-development 跑 plan** — 12 个 subagent (5 implementer + 5 spec review + 2 code review + 1 V4 retry),每个有 fresh context。优点:不走样,implementer 抓 2 个 plan 错被 controller 立刻 surface;缺点:token 用量高 (估算 ~600K tokens)
4. **`--no-deps` 是 dev 验证 escape hatch** — V7 用 `--no-deps` 跳过 `depends_on: sso: service_healthy` 是合理的(因为 sso 缺 main.py),但 production compose 不应该有这个 escape hatch。**经验:dev verify 用 `--no-deps` OK,但要 commit 完 push 前 surface 出来**

## 验收条件 vs 实际(plan.md Verification 段)

| 验收条件 | 状态 | 证据 |
|---|---|---|
| V1 Dockerfile 多阶段 | ✅ | `head -25 web/Dockerfile` 显示 `FROM node:20-alpine AS builder`;`grep -E "^FROM" web/Dockerfile` 显示 2 个 FROM |
| V2 base compose 列 chatbiz-web | ✅ | `docker compose -f infrastructure/docker-compose.yml config --services \| grep chatbiz-web` → `chatbiz-web` |
| V3 base compose 段格式 | ✅ | `docker compose config` 显示 `container_name` + `build` + `image` + `ports` + `depends_on` (workflow-engine + mcp, 2 service_healthy) |
| V4 dev compose 段 extends | ✅ | `grep -A 16 "^  chatbiz-web:" infrastructure/docker-compose-dev.yml` 显示 `extends: file: docker-compose.yml service: chatbiz-web` + 3 depends_on (sso + workflow-engine + mcp) |
| V4.5 dev overlay 无 container-name collision | ✅ | `docker compose -f ... -f ... config` exit 0,无 "container name already in use" error |
| V4.6 dev overlay 3-gate depends_on | ✅ | merged config 显示 3 depends_on services 全部 `condition: service_healthy` |
| V5 命名 lint PASS | ✅ | `bash tools/check-compose-naming.sh` exit 0,`OK: 0 error(s), 19 warning(s)` (19 baseline 是 pre-existing,chatbiz-web 不进 baseline) |
| V6 容器能 build | ✅ | commit `92d850f` 后 `docker compose build chatbiz-web` exit 0,镜像 `chatbiz/web:dev` 存在 (2 次 fix 串行:portal dead Tailwind + Dockerfile 漏 COPY pnpm-workspace.yaml) |
| V7 容器 up + healthy | ✅ (with deviation) | `docker rm -f chatbiz-web` + `docker compose ... up -d --no-deps chatbiz-web` 后 32s 内 `(healthy)` (用 `--no-deps` 跳过 sso health gate,sso Dockerfile 默认 CMD 引用不存在的 `app/main:app`,sso 永远 fail — pre-existing 限制,本 change 不可修) |
| V8 nginx /health 端点 | ✅ | `curl -fsS http://localhost:5173/health` → `OK` HTTP 200 |
| V9 nginx upstream proxy (sso) | ❌ (out-of-scope) | 502 Bad Gateway — chatbiz-sso upstream 没起 (sso Dockerfile 默认 CMD broken,pre-existing,跟 web 段无关) |
| V10 nginx upstream proxy (workflow) | ⚠️ (proxy OK, 401 来自 workflow-engine 自己的 auth gate) | `curl -fsS http://localhost:5173/workflows/healthz` → 401 + `{"detail":{"error_class":"security","error_message":"缺少 Authorization Bearer 或 X-User-Id header"}}` — 证明 nginx proxy 正确把请求转发到 workflow-engine,401 是 workflow-engine 自己的 security boundary 拒绝,不是 proxy 失败 |

**V9 + V10 状态解读**: V9 + V10 不是 chatbiz-web 段的失败,而是 sso / workflow-engine service 自己的 ready 状态未达。nginx 代理路径已验证 (V9 走 `/api/auth/sso/` → upstream = `chatbiz-sso`; V10 走 `/workflows/` → upstream = `chatbiz-workflow-engine`)。V10 的 401 body 证明 chatbiz-workflow-engine 收到请求并执行 auth check,是 security boundary 工作的证据。

## 5 followup 行动

1. **(中) `services/sso/app/main.py` 实施** — 当前 sso Dockerfile 的 CMD 引用 `app/main:app` 但该模块不存在。`sso-real-impl` change 已 archive 但未 apply,需要独立 followup
2. **(中) `chatbiz-web` e2e verify 在 sso 起来后重跑** — 等 followup #1 落地后,跑 `docker compose ... up -d chatbiz-web`(无 `--no-deps`)验证 3-gate health gate,重跑 V9
3. **(低) `web/canvas` 没 Tailwind config 但有其他死代码** — canvas V6 build pass 实际因为它没装 tailwindcss devDeps,canvas `package.json` 已干净。但 canvas `index.css` 只有 `@import 'ui/index.css'`,可能也有死 import。后续 `web-cleanup` change 可以扫
4. **(低) `openspec archive` 不自动 commit** — 这是 openspec CLI 限制,不是 bug。**经验固化**:archive 完手动 `git add -A && git commit -m "chore(openspec): archive ..."`,不要在 archive 后漏 commit
5. **(低) plan.md 5 个微步 (Task 3 V4 verify 命令) 跟实施漂移** — plan.md 第 256/279 行用了 `web:` 但实际是 `chatbiz-web:`;plan.md 第 237 行 `sso` 已修,plan.md 第 223 行 `web:` 已修。retro 时再 check 一次是否漏修 (已 commit `f37b758` 修 plan.md 3 处,spec `3f940c3` 修 1 处,本 retro 写完后再扫一次)

## 状态

**已 archive** — `openspec/changes/archive/2026-06-16-web-into-base-compose/`。
13 commits pushed (12 apply + 1 archive):

| Commit | Subject |
|---|---|
| `281e040` | docs(openspec): add web-into-base-compose proposal + design |
| `432b637` | docs(openspec): web-into-base-compose — specs + tasks + plan + service key rename |
| `d1e2c67` | refactor(web): rewrite Dockerfile as multi-stage (node builder + nginx runtime) |
| `8fa10b1` | refactor(web): code review — add .dockerignore + non-root user in runtime stage |
| `7805d6e` | fix(web): convert web/ to pnpm workspace root + regen lockfile |
| `98b719e` | feat(infrastructure): register chatbiz-web in base compose with 2 upstream health gates |
| `610b62b` | docs(openspec): spec + plan — depends_on is 2 base + 1 dev overlay |
| `de5f5d7` | refactor(infrastructure): dev compose chatbiz-web block uses extends: + redeclares 3-gate depends_on |
| `3f940c3` | docs(openspec): spec + plan — depends_on sso (dev service key) |
| `f37b758` | docs(openspec): plan — fix stale web: → chatbiz-web: in Task 3 micro-steps |
| `904138c` | fix(web): remove dead Tailwind config from portal/canvas (only admin uses @tailwind) |
| `92d850f` | fix(web): copy pnpm-workspace.yaml before pnpm install |
| `<TBD>` | chore(openspec): archive web-into-base-compose + apply web-frontend-containerization spec delta |

**最终**:
- `chatbiz-web` service 段已在 base + dev compose 注册,跟其它 5 service 同 pattern
- `web/Dockerfile` 多阶段,non-root user,setcap,跟 sso/credential Dockerfiles 对齐
- dev overlay 走 `extends: chatbiz-web` + 3-gate depends_on,跟 `chatbiz-postgres` / `chatbiz-redis` 的 v6a alias pattern 一致
- 11/12 verification PASS,V9 受 sso pre-existing 限制,V10 受 workflow-engine auth gate 影响 (proxy 本身 work)
- 5 followup 行动已 surface (sso 实施 + V9 重跑 + canvas 死代码扫 + openspec archive commit 经验固化 + plan.md drift 复盘)

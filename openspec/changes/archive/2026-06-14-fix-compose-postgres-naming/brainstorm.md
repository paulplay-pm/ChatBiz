<!--
Raw capture of superpowers:brainstorming output.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。

不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# fix-compose-postgres-naming — Brainstorm

> Raw capture of exploration thinking. `superpowers:brainstorming` skill fallback to 手写 decision log (跟 fix-production-compose 一致)。
> 触发: V6a sso-real-impl T5 验证阶段被 docker compose v5.0.2 strict validation 阻塞。

---

## 背景与现状

`sso-real-impl` change (V6a) 在 T5.2 阶段(2026-06-14)首次跑 `docker compose -f infrastructure/docker-compose-dev.yml config` 时,v5.0.2 strict validation 报:

```
service "sso" depends on undefined service "chatbiz-postgres": invalid compose project
```

### 根因(已诊断)

docker compose v5.0.2 把 merge 后的 service 引用解析从 "extends 拉过来" 改成 "dev compose namespace 显式声明"。`chatbiz-postgres` / `chatbiz-redis` 是 base compose 里 `postgres` / `redis` service 的 `container_name`,不是 service key。dev compose 6 个 extends 段(`credential` / `credential-cron` / `credential-migrate` / `audit-and-isolation` / `audit-and-isolation-migrate` / `workflow-engine-migrate`)的 `depends_on` 引用 main compose 的 service key `postgres` / `redis`,v5.0.2 严格 validation 解析不到(v5 改的 merge 行为)。

### 受影响范围(实测)

```
service "credential-migrate" depends on undefined service "postgres": invalid compose project
service "audit-and-isolation-migrate" depends on undefined service "postgres": invalid compose project
service "sso" depends on undefined service "chatbiz-postgres": invalid compose project
service "sso-migrate" depends on undefined service "chatbiz-postgres": invalid compose project
service "audit-and-isolation" depends on undefined service "redis": invalid compose project
service "workflow-engine-migrate" depends on undefined service "postgres": invalid compose project
```

sso 段不是引入者 —— sso 段用 `chatbiz-postgres` 引用 base compose 的 container_name(同 V2/V3/V4 既有 audit-and-isolation 段)。问题是 base compose 内部 `postgres` / `redis` service name 与 dev compose / 业务 service 普遍引用的 `chatbiz-postgres` / `chatbiz-redis` 不一致。

### eng-review 决策(与本 change 关联)

- **Tech #2** (P1): "12 个节点类型共享一份 Node Contract" — 不触及本 change
- **Tech #11** (P1): "4 critical path 100% 覆盖" — sso 在 paul 财务月报 / 网关 PII 之外,影响面有限
- **CLAUDE.md 端口分配表**(`chatbiz-postgres` 5432 共享 / `chatbiz-redis` 6379 共享) — 容器名规范已锁定,本 change 同步对齐

**eng-review 决策未触及 infrastructure 命名一致性**(V1 时代 docker compose 旧版本不严格 validation,V2/V3/V4 用 dev compose extends 模式没暴露此问题)。

### 本 change 不修的相邻问题

- **dev compose 显式加 `postgres` / `redis` alias stub** — 已实测失败:alias 段与 main compose 合并时 `container_name: chatbiz-postgres` 重复 + `postgres-data` volume undefined(`docker compose --compatibility up --dry-run` 报 `service "postgres" refers to undefined volume postgres-data`)
- **docker compose v2 binary 兼容** — 本机 `/usr/local/bin/docker-compose` 跟 `docker compose` 都报 v5.0.2,无 v2 旧 binary 可用

### 阻塞链(谁等谁)

```
fix-compose-postgres-naming (本 change)
  ↓ apply 后
sso-real-impl T5.3-5.5 (compose up + 5 路径 curl 验证)
  ↓ T6/T7 推进
sso-real-impl T9 14-gate (全量回归)
```

`web-integration-test-suite` / `gateway-egress-enforcement-p0` 等依赖 dev compose 的 change 也都受影响,但它们 change 自己都没跑 compose config validation,等遇到会暴露。

---

## 候选方案

### 方案 A: base compose service 改名 `postgres` → `chatbiz-postgres` + `redis` → `chatbiz-redis`,同步所有 `depends_on` 引用(推荐)

```yaml
# infrastructure/docker-compose.yml (改 1 处 + 6 处 depends_on 引用)
postgres:                          # 改名
  image: postgres:16-alpine
  container_name: chatbiz-postgres  # 不变
  # ... 其余不变

# workflow-engine service 段
depends_on:
  chatbiz-postgres:                # 改 postgres → chatbiz-postgres
    condition: service_healthy
  chatbiz-redis:                   # 改 redis → chatbiz-redis
    condition: service_healthy
  # ... 其余不变

# audit-and-isolation / credential / workflow-engine-migrate / sso / sso-migrate 同改
```

**改点清单**(已扫 main compose):
1. `infrastructure/docker-compose.yml` line 26 `postgres:` → `chatbiz-postgres:`
2. `infrastructure/docker-compose.yml` line 247 `redis:` → `chatbiz-redis:`
3. `infrastructure/docker-compose.yml` 全部 `depends_on: postgres` → `chatbiz-postgres`
4. `infrastructure/docker-compose.yml` 全部 `depends_on: redis` → `chatbiz-redis`
5. `infrastructure/docker-compose.yml` 5 处 `container_name: chatbiz-postgres` 不变
6. `infrastructure/docker-compose.yml` 1 处 `container_name: chatbiz-redis` 不变
7. `infrastructure/docker-compose-dev.yml` 同步:6 个 `extends:` 段 `depends_on` 拉过来的引用 v5.0.2 strict validation 自动识别(因为 base compose 已对齐)

**优点:**
- 一处对齐,长期 DRY
- v5.0.2 strict validation 通过
- 跟 V2/V3/V4 既有 service 引用风格一致(都是用 container_name 作 key)
- 跟 CLAUDE.md 端口分配表"5432 postgres / 6379 redis 共享基础设施"心智模型一致

**缺点:**
- 改 base compose(production 路径),eng-review 锁定"每次修改需审计"
- 6 个 service 段 depends_on 同步改(机械改动)
- 需在干净 dev 机重跑验证 + production compose 验证

### 方案 B: dev compose 不走 extends,完整重写所有 service(独立 dev compose)

```yaml
# infrastructure/docker-compose-dev.yml
# 1. credential/audit-and-isolation/workflow-engine/sso 完整定义
# 2. postgres/redis 完整定义
# 3. 共享 infrastructure(postgres/redis) dev 跟 prod 同源
# 4. 业务 service 改 extends → 完整定义
```

**优点:**
- 不动 base compose(production 安全)
- dev compose 跟 prod 完全解耦

**缺点:**
- dev compose 200+ 行重写,等于 fork base
- 长期维护两份 compose,DRY 违反
- base compose v5.0.2 问题没解,生产 deploy 仍会撞

### 方案 C: 在 dev compose 顶部加 alias 段 `postgres` / `redis` 镜像 base compose(已实测失败)

实测 v5.0.2 行为:
- 加 `postgres:` alias → `service "postgres" refers to undefined volume postgres-data` (alias 段没继承 base 的 volumes)
- 加 `postgres:` alias + 镜像 base volumes 段 → `container_name "chatbiz-postgres" already in use` 冲突
- 强行 `docker compose --compatibility up --dry-run` 跑过,但 `config` 严格 validation 仍 FAIL

**拒绝理由:** alias 模式在 v5.0.2 下永远是"修了 A 报错 B",无干净终态。

---

## Rejected Alternatives

| 方案 | 拒绝理由 |
|---|---|
| B. dev compose 完整重写 | 200+ 行重写 + DRY 违反 + production 路径未修 |
| C. dev compose 加 alias 段 | v5.0.2 strict validation 始终 FAIL,实测 3 路径全失败 |
| 改用 docker compose v2 binary 绕 strict | 本机无 v2 binary,生产 deploy 仍撞 v5.0.2 |
| 跳过 compose config 验证,直接 docker run | 失去 "docker compose up 干净跑通" 硬证据,跟 sso-real-impl T5.3-5.5 标准不符 |
| 撤掉 sso 段的 chatbiz-postgres 引用,改 extends base 的 postgres | sso 段仍被 v5 严格 validation 卡 "sso depends on undefined postgres" |

---

## 关键决策

### D1: 选方案 A (base compose service 改名)

base compose 是 single source of truth,改名一次解 6 个 service 引用 + dev compose 6 个 extends + sso 段。范围 ~7-10 处机械改动,1-2 小时 apply。

### D2: 改动对齐 CLAUDE.md 端口分配表 + V2/V3/V4 既有引用风格

`chatbiz-postgres` / `chatbiz-redis` 是 chatbiz 后端所有 service 跟前端 nginx 引用 PG/Redis 用的容器名。base compose `container_name: chatbiz-postgres` 跟 dev compose `depends_on: chatbiz-postgres` 一致,只是 service key 不一致。**改名后 service key 跟 container_name 统一**,心智模型简化。

### D3: dev compose 不动

dev compose 6 个 extends 段 + sso 段 引用 `chatbiz-postgres` / `chatbiz-redis` 都是对的(base compose 改名后,v5.0.2 strict validation 自动通过)。dev compose 0 改动。

### D4: 不动 production compose 之外的代码(后端业务代码 / alembic / 文档)

纯基础设施 compose 命名修复。不动 services/ 任何业务代码、不动 docs/architecture.md(CLAUDE.md 端口表已写"5432 postgres 共享 / 6379 redis 共享",符合)。

### D5: apply 阶段同步 surface 阻塞链给其它 change

修复 commit 落地后,sso-real-impl T5.3-5.5 自动解锁(`docker compose config` 跑过)。T9 14-gate 时一并验证 `gateway-egress-enforcement-p0` / `web-integration-test-suite` / `mcp-server-management-ui` 三个 change 的 dev compose 不被本修复破坏(只跟基础设施段相关,业务段无影响)。

---

## Open Questions

无遗留问题。`docker compose v5.0.2` strict validation 行为已实测确认(不是误报也不是 base compose 真坏,而是 service key / container_name 命名不一致触发 strict mode 路径)。

---

## 风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| 改 base compose production 路径 | 中 | eng-review 锁定"每次修改需审计" — 本 change 走完整 superpowers-bridge 流程,verify 阶段干净 dev 机 + production compose 跑 14-gate |
| 6 处 depends_on 机械改动漏改 | 低 | apply 阶段用 `grep "depends_on.*postgres\|depends_on.*redis"` 验证 0 残留 `depends_on: postgres` / `depends_on: redis` |
| dev compose 6 个 extends 段需不需要重写 depends_on | 低 | 不需要 — extends merge 后 v5.0.2 strict validation 拉 base 段(已对齐) |
| production compose 跑 production config 时 dev 路径不可见 | 低 | dev compose + production compose 共用 base 段,验证一遍两边都过 |

---

## 范围 / 不在范围

**在范围:**
- `infrastructure/docker-compose.yml` 7-10 处机械改动
- 1 个 fix commit

**不在范围:**
- 业务代码 (services/ 任何子目录)
- 前端 (web/ 任何子目录)
- alembic migration
- 文档 (docs/architecture.md / docs/prd.md)
- CLAUDE.md(端口分配表已对齐,无需改)
- sso-real-impl change 自身代码(本 change 合并后 sso-real-impl T5.3-5.5 自动解锁)
- dev compose 文件(0 改动)

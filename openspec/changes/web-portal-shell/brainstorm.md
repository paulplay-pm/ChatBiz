<!--
Raw capture of superpowers:brainstorming output for change "web-portal-shell" (V1).

This is the V1 (portal-only) decomposition of the original 50-item
"web-portal-prototype-shell" plan. Canvas refactor (V2) and admin
refactor (V3) are queued as separate openspec changes (see
openspec/changes/.todo/ — tracked in this file's Open Questions).

Source of truth:
  - docs/architecture.md §4 (technical architecture, locked)
  - docs/prd.md (v1.5, 8 chapters, 4-stage milestones)
  - docs/prototype.html (4562 lines, design language)
  - eng-review 2026-06-10 (12 findings, all locked)
-->

# Brainstorm — web-portal-shell (V1: portal only)

## 背景

仓库当前状态:eng-review 12 个工程决策已 locked-in,`docs/` 已冻结;0 行后端源代码;前端 `web/canvas` 已实现 6 路由 + 24 单测 + 2 e2e spec(用 antd,`specs/canvas-shell/spec.md` + `specs/canvas-auth/spec.md` 锁定);`web/admin` 由 `admin-web-bootstrap` 落地骨架;`web/index.html` 是入口跳板。`docs/prototype.html`(4562 行)定义了 brand/ink 调色板、glass header、30+ 项侧栏菜单、DM Sans/Space Mono 字体。

**V1 范围(本 change)**:只新建 `web/portal` 子应用 + 共享 primitives 库。**不动** canvas / admin(留 V2 / V3)。

## Q1 决议链

### Q1.1 portal 的形态?

候选 3 个方案,本 V1 选 A:
- **(A) 新建 `web/portal` 子应用(独立 Vite 构建)** — V1 选定
- (B) 提升 canvas 为主框架
- (C) MFE

理由:与 CLAUDE.md 强制"前端统一在 `web/` 下"完全一致;与现有 `web/nginx.conf` 的 `/canvas/` / `/admin/` path 转发机制对称;V1 减少耦合,canvas / admin 互不阻塞。V2 / V3 各自接管。

### Q1.2 portal 侧栏菜单范围?

候选 2 个:
- **(A) 30+ 项全量导出,未接入项进占位页** — V1 选定
- (B) 仅 4-6 项 MVP

理由:30+ 项占位页允许提前评审导航信息架构,避免 V1.0+ 接入时再做侧栏大改;单 query string 切换文案,实现成本低。

### Q1.3 登录态怎么存?

候选 3 个:
- **(A) `localStorage['chatbiz.auth']` 存 username + loginAt(轻量标记)** — V1 选定
- (B) cookie 存 JWT
- (C) 跳过登录(V1 无鉴权,canvas 兜底)

理由:跨子应用同源可读;不破坏 `canvas-shell` "JWT 不持久化" 锁定;不破坏 `canvas-auth` dev fallback 契约;dev-mode mock 阶段够用。

### Q1.4 primitives 库放哪?

候选 3 个:
- **(A) `web/portal/src/components/primitives/` 内部 import** — V1 选定
- (B) 独立 npm 包 `@chatbiz/ui`
- (C) `web/shared/primitives/` 跨子应用 import

理由:本 V1 portal 单独使用,V2/V3 接入时再考虑共享机制;V1 保持依赖简单。

### Q1.5 canvas / admin 跳到 portal 怎么走?

候选 2 个:
- **(A) 完整 SPA navigate** — V1 选定
- (B) iframe

理由:简单、保留浏览器历史、避免 iframe 跨域 cookie / postMessage 复杂度。

### Q1.6 V1 验收边界?

候选 2 个:
- **(A) portal 单独跑通(独立 dev server,完整登录/侧栏/占位 e2e)** — V1 选定
- (B) portal 集成进 nginx 5173 全栈

理由:V1 范围最小化,canvas / admin 不变 → 集成测试可后续独立 change 做(V1 不动 web/nginx.conf,留 V2/V3 一起做)。

## 被拒方案(rejected alternatives)

- **Q1.1-B 提升 canvas 为主框架**: canvas 路由膨胀,违背职责单一
- **Q1.1-C MFE**: MVP 阶段不值得引入 host/remote 共享依赖复杂度
- **Q1.2-B 仅 MVP 4-6 项**: V1.0+ 接入服务时再做侧栏大改成本高
- **Q1.3-B cookie JWT**: 违背 `canvas-shell` "JWT 不持久化" 锁定
- **Q1.3-C 跳过登录**: portal 既然是主框架,必须有登录入口(否则 V2/V3 接入时还得加)
- **Q1.4-B 独立 npm 包 `@chatbiz/ui`**: V1 只有 1 个消费者,过早抽象
- **Q1.4-C `web/shared/`**: Vite 跨子应用 import 配置复杂,V2 再说
- **Q1.5-B iframe**: 跨域 cookie、双登录态、postMessage 通信,全部不要
- **Q1.6-B 集成 nginx 5173**: V1 改 nginx 会涉及 canvas / admin 的 nginx path 重新部署,扩大 scope

## Open Questions(本轮未决)

- **OQ1**: V1 是否要在 `web/index.html` 跳板新增 portal 卡片?(建议:是,dev 期方便跳转;V2/V3 一并跳)
- **OQ2**: V1 portal 的 e2e 跑在 `web/portal/dev server :5174` 还是 `nginx :5173`?(V1 选 5174 独立跑,V2/V3 集成)
- **OQ3**: V1 完成后,canvas / admin 是否需要 `localStorage['chatbiz.auth']` 互认?(V1 不改 canvas / admin,V2/V3 各自处理)

## 关键约束(从 eng-review 12 finding + CLAUDE.md)

1. eng-review #1 数据隔离网关 egress 强制 — **不属 V1**(纯 UI)
2. eng-review #2 Node Contract 12×4=48 组件 — **不属 V1**(本 V1 占位菜单留 future 接入)
3. CLAUDE.md 强制: 所有前端放 `web/` 下,统一 nginx 5173 入口 — V1 在 `web/portal/` 独立 dev 5174,V2/V3 集成 nginx
4. CLAUDE.md 强制: `VITE_APP_BASE=/<frontend-name>/` — V1 设 `/portal/`
5. CLAUDE.md 强制: worktree `.worktrees/` — V1 用 `.worktrees/web-portal-shell`
6. openspec/config.yaml 强制: 简体中文,SHALL/MUST,每 Requirement 配 WHEN/THEN,任务 ≤2h
7. openspec/config.yaml 强制: `[FUTURE-IMPLEMENTATION]` 标签 — V1 触及 V2/V3 未来工作处标注
8. 测试覆盖率: V1 单元 ≥100% / 接口 100% / 关键路径 e2e
9. Source of truth 顺序: `docs/architecture.md` > `docs/prd.md` > design doc — V1 与 prototype.html 视觉冲突时回 prototype 优先

## V1 / V2 / V3 拆分(V1 的范围明确边界)

| 范围 | V1 (本 change) | V2 (未来 change) | V3 (未来 change) |
|---|---|---|---|
| web/portal 新建 | ✅ | — | — |
| web/portal/dist build | ✅ | — | — |
| web/portal/tests vitest | ✅ | — | — |
| web/portal/e2e playwright | ✅ | — | — |
| canvas 删 antd 改 tailwind | ❌ | ✅ | — |
| canvas AppLayout / LoginPage / 5 page 重写 | ❌ | ✅ | — |
| canvas tests / e2e 适配 | ❌ | ✅ | — |
| admin 删 antd 改 tailwind | ❌ | — | ✅ |
| admin SideNav / AppShell / PlaceholderView 重写 | ❌ | — | ✅ |
| tailwind config 三套对齐 | ❌ | ✅ | ✅ |
| web/nginx.conf + Dockerfile 增量 | ❌ | ✅ | ✅ |
| web/README.md + canvas/admin/README.md | ❌ | ✅ | ✅ |
| specs/canvas-shell MODIFIED delta | ❌ | ✅ | — |
| specs/canvas-auth delta | ❌ | — | —(沿用) |
| integration test(portal ↔ canvas ↔ admin 5173) | ❌ | — | — |

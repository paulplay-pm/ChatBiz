## Context

**Background.** ChatBiz 是企业级 AI Agent 智能体平台(Lead Agent / Sub Agent + 工作流引擎 + 内网 AI + 数据隔离网关)。仓库当前 pre-build 阶段:`docs/architecture.md` / `docs/prd.md` / `docs/prototype.html` 全部冻结,eng-review 2026-06-10 12 个工程决策全部 locked-in,0 行后端源代码。

**Current state.**
- `web/canvas`: Vite + React + TS + Ant Design + zustand + react-query + react-router-dom;6 路由 + 24 单测 + 2 e2e;锁定于 `specs/canvas-shell/spec.md` + `specs/canvas-auth/spec.md`
- `web/admin`: 2026-06-12 由 `admin-web-bootstrap` 落地 src 骨架(11 项占位菜单 + SideNav + AppShell + PlaceholderView)
- `web/index.html`: 静态跳板
- infra: Docker Compose + nginx 5173 入口就绪

**V1 范围**(本 change 唯一范围):只新建 `web/portal` 子应用 + 设计 token 落地 + 30+ 项侧栏菜单 + 5 个 page + primitives 库。**不动** canvas / admin / nginx.conf / Dockerfile / 任何既有 spec。

**V2 / V3 显式不在 V1 范围**(留后续独立 change):
- V2: canvas 删 antd 改 tailwind + 配 `specs/canvas-shell` MODIFIED delta
- V3: admin 删 antd 改 tailwind
- V2 + V3 一起做:`web/nginx.conf` + `web/Dockerfile` 集成 + `web/README.md`

**Brainstormed V1 decisions (见 `brainstorm.md`):**
- portal 形态: 独立 Vite 子应用(挂 `/portal/`)
- 侧栏范围: 30+ 项全量导出,未接入项进占位页
- 登录态: `localStorage['chatbiz.auth']` 存 username + loginAt
- primitives 库: `web/portal/src/components/primitives/` 内部 import
- 工作流跳转: 完整 SPA navigate(非 iframe)
- 验收边界: 独立 dev 5174 跑通,不动 nginx

**Stakeholders.**
- paul(财务运营)— MVP 第一个具名用户,V1 的"工作流"菜单是他的日均入口
- 前端组 — V1 主要实施者;V2 / V3 由本批前端组继续
- C-level sponsor — review 平台形态时的关键观众

**Constraints from CLAUDE.md / openspec/config.yaml.**
- CLAUDE.md 强制: 统一前端在 `web/` 下,V1 在 `web/portal/` 独立 dev 5174
- CLAUDE.md 强制: `VITE_APP_BASE=/<frontend-name>/` — V1 设 `/portal/`
- CLAUDE.md 强制: worktree 必须放 `.worktrees/`,V1 worktree 名 `web-portal-shell`
- openspec/config.yaml 强制: 简体中文,SHALL/MUST,每 Requirement 配 WHEN/THEN,任务 ≤2h
- openspec/config.yaml 强制: 单元 ≥100% / 接口 100% / 安全全覆盖

## Goals / Non-Goals

**Goals:**

- G1: `web/portal` 子应用跑通"独立 dev 5174 → 登录 → 30+ 项侧栏 → 跳 /canvas/* 或 /portal/coming-soon"完整路径
- G2: portal 用 prototype 的 design language(brand/ink + glass + DM Sans + Space Mono),`tailwind.config.js` 逐位对齐 `docs/prototype.html:7-40`
- G3: 登录态写 `localStorage['chatbiz.auth']`(仅 username + 登录时间,沿用 `canvas-auth` dev fallback 契约,不存 token)
- G4: portal 完整导出 prototype 中 30+ 项菜单(分 5 个 section:对话 / 工作流 / Agent / 知识库 / 系统设置),未接入项进入 `/portal/coming-soon?from=<id>` 占位页(单组件按 query 切换文案)
- G5: 11 个 primitives(Button / Card / MetricCard / StatusDot / Input / Form / Modal / Toast / Sidebar / SidebarItem / SidebarSection)+ AppLayout + RequireAuth + 5 page 全部有 ≥1 个 vitest 单测
- G6: 2 个 playwright e2e spec 覆盖"登录 → 跳转 → 占位"关键路径
- G7: 端到端构建命令统一在 `web/portal/README.md`(新建)单一说明
- G8: V1 期间不动 canvas / admin / nginx.conf / Dockerfile / 既有 spec

**Non-Goals:**

- N1: 任何后端 API 实现 — 登录是 dev-mode mock
- N2: canvas / admin 任何修改 — V2 / V3 各自独立 change 接管
- N3: nginx 5173 集成 — V2 + V3 一起做
- N4: 集成 test(portal ↔ canvas ↔ admin)— 留 V3 之后
- N5: 设计 token 抽到共享 npm 包 — V1 内部 `web/portal/tailwind.config.js`;V2 / V3 复用
- N6: 国际化(i18n)— 简体中文硬编码,后续 `i18n-bridge` change 接管
- N7: 暗色模式 — V1 仅亮色
- N8: 移动端响应式 — V1 仅 ≥1024px
- N9: 真实 OAuth / SSO — 沿用 dev fallback
- N10: 写 `web/README.md` 统一三套子应用说明 — V2 + V3 一起做

## Decisions

### D1: portal = 独立 `web/portal` 子应用(独立 Vite 构建)

- **选择**: 在 `web/` 下新建 `web/portal/`,Vite dev server 跑 5174 端口(`base: '/portal/'`,V1 期间**不**集成 nginx 5173)
- **理由**: 与 CLAUDE.md "前端统一在 `web/` 下" 一致;与 canvas / admin 解耦,V2 / V3 期间 portal 不阻塞;V1 验收简单(独立 dev server 跑通即可)
- **已考虑 alternative**:
  - 提升 canvas 为主框架(被弃): canvas 路由膨胀
  - MFE(被弃): MVP 阶段不值得引入复杂度

### D2: 删除 antd 改 tailwind — V1 **不**做(留 V2)

- **选择**: V1 portal 自己用 tailwind + React 原语(不引 antd);V1 **不**动 canvas / admin 的 antd 引用
- **理由**: V1 portal 单独新写代码,不与 antd 冲突;V2 单独 change 处理 canvas 删 antd,V3 处理 admin
- **已考虑 alternative**:
  - V1 也改 canvas(被弃): V1 scope 膨胀,失去分解意义
  - V1 portal 用 antd 与 canvas 对齐(被弃): 与 "三套应用全部重制" 目标冲突,user 已选 B

### D3: 侧栏 30+ 项全量导出,未接入项进占位页

- **选择**: portal 侧栏完整渲染 prototype 中 30+ 项菜单,5 个 section(对话 / 工作流 / Agent / 知识库 / 系统设置);已接入菜单(工作流 / Chatflow / 设置)走 SPA navigate,未接入菜单进 `/portal/coming-soon?from=<id>` 占位页
- **理由**: 提前评审导航信息架构,避免 V1.0 接入时再做侧栏大改;占位页单组件按 query 切换文案
- **已考虑 alternative**:
  - 仅 4-6 项 MVP(被弃): V1.0+ 接入时再做侧栏大改成本高
  - 25+ 占位页写 25 个文件(被弃): 单 query string 切换文案覆盖

### D4: 设计 token = `web/portal/tailwind.config.js`(单文件,prototype 1:1)

- **选择**: `web/portal/tailwind.config.js` 复制 prototype 完整 brand-50..900 / ink-50..950 + font-sans(DM Sans) + font-mono(Space Mono);与 `docs/prototype.html:7-40` 逐位一致
- **理由**: V1 单独 1 个消费者;V2 / V3 复用同份 config(不抽共享 npm 包)
- **已考虑 alternative**:
  - 共享 JSON token(被弃): Vite 跨包 import + Tailwind preset 机制,V1 1 个消费者不抵
  - 共享 CSS 变量(被弃): tailwind utility class 与 CSS 变量两套调谐

### D5: 登录态 `localStorage` 轻量标记(token 走 zustand 内存)

- **选择**: portal Login 写 `localStorage['chatbiz.auth'] = JSON.stringify({ username, loginAt })`(只存 username + 登录时间);`RequireAuth` 读同一 key;JWT 仍按 `canvas-shell` 走 zustand 内存(本 V1 不实现 JWT,只 dev-mode 标记)
- **理由**: 不破坏 `canvas-auth` dev fallback 契约;不破坏 `canvas-shell` "JWT 不持久化" 锁定;localStorage 跨子应用同源可读(V2 / V3 直接复用)
- **已考虑 alternative**:
  - cookie JWT(被弃): 违背 `canvas-shell` 锁定
  - 跳过登录(被弃): portal 必须有登录入口

### D6: 工作流菜单点击 = SPA navigate(非 iframe)

- **选择**: 侧栏点击"工作流"触发 `navigate('/canvas/workflows')`;V1 期间 SPA navigate 实际是 `window.location.href`(因为 V1 独立 dev 5174,不依赖 nginx path 转发);V2 集成 nginx 后改 `navigate`
- **理由**: V1 独立 dev 5174 + V2 集成 nginx 是 2 个阶段;V1 阶段用 `window.location.href` 跨 origin 跳转,V2 阶段改用 `navigate` 跨 path
- **已考虑 alternative**:
  - iframe(被弃): 跨域 cookie、双登录态
  - 单 SPA nested routes(被弃): 与 D1 多子应用结构冲突

### D7: V1 **不**修改 `web/nginx.conf` / `web/Dockerfile` / `web/index.html`

- **选择**: V1 portal 独立 dev 5174 跑通,不动 nginx / Docker / 跳板
- **理由**: V1 范围最小化;V2 / V3 集成 nginx 时一起改
- **已考虑 alternative**:
  - V1 也集成 nginx(被弃): V1 scope 膨胀,需重测 canvas / admin 既有 nginx path

### D8: V1 **不**配任何 spec MODIFIED delta

- **选择**: V1 0 个 modified capabilities;只 new 3 个 capability(portal-shell / design-tokens / tailwind-primitive-library)
- **理由**: V1 不动 canvas / admin 任何 spec 锁定
- **已考虑 alternative**:
  - V1 配 canvas-shell delta(被弃): V1 不改 canvas 任何文件,delta 触发 archive 时报错
  - V1 配 canvas-auth delta(被弃): V1 沿用 canvas-auth dev fallback 契约,无新增

## Risks / Trade-offs

- [Risk] V1 portal 独立 dev 5174,V2 / V3 集成 nginx 时需改 D6(SPAnavigate → `navigate`) → Mitigation: V1 LoginPage 内部用 `window.location.assign(href)`(跨 origin 通用),V2 改用 `navigate(href)` 时仅改 1 行
- [Risk] 11 个 primitives 每个 ≥1 个 vitest,共 ~15 个测试文件,工作量大 → Mitigation: tasks 拆分到 6 个 task group,每个 ≤2h
- [Risk] `localStorage['chatbiz.auth']` key 名与 canvas 现有 key 冲突(若 canvas 用别的 key)→ Mitigation: V1 portal 自己的 key,V2 改 canvas 时统一 key
- [Risk] prototype 30+ 项菜单的视觉细节多,直接复制会陷入"画一遍原型" → Mitigation: V1 先做 4 个高频菜单(控制台 / 工作流 / Chatflow / 设置)的视觉验收,剩余 25+ 占位菜单仅做"侧栏 item + Coming soon 页"骨架,V1.0+ 接入时再调细节
- [Risk] V1 portal / canvas / admin 三套 `tailwind.config.js` 各自维护,V2 / V3 集成时 token 漂移 → Mitigation: V1 portal 内部 `web/portal/tailwind.config.js` 写完后,建立 `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md` 模板;V2 / V3 各自 `diff` 三套 config;V1 verify 时仅校验 portal 单份
- [Trade-off] V1 期间不动 nginx,V1 验收只跑 dev 5174 → 接受理由: V1 scope 最小化;V2 / V3 集成测试覆盖
- [Trade-off] V1 期间不动 `web/index.html` 跳板 → 接受理由: 跳板保留,dev 期仍可跳到 `/canvas/` `/admin/`;V1 portal 跑 5174 独立 dev
- [Trade-off] 不实现暗色 / 移动端 / i18n → 接受理由: prototype 仅亮色桌面端,过度实现即浪费
- [Trade-off] `MenuItem` 类型在 `web/portal/src/data/menu.ts` 内部,V2 / V3 复用时需 import 路径配置 → 接受理由: V1 简化,留 V2 解决
- [Risk] e2e playwright `chromium` 浏览器下载 200MB+ 慢 → Mitigation: V1 plan task 8 接受 5-10 min 安装时间,做 1 次性下载

## Migration Plan

本 V1 不涉及生产数据迁移、API 变更、数据库 schema 变更、nginx / Docker 变更,**纯前端 portal 子应用新增**。

**部署顺序**(V1 期间):
1. 准备 worktree: `git worktree add .worktrees/web-portal-shell -b worktree-web-portal-shell`
2. 在 worktree 内执行 tasks.md 任务
3. CI 通过(`tsc --noEmit && vite build`)后合并回 main
4. 本地 dev 验证: `pnpm --dir portal exec vite` → `http://localhost:5174/`

**V1 不做的事**(留 V2 / V3):
- ❌ nginx 集成(`web/nginx.conf` + `web/Dockerfile` 增量)
- ❌ `web/index.html` 跳板加 portal 卡片
- ❌ `web/README.md` 统一三套子应用说明
- ❌ `web/canvas/README.md` + `web/admin/README.md` 增量
- ❌ `infrastructure/README.md` 增量
- ❌ specs/canvas-shell MODIFIED delta
- ❌ 集成 test(portal ↔ canvas ↔ admin 5173)

**Rollback 策略**:
- 单 PR 粒度回滚: V1 tasks 拆分到 PR 粒度,每个 PR 独立可回滚
- 整 V1 回滚: `git revert` merge commit + 删除 `web/portal/` 目录
- V1 不动既有 canvas / admin / nginx → 整 V1 回滚不影响既有功能

**验收条件**(V1 独立):
- [ ] `pnpm --dir web/portal exec tsc --noEmit` exit 0
- [ ] `pnpm --dir web/portal exec vite build` 成功,产物在 `web/portal/dist/`
- [ ] `pnpm --dir web/portal exec vitest run` 全部新测试通过(估计 15+ 个)
- [ ] `pnpm --dir web/portal exec playwright test` 全部新 e2e spec 通过(2 个)
- [ ] 浏览器手动验收: `http://localhost:5174/portal/login` → 登录 → `/portal/` → 点击"工作流" → 跳到 `/canvas/workflows`(V1 阶段用 `window.location.href` 跳 5173)→ 点击 portal 侧栏"凭证管理" → 进入 `/portal/coming-soon?from=credential`
- [ ] `openspec validate web-portal-shell` exit 0
- [ ] V1 0 个 spec MODIFIED delta
- [ ] canvas / admin / nginx / Dockerfile / 跳板 0 改动(git diff main 仅 +X portal 子应用)

**N/A 检查**:
- 不涉及数据迁移 ✓
- 不涉及 API 端点变更 ✓
- 不涉及数据库 schema ✓
- 不涉及基础设施 compose 变更(infrastructure/docker-compose*.yml 0 改动) ✓
- V1 nginx / Dockerfile / 跳板 0 改动 ✓
- 既有 spec 0 改动 ✓

## Open Questions

(本 V1 范围内,设计阶段仍未决 — 留待 apply 阶段 task 1.1 拍板)

- **OQ1**: V1 完成后是否在 `web/portal/README.md` 标注 dev 端口 5174 与 V2 集成端口 5173 路径?倾向:是(V2 集成时改 README)
- **OQ2**: V1 e2e 是否跑在 `web/portal/dev :5174` 还是 `nginx :5173`?V1 选 5174 独立跑,V2 / V3 集成后改 5173
- **OQ3**: V1 portal `localStorage['chatbiz.auth']` key 名是否与 canvas 现有 key 兼容?tasks 1.1 探测;V2 一并统一
- **OQ4**: V1 期间是否在 `web/index.html` 跳板加 portal 卡片(仅 dev 期方便)?倾向:V1 不动跳板,V2 一并加

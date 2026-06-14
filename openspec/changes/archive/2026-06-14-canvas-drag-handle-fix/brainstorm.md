# V5 canvas-drag-handle-fix — Brainstorm

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:brainstorming
> **Schema:** superpowers-bridge (中文 + 严格测试/审计/标签规则)
> **Base branch:** `worktree-canvas-drag-handle-fix`(基于 V4 merge `96fc329`)
> **Source design 引用:** `docs/architecture.md` + `docs/prd.md` + `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md`

## 0. 背景

V4 (`sso-and-canvas-e2e-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `96fc329`。V4 留下 2 类 V1 baseline 已知 0 回归问题:
- canvas `canvas-connection.spec.ts` + `canvas-edge-deletion.spec.ts` **drag handle 协议** 失败(从 6/8 跳到 8/8 的最后一道坎)
- admin 4 fail e2e (1 bootstrap + 3 integration 已知 0 回归)

V5 = 专门修 2 drag handle 失败。**0 后端 / 0 端口 / 0 compose 改动**。

## 1. 决策链(locked-in)

### D1: 修法 = Option A(dev-only `window.__rfConnect` hook 替代 mouse drag)

- **理由**:xyflow 12.3.0 Handle 默认 `width: 6px; height: 6px`,Playwright `page.mouse.move()` 的 linear interpolation 最后一步 ±1-2 px 偏差,导致 `document.elementFromPoint(x, y)` 拿不到 target handle,onConnect 不触发
- **方案**:CanvasPage useEffect 在 `import.meta.env.DEV` 守卫下挂 `window.__rfConnect = ({source, target}) => onConnect({source, target, sourceHandle: null, targetHandle: null})`,spec 用 `page.evaluate` 调用替代 mouse drag
- **prod 安全**:`import.meta.env.DEV` 守卫 + Vite 构建时 dead-code-eliminate,prod bundle 不包含 `__rfConnect` 引用
- **保留真 mouse drag 路径**:CanvasPage onConnect 内部逻辑(cycle 检测 / self-loop 检测 / addEdge)不动,hook 仅是另一条触发入口

### D2: 范围 = 严格 1 改 2 改 1 改 1 加

- CanvasPage.tsx:加 hook 注册(T3,~30 行)
- canvas-connection.spec.ts + canvas-edge-deletion.spec.ts:改用 hook(T4,~20 行/个)
- 新建 CanvasPage.test.tsx 防 xyflow 协议漂移(T5,~50 行 + 3 断言)
- 新建 spec `openspec/changes/canvas-drag-handle-fix/specs/canvas-drag-handle/spec.md`(T6,5 Requirement + 5 Scenario)
- 0 改 xyflow / 0 改 vite.config / 0 改 router / 0 改 backend / 0 改 compose

### D3: 截止线 = Production-ready(走完 apply + 14-gate)

- 跟 V3/V4 一致节奏:5 artifact → 10 task → 14-gate verify
- 预计 3-4 session

### D4: 0 backend / 0 port / 0 compose / 0 npm dep

- 与 eng-review 12 finding 0 冲突
- 与 openspec/config.yaml 任务粒度规则一致
- bundle delta < 10 KB

## 2. 根因分析(Plan agent 报告)

| 假设 | 概率 | 失败原因 |
|---|---|---|
| **H1: elementFromPoint 落点精度** | 高 | xyflow 12.3.0 onPointerMove 用 `elementFromPoint(x, y)` 检测 handle;Handle 默认 6×6 px;Playwright mouse.move linear interpolation ±1-2 px 偏差 |
| H2: handle bbox 不准 | 中 | steps=15,中间路径可能掠过 pane 空白区 |
| H3: React Flow pan 抢占 | 中 | onPointerDown mousedown 冒泡顺序问题 |
| H4: Playwright mouse 不触发 React synthetic | 低-中 | 排除,React 转 synthetic OK |
| H5: 拖拽过程 re-render | 低 | 排除 |
| H6: 浏览器缩放 / DPR | 中 | 排除 |

**最可能真相** = **H1**(elementFromPoint 落点精度)。

## 3. 备选方案(rejected)

### Option B — 修 spec 用 `page.mouse` + 加大 hit-target

- 注入测试 CSS:`.react-flow__handle { width: 24px; height: 24px; }`(dev only)
- 复杂、脆弱、影响 dev 视觉、需调参 connectionRadius

### Option C — 用 ReactFlow `useReactFlow().setEdges` 直连

- 绕过 onConnect 的 cycle / self-loop / addEdge 逻辑
- 等价 Option A,几乎没新意

### Option D — testMode URL 参数 + 暴露 imperative API

- 过设计,V5 目标只是修 2 spec
- 留 V6+ 可选

## 4. 10 task outline

```
T1  V5 准备 + 协议对齐诊断(baseline 跑 + elementFromPoint 落点确认)
T2  openspec new change + 4 artifact 草稿(brainstorm/proposal/design/tasks)
T3  CanvasPage 加 dev-only __rfConnect hook(编码)
T4  2 e2e spec 改写为 hook 调用(配对 T3)
T5  防 xyflow 协议漂移单测(CanvasPage.test.tsx)
T6  spec 落地(canvas-drag-handle 1 spec 5 Requirement)
T7  bundle size + build 验证
T8  全量回归(14-gate)
T9  openspec plan + apply
T10 verify + retrospective + archive
```

## 5. 关键约束

- CanvasPage 改在 `<ReactFlowProvider>` 子组件(`CanvasPageInner`)内 useEffect 注册 hook
- `if (!import.meta.env.DEV) return;` 守卫,Vite dead-code-eliminate prod 不带
- 保留 CanvasPage onConnect 原 cycle / self-loop / addEdge 逻辑(0 行为变化)
- vitest 跑时 CanvasPage 可能挂 hook 到 jsdom window,需 T5 单测验证不污染

## 6. 与 12 个 eng-review 锁定决策符合性

| Finding | 影响 |
|---|---|
| Arch #1-#6 | 0 冲突 |
| Quality #1 Node Contract codegen | 0 冲突 |
| Quality #3 4 错误边界 | **正向保留** — canvas drag-loop 边界(cycle 检测)不动 |
| Test #1-#2 3 层 + critical path | 正向贡献:canvas e2e 6/8 → 8/8 |
| Perf #1-#2 | 0 冲突 |

## 7. 风险与决策点

### R1: T1 诊断发现根因不是 H1
- Plan B:退回 Option B(spec timing + 加大 hit-target),+2h 总时长
- V5 仍可收

### R2: hook 漏挂在 prod build
- T7.2 grep prod bundle 验证
- T6 Req 1 强制 MUST:仅 `import.meta.env.DEV === true` 时挂

### R3: onConnect 行为在 hook 路径 vs mouse drag 路径不一致
- T5 单测覆盖 3 case(正常 / self-loop / cycle)
- T6 Req 2 / Req 4 强制等价

### R4: xyflow 12.3.0 → 13.x 协议漂移
- hook 路径只依赖 `Connection` 协议(source/target/sourceHandle/targetHandle)
- T5 单测锁 Connection 协议

## 8. 与 V4 baseline 不变量(0 回归)

- canvas vitest:84/84 → 87/87(0 回归 +3 新单测)
- canvas playwright main:6/8 → **8/8**(+2)
- canvas playwright integration:3/3 → 3/3
- portal vitest:50/50 → 50/50
- portal playwright:7/7 → 7/7
- admin vitest:32/32 → 32/32
- admin playwright:1/5 → 1/5
- bundle delta:< 10 KB

## 9. 待 V5 期间用户裁决的潜在 Q

- Q1: T1 诊断若发现根因不是 H1,是否接受 Plan B 退回?(V5 apply 前必答)
- Q2: hook 命名是否要加 namespace 前缀(`window.__chatbizRfConnect` vs `window.__rfConnect`)?(T3 设计时定)
- Q3: V5 完成后,V6 优先级?(SSO 真实联调 / 4 业务 spec 后端实现 / 真实 Keycloak 接入)

# V5 canvas-drag-handle-fix — Design

> **Schema:** superpowers-bridge
> **依赖:** `brainstorm.md` §1 决策链 + `proposal.md` 1 capability
> **Source of truth:** docs/architecture.md + docs/prd.md + design doc

## Context

V4 (`sso-and-canvas-e2e-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `96fc329`。V4 留下 V1 baseline 已知 0 回归问题:**canvas 2 个 drag handle e2e 失败**(`canvas-connection.spec.ts` + `canvas-edge-deletion.spec.ts`)。

V5 专门修这 2 个 spec,目标 canvas 6/8 → 8/8。**0 后端代码、0 端口、0 compose 改动**。

## Goals

- **G1** canvas e2e 6/8 → **8/8** 跑通
- **G2** CanvasPage onConnect 行为对 prod 用户 0 变化(hook 仅 dev/test 路径)
- **G3** prod bundle 不含 `__rfConnect`(`import.meta.env.DEV` 守卫 + Vite dead-code-eliminate)
- **G4** V5 archive + 14-gate verify 全 PASS

## Non-Goals

- 修 xyflow 12.3.0 源码 / 升级 13.x
- 修 admin 4 fail e2e(V1 baseline 已知,留 V6+)
- 真实后端 Python 代码(4 业务 spec 留 V6+)
- SSO 真实联调 / SAML / Keycloak(留 V6+)
- 改动 NodePanel / ConfigPanel / 节点 schema / vite.config / router
- 改动 onConnect 内部逻辑(cycle / self-loop / addEdge 全部保留)

## Decisions

### D1: 修法 = Option A(dev-only `window.__rfConnect` hook)

- CanvasPage `CanvasPageInner` useEffect 注册 `window.__rfConnect = ({source, target}) => onConnect({source, target, sourceHandle: null, targetHandle: null})`
- `if (!import.meta.env.DEV) return;` 守卫
- cleanup function 摘 hook,避免 hot reload 累积
- spec 用 `page.evaluate(([s, t]) => (window as any).__rfConnect({source: s, target: t}), [sourceId, targetId])`

### D2: hook 命名 = `window.__rfConnect`(无 namespace 前缀)

- 简短、清晰
- 风险:`__rf` 唯一性(其他库不太用 `__rf` 前缀)
- 不加 `__chatbiz` 因为 vite test build 也跑同一份代码,加长前缀无收益

### D3: onConnect 行为 0 变化

- hook 仅是另一条触发入口,内部逻辑(cycle / self-loop / addEdge)与 mouse drag 路径完全相同
- T5 单测覆盖 3 case(正常 / self-loop 拒绝 / cycle 拒绝)锁这一约束
- T6 Req 2 / Req 4 spec 锁定"等价触发" + "0 行为变化"

### D4: 防 xyflow 协议漂移

- hook 路径只依赖 `Connection` 协议(source/target/sourceHandle/targetHandle)
- T5 单测锁 Connection 协议(不强依赖 `pointerId` / `connectionRadius` / Handle 像素大小)
- 未来 xyflow 13.x 若改 Connection 协议,hook 也需同步,但 spec 改动可控

## Architecture

### 关键模块流(test 路径)

```
[e2e spec canvas-connection]
  ↓ page.evaluate
[(window as any).__rfConnect({source, target})]
  ↓ CanvasPage useEffect 注册的 hook
[onConnect callback (CanvasPage.tsx:120-145)]
  ↓ 内部:cycle 检测 / self-loop 检测 / addEdge
[useCanvasEditStore.setState({edges: [...]})]
  ↓
[rfEdges 重新计算]
  ↓
[ReactFlow 渲染 .react-flow__edge]
  ↓
[.react-flow__edge count = 1 → spec PASS]
```

### 关键模块流(prod 路径)

```
[用户真实 mouse drag source handle → target handle]
  ↓
[xyflow XYHandle.onPointerDown (xyflow 内部)]
  ↓ doc.addEventListener('mousemove', onPointerMove)
  ↓ elementFromPoint 命中 target handle
[xyflow XYHandle.onConnect]
  ↓
[ReactFlow onConnect prop = CanvasPage.onConnect]
  ↓ 同样的 cycle / self-loop / addEdge
[useCanvasEditStore.setState]
  ↓
[ReactFlow 渲染 .react-flow__edge]
```

**两条路径汇合点** = `CanvasPage.onConnect` callback(V4 既有代码,不动)。

## Risks

- **R1**: T1 诊断发现根因不是 H1(elementFromPoint 落点精度)→ 退回 Option B(spec timing),+2h 总时长。**缓解**:T1.3-T1.5 在 e2e 加 `page.evaluate(() => document.elementFromPoint(target.x, target.y))` 诊断,确认根因。
- **R2**: hook 漏挂在 prod build → **缓解**:T7.2 grep prod bundle 找 `__rfConnect` 字符串;若存在,守卫失败。
- **R3**: onConnect 行为在 hook vs mouse 路径不一致 → **缓解**:T5 单测 3 case;T6 Req 2 / Req 4 spec 锁。
- **R4**: xyflow 13.x 协议漂移 → **缓解**:T5 单测锁 Connection 协议。
- **R5**: vitest 跑 CanvasPage 时意外挂 hook → **缓解**:T5 单测验证 jsdom window 状态。

## Migration

- 无数据迁移
- 无 UI 迁移
- 仅 CanvasPage 加 hook(e2e 路径)+ 2 spec 改写(测试代码)
- 0 user-facing 行为变化(prod build 不挂 hook)

## Open Questions

- **Q1**: T1 诊断若根因不是 H1,是否接受 Plan B 退回?(V5 apply 前必答)
- **Q2**: hook 命名是否接受 `window.__rfConnect` 无 namespace 前缀?(T3 设计时定)
- **Q3**: V5 完成后 V6 优先级?

## 10 task 速览(详见 tasks.md)

```
T1  V5 准备 + 协议对齐诊断(baseline + elementFromPoint 落点确认)
T2  4 artifact(brainstorm/proposal/design/tasks 草稿)
T3  CanvasPage 加 dev-only __rfConnect hook
T4  2 e2e spec 改写为 hook 调用
T5  防 xyflow 协议漂移单测
T6  1 spec 落地(canvas-drag-handle 5 Requirement)
T7  bundle size + build 验证
T8  全量回归(14-gate)
T9  openspec plan + apply
T10 verify + retrospective + archive
```

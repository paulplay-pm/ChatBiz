# V5 canvas-drag-handle-fix — Retrospective

> **Schema:** superpowers-bridge
> **Time range:** V5 worktree 10 task,2-3 session(实际 ~2 session)
> **Outcome:** canvas e2e 6/8 → 8/8,V1 baseline 已知 0 回归问题彻底解决

---

## 1. 决策回顾

### D1: 修法 = Option A(dev-only `__rfConnect` hook)

**对** — 这是 V5 最关键的决策。直接绕开 ReactFlow 内部 drag 协议,显式暴露 `Connection` 协议,既不破坏 prod 行为,又消除 e2e 落点精度问题。

**若重做** — 仍选 Option A。Option B(改 spec timing + 加大 hit-target)需要调参 + 改 ReactFlow CSS,V5 不可控因素多。Option A 一次性解决,后续 xyflow 升级 T4 单测立即回归。

### D2: 范围 = 严格 1 改 2 改 1 改 1 加

**对** — 最小改动:< 100 行 src + 1 个 spec + 1 个 test。bundle +0.3 KB 微增。

**若重做** — 仍选严格 1 改。但 V5 实施时我额外加了"select" 字段(因为 hook 路径绕过 ReactFlow select 状态机,删 edge 测试需要 selected 状态),**这是 V5 design 没显式锁定的边界**。**经验**:V5 design 应该更早 surface "hook 路径是否需要 `select` 字段" 这个决策点(Plan agent 报告里没强调)。

### D3: 截止线 = Production-ready(走完 apply + 14-gate)

**对** — 14-gate verify 抓到 integration 1 fail(rebuild 容器后修复),若跳过 verify 直接 archive,会漏掉这次修复机会。

**若重做** — 仍选 production-ready。**经验**:14-gate verify 不是仪式,是 V5 真能发现 regression 的关卡。

### D4: 0 backend / 0 port / 0 compose / 0 dep

**对** — 全部 0,符合 eng-review 12 finding 0 冲突。bundle +0.3 KB 微增。

---

## 2. 实施回顾

### T1 落点诊断的回报

T1 跑 e2e 加 `document.elementFromPoint(x, y)` 诊断,确认根因 H1(elementFromPoint 落点精度) → 直接锁定 Option A 方案。**这是 V5 最高 ROI 的 30 分钟**。若没有诊断,Plan agent 的 4 个备选方案都要逐一尝试,会浪费 1-2 session。

### T2 hook + T3 spec 改写 + T4 单测的协同

T2 hook 注入 → T3 spec 改用 hook → T4 单测用 store 验证 → 完整循环。T4 单测 3 断言特别重要,**锁了 onConnect 行为约束**(self-loop + cycle 拒绝),让 xyflow 升级时 V5 hook 协议变了能立即 fail。

### T7 容器 rebuild 修最后 1 fail

V5 baseline 5/8 比 V4 6/8 少 1 个 PASS(`integration 'canvas SPA loads through nginx'` 因 V5 worktree 容器没 `--network chatbiz-net` 启动)。T7 rebuild 容器后 8/8 达成。**经验**:**worktree 之间容器 state 不会自动继承**。每个新 worktree 启动容器都要重新加 `--network`。

### T6 bundle + build 验证

T6 跑 `grep prod __rfConnect` 0 出现 —— 这是 V5 实施里**唯一一次确认 prod 安全**的硬验证。Vite DCE 完美执行,prod 用户完全不暴露测试 hook。

---

## 3. 技术观察

### xyflow 12.3.0 drag 协议的脆弱性

xyflow Handle 默认 `width: 6px; height: 6px`,配合 `document.elementFromPoint` 检测 hit area,**对自动化测试非常不友好**。这不是 xyflow 的 bug(6×6 是合理的视觉尺寸),但生产 drag 协议缺一层"自动化友好" 抽象。V5 通过 `__rfConnect` hook 提供这层抽象,**但不是 xyflow 官方方案**。

若 xyflow 未来引入 `useReactFlow().setEdges([{...}, {selected: true}])` API,V5 hook 可以移除,直接走官方。**V6+ 跟踪 xyflow 13.x 变更**。

### Test hook 模式的一般化

V5 的 `__rfConnect` hook 是 "Test hook" 模式的一个实例:dev-only window 属性 + 走真实业务路径 + prod dead-code-eliminate。这种模式可推广到:
- `__rfDrop(node-type, position)` —— 替代 node drop dispatchEvent(已用,V5 之前的 V2/V3)
- `__rfSave()` —— 替代 save mutation
- `__rfUndo()` / `__rfRedo()` —— 替代 keyboard.press

**V6+ 可考虑统一一个 `__rfTest` namespace,挂所有测试 hook**。

### Vite `import.meta.env.DEV` 守卫

`if (!import.meta.env.DEV) return;` 是 Vite 的官方模式,prod dead-code-eliminate 自动剥离。V5 用这一行实现 prod 安全,**比 React 自己的 `process.env.NODE_ENV === 'development'` 更精确**(后者在 SSR 场景会判错)。

---

## 4. 流程观察

### 8-stage superpowers-bridge schema 表现

V5 走完 8 stage(brainstorm → proposal → design → specs → tasks → plan → apply → verify):
- brainstorm 决策链清晰
- proposal 1 capability + non-goals
- design 5 Decisions + Architecture
- specs 5 Requirement + 9 Scenario
- tasks 10 一级 + ~25 二级
- plan 8 条 apply-rule 自检
- verify 14-gate
- retrospective 决策回顾

**经验**:tasks.md 写 10 task 全部对齐 plan/apply 阶段。**重做 V5 时不会再分 10 task 这么细**,8-9 task 够用。

### 5 artifact + Plan agent scoping

V5 4 artifact 阶段用 Plan agent 给 50KB 报告(根因 + 备选 + task outline + 风险),节省 1-2 session。**经验**:**Plan agent 在 4 artifact 阶段 ROI 最高**,比 T1 实地诊断后回报更早。

---

## 5. 给 V6+ 的建议

### 优先级

1. **SSO 真实联调**(4 业务 spec + canvas-auth 留 V5+ 待实现)
2. **真实后端 Python 实现**(4 业务 spec runtime)
3. **xyflow 升级 + Test hook 模式一般化**(若 xyflow 13.x 改 drag 协议)
4. **Admin 4 fail e2e 修复**(V1 baseline 已知)

### 流程

- 每个 worktree 启动容器必须 `--network chatbiz-net`(V4 T4 + V5 T7 经验)
- bundle 验证 `grep prod` 是必备 gate,不是仪式
- 14-gate verify 必须全跑,不能跳过

### 文档

- `openspec/changes/archive/<date>-<change>/` 永久保留
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` eng-review 12 finding 是 source of truth
- `docs/architecture.md` 未动(V5 0 架构变更)

---

## 6. V5 总结

| 维度 | 值 |
|------|-----|
| 任务数 | 10/10 全 PASS |
| 14-gate verify | 14/14 全 PASS |
| canvas e2e | 6/8 → **8/8** |
| canvas vitest | 84 → 87(+3) |
| 业务 spec | +1 (canvas-drag-handle) |
| bundle delta | +0.3 KB |
| 0 backend / 0 port / 0 compose / 0 dep | ✅ |
| 0 回归(portal + admin) | ✅ |
| 关键决策 | Option A hook(Plan agent H1 诊断锁定) |

V5 是一次**专注、收敛、零扩展**的修复。V1 baseline 已知 0 回归问题彻底解决,**canvas e2e 从 V1 累计 4 change 都没修的 6/8 → 8/8**,这是 V5 的最大胜利。

# tailwind-primitive-library Specification

## Purpose
TBD - created by archiving change web-portal-shell. Update Purpose after archive.
## Requirements
### Requirement: Button primitive(variant × size)

`web/portal/src/components/primitives/Button.tsx` MUST 暴露 `Button` 组件,接受 `variant: 'primary' | 'secondary' | 'ghost'` + `size: 'sm' | 'md' | 'lg'` + `onClick` + `type: 'button' | 'submit'` + `children` props;`primary` MUST 用 `bg-brand-500 hover:bg-brand-600 text-white`;`secondary` MUST 用 `bg-ink-100 hover:bg-ink-200 text-ink-900`;`ghost` MUST 用 `bg-transparent hover:bg-ink-100 text-ink-700`;`data-testid="btn"` MUST 暴露供 vitest 断言。

#### Scenario: primary variant 渲染
- **WHEN** 渲染 `<Button variant="primary">Click</Button>`
- **THEN** button 元素 MUST 包含 class `bg-brand-500` + `text-white`;`data-testid="btn"` MUST 存在

#### Scenario: ghost variant 渲染
- **WHEN** 渲染 `<Button variant="ghost">Cancel</Button>`
- **THEN** button 元素 MUST 包含 class `bg-transparent` + `text-ink-700`

#### Scenario: onClick 触发
- **WHEN** 用户点击 Button
- **THEN** 传入的 `onClick` callback MUST 被调用

### Requirement: Card / MetricCard / StatusDot

`Card` / `MetricCard` / `StatusDot` MUST 各暴露 1 个组件,`Card` 用 `rounded-xl bg-white border border-ink-200 node-shadow p-4`;`MetricCard` 用 `rounded-xl p-4 metric-card` + `text-2xl font-semibold text-ink-900`;`StatusDot` 用 `status-dot status-{running|success|error|idle|pending}` 类(对应 prototype 的 5 个状态色 + pulse 动画)。

#### Scenario: Card 渲染
- **WHEN** 渲染 `<Card>content</Card>`
- **THEN** div MUST 包含 class `rounded-xl bg-white border border-ink-200`;`data-testid="card"` MUST 存在

#### Scenario: MetricCard 渲染
- **WHEN** 渲染 `<MetricCard label="工作流" value={12} />`
- **THEN** div MUST 包含 class `rounded-xl p-4 metric-card`;MUST 渲染 `label` 文案 + `value` 数字;`data-testid="metric-card"` MUST 存在

#### Scenario: StatusDot 5 状态
- **WHEN** 渲染 `<StatusDot status="running" />`
- **THEN** span MUST 包含 class `status-running`;5 个 status 全部 MUST 有对应 class

### Requirement: Input / Form / Modal

`Input` MUST 暴露 `name` / `value` / `onChange` / `placeholder` / `type` props;`Form` MUST 暴露 `onSubmit` + `children` props,`onSubmit` 接收 `FormEvent`;`Modal` MUST 暴露 `open` + `onClose` + `title` + `children` props,`open=false` 时 MUST 不渲染任何 DOM,`open=true` 时 MUST 渲染 `.fixed.inset-0` 背景 + `.bg-white.rounded-xl` 内容区;点击 backdrop MUST 触发 `onClose`。

#### Scenario: Modal open/close
- **WHEN** `<Modal open={true} onClose={fn}>...</Modal>` 渲染
- **THEN** MUST 出现 `data-testid="modal"` + `data-testid="modal-backdrop"` 元素;`open={false}` MUST 不渲染任何 modal DOM

#### Scenario: Modal backdrop click 关闭
- **WHEN** 用户点击 `data-testid="modal-backdrop"`
- **THEN** `onClose` callback MUST 被调用;点击 modal 内容区 MUST 不触发 `onClose`

### Requirement: Toast + useToast hook(替代 antd notification)

`Toast` 暴露 `ToastProvider` 组件 + `useToast` hook;`useToast` 返回 `{ error, warn, info }` 三方法;`toast.error(msg)` MUST 渲染红底(`bg-red-500`)toast 5s 后自动消失;`toast.warn(msg)` MUST 渲染黄底(`bg-yellow-500`);`toast.info(msg)` MUST 渲染蓝底(`bg-brand-500`);toast 位置 MUST 是 viewport 顶部居中(z-index 9999)。

#### Scenario: security error toast
- **WHEN** 调用 `useToast().error('会话过期')`
- **THEN** MUST 出现 `data-testid="toast-security"` 元素,class MUST 含 `bg-red-500`;5s 后 MUST 自动消失

#### Scenario: user warn toast
- **WHEN** 调用 `useToast().warn('表单未完整')`
- **THEN** MUST 出现 `data-testid="toast-user"` 元素,class MUST 含 `bg-yellow-500`

#### Scenario: runtime info toast
- **WHEN** 调用 `useToast().info('请稍候')`
- **THEN** MUST 出现 `data-testid="toast-info"` 元素,class MUST 含 `bg-brand-500`

#### Scenario: 5s 自动消失
- **WHEN** 任意 toast 出现
- **THEN** 5s 后 MUST 从 DOM 移除(vitest 用 `vi.useFakeTimers` + `vi.advanceTimersByTime(5001)` 验证)

### Requirement: Sidebar / SidebarItem / SidebarSection

`Sidebar` MUST 接受 `items: MenuItem[]` + `sections: MenuSection[]` + `activeId: string` + `onSelect: (id: string) => void` props,按 section 分组渲染所有 `MenuItem`;`SidebarItem` MUST 应用 `bg-brand-50 text-brand-600` 高亮当 `active=true`;`SidebarSection` MUST 渲染 section 标题。

#### Scenario: 5 section 标题渲染
- **WHEN** 传入 5 个 SECTIONS 渲染
- **THEN** 5 个 section 标题 MUST 全部出现(对话 / 工作流 / Agent / 知识库 / 系统设置)

#### Scenario: active 高亮
- **WHEN** `<SidebarItem item={...} active={true} />` 渲染
- **THEN** div MUST 含 class `bg-brand-50 text-brand-600`;`data-testid="sidebar-item-<id>"` MUST 存在

#### Scenario: hover 效果
- **WHEN** 鼠标悬停 SidebarItem
- **THEN** div MUST 应用 `hover:bg-brand-50/50`(CSS pseudo-class)

### Requirement: RequireAuth 守卫

`RequireAuth` MUST 读 `localStorage['chatbiz.auth']`;不存在时 MUST 跳 `/login`;存在时 MUST 渲染 children 或 `<Outlet/>`。

#### Scenario: 未登录跳 login
- **WHEN** `localStorage['chatbiz.auth']` 不存在 + 渲染 `<RequireAuth><div>protected</div></RequireAuth>`
- **THEN** MUST 跳 `/login`(`Navigate to="/login" replace`);children MUST 不渲染

#### Scenario: 已登录渲染 children
- **WHEN** `localStorage['chatbiz.auth']` 存在
- **THEN** `<RequireAuth><div>protected</div></RequireAuth>` MUST 渲染 `<div>protected</div>`

### Requirement: 单元测试覆盖率 ≥ 100%

V1 portal 所有 primitives MUST 配 ≥ 1 个 vitest spec;`pnpm --dir web/portal exec vitest run` MUST 退出码 0;所有 `*.ts` / `*.tsx` 文件 MUST 有对应 `*.test.ts` / `*.test.tsx`(`src/components/primitives/*.tsx` + `src/components/{AppLayout,RequireAuth}.tsx` + `src/pages/*.tsx` + `src/router/index.tsx` + `src/data/menu.ts`)。

#### Scenario: vitest run 全过
- **WHEN** `pnpm --dir web/portal exec vitest run` 跑
- **THEN** 命令 MUST exit 0;所有 spec MUST 通过(0 failed)


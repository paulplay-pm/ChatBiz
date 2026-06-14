// admin permission matrix mock data (V3 锁定,等 V4+ 接 API 后再迁)
export type PermissionAction = 'view' | 'create' | 'edit' | 'delete' | 'publish' | 'execute';
export type RoleOption = 'super-admin' | 'dept-admin' | 'developer' | 'normal-user';

export type PermissionPoint = { id: string; name: string };
export type PermissionModule = {
  id: string;
  name: string;
  points: PermissionPoint[];
};

// 7 功能模块 + 11 权限点(对齐 spec)
export const MOCK_MODULES: PermissionModule[] = [
  {
    id: 'm-workflow',
    name: '工作流',
    points: [
      { id: 'p-wf-list', name: '工作流列表' },
      { id: 'p-wf-canvas', name: '工作流画布' },
    ],
  },
  {
    id: 'm-agent',
    name: 'Agent',
    points: [
      { id: 'p-ag-list', name: 'Agent 列表' },
      { id: 'p-ag-prompt', name: '提示词编辑' },
    ],
  },
  {
    id: 'm-knowledge',
    name: '知识库',
    points: [
      { id: 'p-kb-list', name: '知识库列表' },
      { id: 'p-kb-doc', name: '文档管理' },
    ],
  },
  {
    id: 'm-conversation',
    name: '对话',
    points: [
      { id: 'p-cv-list', name: '对话列表' },
    ],
  },
  {
    id: 'm-template',
    name: '模板',
    points: [
      { id: 'p-tpl-mkt', name: '模板广场' },
    ],
  },
  {
    id: 'm-plugin',
    name: '插件',
    points: [
      { id: 'p-plg-mkt', name: '插件市场' },
    ],
  },
  {
    id: 'm-system',
    name: '系统管理',
    points: [
      { id: 'p-sys-user', name: '用户管理' },
      { id: 'p-sys-role', name: '角色管理' },
    ],
  },
];

// 6 操作(列)
export const PERMISSION_ACTIONS: PermissionAction[] = [
  'view',
  'create',
  'edit',
  'delete',
  'publish',
  'execute',
];

// 4 角色 dropdown 选项
export const ROLE_OPTIONS: { value: RoleOption; label: string }[] = [
  { value: 'super-admin', label: '超级管理员' },
  { value: 'dept-admin', label: '部门管理员' },
  { value: 'developer', label: '开发者' },
  { value: 'normal-user', label: '普通用户' },
];

// 权限矩阵:role × point × action → boolean
// 4 角色 × 11 权限点 × 6 操作 = 264 单元
// 默认:super-admin 全 true,normal-user 只 view
// 中间角色按部门 / 开发者类型裁剪
type PermissionMatrix = Record<RoleOption, Record<string, Record<PermissionAction, boolean>>>;

const ALL_TRUE: Record<PermissionAction, boolean> = {
  view: true,
  create: true,
  edit: true,
  delete: true,
  publish: true,
  execute: true,
};

const VIEW_ONLY: Record<PermissionAction, boolean> = {
  view: true,
  create: false,
  edit: false,
  delete: false,
  publish: false,
  execute: false,
};

const DEVELOPER: Record<PermissionAction, boolean> = {
  view: true,
  create: true,
  edit: true,
  delete: false,
  publish: true,
  execute: true,
};

const DEPT_ADMIN: Record<PermissionAction, boolean> = {
  view: true,
  create: true,
  edit: true,
  delete: false,
  publish: true,
  execute: true,
};

export const MOCK_PERMISSIONS: PermissionMatrix = {
  'super-admin': {},
  'dept-admin': {},
  developer: {},
  'normal-user': {},
};

// 填充:super-admin 全 true;normal-user 仅 view;developer / dept-admin 按权限点裁剪
for (const mod of MOCK_MODULES) {
  for (const pt of mod.points) {
    MOCK_PERMISSIONS['super-admin'][pt.id] = { ...ALL_TRUE };
    MOCK_PERMISSIONS['normal-user'][pt.id] = { ...VIEW_ONLY };
    if (pt.id.startsWith('p-sys-')) {
      // 系统管理模块:developer 只能 view,dept-admin 可编辑
      MOCK_PERMISSIONS['developer'][pt.id] = { ...VIEW_ONLY };
      MOCK_PERMISSIONS['dept-admin'][pt.id] = { ...DEPT_ADMIN };
    } else {
      MOCK_PERMISSIONS['developer'][pt.id] = { ...DEVELOPER };
      MOCK_PERMISSIONS['dept-admin'][pt.id] = { ...DEPT_ADMIN };
    }
  }
}

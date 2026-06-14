// admin role mock data (V3 锁定,等 V4+ 接 API 后再迁)
export type RolePermissionAction = 'view' | 'create' | 'edit' | 'delete' | 'publish';
export type RolePermissionTarget = 'workflow' | 'conversation';

export type RoleCardData = {
  id: string;
  name: string;
  description: string;
  icon: string;
  memberAvatars: string[]; // 至少 3 个 mock 成员头像(中文姓氏首字)
  // 权限矩阵:target × action 的二维布尔
  matrix: Record<RolePermissionTarget, Record<RolePermissionAction, boolean>>;
};

export const MOCK_ROLES: RoleCardData[] = [
  {
    id: 'super-admin',
    name: '超级管理员',
    description: '拥有系统全部权限,可管理所有模块',
    icon: 'fas fa-crown',
    memberAvatars: ['张', '陈', '周'],
    matrix: {
      workflow: { view: true, create: true, edit: true, delete: true, publish: true },
      conversation: { view: true, create: true, edit: true, delete: true, publish: true },
    },
  },
  {
    id: 'dept-admin',
    name: '部门管理员',
    description: '管理本部门成员和数据,跨部门需申请',
    icon: 'fas fa-user-tie',
    memberAvatars: ['李', '孙', '吴'],
    matrix: {
      workflow: { view: true, create: true, edit: true, delete: false, publish: true },
      conversation: { view: true, create: true, edit: true, delete: false, publish: false },
    },
  },
  {
    id: 'developer',
    name: '开发者',
    description: '创建和编辑工作流,管理已发布资源',
    icon: 'fas fa-code',
    memberAvatars: ['赵', '钱', '黄'],
    matrix: {
      workflow: { view: true, create: true, edit: true, delete: false, publish: false },
      conversation: { view: true, create: true, edit: true, delete: false, publish: false },
    },
  },
  {
    id: 'normal-user',
    name: '普通用户',
    description: '只能使用已发布的工作流和对话,无编辑权限',
    icon: 'fas fa-user',
    memberAvatars: ['王', '冯', '蒋'],
    matrix: {
      workflow: { view: true, create: false, edit: false, delete: false, publish: false },
      conversation: { view: true, create: false, edit: false, delete: false, publish: false },
    },
  },
];

export type MenuStatus = 'ready' | 'coming-soon';
export type MenuItem = {
  id: string;
  label: string;
  icon: string;
  section: string;
  status: MenuStatus;
  href: string;
  external: boolean;
};
export type MenuSection = { id: string; title: string };

// 5 大分组(原型图 #5 顺序:工作区/探索/配置中心/运维/系统管理)
export const SECTIONS: MenuSection[] = [
  { id: 'workspace', title: '工作区' },
  { id: 'explore', title: '探索' },
  { id: 'config', title: '配置中心' },
  { id: 'ops', title: '运维' },
  { id: 'system', title: '系统管理' },
];

// 24 menu item,external=true 表示跨 app 跳转(window.location.assign)
// - canvas 跨跳:/canvas/<sub>
// - admin 跨跳:/admin/<sub>
export const MENU: MenuItem[] = [
  // ── 工作区(6 项,首项 internal) ──
  { id: 'dashboard', label: '工作台', icon: 'fas fa-gauge', section: 'workspace', status: 'ready', href: '/', external: false },
  { id: 'workflow-list', label: '工作流', icon: 'fas fa-project-diagram', section: 'workspace', status: 'ready', href: '/canvas/workflows', external: true },
  { id: 'chatflow', label: 'Chatflow', icon: 'fas fa-comments-dollar', section: 'workspace', status: 'ready', href: '/canvas/chatflow', external: true },
  { id: 'runs', label: '运行记录', icon: 'fas fa-play', section: 'workspace', status: 'ready', href: '/canvas/runs', external: true },
  { id: 'agent-list', label: 'Agent 列表', icon: 'fas fa-robot', section: 'workspace', status: 'coming-soon', href: '/canvas/agents', external: true },
  { id: 'knowledge', label: '知识库', icon: 'fas fa-book', section: 'workspace', status: 'coming-soon', href: '/canvas/knowledge', external: true },

  // ── 探索(4 项) ──
  { id: 'conversation', label: '对话', icon: 'fas fa-comments', section: 'explore', status: 'coming-soon', href: '/coming-soon?from=conversation', external: false },
  { id: 'favorites', label: '收藏', icon: 'fas fa-star', section: 'explore', status: 'coming-soon', href: '/coming-soon?from=favorites', external: false },
  { id: 'template', label: '模板广场', icon: 'fas fa-th-large', section: 'explore', status: 'coming-soon', href: '/coming-soon?from=template', external: false },
  { id: 'team-share', label: '团队共享', icon: 'fas fa-share-nodes', section: 'explore', status: 'coming-soon', href: '/coming-soon?from=team-share', external: false },

  // ── 配置中心(5 项,全 internal 跳 coming-soon) ──
  { id: 'plugin', label: '插件市场', icon: 'fas fa-puzzle-piece', section: 'config', status: 'coming-soon', href: '/coming-soon?from=plugin', external: false },
  { id: 'model', label: '模型管理', icon: 'fas fa-microchip', section: 'config', status: 'coming-soon', href: '/coming-soon?from=model', external: false },
  { id: 'channel', label: '通道管理', icon: 'fas fa-route', section: 'config', status: 'coming-soon', href: '/coming-soon?from=channel', external: false },
  { id: 'credential', label: '凭证管理', icon: 'fas fa-key', section: 'config', status: 'coming-soon', href: '/coming-soon?from=credential', external: false },
  { id: 'mcp', label: 'MCP 工具', icon: 'fas fa-plug', section: 'config', status: 'coming-soon', href: '/coming-soon?from=mcp', external: false },

  // ── 运维(3 项) ──
  { id: 'monitor', label: '监控', icon: 'fas fa-chart-line', section: 'ops', status: 'coming-soon', href: '/coming-soon?from=monitor', external: false },
  { id: 'logs', label: '日志', icon: 'fas fa-file-lines', section: 'ops', status: 'coming-soon', href: '/coming-soon?from=logs', external: false },
  { id: 'skill', label: '技能管理', icon: 'fas fa-wand-magic-sparkles', section: 'ops', status: 'coming-soon', href: '/coming-soon?from=skill', external: false },

  // ── 系统管理(6 项,全 external 跳 /admin/<sub>) ──
  { id: 'user-list', label: '用户列表', icon: 'fas fa-users', section: 'system', status: 'ready', href: '/admin/users', external: true },
  { id: 'user-audit', label: '用户审核', icon: 'fas fa-user-shield', section: 'system', status: 'ready', href: '/admin/users/audit', external: true },
  { id: 'role', label: '角色管理', icon: 'fas fa-id-badge', section: 'system', status: 'ready', href: '/admin/roles', external: true },
  { id: 'department', label: '部门管理', icon: 'fas fa-building', section: 'system', status: 'ready', href: '/admin/departments', external: true },
  { id: 'permission', label: '权限管理', icon: 'fas fa-lock', section: 'system', status: 'ready', href: '/admin/permissions', external: true },
  { id: 'data-permission', label: '数据权限', icon: 'fas fa-database', section: 'system', status: 'ready', href: '/admin/data-permissions', external: true },
];

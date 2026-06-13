export type MenuStatus = 'ready' | 'coming-soon';
export type MenuItem = { id: string; label: string; icon: string; section: string; status: MenuStatus; href: string };
export type MenuSection = { id: string; title: string };

export const SECTIONS: MenuSection[] = [
  { id: 'chat', title: '对话' },
  { id: 'workflow', title: '工作流' },
  { id: 'agent', title: 'Agent' },
  { id: 'knowledge', title: '知识库' },
  { id: 'system', title: '系统设置' },
];

export const MENU: MenuItem[] = [
  { id: 'dashboard', label: '控制台', icon: 'fas fa-gauge', section: 'chat', status: 'ready', href: '/' },
  { id: 'conversation', label: '对话', icon: 'fas fa-comments', section: 'chat', status: 'coming-soon', href: '/coming-soon?from=conversation' },
  { id: 'favorites', label: '收藏', icon: 'fas fa-star', section: 'chat', status: 'coming-soon', href: '/coming-soon?from=favorites' },
  { id: 'workflow-list', label: '工作流', icon: 'fas fa-project-diagram', section: 'workflow', status: 'ready', href: '/canvas/workflows' },
  { id: 'chatflow', label: 'Chatflow', icon: 'fas fa-comments-dollar', section: 'workflow', status: 'ready', href: '/canvas/chatflow' },
  { id: 'runs', label: '运行记录', icon: 'fas fa-play', section: 'workflow', status: 'ready', href: '/canvas/runs' },
  { id: 'agent-list', label: 'Agent 列表', icon: 'fas fa-robot', section: 'agent', status: 'coming-soon', href: '/coming-soon?from=agent-list' },
  { id: 'template', label: '模板广场', icon: 'fas fa-th-large', section: 'agent', status: 'coming-soon', href: '/coming-soon?from=template' },
  { id: 'knowledge', label: '知识库', icon: 'fas fa-book', section: 'knowledge', status: 'coming-soon', href: '/coming-soon?from=knowledge' },
  { id: 'team-share', label: '团队共享', icon: 'fas fa-share-nodes', section: 'knowledge', status: 'coming-soon', href: '/coming-soon?from=team-share' },
  { id: 'plugin', label: '插件市场', icon: 'fas fa-puzzle-piece', section: 'system', status: 'coming-soon', href: '/coming-soon?from=plugin' },
  { id: 'model', label: '模型管理', icon: 'fas fa-microchip', section: 'system', status: 'coming-soon', href: '/coming-soon?from=model' },
  { id: 'channel', label: '通道管理', icon: 'fas fa-route', section: 'system', status: 'coming-soon', href: '/coming-soon?from=channel' },
  { id: 'credential', label: '凭证管理', icon: 'fas fa-key', section: 'system', status: 'coming-soon', href: '/coming-soon?from=credential' },
  { id: 'skill', label: '技能管理', icon: 'fas fa-wand-magic-sparkles', section: 'system', status: 'coming-soon', href: '/coming-soon?from=skill' },
  { id: 'mcp', label: 'MCP 工具', icon: 'fas fa-plug', section: 'system', status: 'coming-soon', href: '/coming-soon?from=mcp' },
  { id: 'monitor', label: '监控', icon: 'fas fa-chart-line', section: 'system', status: 'coming-soon', href: '/coming-soon?from=monitor' },
  { id: 'logs', label: '日志', icon: 'fas fa-file-lines', section: 'system', status: 'coming-soon', href: '/coming-soon?from=logs' },
  { id: 'api', label: 'API', icon: 'fas fa-code', section: 'system', status: 'coming-soon', href: '/coming-soon?from=api' },
  { id: 'trace', label: '追踪', icon: 'fas fa-magnifying-glass-chart', section: 'system', status: 'coming-soon', href: '/coming-soon?from=trace' },
  { id: 'infra', label: '基础设施', icon: 'fas fa-server', section: 'system', status: 'coming-soon', href: '/coming-soon?from=infra' },
  { id: 'settings', label: '设置', icon: 'fas fa-gear', section: 'system', status: 'ready', href: '/canvas/settings' },
  { id: 'user-list', label: '用户列表', icon: 'fas fa-users', section: 'system', status: 'coming-soon', href: '/coming-soon?from=user-list' },
  { id: 'user-audit', label: '用户审计', icon: 'fas fa-user-shield', section: 'system', status: 'coming-soon', href: '/coming-soon?from=user-audit' },
  { id: 'role', label: '角色', icon: 'fas fa-id-badge', section: 'system', status: 'coming-soon', href: '/coming-soon?from=role' },
  { id: 'department', label: '部门', icon: 'fas fa-building', section: 'system', status: 'coming-soon', href: '/coming-soon?from=department' },
  { id: 'permission', label: '权限', icon: 'fas fa-lock', section: 'system', status: 'coming-soon', href: '/coming-soon?from=permission' },
  { id: 'data-permission', label: '数据权限', icon: 'fas fa-database', section: 'system', status: 'coming-soon', href: '/coming-soon?from=data-permission' },
  { id: 'system-config', label: '系统配置', icon: 'fas fa-sliders', section: 'system', status: 'coming-soon', href: '/coming-soon?from=system-config' },
  { id: 'billing', label: '计费', icon: 'fas fa-credit-card', section: 'system', status: 'coming-soon', href: '/coming-soon?from=billing' },
];
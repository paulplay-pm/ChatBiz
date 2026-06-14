// Dashboard 静态 mock 数据(V3 锁定,等 V4+ 接 API 后再迁)
export type DashboardMetric = { label: string; value: string | number; trend?: string };
export type QuickStartItem = {
  id: string;
  title: string;
  subtitle: string;
  icon: string; // font-awesome class
  href: string;
  external: boolean;
};
export type RecentAccess = { id: string; title: string; type: string; visitedAt: string };
export type RecentActivity = { id: string; text: string; at: string };

export const METRICS: DashboardMetric[] = [
  { label: '我的工作流', value: 12, trend: '+2 本周' },
  { label: '我的 Agent', value: 5, trend: '+1 本周' },
  { label: '今日调用', value: '2,456', trend: '+18% 较昨日' },
  { label: 'Token 消耗', value: '456K', trend: '+5% 较昨日' },
];

export const QUICK_STARTS: QuickStartItem[] = [
  {
    id: 'new-workflow',
    title: '新建工作流',
    subtitle: '从空白画布或模板开始,可视化编排',
    icon: 'fas fa-project-diagram',
    href: '/canvas/workflows',
    external: true,
  },
  {
    id: 'create-agent',
    title: '创建 Agent',
    subtitle: '绑定工具、记忆、提示词,快速上线',
    icon: 'fas fa-robot',
    href: '/canvas/agent', // spec 锁定:单数 agent
    external: true,
  },
  {
    id: 'upload-knowledge',
    title: '上传知识库',
    subtitle: '支持 PDF / Word / Markdown 自动解析',
    icon: 'fas fa-book',
    href: '/canvas/knowledge',
    external: true,
  },
  {
    id: 'start-conversation',
    title: '开始对话',
    subtitle: '与已发布的 Agent 实时对话测试',
    icon: 'fas fa-comments',
    href: '/coming-soon?from=conversation',
    external: false,
  },
];

export const RECENT_ACCESSES: RecentAccess[] = [
  { id: 'ra-1', title: '智能客服机器人', type: 'Agent', visitedAt: '10 分钟前' },
  { id: 'ra-2', title: '数据分析助手', type: '工作流', visitedAt: '1 小时前' },
  { id: 'ra-3', title: '产品知识库', type: '知识库', visitedAt: '昨天 16:24' },
];

export const RECENT_ACTIVITIES: RecentActivity[] = [
  { id: 'act-1', text: '工作流「销售数据分析」执行成功,耗时 3.2s', at: '5 分钟前' },
  { id: 'act-2', text: 'Agent「智能客服机器人」已发布到通道企微', at: '30 分钟前' },
];

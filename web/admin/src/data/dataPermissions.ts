// admin data permission mock data (V3 锁定,等 V4+ 接 API 后再迁)
export type RuleKind = 'personal' | 'department' | 'cross-department';
export type DataRule = {
  id: string;
  kind: RuleKind;
  title: string;
  description: string;
  icon: string;
  defaultSelected: boolean;
};

export type DataShare = {
  id: string;
  resourceName: string;
  resourceType: string;
  createdBy: string;
  department: string;
  scope: string; // 共享范围
};

// 3 规则卡(spec 锁定)
export const MOCK_RULES: DataRule[] = [
  {
    id: 'rule-personal',
    kind: 'personal',
    title: '个人数据',
    description: '仅本人可访问,默认范围最严格',
    icon: 'fas fa-user',
    defaultSelected: true,
  },
  {
    id: 'rule-department',
    kind: 'department',
    title: '部门数据',
    description: '本部门所有成员可访问,跨部门不可见',
    icon: 'fas fa-building',
    defaultSelected: false,
  },
  {
    id: 'rule-cross-dept',
    kind: 'cross-department',
    title: '跨部门共享',
    description: '显式授权后可被指定部门访问,需审批',
    icon: 'fas fa-share-alt',
    defaultSelected: false,
  },
];

// 4 共享记录(spec 锁定:销售数据分析工作流/智能客服 Agent/产品知识库/合同审核工作流)
export const MOCK_SHARES: DataShare[] = [
  {
    id: 's-1',
    resourceName: '销售数据分析工作流',
    resourceType: '工作流',
    createdBy: '张三',
    department: '技术部',
    scope: '运营部、产品部',
  },
  {
    id: 's-2',
    resourceName: '智能客服 Agent',
    resourceType: 'Agent',
    createdBy: '李四',
    department: '产品部',
    scope: '运营部',
  },
  {
    id: 's-3',
    resourceName: '产品知识库',
    resourceType: '知识库',
    createdBy: '王五',
    department: '运营部',
    scope: '全员',
  },
  {
    id: 's-4',
    resourceName: '合同审核工作流',
    resourceType: '工作流',
    createdBy: '张三',
    department: '技术部',
    scope: '法务部',
  },
];

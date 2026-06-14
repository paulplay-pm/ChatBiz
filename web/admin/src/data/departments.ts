// admin department mock data (V3 锁定,等 V4+ 接 API 后再迁)
export type DepartmentNode = {
  id: string;
  name: string;
  memberCount: number;
  memberAvatars: string[];
  children?: DepartmentNode[];
};

export const MOCK_DEPARTMENTS: DepartmentNode[] = [
  {
    id: 'd-tech',
    name: '技术部',
    memberCount: 12,
    memberAvatars: ['张', '赵', '钱', '黄'],
    children: [
      {
        id: 'd-tech-backend',
        name: '后端开发组',
        memberCount: 7,
        memberAvatars: ['张', '钱', '黄', '林'],
      },
      {
        id: 'd-tech-frontend',
        name: '前端开发组',
        memberCount: 5,
        memberAvatars: ['赵', '陈', '周'],
      },
    ],
  },
  {
    id: 'd-product',
    name: '产品部',
    memberCount: 5,
    memberAvatars: ['李', '孙', '吴'],
  },
  {
    id: 'd-ops',
    name: '运营部',
    memberCount: 4,
    memberAvatars: ['王', '冯', '蒋', '沈'],
  },
];

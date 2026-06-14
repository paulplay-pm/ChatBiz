// admin user mock data (V3 锁定,等 V4+ 接 API 后再迁)
export type UserStatus = 'active' | 'pending' | 'disabled';
export type UserRow = {
  id: string;
  name: string;
  email: string;
  avatar: string; // font-awesome / initial
  department: string;
  role: string;
  status: UserStatus;
  lastLogin: string;
};

export const MOCK_USERS: UserRow[] = [
  {
    id: 'u-1',
    name: '张三',
    email: 'zhangsan@chatbiz.com',
    avatar: '张',
    department: '技术部',
    role: '管理员',
    status: 'active',
    lastLogin: '5 分钟前',
  },
  {
    id: 'u-2',
    name: '李四',
    email: 'lisi@chatbiz.com',
    avatar: '李',
    department: '产品部',
    role: '开发者',
    status: 'active',
    lastLogin: '1 小时前',
  },
  {
    id: 'u-3',
    name: '王五',
    email: 'wangwu@chatbiz.com',
    avatar: '王',
    department: '运营部',
    role: '普通用户',
    status: 'pending',
    lastLogin: '尚未登录',
  },
];

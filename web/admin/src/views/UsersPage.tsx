import { MOCK_USERS } from '@/data/users';

const COLUMNS = [
  '用户',
  '部门',
  '角色',
  '状态',
  '最后登录',
  '操作',
];

const STATUS_TAG: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  pending: 'bg-amber-100 text-amber-700',
  disabled: 'bg-ink-100 text-ink-500',
};

const STATUS_LABEL: Record<string, string> = {
  active: '正常',
  pending: '待审核',
  disabled: '已禁用',
};

export function UsersPage(): JSX.Element {
  return (
    <div data-testid="users-page" className="space-y-4">
      <h1 className="text-xl font-semibold text-ink-900">用户列表</h1>
      {/* 工具栏 */}
      <div data-testid="users-toolbar" className="flex items-center gap-2">
        <input
          type="search"
          placeholder="搜索姓名 / 邮箱"
          className="px-3 h-9 rounded-lg border border-ink-200 text-sm flex-1 max-w-xs"
        />
        <button className="px-3 h-9 rounded-lg border border-ink-200 text-sm text-ink-700">
          批量导入
        </button>
        <button className="px-3 h-9 rounded-lg border border-ink-200 text-sm text-ink-700">
          导出
        </button>
        <button
          data-testid="add-user"
          className="px-3 h-9 rounded-lg bg-brand-500 text-white text-sm font-medium"
        >
          + 添加用户
        </button>
      </div>
      {/* 表格 */}
      <div className="rounded-xl bg-white border border-ink-200 overflow-hidden">
        <table data-testid="users-table" className="w-full text-sm">
          <thead>
            <tr className="bg-ink-50 text-ink-500 text-left">
              {COLUMNS.map((c) => (
                <th key={c} className="px-4 py-3 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MOCK_USERS.map((u) => (
              <tr
                key={u.id}
                data-testid="user-row"
                data-user-id={u.id}
                className="border-t border-ink-100 hover:bg-ink-50"
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-white text-xs flex items-center justify-center font-medium">
                      {u.avatar}
                    </div>
                    <div>
                      <div className="text-ink-900">{u.name}</div>
                      <div className="text-xs text-ink-500">{u.email}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-ink-700">{u.department}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    data-testid="user-status"
                    className={`px-2 py-0.5 rounded text-xs ${STATUS_TAG[u.status]}`}
                  >
                    {STATUS_LABEL[u.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-500 text-xs">{u.lastLogin}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    <button className="px-2 h-7 text-xs text-ink-700 border border-ink-200 rounded">
                      编辑
                    </button>
                    <button className="px-2 h-7 text-xs text-red-600 border border-ink-200 rounded">
                      禁用
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { MOCK_USERS } from '@/data/users';

const PENDING = MOCK_USERS.filter((u) => u.status === 'pending');

export function UserAuditPage(): JSX.Element {
  return (
    <div data-testid="user-audit-page" className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-ink-900">用户审核</h1>
        <span
          data-testid="pending-badge"
          className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium"
        >
          {PENDING.length} 待审核
        </span>
      </div>

      {PENDING.length === 0 ? (
        <div className="rounded-xl bg-white border border-ink-200 p-8 text-center text-sm text-ink-500">
          当前无待审核用户
        </div>
      ) : (
        <div className="rounded-xl bg-white border border-ink-200 overflow-hidden">
          <table data-testid="audit-table" className="w-full text-sm">
            <thead>
              <tr className="bg-ink-50 text-ink-500 text-left">
                <th className="px-4 py-3 font-medium">用户</th>
                <th className="px-4 py-3 font-medium">部门</th>
                <th className="px-4 py-3 font-medium">角色</th>
                <th className="px-4 py-3 font-medium">注册时间</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {PENDING.map((u) => (
                <tr
                  key={u.id}
                  data-testid="audit-row"
                  className="border-t border-ink-100"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 text-white text-xs flex items-center justify-center font-medium">
                        {u.avatar}
                      </div>
                      <div>
                        <div className="text-ink-900">{u.name}</div>
                        <div className="text-xs text-ink-500">{u.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{u.department}</td>
                  <td className="px-4 py-3 text-ink-700">{u.role}</td>
                  <td className="px-4 py-3 text-ink-500 text-xs">2026-06-13</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button
                        data-testid="audit-approve"
                        className="px-2 h-7 text-xs text-white bg-green-500 rounded"
                      >
                        通过
                      </button>
                      <button
                        data-testid="audit-reject"
                        className="px-2 h-7 text-xs text-white bg-red-500 rounded"
                      >
                        拒绝
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

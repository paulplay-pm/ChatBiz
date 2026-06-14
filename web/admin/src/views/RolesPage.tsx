import { useState } from 'react';
import { MOCK_ROLES, type RoleCardData } from '@/data/roles';

const MATRIX_ACTIONS: { key: keyof RoleCardData['matrix']['workflow']; label: string }[] = [
  { key: 'view', label: '查看' },
  { key: 'create', label: '创建' },
  { key: 'edit', label: '编辑' },
  { key: 'delete', label: '删除' },
  { key: 'publish', label: '发布' },
];

const MATRIX_ROWS: { key: keyof RoleCardData['matrix']; label: string }[] = [
  { key: 'workflow', label: '工作流' },
  { key: 'conversation', label: '对话' },
];

export function RolesPage(): JSX.Element {
  const [selectedRoleId, setSelectedRoleId] = useState<string>(MOCK_ROLES[0]?.id ?? '');
  const selected = MOCK_ROLES.find((r) => r.id === selectedRoleId);

  return (
    <div data-testid="roles-page" className="space-y-4">
      <h1 className="text-xl font-semibold text-ink-900">角色管理</h1>

      {/* 顶部 info bar */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700">
        一个用户可拥有多个角色,最终权限为所有角色权限的并集。点击「管理成员」查看和分配角色。
      </div>

      {/* 4 角色卡 */}
      <div className="grid grid-cols-4 gap-4">
        {MOCK_ROLES.map((role) => {
          const isActive = role.id === selectedRoleId;
          return (
            <div
              key={role.id}
              data-testid="role-card"
              data-role-id={role.id}
              onClick={() => setSelectedRoleId(role.id)}
              className={`rounded-xl bg-white border p-4 cursor-pointer transition-shadow hover:shadow-md ${
                isActive ? 'border-brand-500 ring-2 ring-brand-200' : 'border-ink-200'
              }`}
            >
              <i className={`${role.icon} text-2xl text-brand-500 mb-2 block`} />
              <div className="font-medium text-ink-900">{role.name}</div>
              <div className="text-xs text-ink-500 mt-1 mb-3 h-8">{role.description}</div>
              <div className="flex -space-x-2">
                {role.memberAvatars.slice(0, 3).map((a, i) => (
                  <div
                    key={i}
                    className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-300 to-brand-500 text-white text-xs flex items-center justify-center border-2 border-white"
                  >
                    {a}
                  </div>
                ))}
                {role.memberAvatars.length > 3 && (
                  <div className="w-7 h-7 rounded-full bg-ink-200 text-ink-600 text-xs flex items-center justify-center border-2 border-white">
                    +{role.memberAvatars.length - 3}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 权限矩阵 */}
      {selected && (
        <div data-testid="role-matrix" className="rounded-xl bg-white border border-ink-200 p-4">
          <h2 className="font-medium text-ink-900 mb-3">
            {selected.name} — 权限矩阵
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-500">
                <th className="text-left py-2 pr-4">模块</th>
                {MATRIX_ACTIONS.map((a) => (
                  <th key={a.key} className="text-center py-2 px-2">
                    {a.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MATRIX_ROWS.map((row) => (
                <tr key={row.key} className="border-t border-ink-100">
                  <td className="py-2 pr-4 text-ink-900">{row.label}</td>
                  {MATRIX_ACTIONS.map((a) => {
                    const allowed = selected.matrix[row.key][a.key];
                    return (
                      <td key={a.key} className="text-center py-2 px-2">
                        {allowed ? (
                          <i
                            data-testid="matrix-check"
                            className="fas fa-check text-green-500"
                          />
                        ) : (
                          <span
                            data-testid="matrix-deny"
                            className="text-ink-300"
                          >
                            —
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

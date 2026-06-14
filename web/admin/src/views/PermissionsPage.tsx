import { useState } from 'react';
import {
  MOCK_MODULES,
  MOCK_PERMISSIONS,
  PERMISSION_ACTIONS,
  ROLE_OPTIONS,
  type RoleOption,
  type PermissionAction,
} from '@/data/permissions';

const ACTION_LABEL: Record<PermissionAction, string> = {
  view: '查看',
  create: '创建',
  edit: '编辑',
  delete: '删除',
  publish: '发布',
  execute: '执行',
};

export function PermissionsPage(): JSX.Element {
  const [role, setRole] = useState<RoleOption>('super-admin');
  const [readOnly, setReadOnly] = useState<boolean>(true);
  const matrix = MOCK_PERMISSIONS[role];

  return (
    <div data-testid="permissions-page" className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink-900">权限管理</h1>
        <div className="flex items-center gap-3">
          {/* 角色 dropdown */}
          <select
            data-testid="role-select"
            value={role}
            onChange={(e) => setRole(e.target.value as RoleOption)}
            className="h-9 rounded-lg border border-ink-200 px-3 text-sm"
          >
            {ROLE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {/* 只读 toggle */}
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              data-testid="readonly-toggle"
              type="checkbox"
              checked={readOnly}
              onChange={(e) => setReadOnly(e.target.checked)}
              defaultChecked
            />
            只读查看
          </label>
        </div>
      </div>

      <div className="rounded-xl bg-white border border-ink-200 overflow-hidden">
        <table data-testid="permission-matrix" className="w-full text-sm">
          <thead>
            <tr className="bg-ink-50 text-ink-500">
              <th className="text-left px-4 py-3 font-medium">功能模块 / 权限点</th>
              {PERMISSION_ACTIONS.map((a) => (
                <th key={a} className="text-center px-3 py-3 font-medium">
                  {ACTION_LABEL[a]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MOCK_MODULES.map((mod) => (
              <>
                <tr key={`mod-${mod.id}`} className="bg-ink-50/50">
                  <td
                    colSpan={PERMISSION_ACTIONS.length + 1}
                    className="px-4 py-2 text-xs font-semibold text-ink-700"
                  >
                    {mod.name}
                  </td>
                </tr>
                {mod.points.map((pt) => (
                  <tr
                    key={pt.id}
                    data-testid="permission-row"
                    data-point-id={pt.id}
                    className="border-t border-ink-100"
                  >
                    <td className="px-4 py-2 pl-8 text-ink-700">{pt.name}</td>
                    {PERMISSION_ACTIONS.map((a) => {
                      const allowed = matrix[pt.id]?.[a] ?? false;
                      return (
                        <td key={a} className="text-center px-3 py-2">
                          <input
                            data-testid="permission-cell"
                            data-allowed={allowed ? 'true' : 'false'}
                            type="checkbox"
                            checked={allowed}
                            disabled={readOnly}
                            readOnly
                            className="w-4 h-4"
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

import { MOCK_RULES, MOCK_SHARES } from '@/data/dataPermissions';

export function DataPermissionsPage(): JSX.Element {
  return (
    <div data-testid="data-permissions-page" className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink-900">数据权限</h1>
        <span
          data-testid="dept-isolation-badge"
          className="px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-xs text-blue-700"
        >
          基于部门的数据隔离
        </span>
      </div>

      {/* 3 规则卡 */}
      <div className="grid grid-cols-3 gap-4">
        {MOCK_RULES.map((rule) => (
          <div
            key={rule.id}
            data-testid="data-rule-card"
            data-rule-kind={rule.kind}
            className={`rounded-xl bg-white border p-4 cursor-pointer transition-shadow hover:shadow-md ${
              rule.defaultSelected
                ? 'border-brand-500 ring-2 ring-brand-200'
                : 'border-ink-200'
            }`}
          >
            <i className={`${rule.icon} text-2xl text-brand-500 mb-2 block`} />
            <div className="font-medium text-ink-900">{rule.title}</div>
            <div className="text-xs text-ink-500 mt-1">{rule.description}</div>
            {rule.defaultSelected && (
              <span className="inline-block mt-2 text-[10px] px-2 py-0.5 rounded-full bg-brand-50 text-brand-600">
                默认
              </span>
            )}
          </div>
        ))}
      </div>

      {/* 共享记录表 */}
      <div className="rounded-xl bg-white border border-ink-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-ink-100 flex items-center justify-between">
          <h2 className="font-medium text-ink-900">数据共享记录</h2>
          <span className="text-xs text-ink-500">共 {MOCK_SHARES.length} 条</span>
        </div>
        <table data-testid="shares-table" className="w-full text-sm">
          <thead>
            <tr className="bg-ink-50 text-ink-500 text-left">
              <th className="px-4 py-3 font-medium">资源名称</th>
              <th className="px-4 py-3 font-medium">类型</th>
              <th className="px-4 py-3 font-medium">创建者</th>
              <th className="px-4 py-3 font-medium">所属部门</th>
              <th className="px-4 py-3 font-medium">共享范围</th>
              <th className="px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_SHARES.map((s) => (
              <tr
                key={s.id}
                data-testid="share-row"
                className="border-t border-ink-100"
              >
                <td className="px-4 py-3 text-ink-900">{s.resourceName}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">
                    {s.resourceType}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-700">{s.createdBy}</td>
                <td className="px-4 py-3 text-ink-700">{s.department}</td>
                <td className="px-4 py-3 text-ink-700 text-xs">{s.scope}</td>
                <td className="px-4 py-3">
                  <button className="text-xs text-brand-600 hover:underline">查看</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

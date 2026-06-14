import { Fragment } from 'react';
import { MOCK_DEPARTMENTS, type DepartmentNode } from '@/data/departments';

function renderNode(node: DepartmentNode, depth: number): JSX.Element {
  return (
    <Fragment key={node.id}>
      <div
        data-testid="dept-node"
        data-dept-id={node.id}
        className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-ink-50"
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
      >
        <i
          className={`fas ${
            depth === 0 ? 'fa-building text-brand-500' : 'fa-code-branch text-ink-400'
          } text-sm w-4 text-center`}
        />
        <span className="text-sm text-ink-900 flex-1">{node.name}</span>
        <div className="flex -space-x-2">
          {node.memberAvatars.slice(0, 3).map((a, i) => (
            <div
              key={i}
              className="w-6 h-6 rounded-full bg-gradient-to-br from-brand-300 to-brand-500 text-white text-[10px] flex items-center justify-center border-2 border-white"
            >
              {a}
            </div>
          ))}
        </div>
        <span
          data-testid="dept-member-count"
          className="text-xs px-2 py-0.5 rounded-full bg-ink-100 text-ink-600"
        >
          +{node.memberCount}
        </span>
      </div>
      {node.children?.map((child) => renderNode(child, depth + 1))}
    </Fragment>
  );
}

export function DepartmentsPage(): JSX.Element {
  return (
    <div data-testid="departments-page" className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink-900">部门管理</h1>
        <button
          data-testid="add-department"
          className="px-3 h-9 rounded-lg bg-brand-500 text-white text-sm font-medium"
        >
          + 添加部门
        </button>
      </div>
      <div className="rounded-xl bg-white border border-ink-200 p-2">
        {MOCK_DEPARTMENTS.map((d) => renderNode(d, 0))}
      </div>
    </div>
  );
}

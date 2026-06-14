import { useState } from 'react';
import { NodeSearchModal } from './NodeSearchModal';

const CATEGORIES = [
  { label: '开始 / 结束', items: [
    { type: 'start', icon: '▶️', name: '开始' },
    { type: 'end', icon: '⏹️', name: '结束' },
  ]},
  { label: '业务节点', items: [
    { type: 'llm', icon: '🤖', name: 'LLM' },
    { type: 'knowledge', icon: '📚', name: '知识检索' },
    { type: 'agent', icon: '🧠', name: 'Agent' },
    { type: 'code', icon: '💻', name: '代码执行' },
    { type: 'http', icon: '🌐', name: 'HTTP 请求' },
  ]},
  { label: '控制节点', items: [
    { type: 'condition', icon: '🔀', name: '条件分支' },
    { type: 'loop', icon: '🔁', name: '循环' },
    { type: 'iterate', icon: '🔂', name: '迭代' },
    { type: 'variable_assign', icon: '📝', name: '变量赋值' },
  ]},
  { label: '集成节点', items: [
    { type: 'approval', icon: '✋', name: '人工审批' },
    { type: 'subflow', icon: '🔗', name: '子流程' },
    { type: 'extract', icon: '🔍', name: '参数提取' },
  ]},
];

export function NodePanel() {
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="w-[220px] p-3 bg-ink-50 border-r border-ink-200 h-full overflow-auto">
      <div className="font-semibold text-ink-900 mb-2">节点</div>
      <div className="text-xs text-ink-500 mb-3">按 / 搜索</div>
      {CATEGORIES.map((cat) => (
        <div key={cat.label} className="mb-3">
          <div className="text-xs text-ink-500 mb-1">{cat.label}</div>
          {cat.items.map((n) => (
            <div
              key={n.type}
              data-node-type={n.type}
              className="mb-1 p-2 bg-white border border-ink-200 rounded cursor-grab hover:border-brand-500 text-sm flex items-center gap-2"
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/chatbiz-node', n.type);
              }}
              onClick={() => setSearchOpen(true)}
            >
              <span>{n.icon}</span>
              <span className="flex-1">{n.name}</span>
              <span className="rounded px-1.5 py-0.5 text-[10px] bg-ink-100 text-ink-700">{n.type}</span>
            </div>
          ))}
        </div>
      ))}
      <NodeSearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}

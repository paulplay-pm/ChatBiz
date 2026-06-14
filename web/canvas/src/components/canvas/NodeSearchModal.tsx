import { useState, useMemo, useEffect } from 'react';
import { Modal, Input } from 'ui/index';

const ALL_NODES = [
  { type: 'start', icon: '▶️', name: '开始' },
  { type: 'end', icon: '⏹️', name: '结束' },
  { type: 'llm', icon: '🤖', name: 'LLM' },
  { type: 'knowledge', icon: '📚', name: '知识检索' },
  { type: 'agent', icon: '🧠', name: 'Agent' },
  { type: 'code', icon: '💻', name: '代码执行' },
  { type: 'http', icon: '🌐', name: 'HTTP 请求' },
  { type: 'condition', icon: '🔀', name: '条件分支' },
  { type: 'loop', icon: '🔁', name: '循环' },
  { type: 'iterate', icon: '🔂', name: '迭代' },
  { type: 'variable_assign', icon: '📝', name: '变量赋值' },
  { type: 'approval', icon: '✋', name: '人工审批' },
  { type: 'subflow', icon: '🔗', name: '子流程' },
  { type: 'extract', icon: '🔍', name: '参数提取' },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function NodeSearchModal({ open, onClose }: Props) {
  const [search, setSearch] = useState('');
  const filtered = useMemo(
    () => ALL_NODES.filter((n) => n.name.includes(search) || n.type.includes(search.toLowerCase())),
    [search],
  );

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <Modal open={open} onClose={onClose} title="搜索节点">
      <div className="mb-3">
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="输入节点名称或类型"
        />
      </div>
      <div className="space-y-1 max-h-96 overflow-auto">
        {filtered.length === 0 ? (
          <div className="text-sm text-ink-500 text-center py-4">无匹配节点</div>
        ) : (
          filtered.map((n) => (
            <div
              key={n.type}
              className="cursor-grab flex items-center gap-2 p-2 rounded hover:bg-ink-50 text-sm border border-transparent hover:border-ink-200"
              draggable
              onDragStart={(e) => e.dataTransfer.setData('application/chatbiz-node', n.type)}
            >
              <span>{n.icon}</span>
              <span className="flex-1">{n.name}</span>
              <span className="rounded px-1.5 py-0.5 text-xs bg-ink-100 text-ink-700">{n.type}</span>
            </div>
          ))
        )}
      </div>
    </Modal>
  );
}

import { Modal, Input, List, Tag } from 'antd';
import { useState, useMemo, useEffect } from 'react';

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
    <Modal title="搜索节点" open={open} onCancel={onClose} footer={null} width={480}>
      <Input
        autoFocus
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="输入节点名称或类型"
        style={{ marginBottom: 12 }}
      />
      <List
        dataSource={filtered}
        renderItem={(n) => (
          <List.Item
            key={n.type}
            style={{ cursor: 'pointer' }}
            draggable
            onDragStart={(e) => e.dataTransfer.setData('application/chatbiz-node', n.type)}
          >
            <span style={{ marginRight: 8 }}>{n.icon}</span>
            {n.name}
            <Tag style={{ marginLeft: 8 }}>{n.type}</Tag>
          </List.Item>
        )}
      />
    </Modal>
  );
}

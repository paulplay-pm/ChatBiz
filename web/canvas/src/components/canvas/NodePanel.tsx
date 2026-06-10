import { Card, Tag } from 'antd';
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
    <div style={{ width: 220, padding: 12, background: '#fafafa', borderRight: '1px solid #f0f0f0', height: '100%', overflow: 'auto' }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>节点</div>
      <div style={{ color: '#999', fontSize: 12, marginBottom: 12 }}>按 / 搜索</div>
      {CATEGORIES.map((cat) => (
        <div key={cat.label} style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#999', marginBottom: 4 }}>{cat.label}</div>
          {cat.items.map((n) => (
            <Card
              key={n.type}
              size="small"
              style={{ marginBottom: 4, cursor: 'grab' }}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData('application/chatbiz-node', n.type);
              }}
              onClick={() => setSearchOpen(true)}
            >
              <span style={{ marginRight: 4 }}>{n.icon}</span>
              {n.name}
              <Tag style={{ marginLeft: 4, fontSize: 10 }}>{n.type}</Tag>
            </Card>
          ))}
        </div>
      ))}
      <NodeSearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}

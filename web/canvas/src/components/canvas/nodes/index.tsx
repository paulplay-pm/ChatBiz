import { Handle, Position, NodeProps } from '@xyflow/react';
import { NodeStatus } from '@/store/useCanvasEditStore';

interface NodeMeta {
  icon: string;
  label: string;
  summary: (config: any) => string;
  statusColor: Record<NodeStatus, string>;
}

const STATUS_COLORS: Record<NodeStatus, string> = {
  pending: '#d9d9d9',
  running: '#1890ff',
  completed: '#52c41a',
  failed: '#ff4d4f',
  skipped: '#faad14',
};

const META: Record<string, NodeMeta> = {
  start: { icon: '▶️', label: '开始', summary: (c) => c.name || '开始节点', statusColor: STATUS_COLORS },
  end: { icon: '⏹️', label: '结束', summary: (c) => c.output_keys?.join(', ') || '结束', statusColor: STATUS_COLORS },
  variable_assign: { icon: '📝', label: '变量赋值', summary: (c) => Object.keys(c.vars || {}).join(', ') || '变量赋值', statusColor: STATUS_COLORS },
  condition: { icon: '🔀', label: '条件分支', summary: (c) => c.expression || '条件表达式', statusColor: STATUS_COLORS },
  llm: { icon: '🤖', label: 'LLM', summary: (c) => `${c.model || '未配模型'} · t=${c.temperature ?? 0.7}`, statusColor: STATUS_COLORS },
  knowledge: { icon: '📚', label: '知识检索', summary: (c) => `${c.knowledge_base_id || 'kb'} · top_k=${c.top_k ?? 5}`, statusColor: STATUS_COLORS },
  agent: { icon: '🧠', label: 'Agent', summary: (c) => `${c.agent_id || 'agent'} · max=${c.max_iterations ?? 10}`, statusColor: STATUS_COLORS },
  http: { icon: '🌐', label: 'HTTP', summary: (c) => `${c.method || 'GET'} ${(c.url || '').slice(0, 20)}`, statusColor: STATUS_COLORS },
  code: { icon: '💻', label: '代码', summary: (c) => `${c.language || 'python'} · timeout=${c.timeout_s ?? 30}s`, statusColor: STATUS_COLORS },
  approval: { icon: '✋', label: '人工审批', summary: (c) => `→ ${c.approver_user_id || '?'} · ${c.timeout_hours ?? 24}h`, statusColor: STATUS_COLORS },
  loop: { icon: '🔁', label: '循环', summary: (c) => `max=${c.max_iterations ?? 10}`, statusColor: STATUS_COLORS },
  iterate: { icon: '🔂', label: '迭代', summary: (c) => `${c.input_array || 'arr'} · conc=${c.concurrency ?? 1}`, statusColor: STATUS_COLORS },
  subflow: { icon: '🔗', label: '子流程', summary: (c) => c.sub_workflow_id || 'sub', statusColor: STATUS_COLORS },
  extract: { icon: '🔍', label: '参数提取', summary: (c) => c.source?.slice(0, 20) || 'extract', statusColor: STATUS_COLORS },
};

const ALL_TYPES = Object.keys(META);

export function NodeWrapper({ type, data, selected }: NodeProps) {
  const nodeData = (data ?? {}) as { config?: Record<string, unknown>; status?: NodeStatus };
  const meta = META[type || 'start'] ?? META.start;
  const config = nodeData.config || {};
  const status: NodeStatus = nodeData.status || 'pending';
  const borderColor = selected ? '#1890ff' : (meta?.statusColor[status] || '#d9d9d9');

  return (
    <div
      style={{
        padding: 8,
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        background: '#fff',
        minWidth: 180,
        maxWidth: 240,
        fontSize: 12,
      }}
    >
      {type !== 'start' && <Handle type="target" position={Position.Left} />}
      <div style={{ fontWeight: 600, marginBottom: 4 }}>
        {meta?.icon} {meta?.label}
      </div>
      <div style={{ color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {meta?.summary(config)}
      </div>
      {type !== 'end' && <Handle type="source" position={Position.Right} />}
    </div>
  );
}

export const nodeTypes = ALL_TYPES.reduce((acc, t) => {
  acc[t] = NodeWrapper;
  return acc;
}, {} as Record<string, React.ComponentType<NodeProps>>);

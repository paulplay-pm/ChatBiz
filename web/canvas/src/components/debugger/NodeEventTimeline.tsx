import { Timeline, Tag, Typography } from 'antd';
import {
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import type React from 'react';

export interface NodeEvent {
  id: number;
  node_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  error_class: string | null;
  error_message: string | null;
}

const statusIcon: Record<string, React.ReactNode> = {
  running: <ClockCircleOutlined style={{ color: '#1890ff' }} />,
  completed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  failed: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
  skipped: <MinusCircleOutlined style={{ color: '#faad14' }} />,
  pending: <ClockCircleOutlined style={{ color: '#d9d9d9' }} />,
};

const statusColor: Record<string, string> = {
  running: 'blue',
  completed: 'green',
  failed: 'red',
  skipped: 'gold',
  pending: 'default',
};

interface Props {
  events: NodeEvent[];
  filter?: string;
}

export function NodeEventTimeline({ events, filter }: Props) {
  const filtered = filter ? events.filter((e) => e.status === filter) : events;
  const { Text } = Typography;

  return (
    <Timeline>
      {filtered.map((ev) => (
        <Timeline.Item key={ev.id} dot={statusIcon[ev.status] || statusIcon.pending}>
          <div>
            <Tag color={statusColor[ev.status] || 'default'}>{ev.status}</Tag>
            <Text strong>{ev.node_id}</Text>
          </div>
          <div style={{ fontSize: 12, color: '#999' }}>
            {ev.started_at ? new Date(ev.started_at).toLocaleTimeString() : '—'}
            {' → '}
            {ev.ended_at ? new Date(ev.ended_at).toLocaleTimeString() : '进行中'}
          </div>
          {ev.error_class && (
            <div style={{ fontSize: 12, color: '#ff4d4f', marginTop: 4 }}>
              错误: {ev.error_class} — {ev.error_message}
            </div>
          )}
        </Timeline.Item>
      ))}
    </Timeline>
  );
}

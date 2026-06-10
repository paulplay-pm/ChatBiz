import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tag, Descriptions, Spin, Result, Select } from 'antd';
import { api } from '@/lib/apiClient';
import { useRunEvents } from '@/hooks/useRunEvents';
import { NodeEventTimeline, NodeEvent } from '@/components/debugger/NodeEventTimeline';
import { RetryCancelButtons } from '@/components/debugger/RetryCancelButtons';

interface RunData {
  run_id: string;
  workflow_id: string;
  workflow_version: number;
  thread_id: string;
  mode: string;
  status: string;
  started_by: string;
  started_at: string | null;
  ended_at: string | null;
  error_class: string | null;
  error_message: string | null;
  events: NodeEvent[];
}

const statusTagColor: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  paused: 'warning',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
};

export default function RunDebuggerPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunData | null>(null);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState<string | undefined>();

  useRunEvents(runId || null);

  useEffect(() => {
    if (!runId) return;
    api.get<RunData>(`/runs/${runId}`)
      .then((r) => {
        setRun(r.data);
        setLoading(false);
      })
      .catch((e: unknown) => {
        const status = (e as { response?: { status?: number } }).response?.status;
        if (status === 403) {
          navigate('/403');
        }
        setLoading(false);
      });
  }, [runId, navigate]);

  if (loading) return <Spin />;
  if (!run) return <Result status="404" title="运行不存在" subTitle={`run_id: ${runId}`} />;

  return (
    <div>
      <Card title={`运行: ${runId?.slice(0, 8)}...`} style={{ marginBottom: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="状态">
            <Tag color={statusTagColor[run.status] || 'default'}>{run.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="模式">{run.mode}</Descriptions.Item>
          <Descriptions.Item label="启动者">{run.started_by}</Descriptions.Item>
          <Descriptions.Item label="启动时间">
            {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="结束时间">
            {run.ended_at ? new Date(run.ended_at).toLocaleString() : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="thread_id">{run.thread_id?.slice(0, 12)}...</Descriptions.Item>
        </Descriptions>
        {run.error_class && (
          <div style={{ marginTop: 12, padding: 12, background: '#fff2f0', borderRadius: 8, color: '#ff4d4f' }}>
            [{run.error_class}] {run.error_message}
          </div>
        )}
        <div style={{ marginTop: 16 }}>
          <RetryCancelButtons workflowId={run.workflow_id} runId={run.run_id} status={run.status} />
        </div>
      </Card>

      <Card
        title="节点事件"
        extra={
          <Select
            placeholder="过滤状态"
            value={eventFilter}
            onChange={setEventFilter}
            allowClear
            style={{ width: 120 }}
          >
            <Select.Option value="running">running</Select.Option>
            <Select.Option value="completed">completed</Select.Option>
            <Select.Option value="failed">failed</Select.Option>
            <Select.Option value="skipped">skipped</Select.Option>
          </Select>
        }
      >
        <NodeEventTimeline events={run.events || []} filter={eventFilter} />
      </Card>
    </div>
  );
}

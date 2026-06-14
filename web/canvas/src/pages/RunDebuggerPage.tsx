import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from 'ui/index';
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

const statusTagColors: Record<string, string> = {
  pending: 'bg-ink-100 text-ink-700',
  running: 'bg-blue-100 text-blue-700',
  paused: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-ink-100 text-ink-700',
};

export default function RunDebuggerPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunData | null>(null);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState<string>('');

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

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-ink-500 text-sm">
        <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        加载运行…
      </div>
    );
  }
  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <h1 className="text-4xl font-semibold text-ink-900 mb-2">运行不存在</h1>
        <p className="text-sm text-ink-500 mb-4">run_id: {runId}</p>
        <button
          onClick={() => navigate('/workflows')}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-sm"
        >
          回工作流
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-base font-semibold text-ink-900 mb-3">
          运行: {runId?.slice(0, 8)}...
        </h2>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div>
            <div className="text-xs text-ink-500">状态</div>
            <span className={`inline-block rounded px-2 py-0.5 text-xs ${statusTagColors[run.status] || 'bg-ink-100 text-ink-700'}`}>
              {run.status}
            </span>
          </div>
          <div>
            <div className="text-xs text-ink-500">模式</div>
            <div className="text-ink-900">{run.mode}</div>
          </div>
          <div>
            <div className="text-xs text-ink-500">启动者</div>
            <div className="text-ink-900">{run.started_by}</div>
          </div>
          <div>
            <div className="text-xs text-ink-500">启动时间</div>
            <div className="text-ink-900">{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</div>
          </div>
          <div>
            <div className="text-xs text-ink-500">结束时间</div>
            <div className="text-ink-900">{run.ended_at ? new Date(run.ended_at).toLocaleString() : '—'}</div>
          </div>
          <div>
            <div className="text-xs text-ink-500">thread_id</div>
            <div className="text-ink-900">{run.thread_id?.slice(0, 12)}...</div>
          </div>
        </div>
        {run.error_class && (
          <div className="mt-3 p-3 bg-red-50 rounded-lg text-red-600 text-sm">
            [{run.error_class}] {run.error_message}
          </div>
        )}
        <div className="mt-4">
          <RetryCancelButtons workflowId={run.workflow_id} />
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-ink-900">节点事件</h3>
          <select
            value={eventFilter}
            onChange={(e) => setEventFilter(e.target.value)}
            className="px-2 py-1 rounded border border-ink-200 text-sm w-32 focus:outline-none focus:border-brand-500"
          >
            <option value="">全部状态</option>
            <option value="running">running</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="skipped">skipped</option>
          </select>
        </div>
        <NodeEventTimeline events={run.events || []} filter={eventFilter || undefined} />
      </Card>
    </div>
  );
}

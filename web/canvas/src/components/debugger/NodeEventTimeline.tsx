import { Card, StatusDot } from 'ui/index';

export interface NodeEvent {
  id: number;
  node_id: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  error_class: string | null;
  error_message: string | null;
}

// Map canvas runtime statuses → ui StatusDot statuses.
const statusToDot: Record<string, 'running' | 'success' | 'error' | 'idle' | 'pending'> = {
  running: 'running',
  completed: 'success',
  failed: 'error',
  skipped: 'pending',
  pending: 'pending',
};

const statusColors: Record<string, string> = {
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  skipped: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-ink-100 text-ink-700',
};

interface Props {
  events: NodeEvent[];
  filter?: string;
}

export function NodeEventTimeline({ events, filter }: Props) {
  const filtered = filter ? events.filter((e) => e.status === filter) : events;

  return (
    <Card>
      <h3 className="text-sm font-semibold text-ink-900 mb-3">事件时间线</h3>
      {filtered.length === 0 ? (
        <div className="text-sm text-ink-500 text-center py-4">无事件</div>
      ) : (
        <ol className="space-y-3">
          {filtered.map((ev) => (
            <li key={ev.id} className="flex items-start gap-2 text-sm">
              <div className="mt-1.5 flex-shrink-0">
                <StatusDot status={statusToDot[ev.status] || 'idle'} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`inline-block rounded px-2 py-0.5 text-xs ${statusColors[ev.status] || 'bg-ink-100 text-ink-700'}`}>
                    {ev.status}
                  </span>
                  <span className="font-semibold text-ink-900">{ev.node_id}</span>
                </div>
                <div className="text-xs text-ink-500 mt-0.5">
                  {ev.started_at ? new Date(ev.started_at).toLocaleTimeString() : '—'}
                  {' → '}
                  {ev.ended_at ? new Date(ev.ended_at).toLocaleTimeString() : '进行中'}
                </div>
                {ev.error_class && (
                  <div className="text-xs text-red-500 mt-1">
                    错误: {ev.error_class} — {ev.error_message}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

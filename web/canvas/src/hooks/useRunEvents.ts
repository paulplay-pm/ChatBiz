import { useEffect, useRef } from 'react';
import { useCanvasEditStore, NodeStatus } from '@/store/useCanvasEditStore';

export function useRunEvents(runId: string | null) {
  const setNodeStatus = useCanvasEditStore((s) => s.setNodeStatus);
  const errCountRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    const url = `/runs/${runId}/events`;
    const es = new EventSource(url, { withCredentials: false });

    const handler = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        const nodeId = data.node_id as string | undefined;
        if (!nodeId) return;
        const status = event.type.replace('node_', '') as NodeStatus;
        if (['running', 'completed', 'failed', 'skipped'].includes(status)) {
          setNodeStatus(nodeId, status);
        }
      } catch {
        // ignore parse errors on comments/keep-alive
      }
    };

    const events = [
      'node_running',
      'node_completed',
      'node_failed',
      'node_skipped',
      'run_completed',
      'run_failed',
      'run_cancelled',
    ];
    events.forEach((ev) => es.addEventListener(ev, handler));

    const closeEs = () => es.close();
    es.addEventListener('run_completed', closeEs);
    es.addEventListener('run_failed', closeEs);
    es.addEventListener('run_cancelled', closeEs);

    es.onerror = () => {
      errCountRef.current += 1;
      if (errCountRef.current >= 3) {
        es.close();
      }
      // Otherwise, browser will auto-reconnect per EventSource spec
    };

    return () => {
      es.close();
    };
  }, [runId, setNodeStatus]);
}

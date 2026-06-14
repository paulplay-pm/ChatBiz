export function StatusDot({ status }: { status: 'running' | 'success' | 'error' | 'idle' | 'pending' }) {
  return <span data-testid="status-dot" className={`status-dot status-${status}`} />;
}

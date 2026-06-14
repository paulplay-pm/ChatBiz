import { ReactNode } from 'react';
export function MetricCard({ label, value, trend }: { label: string; value: string | number; trend?: ReactNode }) {
  return (
    <div data-testid="metric-card" className="rounded-xl p-4 metric-card">
      <div className="text-xs text-ink-500">{label}</div>
      <div className="text-2xl font-semibold text-ink-900 mt-1">{value}</div>
      {trend && <div className="text-xs text-brand-500 mt-2">{trend}</div>}
    </div>
  );
}

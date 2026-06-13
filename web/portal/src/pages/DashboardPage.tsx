import { MetricCard } from 'ui/primitives/MetricCard';
import { Button } from 'ui/primitives/Button';

export default function DashboardPage() {
  return (
    <div data-testid="dashboard" className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold text-ink-900">控制台</h1>
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="工作流" value={12} trend="+2 本周" />
        <MetricCard label="Agent" value={4} trend="+1 本周" />
        <MetricCard label="运行次数" value={87} trend="+15 本周" />
        <MetricCard label="知识库" value={3} />
      </div>
      <div className="rounded-xl bg-white border border-ink-200 p-6">
        <h2 className="text-lg font-semibold text-ink-900 mb-4">最近工作流</h2>
        <p className="text-sm text-ink-500">暂无数据 — 创建第一个工作流以开始</p>
      </div>
      <div data-testid="quick-action">
        <Button onClick={() => { window.location.assign('/canvas/workflows'); }}>新建工作流</Button>
      </div>
    </div>
  );
}

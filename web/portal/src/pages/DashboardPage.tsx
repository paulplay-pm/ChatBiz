import { MetricCard } from 'ui/primitives/MetricCard';
import { Card } from 'ui/primitives/Card';
import {
  METRICS,
  QUICK_STARTS,
  RECENT_ACCESSES,
  RECENT_ACTIVITIES,
} from '@/data/dashboard';

function handleClick(href: string, external: boolean) {
  if (external) {
    window.location.assign(`http://localhost:5173${href}`);
  } else {
    window.location.assign(href);
  }
}

export default function DashboardPage() {
  return (
    <div data-testid="dashboard" className="p-8 space-y-6">
      {/* 页头 */}
      <h1 className="text-2xl font-semibold text-ink-900">工作台</h1>

      {/* 4 metric 卡 */}
      <section data-testid="metric-section" className="grid grid-cols-4 gap-4">
        {METRICS.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} trend={m.trend} />
        ))}
      </section>

      <div className="grid grid-cols-3 gap-6">
        {/* 快速开始 4 张 2x2 */}
        <section data-testid="quick-starts" className="col-span-2">
          <h2 className="text-lg font-semibold text-ink-900 mb-4">快速开始</h2>
          <div className="grid grid-cols-2 gap-4">
            {QUICK_STARTS.map((qs) => (
              <Card
                key={qs.id}
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => handleClick(qs.href, qs.external)}
              >
                <div className="flex items-start gap-3" data-testid="quick-start">
                  <i className={`${qs.icon} text-2xl text-brand-500 mt-1`} />
                  <div>
                    <div className="font-medium text-ink-900">{qs.title}</div>
                    <div className="text-xs text-ink-500 mt-1">{qs.subtitle}</div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>

        {/* 右侧:最近访问 + 最近动态 */}
        <aside className="space-y-6">
          <section data-testid="recent-access">
            <h2 className="text-lg font-semibold text-ink-900 mb-4">最近访问</h2>
            <Card>
              <ul className="space-y-3">
                {RECENT_ACCESSES.map((r) => (
                  <li
                    key={r.id}
                    data-testid="recent-access-item"
                    className="flex items-center justify-between"
                  >
                    <div>
                      <div className="text-sm text-ink-900">{r.title}</div>
                      <div className="text-xs text-ink-500">{r.type}</div>
                    </div>
                    <div className="text-xs text-ink-500">{r.visitedAt}</div>
                  </li>
                ))}
              </ul>
            </Card>
          </section>

          <section data-testid="recent-activity">
            <h2 className="text-lg font-semibold text-ink-900 mb-4">最近动态</h2>
            <Card>
              <ul className="space-y-3">
                {RECENT_ACTIVITIES.map((a) => (
                  <li
                    key={a.id}
                    data-testid="recent-activity-item"
                    className="text-sm text-ink-700"
                  >
                    <div>{a.text}</div>
                    <div className="text-xs text-ink-500 mt-1">{a.at}</div>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        </aside>
      </div>
    </div>
  );
}

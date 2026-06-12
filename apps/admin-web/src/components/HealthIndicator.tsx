import { useHealth } from "@/api/health";
import type { HealthStatus } from "@/types";

const STATUS_COLOR: Record<HealthStatus, string> = {
  healthy: "bg-green-500",
  degraded: "bg-yellow-500",
  down: "bg-red-500",
  unknown: "bg-ink-400",
};

const STATUS_LABEL: Record<HealthStatus, string> = {
  healthy: "健康",
  degraded: "降级",
  down: "不可用",
  unknown: "未知",
};

/**
 * 顶部 header 右侧的健康圆点。读 useHealth() 状态。
 * - aria-label "服务健康：<中文状态>"
 * - 圆点用 aria-hidden，文字标签让 SR 友好
 */
export function HealthIndicator(): JSX.Element {
  const { data } = useHealth();
  const status: HealthStatus = data?.status ?? "unknown";
  return (
    <div
      className="flex items-center gap-2 text-xs text-ink-500"
      aria-label={`服务健康：${STATUS_LABEL[status]}`}
    >
      <span className={`w-2 h-2 rounded-full ${STATUS_COLOR[status]}`} aria-hidden="true" />
      <span>{STATUS_LABEL[status]}</span>
    </div>
  );
}

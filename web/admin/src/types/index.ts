// 共享类型 — 给 components/router/api 复用

export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";

export interface HealthResponse {
  readonly status: HealthStatus;
}

export interface MenuItem {
  readonly name: string;
  readonly href: string;
  readonly icon: string; // FontAwesome class 短码，如 "fa-robot"
  readonly changeName: string; // 后续落地 change 的名称，PlaceholderView 显示
}

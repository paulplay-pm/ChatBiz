import type { MenuItem } from "@/types";

/**
 * 14 个左侧导航 menu item，顺序来自 `docs/prototype.html:235-410` + spec `side-nav-shell` §
 * Requirement: SideNav renders 14 menu items。
 *
 * 同时是 router/index.tsx 14 条路由的来源，避免 SideNav 与路由表漂移。
 *
 * 后续业务 change（如 mcp-server-management-ui）接入时：
 *   - SideNav 保持 14 项不动
 *   - router/index.tsx 把对应 path 的 PlaceholderView 换成真实视图
 */
export const MENU_ITEMS: ReadonlyArray<MenuItem> = [
  { name: "工作流", href: "/workflow", icon: "fa-th-large", changeName: "workflow-engine" },
  { name: "Agent", href: "/agent", icon: "fa-robot", changeName: "agent-runtime" },
  { name: "知识库", href: "/knowledge", icon: "fa-book", changeName: "knowledge-base" },
  { name: "模板广场", href: "/templates", icon: "fa-clone", changeName: "template-marketplace" },
  { name: "团队共享", href: "/team", icon: "fa-users", changeName: "team-sharing" },
  { name: "插件市场", href: "/plugins", icon: "fa-puzzle-piece", changeName: "plugin-marketplace" },
  { name: "模型管理", href: "/models", icon: "fa-microchip", changeName: "model-management" },
  { name: "通道管理", href: "/channels", icon: "fa-route", changeName: "channel-management" },
  { name: "凭证管理", href: "/credentials", icon: "fa-key", changeName: "credential" },
  { name: "技能管理", href: "/skills", icon: "fa-magic", changeName: "skill-management" },
  { name: "MCP 工具", href: "/mcp-tools", icon: "fa-plug", changeName: "mcp-server-management-ui" },
  { name: "中间件链", href: "/middleware", icon: "fa-link", changeName: "middleware-chain" },
  { name: "监控", href: "/monitoring", icon: "fa-chart-line", changeName: "monitoring" },
  { name: "日志", href: "/logs", icon: "fa-file-alt", changeName: "log-query" },
] as const;

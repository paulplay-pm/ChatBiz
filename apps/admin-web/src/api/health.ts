import useSWR from "swr";
import type { HealthResponse } from "@/types";

/**
 * useHealth — 探 `services/mcp` (端口 8004) 健康。
 * - SWR 5s 轮询
 * - 网络失败 / 非 2xx fallback 为 `{ status: "down" }`，永不抛
 *
 * 后续 change 可以传不同 baseUrl 复用同一 hook 探别的 service。
 */
async function fetcher(url: string): Promise<HealthResponse> {
  try {
    const res = await fetch(url, { method: "GET" });
    if (!res.ok) {
      return { status: "down" };
    }
    const data: unknown = await res.json();
    if (
      typeof data === "object" &&
      data !== null &&
      "status" in data &&
      typeof (data as { status: unknown }).status === "string"
    ) {
      const status = (data as { status: string }).status;
      if (status === "healthy" || status === "degraded" || status === "down") {
        return { status };
      }
    }
    return { status: "unknown" };
  } catch {
    return { status: "down" };
  }
}

export function useHealth(baseUrl = "http://localhost:8004"): {
  data: HealthResponse | undefined;
} {
  const { data } = useSWR<HealthResponse>(`${baseUrl}/healthz`, fetcher, {
    refreshInterval: 5_000,
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  return { data };
}

import useSWR from "swr";
import type { HealthResponse } from "@/types";

/**
 * useHealth — probe mcp service health.
 * - Default: relative path `/healthz`, proxied by nginx to chatbiz-mcp:8080.
 * - Dev fallback: VITE_ADMIN_HEALTH_DIRECT=1 → direct host 8004.
 * - SWR 5s polling
 * - Network/non-2xx → fallback `{ status: "down" }`, never throws
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

export function useHealth(baseUrl?: string): {
  data: HealthResponse | undefined;
} {
  const effectiveBase =
    baseUrl ??
    (import.meta.env.VITE_ADMIN_HEALTH_DIRECT === "1"
      ? "http://localhost:8004"
      : "");
  const { data } = useSWR<HealthResponse>(
    `${effectiveBase}/healthz`,
    fetcher,
    {
      refreshInterval: 5_000,
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    },
  );
  return { data };
}

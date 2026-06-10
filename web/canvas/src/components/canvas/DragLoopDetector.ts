export function detectCycle(
  nodes: string[],
  edges: { from: string; to: string }[],
): string[] | null {
  const adj = new Map<string, string[]>();
  for (const n of nodes) adj.set(n, []);
  for (const e of edges) adj.get(e.from)?.push(e.to);

  const WHITE = 0, GRAY = 1, BLACK = 2;
  const color = new Map<string, number>();
  const parent = new Map<string, string>();
  for (const n of nodes) color.set(n, WHITE);

  function dfs(u: string): string[] | null {
    color.set(u, GRAY);
    for (const v of adj.get(u) || []) {
      if (color.get(v) === GRAY) {
        // Reconstruct cycle: v -> ... -> u -> v
        const cycle: string[] = [v];
        let cur: string = u;
        while (cur !== v) {
          cycle.push(cur);
          cur = parent.get(cur)!;
        }
        cycle.push(v);
        return cycle.reverse();
      }
      if (color.get(v) === WHITE) {
        parent.set(v, u);
        const result = dfs(v);
        if (result) return result;
      }
    }
    color.set(u, BLACK);
    return null;
  }

  for (const n of nodes) {
    if (color.get(n) === WHITE) {
      const result = dfs(n);
      if (result) return result;
    }
  }
  return null;
}

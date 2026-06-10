import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { temporal } from 'zundo';

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

export interface CanvasNode {
  id: string;
  type: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  status?: NodeStatus;
}

export interface CanvasEdge {
  id: string;
  from: string;
  to: string;
  condition?: string;
}

interface CanvasEditState {
  workflowId: string | null;
  version: number;
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  dirty: boolean;
  selectedNodeId: string | null;
  setInitial: (id: string, version: number, nodes: CanvasNode[], edges: CanvasEdge[]) => void;
  addNode: (node: CanvasNode) => void;
  updateNode: (id: string, patch: Partial<CanvasNode>) => void;
  removeNode: (id: string) => void;
  addEdge: (edge: CanvasEdge) => void;
  removeEdge: (id: string) => void;
  setNodeStatus: (id: string, status: NodeStatus) => void;
  selectNode: (id: string | null) => void;
  markClean: () => void;
}

export const useCanvasEditStore = create<CanvasEditState>()(
  temporal(
    persist(
      (set) => ({
        workflowId: null,
        version: 0,
        nodes: [],
        edges: [],
        dirty: false,
        selectedNodeId: null,
        setInitial: (id, version, nodes, edges) =>
          set({ workflowId: id, version, nodes, edges, dirty: false, selectedNodeId: null }),
        addNode: (node) => set((s) => ({ nodes: [...s.nodes, node], dirty: true })),
        updateNode: (id, patch) =>
          set((s) => ({
            nodes: s.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)),
            dirty: true,
          })),
        removeNode: (id) =>
          set((s) => ({
            nodes: s.nodes.filter((n) => n.id !== id),
            edges: s.edges.filter((e) => e.from !== id && e.to !== id),
            dirty: true,
          })),
        addEdge: (edge) => set((s) => ({ edges: [...s.edges, edge], dirty: true })),
        removeEdge: (id) =>
          set((s) => ({ edges: s.edges.filter((e) => e.id !== id), dirty: true })),
        setNodeStatus: (id, status) =>
          set((s) => ({
            nodes: s.nodes.map((n) => (n.id === id ? { ...n, status } : n)),
          })),
        selectNode: (id) => set({ selectedNodeId: id }),
        markClean: () => set({ dirty: false }),
      }),
      { name: 'chatbiz-canvas' },
    ),
    { limit: 50 },
  ),
);

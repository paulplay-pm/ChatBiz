import dagre from 'dagre';
import { CanvasNode, CanvasEdge } from '@/store/useCanvasEditStore';

export function autoLayout(nodes: CanvasNode[], edges: CanvasEdge[]): CanvasNode[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel((_sr: unknown, _tr: unknown, _lbl: unknown) => ({}));
// dagre 2.x default edge label callback — name must be 'LR' for left-to-right


  g.setGraph({ rankdir: 'LR', nodesep: 50, ranksep: 100 });

  nodes.forEach((n) => g.setNode(n.id, { width: 180, height: 80 }));
  edges.forEach((e) => g.setEdge(e.from, e.to));

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - 90, y: pos.y - 40 } };
  });
}

import { useEffect, useState, useCallback, useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, ReactFlowProvider, useReactFlow, Connection } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button } from 'ui/primitives/Button';
import { useToast } from 'ui/primitives/Toast';
import { useParams, useNavigate } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import { useSaveWorkflow } from '@/hooks/useSaveWorkflow';
import { nodeTypes } from '@/components/canvas/nodes';
import { NodePanel } from '@/components/canvas/NodePanel';
import { ConfigPanel } from '@/components/canvas/ConfigPanel';
import { NodeSearchModal } from '@/components/canvas/NodeSearchModal';
import { EdgeConditionMenu } from '@/components/canvas/EdgeConditionMenu';
import { detectCycle } from '@/components/canvas/DragLoopDetector';
import { autoLayout } from '@/components/canvas/AutoLayout';
import { api } from '@/lib/apiClient';

const IconSave = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
    <polyline points="7 3 7 8 15 8" />
  </svg>
);
const IconPartition = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
  </svg>
);

function CanvasPageInner() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    workflowId, nodes, edges, dirty,
    setInitial, addNode, addEdge, removeNode, removeEdge,
    selectNode,
  } = useCanvasEditStore();
  const { screenToFlowPosition } = useReactFlow();
  const [searchOpen, setSearchOpen] = useState(false);
  const [edgeMenu, setEdgeMenu] = useState<{ edgeId: string; value: string } | null>(null);
  const saveMutation = useSaveWorkflow();

  const [selectedEdgeIds, setSelectedEdgeIds] = useState<Set<string>>(new Set());

  const rfNodes = useMemo(
    () => nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: { config: n.config, status: n.status },
    })),
    [nodes],
  );
  const rfEdges = useMemo(
    () => edges.map((e) => ({
      id: e.id,
      source: e.from,
      target: e.to,
      data: e.condition ? { condition: e.condition } : undefined,
      selected: selectedEdgeIds.has(e.id),
    })),
    [edges, selectedEdgeIds],
  );

  useUndoRedo();

  useEffect(() => {
    if (!id) return;
    if (workflowId === id) return; // already loaded
    api.get(`/workflows/${id}`).then((r) => {
      const wf = r.data;
      setInitial(wf.id, wf.version, wf.definition_json.nodes || [], wf.definition_json.edges || []);
    }).catch(() => {
      toast.error('加载工作流失败');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    const handler = () => saveMutation.mutate(undefined, {
      onSuccess: (data: any) => {
        if (!workflowId && data?.id) {
          navigate(`/workflows/${data.id}/edit`, { replace: true });
        }
      },
    });
    window.addEventListener('chatbiz-save-workflow', handler);
    return () => window.removeEventListener('chatbiz-save-workflow', handler);
  }, [saveMutation, workflowId, navigate]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      if (connection.source === connection.target) {
        toast.warn('节点不能连接自身');
        return;
      }
      const allNodeIds = [
        ...nodes.map((n) => n.id),
        connection.source,
        connection.target,
      ].filter((v, i, a) => a.indexOf(v) === i);
      const edgeList = [
        ...edges,
        { id: uuidv4(), from: connection.source, to: connection.target },
      ];
      const cycle = detectCycle(allNodeIds, edgeList);
      if (cycle) {
        toast.warn(`工作流存在循环: ${cycle.join(' → ')}`);
        return;
      }
      addEdge({ id: uuidv4(), from: connection.source, to: connection.target });
    },
    [nodes, edges, addEdge, toast],
  );

  // V5 T2: dev-only __rfConnect hook,供 e2e 替代 mouse drag
  // 根因:xyflow .react-flow__handle 默认 6x6 px,Playwright mouse.move
  // linear interpolation ±1-2 px 偏差,导致 elementFromPoint 拿不到 handle。
  // Hook 走 onConnect 同步路径,行为与真实 drag 完全等价。
  // Vite dead-code-eliminate prod build,window.__rfConnect 不挂载。
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    type RfConnectArgs = { source: string; target: string };
    (window as unknown as { __rfConnect: (args: RfConnectArgs) => void }).__rfConnect = ({ source, target }: RfConnectArgs) => {
      onConnect({ source, target, sourceHandle: null, targetHandle: null });
    };
    return () => {
      delete (window as unknown as { __rfConnect?: unknown }).__rfConnect;
    };
  }, [onConnect]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const type = e.dataTransfer.getData('application/chatbiz-node');
      if (!type) return;
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
      addNode({
        id: uuidv4(),
        type,
        config: {},
        position,
      });
      selectNode(nodes.length ? '' : '');
    },
    [screenToFlowPosition, addNode, selectNode, nodes.length],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onLayout = useCallback(() => {
    const layouted = autoLayout(nodes, edges);
    useCanvasEditStore.setState({ nodes: layouted, dirty: true });
    toast.info('已自动布局');
  }, [nodes, edges, toast]);

  const onSave = useCallback(() => {
    saveMutation.mutate(undefined, {
      onSuccess: (data: any) => {
        if (!workflowId && data?.id) {
          navigate(`/workflows/${data.id}/edit`, { replace: true });
        }
      },
    });
  }, [saveMutation, workflowId, navigate]);

  return (
    <div className="flex h-[calc(100vh-64px)]">
      <NodePanel />
      <div className="flex-1 relative" onDrop={onDrop} onDragOver={onDragOver}>
        <ReactFlow
          nodes={rfNodes as any}
          edges={rfEdges as any}
          nodeTypes={nodeTypes as any}
          deleteKeyCode={['Backspace', 'Delete']}
          onNodesChange={(changes) => {
            changes.forEach((c) => {
              if (c.type === 'position' && c.position) {
                useCanvasEditStore.setState((s) => ({
                  nodes: s.nodes.map((n) => n.id === c.id ? { ...n, position: c.position! } : n),
                  dirty: true,
                }));
              } else if (c.type === 'remove') {
                removeNode(c.id);
              } else if (c.type === 'select') {
                selectNode(c.selected ? c.id : null);
              }
            });
          }}
          onEdgesChange={(changes) => {
            changes.forEach((c) => {
              if (c.type === 'remove') {
                removeEdge(c.id);
                setSelectedEdgeIds((prev) => {
                  if (!prev.has(c.id)) return prev;
                  const next = new Set(prev);
                  next.delete(c.id);
                  return next;
                });
              } else if (c.type === 'select') {
                setSelectedEdgeIds((prev) => {
                  const next = new Set(prev);
                  if (c.selected) next.add(c.id);
                  else next.delete(c.id);
                  return next;
                });
              }
            });
          }}
          onConnect={onConnect}
          onEdgeContextMenu={(e, edge) => {
            e.preventDefault();
            setEdgeMenu({
              edgeId: edge.id,
              value: edges.find((x) => x.id === edge.id)?.condition || '',
            });
          }}
          onNodeContextMenu={(e, node) => {
            e.preventDefault();
            selectNode(node.id);
          }}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
        <div className="absolute top-3 right-3 flex gap-2 z-10">
          <Button variant="secondary" size="sm" onClick={onLayout}>
            <span className="inline-flex items-center gap-1"><IconPartition /> 自动布局</span>
          </Button>
          <span>
            <Button
              variant="primary"
              size="sm"
              onClick={onSave}
            >
              <span className="inline-flex items-center gap-1">
                <IconSave /> 保存{dirty ? ' *' : ''}
              </span>
            </Button>
          </span>
        </div>
      </div>
      <div className="w-[360px] border-l border-ink-200 bg-white">
        <ConfigPanel />
      </div>
      <NodeSearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
      {edgeMenu && (
        <EdgeConditionMenu
          open={true}
          initialValue={edgeMenu.value}
          onClose={() => setEdgeMenu(null)}
          onSave={(condition) => {
            useCanvasEditStore.setState((s) => ({
              edges: s.edges.map((e) => e.id === edgeMenu.edgeId ? { ...e, condition } : e),
              dirty: true,
            }));
            setEdgeMenu(null);
          }}
        />
      )}
    </div>
  );
}

export default function CanvasPage() {
  return (
    <ReactFlowProvider>
      <CanvasPageInner />
    </ReactFlowProvider>
  );
}

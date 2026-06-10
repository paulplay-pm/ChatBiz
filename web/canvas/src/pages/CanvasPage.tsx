import { useEffect, useState, useCallback } from 'react';
import { ReactFlow, Background, Controls, MiniMap, ReactFlowProvider, useReactFlow, Connection } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Button, Space, message } from 'antd';
import { SaveOutlined, PartitionOutlined, DeleteOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
import { useCanvasEditStore, CanvasNode, CanvasEdge } from '@/store/useCanvasEditStore';
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

function CanvasPageInner() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const {
    workflowId, version, nodes, edges, dirty, selectedNodeId,
    setInitial, addNode, addEdge, removeNode, removeEdge,
    selectNode,
  } = useCanvasEditStore();
  const { screenToFlowPosition } = useReactFlow();
  const [searchOpen, setSearchOpen] = useState(false);
  const [edgeMenu, setEdgeMenu] = useState<{ edgeId: string; value: string } | null>(null);
  const saveMutation = useSaveWorkflow();

  useUndoRedo();

  // Load workflow on mount
  useEffect(() => {
    if (!id) return;
    if (workflowId === id) return; // already loaded
    api.get(`/workflows/${id}`).then((r) => {
      const wf = r.data;
      setInitial(wf.id, wf.version, wf.definition_json.nodes || [], wf.definition_json.edges || []);
    }).catch(() => {
      message.error('加载工作流失败');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // / shortcut to open search modal
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

  // Global save shortcut (dispatched by useUndoRedo on Cmd+S)
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

  // beforeunload guard for unsaved changes
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
        message.warning('节点不能连接自身');
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
        message.warning(`工作流存在循环: ${cycle.join(' → ')}`);
        return;
      }
      addEdge({ id: uuidv4(), from: connection.source, to: connection.target });
    },
    [nodes, edges, addEdge],
  );

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
    message.success('已自动布局');
  }, [nodes, edges]);

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
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)' }}>
      <NodePanel />
      <div style={{ flex: 1, position: 'relative' }} onDrop={onDrop} onDragOver={onDragOver}>
        <ReactFlow
          nodes={nodes as any}
          edges={edges as any}
          nodeTypes={nodeTypes as any}
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
        <div style={{ position: 'absolute', top: 12, right: 12, display: 'flex', gap: 8, zIndex: 10 }}>
          <Button icon={<PartitionOutlined />} onClick={onLayout}>自动布局</Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={onSave}
            loading={saveMutation.isPending}
          >
            保存{dirty ? ' *' : ''}
          </Button>
        </div>
      </div>
      <div style={{ width: 360, borderLeft: '1px solid #f0f0f0', background: '#fff' }}>
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

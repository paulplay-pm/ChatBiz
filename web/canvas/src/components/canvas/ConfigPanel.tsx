import { Spin, Empty } from 'antd';
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { useNodeSchema } from '@/hooks/useNodeSchema';
import { useCanvasEditStore, CanvasNode } from '@/store/useCanvasEditStore';

export function ConfigPanel() {
  const selectedId = useCanvasEditStore((s) => s.selectedNodeId);
  const node = useCanvasEditStore((s) => s.nodes.find((n) => n.id === selectedId));
  const updateNode = useCanvasEditStore((s) => s.updateNode);

  if (!node) {
    return <Empty description="选中节点查看配置" />;
  }

  return (
    <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
      <ConfigForm key={node.id} node={node} onChange={(config) => updateNode(node.id, { config })} />
    </div>
  );
}

function ConfigForm({ node, onChange }: { node: CanvasNode; onChange: (c: any) => void }) {
  const { data: schema, isLoading, error } = useNodeSchema(node.type);

  if (isLoading) return <Spin />;
  if (error || !schema) {
    return <Empty description={`加载 ${node.type} schema 失败`} />;
  }

  return (
    <Form
      schema={schema.config_schema}
      validator={validator}
      formData={node.config}
      onChange={(e) => onChange(e.formData)}
      uiSchema={{
        'ui:submitButtonOptions': { norender: true },
      }}
    />
  );
}

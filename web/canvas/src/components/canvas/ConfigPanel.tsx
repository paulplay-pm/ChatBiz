import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { useNodeSchema } from '@/hooks/useNodeSchema';
import { useCanvasEditStore, CanvasNode } from '@/store/useCanvasEditStore';

export function ConfigPanel() {
  const selectedId = useCanvasEditStore((s) => s.selectedNodeId);
  const node = useCanvasEditStore((s) => s.nodes.find((n) => n.id === selectedId));
  const updateNode = useCanvasEditStore((s) => s.updateNode);

  if (!node) {
    return (
      <div className="p-4 text-sm text-ink-500 text-center">
        <div className="text-2xl mb-2">📭</div>
        <div>选中节点查看配置</div>
      </div>
    );
  }

  return (
    <div className="p-4 h-full overflow-auto">
      <ConfigForm key={node.id} node={node} onChange={(config) => updateNode(node.id, { config })} />
    </div>
  );
}

function ConfigForm({ node, onChange }: { node: CanvasNode; onChange: (c: any) => void }) {
  const { data: schema, isLoading, error } = useNodeSchema(node.type);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4 text-ink-500 text-sm">
        <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        加载 schema…
      </div>
    );
  }
  if (error || !schema) {
    return (
      <div className="text-sm text-ink-500 text-center p-4">
        <div className="text-2xl mb-2">⚠️</div>
        <div>加载 {node.type} schema 失败</div>
      </div>
    );
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

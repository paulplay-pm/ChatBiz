import { useState } from 'react';
import { Modal, Form, Input, Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { useNavigate } from 'react-router-dom';
import { useCreateWorkflow } from '@/hooks/useWorkflows';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateWorkflowModal({ open, onClose }: Props) {
  const navigate = useNavigate();
  const create = useCreateWorkflow();
  const toast = useToast();
  const [mode, setMode] = useState<string>('workflow');
  const [name, setName] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.warn('名称必填');
      return;
    }
    setSubmitting(true);
    try {
      const wf = await create.mutateAsync({
        name,
        mode,
        definition_json: { nodes: [], edges: [], variables: {}, mode },
      });
      toast.info('已创建工作流');
      setName('');
      onClose();
      navigate(`/workflows/${wf.id}/edit?version=${wf.version}`);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { error_message?: string } } } };
      toast.error(err.response?.data?.detail?.error_message ?? '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="新建工作流">
      <Form onSubmit={onSubmit}>
        <div>
          <label className="block text-sm font-medium text-ink-700 mb-1">名称</label>
          <Input
            name="name"
            placeholder="例:paul 财务月报"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium text-ink-700 mb-1">类型</label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode('workflow')}
              className={`px-3 py-1.5 text-sm rounded-lg border ${mode === 'workflow' ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-ink-700 border-ink-200 hover:bg-ink-50'}`}
            >
              Workflow(单次)
            </button>
            <button
              type="button"
              onClick={() => setMode('chatflow')}
              className={`px-3 py-1.5 text-sm rounded-lg border ${mode === 'chatflow' ? 'bg-brand-500 text-white border-brand-500' : 'bg-white text-ink-700 border-ink-200 hover:bg-ink-50'}`}
            >
              Chatflow(多轮)
            </button>
          </div>
        </div>
        <div className="flex gap-2 justify-end mt-6">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <span>
            <Button variant="primary" type="submit">{submitting ? '创建中…' : '创建'}</Button>
          </span>
        </div>
      </Form>
    </Modal>
  );
}

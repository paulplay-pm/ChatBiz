import { useState } from 'react';
import { Modal, Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { useDeleteWorkflow } from '@/hooks/useWorkflows';

interface Props {
  workflowId: string | null;
  workflowName?: string;
  onClose: () => void;
}

export function DeleteConfirmModal({ workflowId, workflowName, onClose }: Props) {
  const del = useDeleteWorkflow();
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);

  const onConfirm = async () => {
    if (!workflowId) return;
    setSubmitting(true);
    try {
      await del.mutateAsync(workflowId);
      toast.info('已删除');
      onClose();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { error_message?: string } } } };
      toast.error(err.response?.data?.detail?.error_message ?? '删除失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={!!workflowId} onClose={onClose} title="确认删除">
      <p className="text-sm text-ink-700">
        确定要删除工作流 <strong>{workflowName}</strong> 吗?此操作不可恢复。
      </p>
      <div className="flex gap-2 justify-end mt-6">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <span>
          <Button variant="primary" onClick={onConfirm}>{submitting ? '删除中…' : '删除'}</Button>
        </span>
      </div>
    </Modal>
  );
}

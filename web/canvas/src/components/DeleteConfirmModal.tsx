import { Modal, message } from 'antd';
import { useDeleteWorkflow } from '@/hooks/useWorkflows';

interface Props {
  workflowId: string | null;
  workflowName?: string;
  onClose: () => void;
}

export function DeleteConfirmModal({ workflowId, workflowName, onClose }: Props) {
  const del = useDeleteWorkflow();

  const onOk = async () => {
    if (!workflowId) return;
    try {
      await del.mutateAsync(workflowId);
      message.success('已删除');
      onClose();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { error_message?: string } } } };
      message.error(err.response?.data?.detail?.error_message ?? '删除失败');
    }
  };

  return (
    <Modal
      title="确认删除"
      open={!!workflowId}
      onCancel={onClose}
      onOk={onOk}
      okButtonProps={{ danger: true, loading: del.isPending }}
      okText="删除"
      cancelText="取消"
    >
      确定要删除工作流 <strong>{workflowName}</strong> 吗?此操作不可恢复。
    </Modal>
  );
}

import { Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { useAuthStore } from '@/store/useAuthStore';
import { api } from '@/lib/apiClient';

interface Props {
  approvalId: string;
  approverUserId: string;
  content: string;
  onResolved: () => void;
}

export function ApprovalInlineCard({ approvalId, approverUserId, content, onResolved }: Props) {
  const user = useAuthStore((s) => s.user);
  const toast = useToast();
  const isApprover = user?.id === approverUserId || user?.name === approverUserId;

  const respond = async (decision: 'approved' | 'rejected') => {
    try {
      await api.post(`/approvals/${approvalId}:resume`, {
        decision,
        payload: { comment: '' },
      });
      toast.info(decision === 'approved' ? '已批准' : '已拒绝');
      onResolved();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      toast.error(detail?.error_message || '操作失败');
    }
  };

  if (!isApprover) {
    return (
      <div className="p-3 bg-green-50 rounded-lg text-center text-ink-500 text-sm">
        等待 {approverUserId} 审批
      </div>
    );
  }

  return (
    <div className="p-3 bg-green-50 rounded-lg border border-green-300">
      <div className="mb-2 font-semibold text-ink-900">✋ 待审批: {content}</div>
      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={() => respond('approved')}>
          批准
        </Button>
        <span className="text-red-600 hover:bg-red-50 rounded-lg">
          <Button variant="ghost" size="sm" onClick={() => respond('rejected')}>
            拒绝
          </Button>
        </span>
      </div>
    </div>
  );
}

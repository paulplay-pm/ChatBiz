import { Button, Space, message } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
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
  const isApprover = user?.id === approverUserId || user?.name === approverUserId;

  const respond = async (decision: 'approved' | 'rejected') => {
    try {
      await api.post(`/approvals/${approvalId}:resume`, {
        decision,
        payload: { comment: '' },
      });
      message.success(decision === 'approved' ? '已批准' : '已拒绝');
      onResolved();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      message.error(detail?.error_message || '操作失败');
    }
  };

  if (!isApprover) {
    return (
      <div
        style={{
          padding: 12,
          background: '#f6ffed',
          borderRadius: 8,
          textAlign: 'center',
          color: '#999',
        }}
      >
        等待 {approverUserId} 审批
      </div>
    );
  }

  return (
    <div
      style={{
        padding: 12,
        background: '#f6ffed',
        borderRadius: 8,
        border: '1px solid #b7eb8f',
      }}
    >
      <div style={{ marginBottom: 8, fontWeight: 600 }}>✋ 待审批: {content}</div>
      <Space>
        <Button type="primary" icon={<CheckOutlined />} onClick={() => respond('approved')}>
          批准
        </Button>
        <Button danger icon={<CloseOutlined />} onClick={() => respond('rejected')}>
          拒绝
        </Button>
      </Space>
    </div>
  );
}

import { Button, Space, Tooltip, message } from 'antd';
import { ReloadOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/apiClient';

interface Props {
  workflowId: string | undefined;
}

export function RetryCancelButtons({ workflowId }: Props) {
  const navigate = useNavigate();

  const onRetry = async () => {
    if (!workflowId) return;
    try {
      const r = await api.post<{ run_id: string }>(`/workflows/${workflowId}:run`, {
        mode: 'workflow',
        initial_inputs: {},
        variables: {},
      });
      message.success('已启动新运行');
      navigate(`/runs/${r.data.run_id}`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      message.error(detail?.error_message || '重试失败');
    }
  };

  return (
    <Space>
      <Tooltip title="重试(用同一 workflow 发起新一次运行)">
        <Button icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      </Tooltip>
      <Tooltip title="取消运行 (V1.0 实现)">
        <Button icon={<CloseCircleOutlined />} disabled>
          取消
        </Button>
      </Tooltip>
    </Space>
  );
}

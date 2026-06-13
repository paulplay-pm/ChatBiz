import { useState } from 'react';
import { Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/apiClient';

interface Props {
  workflowId: string | undefined;
}

export function RetryCancelButtons({ workflowId }: Props) {
  const navigate = useNavigate();
  const toast = useToast();
  const [loading, setLoading] = useState(false);

  const onRetry = async () => {
    if (!workflowId) return;
    setLoading(true);
    try {
      const r = await api.post<{ run_id: string }>(`/workflows/${workflowId}:run`, {
        mode: 'workflow',
        initial_inputs: {},
        variables: {},
      });
      toast.info('已启动新运行');
      navigate(`/runs/${r.data.run_id}`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      toast.error(detail?.error_message || '重试失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex gap-2">
      <span title="重试(用同一 workflow 发起新一次运行)">
        <Button variant="primary" size="sm" onClick={onRetry}>
          {loading ? '启动中…' : '重试'}
        </Button>
      </span>
      <span title="取消运行 (V1.0 实现)">
        <Button variant="ghost" size="sm">取消</Button>
      </span>
    </div>
  );
}

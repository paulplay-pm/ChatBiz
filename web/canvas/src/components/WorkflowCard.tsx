import { useNavigate } from 'react-router-dom';
import { Card, Button, StatusDot } from 'ui/index';
import { Workflow, useToggleFavorite } from '@/hooks/useWorkflows';

interface Props {
  workflow: Workflow;
  onDelete: (id: string) => void;
}

export function WorkflowCard({ workflow, onDelete }: Props) {
  const navigate = useNavigate();
  const toggle = useToggleFavorite();
  const isFavorite = workflow.favorite ?? false;
  const mode = workflow.definition_json?.mode ?? 'workflow';
  const sharing = workflow.definition_json?.sharing ?? 'private';

  const tagBase = 'inline-block rounded px-2 py-0.5 text-xs';
  const tagColors: Record<string, string> = {
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-green-100 text-green-700',
    gray: 'bg-ink-100 text-ink-700',
  };

  return (
    <Card
      className="hover:border-brand-500 cursor-pointer"
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-ink-900">{workflow.name}</h3>
        <StatusDot status={isFavorite ? 'success' : 'idle'} />
      </div>
      <div className="flex items-center gap-1.5 flex-wrap mb-3" onClick={(e) => e.stopPropagation()}>
        <span className={`${tagBase} ${tagColors.gray}`}>v{workflow.version}</span>
        <span className={`${tagBase} ${tagColors.blue}`}>{mode}</span>
        <span className={`${tagBase} ${tagColors.green}`}>{sharing}</span>
        <span
          className="text-xs text-ink-500"
          title="创建时间"
        >
          {new Date(workflow.created_at).toLocaleString()}
        </span>
      </div>
      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => toggle.mutate({ id: workflow.id, favorite: !isFavorite })}
        >
          {isFavorite ? '★ 已收藏' : '☆ 收藏'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/workflows/${workflow.id}/edit`)}
        >
          编辑
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDelete(workflow.id)}
        >
          删除
        </Button>
      </div>
    </Card>
  );
}

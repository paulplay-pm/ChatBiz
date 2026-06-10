import { Card, Tag, Button, Space, Tooltip } from 'antd';
import { StarOutlined, StarFilled, DeleteOutlined, EditOutlined, ShareAltOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
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

  return (
    <Card
      hoverable
      title={workflow.name}
      extra={
        <Space onClick={(e) => e.stopPropagation()}>
          <Button
            type="text"
            icon={isFavorite ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
            onClick={() => toggle.mutate({ id: workflow.id, favorite: !isFavorite })}
          />
          <Button type="text" icon={<EditOutlined />} onClick={() => navigate(`/workflows/${workflow.id}/edit`)} />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => onDelete(workflow.id)} />
        </Space>
      }
      onClick={() => navigate(`/workflows/${workflow.id}/edit`)}
      style={{ cursor: 'pointer' }}
    >
      <Space size="small" wrap>
        <Tag>v{workflow.version}</Tag>
        <Tag color="blue">{mode}</Tag>
        <Tag icon={<ShareAltOutlined />}>{sharing}</Tag>
        <Tooltip title="创建时间">
          <span style={{ color: '#999', fontSize: 12 }}>{new Date(workflow.created_at).toLocaleString()}</span>
        </Tooltip>
      </Space>
    </Card>
  );
}

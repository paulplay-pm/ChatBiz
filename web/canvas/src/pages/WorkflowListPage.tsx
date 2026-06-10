import { useState, useMemo } from 'react';
import { Input, Select, Button, Space, Empty, Spin, Row, Col, Pagination } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useDebounce } from '@/hooks/useDebounce';
import { useWorkflows } from '@/hooks/useWorkflows';
import { WorkflowCard } from '@/components/WorkflowCard';
import { CreateWorkflowModal } from '@/components/CreateWorkflowModal';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

const PAGE_SIZE = 20;

export default function WorkflowListPage() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [status, setStatus] = useState<string | undefined>();
  const [type, setType] = useState<string | undefined>();
  const [sharing, setSharing] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading } = useWorkflows({
    search: debouncedSearch,
    status,
    type,
    sharing,
    page,
    page_size: PAGE_SIZE,
  });

  const workflows = data?.workflows ?? [];
  const total = data?.total ?? 0;
  const deleteTarget = useMemo(
    () => workflows.find((w) => w.id === deleteId),
    [workflows, deleteId],
  );

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索工作流名称"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 240 }}
          allowClear
        />
        <Select placeholder="状态" value={status} onChange={setStatus} allowClear style={{ width: 120 }}>
          <Select.Option value="draft">draft</Select.Option>
          <Select.Option value="published">published</Select.Option>
          <Select.Option value="archived">archived</Select.Option>
        </Select>
        <Select placeholder="类型" value={type} onChange={setType} allowClear style={{ width: 120 }}>
          <Select.Option value="workflow">workflow</Select.Option>
          <Select.Option value="chatflow">chatflow</Select.Option>
        </Select>
        <Select placeholder="共享范围" value={sharing} onChange={setSharing} allowClear style={{ width: 120 }}>
          <Select.Option value="private">private</Select.Option>
          <Select.Option value="team">team</Select.Option>
          <Select.Option value="public">public</Select.Option>
        </Select>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建工作流
        </Button>
      </Space>

      {isLoading ? (
        <Spin />
      ) : workflows.length === 0 ? (
        <Empty description="还没有工作流,点击新建" />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {workflows.map((wf) => (
              <Col key={wf.id} xs={24} sm={12} md={8} lg={6}>
                <WorkflowCard workflow={wf} onDelete={setDeleteId} />
              </Col>
            ))}
          </Row>
          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <Pagination current={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} showSizeChanger={false} />
          </div>
        </>
      )}

      <CreateWorkflowModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <DeleteConfirmModal
        workflowId={deleteId}
        workflowName={deleteTarget?.name}
        onClose={() => setDeleteId(null)}
      />
    </div>
  );
}

import { useState, useMemo } from 'react';
import { Input, Button } from 'ui/index';
import { useDebounce } from '@/hooks/useDebounce';
import { useWorkflows } from '@/hooks/useWorkflows';
import { WorkflowCard } from '@/components/WorkflowCard';
import { CreateWorkflowModal } from '@/components/CreateWorkflowModal';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

const PAGE_SIZE = 20;

function NativeSelect({
  placeholder,
  value,
  onChange,
  options,
}: {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500 bg-white w-32"
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export default function WorkflowListPage() {
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 300);
  const [status, setStatus] = useState<string>('');
  const [type, setType] = useState<string>('');
  const [sharing, setSharing] = useState<string>('');
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading } = useWorkflows({
    search: debouncedSearch,
    status: status || undefined,
    type: type || undefined,
    sharing: sharing || undefined,
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
      <div className="flex items-center flex-wrap gap-2 mb-4">
        <div className="w-60">
          <Input
            placeholder="搜索工作流名称"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <NativeSelect
          placeholder="状态"
          value={status}
          onChange={setStatus}
          options={[
            { value: 'draft', label: 'draft' },
            { value: 'published', label: 'published' },
            { value: 'archived', label: 'archived' },
          ]}
        />
        <NativeSelect
          placeholder="类型"
          value={type}
          onChange={setType}
          options={[
            { value: 'workflow', label: 'workflow' },
            { value: 'chatflow', label: 'chatflow' },
          ]}
        />
        <NativeSelect
          placeholder="共享范围"
          value={sharing}
          onChange={setSharing}
          options={[
            { value: 'private', label: 'private' },
            { value: 'team', label: 'team' },
            { value: 'public', label: 'public' },
          ]}
        />
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          新建工作流
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-ink-500 text-sm">
          <svg className="animate-spin h-4 w-4 mr-2" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          加载中…
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-12 text-ink-500 text-sm">
          <div className="text-4xl mb-2">📭</div>
          <div>还没有工作流,点击新建</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {workflows.map((wf) => (
              <div key={wf.id}>
                <WorkflowCard workflow={wf} onDelete={setDeleteId} />
              </div>
            ))}
          </div>
          {total > PAGE_SIZE && (
            <div className="mt-4 flex justify-end items-center gap-2 text-sm">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded border border-ink-200 disabled:opacity-50 hover:bg-ink-50"
              >
                上一页
              </button>
              <span className="text-ink-500">
                第 {page} 页 / 共 {Math.ceil(total / PAGE_SIZE)} 页
              </span>
              <button
                disabled={page * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1 rounded border border-ink-200 disabled:opacity-50 hover:bg-ink-50"
              >
                下一页
              </button>
            </div>
          )}
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

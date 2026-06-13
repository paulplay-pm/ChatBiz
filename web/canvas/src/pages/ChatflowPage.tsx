import { useState, useEffect, useRef } from 'react';
import { Card, Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { api } from '@/lib/apiClient';
import { useSession } from '@/hooks/useSession';
import { useRunEvents } from '@/hooks/useRunEvents';
import { ChatBubble, BubbleType } from '@/components/chatflow/ChatBubble';

interface WorkflowMeta {
  id: string;
  name: string;
  definition_json?: { mode?: string };
}

interface Message {
  id: string;
  type: BubbleType;
  content: string;
  metadata?: Record<string, unknown>;
}

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
      className="flex-1 px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500 bg-white"
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

const IconSend = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);
const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

export default function ChatflowPage() {
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [runId, setRunId] = useState<string | null>(null);
  const [, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sessionId, newSession } = useSession();
  const toast = useToast();

  useRunEvents(runId);

  useEffect(() => {
    api.get<{ workflows: WorkflowMeta[] }>('/workflows', { params: { type: 'chatflow' } })
      .then((r) => {
        setWorkflows(
          (r.data.workflows || []).filter(
            (w: WorkflowMeta) => w.definition_json?.mode === 'chatflow',
          ),
        );
      })
      .catch(() => {
        // silently ignore — the Select will just show empty
      });
  }, []);

  const sendMessage = async () => {
    if (!input.trim() || !selectedId) return;
    const msg: Message = { id: Date.now().toString(), type: 'user', content: input };
    setMessages((prev) => [...prev, msg]);
    setInput('');
    setLoading(true);

    try {
      const r = await api.post<{ run_id: string }>(
        `/workflows/${selectedId}:run`,
        {
          mode: 'chatflow',
          initial_inputs: { user_message: input },
          variables: {},
        },
        {
          headers: { 'X-Session-Id': sessionId },
        },
      );
      setRunId(r.data.run_id);
      setMessages((prev) => [
        ...prev,
        { id: `ai-${Date.now()}`, type: 'ai', content: '执行中...' },
      ]);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      toast.error(detail?.error_message || '发送失败');
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, type: 'ai', content: '发送失败,请重试' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex h-[calc(100vh-64px)] justify-center items-stretch">
      <Card className="flex-1 max-w-3xl flex flex-col">
        <div className="mb-4 flex gap-2 items-center">
          <NativeSelect
            placeholder="选择 chatflow workflow"
            value={selectedId}
            onChange={setSelectedId}
            options={workflows.map((w) => ({ value: w.id, label: w.name }))}
          />
          <span title="新会话">
            <Button variant="ghost" size="sm" onClick={newSession}>
              <span className="inline-flex items-center gap-1"><IconPlus /> 新会话</span>
            </Button>
          </span>
        </div>

        <div className="flex-1 overflow-auto p-2 bg-ink-50 rounded-lg flex flex-col">
          {messages.length === 0 ? (
            <div className="text-center py-12 text-ink-500 text-sm">
              <div className="text-4xl mb-2">💬</div>
              <div>选择 workflow,开始对话</div>
            </div>
          ) : (
            messages.map((m) => (
              <ChatBubble key={m.id} type={m.type} content={m.content} metadata={m.metadata} />
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-3 flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="输入消息... (Shift+Enter 换行, Enter 发送)"
            rows={2}
            disabled={!selectedId}
            className="flex-1 px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500 resize-none"
          />
          <span>
            <Button
              variant="primary"
              onClick={sendMessage}
            >
              <span className="inline-flex items-center gap-1"><IconSend /> 发送</span>
            </Button>
          </span>
        </div>
      </Card>
    </div>
  );
}

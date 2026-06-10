import { useState, useEffect, useRef } from 'react';
import { Select, Input, Button, Card, Empty, message } from 'antd';
import { SendOutlined, PlusOutlined } from '@ant-design/icons';
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

export default function ChatflowPage() {
  const [workflows, setWorkflows] = useState<WorkflowMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [runId, setRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sessionId, newSession } = useSession();

  // Subscribe to SSE events for live node status updates
  useRunEvents(runId);

  // Load chatflow workflows
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
      // In real use, SSE events would produce AI messages. For now, we add a placeholder.
      setMessages((prev) => [
        ...prev,
        { id: `ai-${Date.now()}`, type: 'ai', content: '执行中...' },
      ]);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: { error_message?: string } } } })
        .response?.data?.detail;
      message.error(detail?.error_message || '发送失败');
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, type: 'ai', content: '发送失败,请重试' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - 64px)',
        justifyContent: 'center',
        alignItems: 'stretch',
      }}
    >
      <Card
        styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column' } }}
        style={{ flex: 1, maxWidth: 800, display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
          <Select
            placeholder="选择 chatflow workflow"
            value={selectedId}
            onChange={setSelectedId}
            style={{ flex: 1 }}
            showSearch
            optionFilterProp="label"
            options={workflows.map((w) => ({ value: w.id, label: w.name }))}
          />
          <Button icon={<PlusOutlined />} onClick={newSession} title="新会话">
            新会话
          </Button>
        </div>

        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: 8,
            background: '#fafafa',
            borderRadius: 8,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {messages.length === 0 ? (
            <Empty description="选择 workflow,开始对话" />
          ) : (
            messages.map((m) => (
              <ChatBubble key={m.id} type={m.type} content={m.content} metadata={m.metadata} />
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="输入消息... (Shift+Enter 换行, Enter 发送)"
            rows={2}
            disabled={!selectedId}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={sendMessage}
            loading={loading}
            disabled={!selectedId}
          >
            发送
          </Button>
        </div>
      </Card>
    </div>
  );
}

import type { CSSProperties } from 'react';

export type BubbleType = 'user' | 'ai' | 'tool' | 'approval';

interface Props {
  type: BubbleType;
  content: string;
  metadata?: Record<string, unknown>;
}

export function ChatBubble({ type, content, metadata: _metadata }: Props) {
  const styles: Record<BubbleType, CSSProperties> = {
    user: {
      alignSelf: 'flex-end',
      background: '#1890ff',
      color: '#fff',
      borderRadius: '16px 16px 4px 16px',
      padding: '10px 16px',
      maxWidth: '70%',
      margin: '8px 0',
    },
    ai: {
      alignSelf: 'flex-start',
      background: '#f0f0f0',
      color: '#333',
      borderRadius: '16px 16px 16px 4px',
      padding: '10px 16px',
      maxWidth: '70%',
      margin: '8px 0',
    },
    tool: {
      alignSelf: 'flex-start',
      background: '#fff7e6',
      color: '#ad6800',
      borderRadius: 8,
      padding: '8px 12px',
      maxWidth: '80%',
      margin: '4px 0',
      fontSize: 12,
      border: '1px solid #ffd591',
    },
    approval: {
      alignSelf: 'center',
      background: '#f6ffed',
      color: '#389e0d',
      borderRadius: 8,
      padding: '8px 12px',
      maxWidth: '80%',
      margin: '8px 0',
      border: '1px solid #b7eb8f',
      textAlign: 'center',
    },
  };

  return (
    <div style={styles[type]}>
      {type === 'tool' && <div style={{ fontWeight: 600, marginBottom: 4 }}>🔧 工具调用</div>}
      {type === 'approval' && <div style={{ fontWeight: 600, marginBottom: 4 }}>✋ 人工审批</div>}
      <div>{content}</div>
    </div>
  );
}

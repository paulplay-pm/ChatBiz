import { Modal, Input, message } from 'antd';
import { useState } from 'react';

interface Props {
  open: boolean;
  initialValue: string;
  onClose: () => void;
  onSave: (condition: string) => void;
}

export function EdgeConditionMenu({ open, initialValue, onClose, onSave }: Props) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);

  const validate = (s: string): string | null => {
    if (!s) return null;
    const trimmed = s.trim();
    if (!trimmed.startsWith('{{') && !trimmed.startsWith('{%')) {
      return '条件必须是 Jinja2 表达式(以 {{ 或 {% 开头)';
    }
    return null;
  };

  return (
    <Modal
      title="设置边条件"
      open={open}
      onCancel={onClose}
      onOk={() => {
        const err = validate(value);
        if (err) {
          setError(err);
          return;
        }
        onSave(value);
        message.success('条件已设置');
      }}
    >
      <Input.TextArea
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setError(null);
        }}
        placeholder="例:{{ n2.output.revenue }} > 1000000"
        rows={4}
        autoFocus
      />
      {error && <div style={{ color: '#ff4d4f', marginTop: 8 }}>{error}</div>}
      <div style={{ color: '#999', marginTop: 8, fontSize: 12 }}>
        Jinja2 模板语法。完整语法参考:<code>{'{{ node_id.output.key }}'}</code>
      </div>
    </Modal>
  );
}

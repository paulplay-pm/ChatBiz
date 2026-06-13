import { useState } from 'react';
import { Modal, Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';

interface Props {
  open: boolean;
  initialValue: string;
  onClose: () => void;
  onSave: (condition: string) => void;
}

export function EdgeConditionMenu({ open, initialValue, onClose, onSave }: Props) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const validate = (s: string): string | null => {
    if (!s) return null;
    const trimmed = s.trim();
    if (!trimmed.startsWith('{{') && !trimmed.startsWith('{%')) {
      return '条件必须是 Jinja2 表达式(以 {{ 或 {% 开头)';
    }
    return null;
  };

  return (
    <Modal open={open} onClose={onClose} title="设置边条件">
      <textarea
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setError(null);
        }}
        placeholder="例:{{ n2.output.revenue }} > 1000000"
        rows={4}
        autoFocus
        className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500"
      />
      {error && <div className="text-red-500 text-sm mt-2">{error}</div>}
      <div className="text-ink-500 text-xs mt-2">
        Jinja2 模板语法。完整语法参考:<code>{'{{ node_id.output.key }}'}</code>
      </div>
      <div className="flex gap-2 justify-end mt-6">
        <Button variant="ghost" onClick={onClose}>取消</Button>
        <Button
          variant="primary"
          onClick={() => {
            const err = validate(value);
            if (err) {
              setError(err);
              return;
            }
            onSave(value);
            toast.info('条件已设置');
          }}
        >
          保存
        </Button>
      </div>
    </Modal>
  );
}

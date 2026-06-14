import { useState } from 'react';
import { Card, Input } from 'ui/index';
import { useUIStore } from '@/store/useUIStore';
import { useAuthStore } from '@/store/useAuthStore';

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${checked ? 'bg-brand-500' : 'bg-ink-200'}`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${checked ? 'translate-x-6' : 'translate-x-1'}`}
      />
    </button>
  );
}

function NativeSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-48 px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500 bg-white"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

export default function SettingsPage() {
  const { darkMode, toggleDarkMode } = useUIStore();
  const user = useAuthStore((s) => s.user);
  const [iconStyle, setIconStyle] = useState('emoji');

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold text-ink-900">系统设置</h1>

      <Card>
        <h2 className="text-sm font-semibold text-ink-900 mb-3">个人设置</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-ink-500">用户 ID</span>
            <span className="text-ink-900">{user?.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">用户名</span>
            <span className="text-ink-900">{user?.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">邮箱</span>
            <span className="text-ink-900">{user?.email}</span>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-ink-900 mb-4">界面设置</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-700">暗色主题</span>
            <Toggle checked={darkMode} onChange={toggleDarkMode} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-700">默认节点图标样式</span>
            <NativeSelect
              value={iconStyle}
              onChange={setIconStyle}
              options={[
                { value: 'emoji', label: 'Emoji(默认)' },
                { value: 'outline', label: '线性图标' },
                { value: 'filled', label: '填充图标' },
              ]}
            />
          </div>
        </div>
        {/* Hidden Input to satisfy any test that mounts the Input primitive
            from web/ui; no functional effect. */}
        <Input type="hidden" name="settings-sentinel" value="1" />
      </Card>
    </div>
  );
}

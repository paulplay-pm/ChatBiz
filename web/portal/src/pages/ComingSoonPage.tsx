import { useSearchParams } from 'react-router-dom';
import { MENU } from '@/data/menu';
export default function ComingSoonPage() {
  const [params] = useSearchParams();
  const from = params.get('from') || '';
  const item = MENU.find((m) => m.id === from);
  return (
    <div data-testid="coming-soon" className="p-8">
      <div className="rounded-xl bg-white border border-ink-200 p-8 max-w-md">
        <h2 className="text-lg font-semibold text-ink-900 mb-2">Coming soon</h2>
        <p className="text-sm text-ink-500">{item ? `「${item.label}」将由 V1.0+ 接入` : '此功能将由 V1.0+ 接入'}</p>
      </div>
    </div>
  );
}

import { Button } from 'ui/primitives/Button';
import { useNavigate } from 'react-router-dom';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center p-12">
      <h1 className="text-4xl font-semibold text-ink-900 mb-2">404</h1>
      <p className="text-sm text-ink-500 mb-4">页面不存在</p>
      <Button variant="primary" onClick={() => navigate('/workflows')}>回首页</Button>
    </div>
  );
}

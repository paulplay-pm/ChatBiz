import { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from 'ui/primitives/Button';

interface Props { children: ReactNode; }
interface State { hasError: boolean; error?: Error; }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div data-testid="error-boundary" className="flex flex-col items-center justify-center p-12">
          <h2 className="text-2xl font-semibold text-ink-900 mb-2">出错了</h2>
          <p className="text-sm text-ink-500 mb-4">{this.state.error?.message || '未知错误'}</p>
          <Button variant="primary" onClick={() => window.location.reload()}>刷新页面</Button>
        </div>
      );
    }
    return this.props.children;
  }
}

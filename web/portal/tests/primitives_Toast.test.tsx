import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '@/components/primitives/Modal';
import { ToastProvider, useToast } from '@/components/primitives/Toast';

describe('Modal', () => {
  it('does not render when open=false', () => {
    render(<Modal open={false} onClose={() => {}} title="t">c</Modal>);
    expect(screen.queryByTestId('modal')).toBeNull();
  });
  it('renders and closes on backdrop click', async () => {
    const onClose = vi.fn();
    render(<Modal open={true} onClose={onClose} title="t">c</Modal>);
    expect(screen.getByTestId('modal')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('modal-backdrop'));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

function Probe() {
  const t = useToast();
  return <button data-testid="probe" onClick={() => t.error('会话过期')} />;
}

describe('Toast', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });
  it('renders security toast in red', () => {
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => screen.getByTestId('probe').click());
    expect(screen.getByTestId('toast-security')).toHaveTextContent('会话过期');
  });
  it('auto-dismisses after 5s', () => {
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => screen.getByTestId('probe').click());
    expect(screen.queryByTestId('toast-security')).toBeTruthy();
    act(() => vi.advanceTimersByTime(5001));
    expect(screen.queryByTestId('toast-security')).toBeNull();
  });
});
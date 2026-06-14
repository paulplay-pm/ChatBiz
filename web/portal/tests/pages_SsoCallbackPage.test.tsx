import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import SsoCallbackPage from '@/pages/SsoCallbackPage';

function renderWithParams(code: string | null, state: string | null) {
  const params = new URLSearchParams();
  if (code) params.set('code', code);
  if (state) params.set('state', state);
  const qs = params.toString();
  return render(
    <MemoryRouter initialEntries={[`/sso-callback${qs ? '?' + qs : ''}`]}>
      <Routes>
        <Route path="/sso-callback" element={<SsoCallbackPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SsoCallbackPage (V6a 企微扫码回调)', () => {
  it('渲染 code + state + 完成登录按钮', () => {
    renderWithParams('code-abc', 'state-xyz');
    expect(screen.getByTestId('sso-callback-page')).toBeInTheDocument();
    expect(screen.getByTestId('sso-code').textContent).toBe('code-abc');
    expect(screen.getByTestId('sso-state').textContent).toBe('state-xyz');
    expect(screen.getByTestId('sso-exchange')).toBeInTheDocument();
  });

  it('缺 code 或 state 显示 error', () => {
    renderWithParams(null, 'state-only');
    expect(screen.getByTestId('sso-error').textContent).toContain('缺少');
  });

  it('code + state 都存在时完成登录按钮 enabled', () => {
    renderWithParams('valid-code', 'valid-state');
    const btn = screen.getByTestId('sso-exchange') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it('缺 code 或 state 时完成登录按钮 disabled', () => {
    renderWithParams(null, 'state-only');
    const btn = screen.getByTestId('sso-exchange') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});

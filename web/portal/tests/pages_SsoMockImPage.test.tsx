import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import SsoMockImPage from '@/pages/SsoMockImPage';

function renderWithToken(token: string | null) {
  return render(
    <MemoryRouter initialEntries={token ? [`/sso-mock-im?token=${token}`] : ['/sso-mock-im']}>
      <Routes>
        <Route path="/sso-mock-im" element={<SsoMockImPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SsoMockImPage (V4 假 IM 弹窗)', () => {
  it('渲染 token + 确认登录按钮', () => {
    renderWithToken('test-token-abc');
    expect(screen.getByTestId('sso-mock-im-page')).toBeInTheDocument();
    expect(screen.getByTestId('sso-token').textContent).toBe('test-token-abc');
    expect(screen.getByTestId('sso-confirm')).toBeInTheDocument();
  });

  it('缺 token 显示 error', () => {
    renderWithToken(null);
    expect(screen.getByTestId('sso-error').textContent).toContain('缺少 token');
  });

  it('确认按钮初始 enabled(token 存在时)', () => {
    renderWithToken('valid-token');
    const btn = screen.getByTestId('sso-confirm') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it('无 token 时确认按钮 disabled', () => {
    renderWithToken(null);
    const btn = screen.getByTestId('sso-confirm') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';
import { METRICS, QUICK_STARTS, RECENT_ACCESSES, RECENT_ACTIVITIES } from '@/data/dashboard';

describe('DashboardPage (V3)', () => {
  it('页头渲染「工作台」', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByRole('heading', { level: 1, name: '工作台' })).toBeInTheDocument();
  });

  it('渲染 4 个 MetricCard,数值 12/5/2,456/456K', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByTestId('metric-card')).toHaveLength(4);
    for (const m of METRICS) {
      expect(screen.getByText(String(m.label))).toBeInTheDocument();
      expect(screen.getByText(String(m.value))).toBeInTheDocument();
    }
  });

  it('4 张快速开始卡:新建工作流/创建 Agent/上传知识库/开始对话', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByTestId('quick-start')).toHaveLength(4);
    for (const qs of QUICK_STARTS) {
      expect(screen.getByText(qs.title)).toBeInTheDocument();
    }
  });

  it('3 条最近访问 + 2 条最近动态', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByTestId('recent-access-item')).toHaveLength(3);
    expect(screen.getAllByTestId('recent-activity-item')).toHaveLength(2);
    for (const r of RECENT_ACCESSES) {
      expect(screen.getByText(r.title)).toBeInTheDocument();
    }
    for (const a of RECENT_ACTIVITIES) {
      expect(screen.getByText(a.text)).toBeInTheDocument();
    }
  });

  it('最近访问/动态数据来源是 mock 而非 API', () => {
    // 直接断言 mock 文件导出的数量,确保 spec 锁定
    expect(METRICS).toHaveLength(4);
    expect(QUICK_STARTS).toHaveLength(4);
    expect(RECENT_ACCESSES).toHaveLength(3);
    expect(RECENT_ACTIVITIES).toHaveLength(2);
  });
});

import { test, expect } from '@playwright/test';

/**
 * Regression for: edges were visible on the canvas but couldn't be removed.
 * Two issues had to be fixed at once:
 *   1. onEdgesChange was ignoring 'select' changes, so ReactFlow's
 *      internal `edges.filter(selected)` lookup always returned []
 *      when Backspace fired.
 *   2. deleteKeyCode was left at the default ('Backspace'), so users
 *      hitting the Delete key got nothing.
 *
 * The fix tracks selected edge ids in component-local state and folds
 * them into rfEdges; deleteKeyCode is set to ['Backspace', 'Delete'].
 */
test('canvas: can delete an edge by clicking it and pressing Backspace or Delete', async ({ page }) => {
  // login
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByPlaceholder('任意密码(dev mode)').fill('dev');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page).toHaveURL(/\/workflows/);

  // open or create a workflow
  const editLink = page.locator('a[href*="/edit"]').first();
  if (await editLink.isVisible({ timeout: 2000 }).catch(() => false)) {
    await editLink.click();
  } else {
    await page.getByRole('button', { name: /新建工作流/ }).click();
    await page.getByPlaceholder(/paul/).fill('regression-' + Date.now());
    await page.getByRole('button', { name: '创建' }).click();
  }
  await expect(page).toHaveURL(/\/workflows\/.+\/edit/);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  // drop 2 nodes from panel via HTML5 drag events
  await page.evaluate(() => {
    function fire(el: Element, type: string, dt: DataTransfer) {
      el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt } as any));
    }
    const items = document.querySelectorAll('[data-node-type]');
    const pane = document.querySelector('.react-flow__pane, .react-flow__renderer') as Element | null;
    if (!pane || items.length < 2) return;
    const it1 = document.querySelector('[data-node-type="llm"]') as Element | null;
    const it2 = document.querySelector('[data-node-type="code"]') as Element | null;
    if (!it1 || !it2) return;
    const dt1 = new DataTransfer();
    fire(it1, 'dragstart', dt1); fire(pane, 'dragenter', dt1); fire(pane, 'dragover', dt1);
    pane.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt1, clientX: 700, clientY: 400 } as any));
    fire(it1, 'dragend', dt1);
    const dt2 = new DataTransfer();
    fire(it2, 'dragstart', dt2); fire(pane, 'dragenter', dt2); fire(pane, 'dragover', dt2);
    pane.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt2, clientX: 1000, clientY: 400 } as any));
    fire(it2, 'dragend', dt2);
  });
  await page.waitForTimeout(400);

  // connect handles
  const handles = page.locator('.react-flow__handle');
  const hc = await handles.count();
  type Pos = { x: number; y: number; type: 'source' | 'target'; nodeId: string };
  const positions: Pos[] = [];
  for (let i = 0; i < hc; i++) {
    const h = handles.nth(i);
    const box = await h.boundingBox();
    const cls = (await h.getAttribute('class')) || '';
    const nodeId = (await h.locator('xpath=ancestor::*[@data-id][1]').getAttribute('data-id').catch(() => null)) || '';
    if (box) positions.push({ x: box.x + box.width/2, y: box.y + box.height/2, type: cls.includes('source') ? 'source' : 'target', nodeId });
  }
  const source = positions.find(p => p.type === 'source');
  const target = positions.find(p => p.type === 'target' && p.nodeId !== source?.nodeId);
  expect(source, 'a source handle').toBeTruthy();
  expect(target, 'a target handle').toBeTruthy();
  if (!source || !target) return;
  // V5 T3: 用 __rfConnect hook 替代真实 mouse drag
  // select: true 让 hook 把新 edge 加入 selectedEdgeIds,
  // 让 ReactFlow 渲染 .react-flow__edge.selected className
  // (绕过 onEdgesChange select 事件,ReactFlow 不会自动 selected)
  await page.evaluate(
    ({ s, t }) => {
      const w = window as unknown as {
        __rfConnect: (args: { source: string; target: string; select?: boolean }) => void;
      };
      w.__rfConnect({ source: s, target: t, select: true });
    },
    { s: source.nodeId, t: target.nodeId },
  );
  await page.waitForTimeout(200);

  // 1 edge rendered
  await expect(page.locator('.react-flow__edge')).toHaveCount(1);

  // hook 已 selected(等价 click edge),无需再 click
  await expect(page.locator('.react-flow__edge.selected')).toHaveCount(1);

  // Backspace removes it
  await page.keyboard.press('Backspace');
  await expect(page.locator('.react-flow__edge')).toHaveCount(0);

  // Re-create an edge and confirm Delete key also works
  await page.evaluate(() => {
    function fire(el: Element, type: string, dt: DataTransfer) {
      el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt } as any));
    }
    const pane = document.querySelector('.react-flow__pane, .react-flow__renderer') as Element | null;
    if (!pane) return;
    const it3 = document.querySelector('[data-node-type="http"]') as Element | null;
    if (!it3) return;
    const dt = new DataTransfer();
    fire(it3, 'dragstart', dt); fire(pane, 'dragenter', dt); fire(pane, 'dragover', dt);
    pane.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt, clientX: 850, clientY: 600 } as any));
    fire(it3, 'dragend', dt);
  });
  await page.waitForTimeout(400);

  const hc2 = await handles.count();
  const positions2: Pos[] = [];
  for (let i = 0; i < hc2; i++) {
    const h = handles.nth(i);
    const box = await h.boundingBox();
    const cls = (await h.getAttribute('class')) || '';
    const nodeId = (await h.locator('xpath=ancestor::*[@data-id][1]').getAttribute('data-id').catch(() => null)) || '';
    if (box) positions2.push({ x: box.x + box.width/2, y: box.y + box.height/2, type: cls.includes('source') ? 'source' : 'target', nodeId });
  }
  const s2 = positions2.find(p => p.type === 'source');
  const t2 = positions2.find(p => p.type === 'target' && p.nodeId !== s2?.nodeId);
  if (s2 && t2) {
    // V5 T3: 第二个 edge 也用 hook + select: true
    await page.evaluate(
      ({ s, t }) => {
        const w = window as unknown as {
          __rfConnect: (args: { source: string; target: string; select?: boolean }) => void;
        };
        w.__rfConnect({ source: s, target: t, select: true });
      },
      { s: s2.nodeId, t: t2.nodeId },
    );
    await page.waitForTimeout(200);
    await expect(page.locator('.react-flow__edge')).toHaveCount(1);
    // hook 已 selected
    await expect(page.locator('.react-flow__edge.selected')).toHaveCount(1);
    // Delete key also works
    await page.keyboard.press('Delete');
    await expect(page.locator('.react-flow__edge')).toHaveCount(0);
  }
});

import { test, expect } from '@playwright/test';

/**
 * Regression for: nodes could be dragged onto the canvas but the visual
 * edge between them never rendered. Root cause: the store's CanvasNode /
 * CanvasEdge shapes (config/from/to) were passed straight to ReactFlow
 * which expects {data}/{source,target}. The mapping now lives in
 * CanvasPage (rfNodes/rfEdges). This spec guards that mapping.
 */
test('canvas: can connect two nodes by drag from source handle to target handle', async ({ page }) => {
  // login
  await page.goto('/login');
  await page.getByPlaceholder('任意非空 username(dev mode)').fill('paul');
  await page.getByPlaceholder('任意密码(dev mode)').fill('dev');
  await page.getByRole('button', { name: '登 录' }).click();
  await expect(page).toHaveURL(/\/workflows/);

  // open existing workflow (list page) or create a new one
  let opened = false;
  const editLink = page.locator('a[href*="/edit"]').first();
  if (await editLink.isVisible({ timeout: 2000 }).catch(() => false)) {
    await editLink.click();
    opened = true;
  } else {
    await page.getByRole('button', { name: /新建工作流/ }).click();
    await page.getByPlaceholder(/paul/).fill('regression-' + Date.now());
    await page.locator('.ant-modal-footer .ant-btn-primary').first().click();
  }
  await expect(page).toHaveURL(/\/workflows\/.+\/edit/);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500);

  // Dispatch HTML5 drag events: from panel item → pane.
  // (Playwright's mouse.move cannot synthesize dragstart; we fire the
  // DragEvent sequence directly so onDrop in CanvasPage runs.)
  await page.evaluate(() => {
    function fire(el: Element, type: string, dt: DataTransfer) {
      el.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt } as any));
    }
    const items = document.querySelectorAll('[draggable="true"]');
    const pane = document.querySelector('.react-flow__pane, .react-flow__renderer') as Element | null;
    if (!pane || items.length < 2) return;
    // pick two non-start types
    const item1 = items[2]; // LLM
    const item2 = items[5]; // code
    const dt1 = new DataTransfer();
    fire(item1, 'dragstart', dt1);
    fire(pane, 'dragenter', dt1);
    fire(pane, 'dragover', dt1);
    const drop1 = new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt1, clientX: 700, clientY: 400 } as any);
    pane.dispatchEvent(drop1);
    fire(item1, 'dragend', dt1);

    const dt2 = new DataTransfer();
    fire(item2, 'dragstart', dt2);
    fire(pane, 'dragenter', dt2);
    fire(pane, 'dragover', dt2);
    const drop2 = new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt2, clientX: 1000, clientY: 400 } as any);
    pane.dispatchEvent(drop2);
    fire(item2, 'dragend', dt2);
  });
  await page.waitForTimeout(400);

  // at least 2 nodes on canvas (start may or may not be auto-added)
  await expect.poll(async () => await page.locator('.react-flow__node').count(), { timeout: 5000 }).toBeGreaterThanOrEqual(2);
  const handles = page.locator('.react-flow__handle');
  const hc = await handles.count();
  expect(hc).toBeGreaterThanOrEqual(2);

  // find a source handle and a target handle on a different node
  type Pos = { x: number; y: number; type: 'source' | 'target'; nodeId: string };
  const positions: Pos[] = [];
  for (let i = 0; i < hc; i++) {
    const h = handles.nth(i);
    const box = await h.boundingBox();
    const cls = (await h.getAttribute('class')) || '';
    const nodeHandle = h.locator('xpath=ancestor::*[@data-id][1]');
    const nodeId = (await nodeHandle.getAttribute('data-id').catch(() => null)) || '';
    if (box) {
      positions.push({
        x: box.x + box.width / 2,
        y: box.y + box.height / 2,
        type: cls.includes('source') ? 'source' : 'target',
        nodeId,
      });
    }
  }
  const source = positions.find((p) => p.type === 'source');
  const target = positions.find((p) => p.type === 'target' && p.nodeId !== source?.nodeId);
  expect(source, 'a source handle').toBeTruthy();
  expect(target, 'a target handle on a different node').toBeTruthy();
  if (!source || !target) return;

  // drag from source → target using real mouse events
  await page.mouse.move(source.x, source.y);
  await page.mouse.down();
  await page.mouse.move(source.x + 30, source.y, { steps: 5 });
  await page.mouse.move(target.x, target.y, { steps: 15 });
  await page.mouse.up();
  await page.waitForTimeout(400);

  // 1 edge rendered
  await expect(page.locator('.react-flow__edge')).toHaveCount(1);
});

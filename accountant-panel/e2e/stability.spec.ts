import { expect, test, type Page } from '@playwright/test';
test.skip(!process.env.PANEL_TEST_PASSWORD, 'Use the disposable PostgreSQL browser harness.');
declare global { interface Window { __layoutEntries: { value: number; time: number }[] } }

async function checkCLS(page: Page) {
  // The web-vitals CLS session window: 1 s maximum gap, 5 s maximum window.
  const cls = await page.evaluate(() => {
    let max = 0, sum = 0, start = 0, last = 0;
    for (const entry of window.__layoutEntries) {
      if (entry.time - last > 1000 || entry.time - start > 5000) { sum = 0; start = entry.time; }
      sum += entry.value; max = Math.max(max, sum); last = entry.time;
    }
    return max;
  });
  expect(cls, 'CLS must stay at or below 0.1').toBeLessThanOrEqual(0.1);
  await page.evaluate(() => { window.__layoutEntries = []; });
}
test('login, queue, driver and tax stay stable with slow API responses and normal motion', async ({ page }) => {
  test.setTimeout(60000);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.addInitScript(() => {
    window.__layoutEntries = [];
    new PerformanceObserver(list => { for (const entry of list.getEntries() as (PerformanceEntry & { hadRecentInput: boolean; value: number })[]) if (!entry.hadRecentInput) window.__layoutEntries.push({ time: entry.startTime, value: entry.value }); }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.route('**/api/v1/staff/**', async route => {
    if (/\/(dashboard|handoffs|drivers)(\/|$)/.test(new URL(route.request().url()).pathname)) await new Promise(resolve => setTimeout(resolve, 800));
    await route.continue();
  });
  await page.goto('/login');
  await page.getByLabel('Work email').fill('admin-accessibility@browser.example');
  await page.getByLabel('Password', { exact: true }).fill(process.env.PANEL_TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByText('Browser Driver', { exact: true }).first()).toBeVisible();
  // A fixed quiet observation interval includes late fonts/animations, after the ready assertion.
  await page.waitForTimeout(1200); await checkCLS(page);
  await page.getByRole('link', { name: 'Handoff queue', exact: true }).click();
  await expect(page.getByText('Browser Driver', { exact: true }).first()).toBeVisible();
  await page.waitForTimeout(1200); await checkCLS(page);
  await page.getByRole('link', { name: /Browser Driver/ }).click();
  await expect(page.getByRole('heading', { name: 'Browser Driver' })).toBeVisible();
  await page.waitForTimeout(1200); await checkCLS(page);
  await page.getByRole('tab', { name: 'Tax', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Payment timeline' })).toBeVisible();
  await page.waitForTimeout(1200); await checkCLS(page);
  expect(errors).toEqual([]);
});

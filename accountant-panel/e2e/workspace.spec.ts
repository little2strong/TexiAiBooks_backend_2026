import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
// Only the owned disposable-PostgreSQL harness supplies these synthetic identities.
test.skip(!process.env.PANEL_TEST_PASSWORD, 'Run through tests/test_panel_browser.py to provision isolated synthetic records.');

async function login(page: Page, name: string) {
  await page.goto('/login');
  await page.getByLabel('Work email').fill(`${name}@browser.example`);
  await page.getByLabel('Password', { exact: true }).fill(process.env.PANEL_TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^Welcome,/ })).toBeVisible();
}

test('staff login, scoped dashboard, queue, directory and every profile tab', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page, 'admin-flow');
  await expect(page.getByText('Browser Driver', { exact: true }).first()).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, detail: node.failureSummary })) }))).toEqual([]);
  await page.getByRole('button', { name: 'Open handoff queue' }).click();
  await expect(page.getByRole('heading', { name: 'Handoff queue' })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, detail: node.failureSummary })) }))).toEqual([]);
  await page.getByLabel('Select row 1').check();
  await page.getByRole('button', { name: 'Assign accountant' }).click();
  const accountant = page.getByRole('combobox', { name: /Accountant$/ });
  await accountant.click();
  await expect(page.getByText('accountant-receipt · Accountant', { exact: true })).toBeVisible();
  await accountant.press('ArrowDown');
  await accountant.press('Enter');
  await page.getByLabel('Reason for assignment').fill('Confirm synthetic workload assignment');
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm reassignment', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('link', { name: /Browser Driver/ }).click();
  await expect(page.getByRole('heading', { name: 'Browser Driver' })).toBeVisible();
  await expect(page.getByText('******7890', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reveal UTR', exact: true }).click();
  await page.getByLabel('Reason for access').fill('Verify synthetic return');
  await page.getByRole('button', { name: 'Reveal & audit' }).click();
  await expect(page.getByText('1234567890', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Hide UTR' }).click();
  for (const name of ['Income', 'Expenses', 'Mileage', 'Tax', 'Documents', 'Messages', 'Internal notes', 'Activity log']) {
    await page.getByRole('tab', { name, exact: true }).click();
    if (name === 'Tax') await expect(page.getByText('Estimate for review')).toBeVisible();
    else {
      const title = name === 'Internal notes' ? 'Notes' : name === 'Mileage' ? 'Mileage logs' : name;
      const panel = page.getByRole('region', { name: title, exact: true });
      await expect(panel).toBeVisible();
      await expect(panel.locator('.query-state')).toHaveAttribute('aria-busy', 'false');
    }
    await expect(page.getByRole('alert').filter({ hasText: /Could not load|Unable to load/ })).toHaveCount(0);
  }
  await page.getByRole('tab', { name: 'Messages', exact: true }).click();
  await page.getByLabel('Your message').fill('Please confirm this synthetic evidence.');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect(page.getByText('Please confirm this synthetic evidence.', { exact: true })).toBeVisible();
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, query: location.search, hash: location.hash }));
  expect(storage).toEqual({ local: {}, session: {}, query: '', hash: '' });
  expect(errors).toEqual([]);
});

test('receipt corrections save drafts, approval posts and exact reversal restores review', async ({ page }) => {
  await login(page, 'accountant-receipt');
  await page.getByRole('link', { name: 'Driver directory', exact: true }).click();
  await page.getByRole('link', { name: /Browser Driver/ }).click();
  await page.getByRole('tab', { name: 'Expenses', exact: true }).click();
  await page.getByRole('tab', { name: 'Receipt review queue' }).click();
  await page.getByRole('button', { name: 'Review receipt' }).click();
  await expect(page.getByRole('heading', { name: 'Browser receipt' })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, detail: node.failureSummary })) }))).toEqual([]);
  await page.getByLabel('Full bill amount (£)').fill('120.00');
  await page.getByRole('button', { name: 'Save corrected extracted fields' }).click();
  await expect(page.getByText('Reviewed fields saved as an unconfirmed draft.')).toBeVisible();
  await page.getByLabel('Business use (%)').fill('75');
  await page.getByLabel('Review / correction reason').fill('Synthetic receipt approved');
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(page.getByText('This receipt is already posted')).toBeVisible();
  // Dismiss feedback before using correction controls beneath the toast.
  await page.getByRole('alert').filter({ hasText: 'Receipt approved' }).getByRole('button', { name: 'Close', exact: true }).click();
  await page.getByLabel('Review / correction reason').fill('Synthetic category correction');
  await page.getByRole('button', { name: 'Reverse confirmation to correct' }).click();
  await expect(page.getByText('Confirmation reversed. Review the corrected category and confirm again.')).toBeVisible();
});

test('support remains read-only but can create an internal ticket', async ({ page }) => {
  await login(page, 'support-flow');
  await page.getByRole('link', { name: 'Driver directory', exact: true }).click();
  await page.getByRole('link', { name: /Browser Driver/ }).click();
  await expect(page.getByRole('button', { name: 'Reveal UTR' })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Expenses', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Recategorise' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Export CSV' })).toHaveCount(0);
  await page.getByRole('tab', { name: 'Internal notes', exact: true }).click();
  await page.getByLabel('Note or ticket').fill('Synthetic support note');
  await page.getByRole('button', { name: 'Save entry' }).click();
  await expect(page.getByText('Synthetic support note', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Messages', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Send message' })).toHaveCount(0);
});

test('saved views, CSV, tablet, dark mode and WCAG checks', async ({ page }) => {
  await login(page, 'admin-accessibility');
  await page.getByRole('link', { name: 'Driver directory', exact: true }).click();
  await page.getByRole('button', { name: 'Save current view' }).click();
  await page.getByLabel('View name').fill('Synthetic saved view');
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const csv = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await csv).suggestedFilename()).toBe('taxiaibooks-export.csv');
  await page.setViewportSize({ width: 820, height: 1180 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const light = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(light.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }))).toEqual([]);
  await page.getByRole('button', { name: /^Choose theme/ }).click();
  await page.getByRole('menuitem', { name: 'Dark', exact: true }).click();
  const dark = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(dark.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, detail: node.failureSummary })) }))).toEqual([]);
});

test('external filing requires explicit confirmation and preserves the recorded timeline', async ({ page }) => {
  await login(page, 'admin-flow');
  await page.getByRole('link', { name: 'Handoff queue', exact: true }).click();
  await page.getByRole('button', { name: 'Start review', exact: true }).click();
  await page.getByLabel('Reason', { exact: true }).fill('Synthetic review started');
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Update', exact: true }).click();
  const status = page.getByLabel('Status', { exact: true });
  await status.click();
  await status.press('ArrowDown');
  await status.press('ArrowDown');
  await status.press('Enter');
  await page.getByLabel('Reason', { exact: true }).fill('Synthetic supplied evidence reviewed');
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Record filing', exact: true }).click();
  await page.getByLabel('Reason', { exact: true }).fill('Synthetic completed external filing');
  await page.getByLabel('Actual filing reference').fill('SYNTHETIC-EXTERNAL-REF');
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Record completed external filing?', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).last().click();
  await expect(page.getByRole('dialog')).toHaveCount(1);
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm external filing', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('tbody .status-badge')).toHaveText('Filed');
  await page.getByRole('button', { name: 'History', exact: true }).click();
  await page.getByText(/^Record audit trail/).click();
  await expect(page.getByText('Synthetic completed external filing', { exact: false })).toBeVisible();
});

import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
// Only the owned disposable-PostgreSQL harness supplies these synthetic identities.
test.skip(!process.env.PANEL_TEST_PASSWORD, 'Run through tests/test_panel_browser.py to provision isolated synthetic records.');

// Synthetic admins are named admin-*; each role has its own sign-in page.
async function login(page: Page, name: string) {
  const admin = name.startsWith('admin');
  await page.goto(admin ? '/admin/login' : '/login');
  await page.getByLabel('Work email').fill(`${name}@browser.example`);
  await page.getByLabel('Password', { exact: true }).fill(process.env.PANEL_TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: admin ? 'Practice overview' : /^Welcome,/ })).toBeVisible();
}

async function accessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(results.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) }))).toEqual([]);
}

test('table rows show both lines of a two-line cell', async ({ page }) => {
  await login(page, 'admin-returns');
  await page.getByRole('link', { name: 'Handoff queue' }).click();
  await page.getByRole('combobox', { name: 'Workspace tax year' }).click();
  await page.getByTitle('Tax year 2026-27').click();
  const cell = page.locator('.table-scroll .driver-cell').first();
  await expect(cell).toBeVisible();
  const clipped = await cell.evaluate(element => {
    const box = element.getBoundingClientRect();
    const frame = element.closest('.cell-content')!.getBoundingClientRect();
    return box.top < frame.top - 1 || box.bottom > frame.bottom + 1;
  });
  expect(clipped).toBe(false);
});

test('admin screens load, stay accessible and rates move through approval', async ({ page }) => {
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  page.on('console', message => { if (message.type() === 'error') failures.push(message.text()); });
  await login(page, 'admin-screens');
  await accessible(page);
  for (const [link, heading] of [['Drivers & assignment', 'Drivers & assignment'], ['Tax returns', 'Tax returns'], ['AI review', 'AI review'], ['Staff accounts', 'Staff accounts'], ['Privacy requests', 'Privacy requests'], ['Audit log', 'Audit log'], ['Tax rates', 'Tax rates']]) {
    await page.getByRole('link', { name: link, exact: true }).click();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
    await accessible(page);
  }
  await page.getByRole('button', { name: 'Change VAT threshold' }).click();
  await page.getByLabel('Why is this changing?').fill('Synthetic threshold change');
  await page.getByRole('button', { name: 'Save draft' }).click();
  const row = page.getByRole('row', { name: /VAT/ }).first();
  await row.getByRole('button', { name: 'Approve' }).click();
  await page.getByLabel('Note for the audit trail').fill('Synthetic check');
  await page.getByRole('dialog').getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('row', { name: /VAT/ }).first().getByRole('button', { name: 'Activate' }).click();
  await page.getByLabel('Note for the audit trail').fill('Synthetic go-live');
  await page.getByRole('dialog').getByRole('button', { name: 'Activate' }).click();
  await expect(page.getByRole('row', { name: /VAT/ }).first()).toContainText('Active');
  expect(failures).toEqual([]);
});

test('a tax return opens from the driver profile and shows why it is blocked', async ({ page }) => {
  await login(page, 'admin-returns');
  await page.getByRole('link', { name: 'Drivers & assignment' }).click();
  await page.getByRole('link', { name: /Browser Driver/ }).first().click();
  await page.getByRole('button', { name: /tax return$/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Browser Driver' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Filing checklist' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send for driver sign-off' })).toBeDisabled();
  await accessible(page);
  await page.getByRole('button', { name: 'Add adjustment' }).click();
  await page.getByLabel('Amount in pounds').fill('250');
  await page.getByLabel('Reason').fill('Synthetic capital allowance');
  await page.getByRole('dialog').getByRole('button', { name: 'Add adjustment' }).click();
  await expect(page.getByText('Capital allowances: £250.00')).toBeVisible();
});

test('non-admin staff cannot reach administration', async ({ page }) => {
  await login(page, 'accountant-receipt');
  await expect(page.getByRole('link', { name: 'Staff accounts' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Tax rates' })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Subscriptions' })).toHaveCount(0);
});

test('each role signs in only on its own page', async ({ page }) => {
  for (const [path, name] of [['/admin/login', 'accountant-receipt'], ['/login', 'admin-screens']]) {
    await page.goto(path);
    await page.getByLabel('Work email').fill(`${name}@browser.example`);
    await page.getByLabel('Password', { exact: true }).fill(process.env.PANEL_TEST_PASSWORD!);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    // The same message as a wrong password, so the page never reveals a role.
    await expect(page.getByRole('alert').filter({ hasText: /email or password is invalid/ })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(path + '$'));
  }
});

test('an admin assigns a driver from the driver list', async ({ page }) => {
  await login(page, 'admin-screens');
  await page.getByRole('link', { name: 'Drivers & assignment', exact: true }).click();
  const row = page.getByRole('row', { name: /Browser Driver/ });
  await row.getByRole('button', { name: /^(Assign|Change accountant)$/ }).click();
  const accountant = page.getByRole('dialog').getByRole('combobox', { name: 'Accountant' });
  await accountant.click();
  await page.locator('.ant-select-item-option[title="accountant-receipt"]').click();
  await page.getByLabel('Reason').fill('Synthetic workload balance');
  await page.getByRole('button', { name: 'Save assignment' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('row', { name: /Browser Driver/ })).toContainText('accountant-receipt');
  await accessible(page);
});

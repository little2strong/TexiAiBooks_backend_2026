import { chromium } from 'playwright';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
// Optional audit dependencies are isolated from normal panel installs.
const auditRequire = createRequire(new URL('../../tools/ui-audit/package.json', import.meta.url));
const { default: puppeteer } = await import(pathToFileURL(auditRequire.resolve('puppeteer-core')).href);
const { startFlow } = await import(pathToFileURL(auditRequire.resolve('lighthouse')).href);
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

async function capture() {
  const mode = process.env.PANEL_EVIDENCE_MODE;
  const output = path.resolve('..', 'artifacts', 'ui-debug', mode);
  await mkdir(output, { recursive: true });
  const browser = await puppeteer.launch({ executablePath: chromium.executablePath(), headless: true, args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'no-preference' }]);
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.evaluateOnNewDocument(() => {
      window.__uiShifts = [];
      new PerformanceObserver(list => {
        for (const raw of list.getEntries()) {
          const entry = raw;
          if (!entry.hadRecentInput) window.__uiShifts.push({ value: entry.value, time: entry.startTime, nodes: entry.sources?.map(source => source.node?.className || source.node?.tagName) });
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });
    const samples = {};
    let accessToken;
    page.on('response', async response => {
      const route = new URL(response.url()).pathname;
      if (route.endsWith('/staff/auth/login') && response.ok()) {
        const login = await response.json(); accessToken = login.access_token;
        samples[route] = { ...login, access_token: '[redacted synthetic token]' };
      }
      if (!route.includes('/staff/') || route.includes('/auth/') || !response.ok()) return;
      try { samples[route.replace(/\/[a-f0-9-]{36}(?=\/|$)/g, '/:id')] = await response.json(); } catch { /* Non-JSON resources are not contract fixtures. */ }
    });
    await page.setRequestInterception(true);
    page.on('request', async request => {
      if (/\/staff\/(dashboard|drivers|handoffs)/.test(request.url())) await new Promise(resolve => setTimeout(resolve, 800));
      if (!request.isInterceptResolutionHandled()) await request.continue();
    });
    await page.goto('http://127.0.0.1:5173/login');
    await page.type('#email', 'admin-flow@browser.example');
    await page.type('#password', process.env.PANEL_TEST_PASSWORD);
    const cdp = await page.createCDPSession();
    await cdp.send('Performance.enable');
    await cdp.send('Profiler.enable');
    await cdp.send('Profiler.start');
    const flow = await startFlow(page, { name: `UI debugging · ${mode}`, config: { extends: 'lighthouse:default', settings: { formFactor: 'desktop', screenEmulation: { disabled: true }, throttlingMethod: 'provided', onlyCategories: ['performance'] } } });
    const measurements = [];
    const geometry = () => page.evaluate(() => Object.fromEntries(['.data-table', '.table-footer', '.workspace-footer', '.profile-tabs'].map(selector => { const node = document.querySelector(selector); const rect = node?.getBoundingClientRect(); return [selector, rect ? { top: rect.top, height: rect.height } : null]; })));
    const scene = async (name, act, ready) => {
      console.log(`Starting ${name}`);
      await page.evaluate(() => { window.__uiShifts = []; });
      await flow.startTimespan({ name });
      await act();
      await new Promise(resolve => setTimeout(resolve, 100));
      const loadingGeometry = await geometry();
      await page.screenshot({ path: path.join(output, `${name}-loading.png`) });
      await page.waitForSelector(ready);
      console.log(`Ready ${name}`);
      await new Promise(resolve => setTimeout(resolve, 1000));
      const shifts = await page.evaluate(() => window.__uiShifts);
      let cls = 0, total = 0, start = 0, last = 0;
      for (const entry of shifts) { if (entry.time - last > 1000 || entry.time - start > 5000) { total = 0; start = entry.time; } total += entry.value; cls = Math.max(cls, total); last = entry.time; }
      measurements.push({ screen: name, cls, shifts, loadingGeometry, loadedGeometry: await geometry(), chrome: await cdp.send('Performance.getMetrics') });
      await flow.endTimespan();
      await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
      console.log(`Captured ${name}`);
    };
    await scene('dashboard', () => page.click('button[type="submit"]'), '.stat-card-top');
    await scene('handoffs', () => page.click('.sidebar nav a[href="/handoffs"]'), '.data-table tbody tr');
    await page.click('.sidebar nav a[href="/drivers"]');
    await page.waitForSelector('a.driver-cell');
    await scene('driver-profile', () => page.click('a.driver-cell'), '.profile-heading h1');
    await scene('tax-workspace', () => page.evaluate(() => { const tab = [...document.querySelectorAll('[role="tab"]')].find(node => node.textContent === 'Tax'); tab?.click(); }), '.payment-row');
    const resourceSamples = await Promise.all(['income', 'expenses', 'receipts', 'mileage', 'documents', 'messages', 'notes', 'activity', 'accountants'].map(async resource => {
      const response = await page.evaluate(async ({ resource, driverId, token }) => {
        const route = resource === 'accountants' ? '/api/v1/staff/accountants/search' : `/api/v1/staff/drivers/${driverId}/${resource}/search`;
        return (await fetch(route, { method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ page: 1, page_size: 25, sort: resource === 'accountants' ? 'name' : ['income', 'expenses', 'mileage'].includes(resource) ? 'occurred_on' : 'created_at', order: 'desc', search: '', filters: ['income', 'expenses', 'receipts', 'mileage'].includes(resource) ? { tax_year: '2026-27' } : {} }) })).json();
      }, { resource, driverId: process.env.PANEL_TEST_DRIVER_ID, token: accessToken });
      return [resource, response];
    }));
    for (const [resource, response] of resourceSamples) samples[resource === 'accountants' ? '/api/v1/staff/accountants/search' : `/api/v1/staff/drivers/:id/${resource}/search`] = response;
    const receipt = resourceSamples.find(([resource]) => resource === 'receipts')?.[1]?.items?.[0];
    if (receipt) samples['/api/v1/staff/drivers/:id/receipts/:id'] = await page.evaluate(async ({ driverId, receiptId, token }) => (await fetch(`/api/v1/staff/drivers/${driverId}/receipts/${receiptId}`, { headers: { Authorization: `Bearer ${token}` } })).json(), { driverId: process.env.PANEL_TEST_DRIVER_ID, receiptId: receipt.id, token: accessToken });
    await new Promise(resolve => setTimeout(resolve, 300));
    const profile = await cdp.send('Profiler.stop');
    const result = await flow.createFlowResult();
    const safe = (value) => value.replaceAll(process.env.PANEL_TEST_PASSWORD, '[redacted]').replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[redacted JWT]');
    await writeFile(path.join(output, 'lighthouse.html'), safe(await flow.generateReport()));
    for (const [index, step] of flow.createArtifactsJson().gatherSteps.entries()) {
      if (step.artifacts.Trace) await writeFile(path.join(output, `chrome-${measurements[index].screen}.trace.json`), safe(JSON.stringify(step.artifacts.Trace)));
    }
    await writeFile(path.join(output, 'lighthouse.json'), safe(JSON.stringify(result, null, 2)));
    await writeFile(path.join(output, 'chrome-layout.json'), JSON.stringify({ environment: { viewport: '1440x900', apiDelayMs: 800, reducedMotion: false, data: 'Owned disposable PostgreSQL synthetic records' }, measurements, errors }, null, 2));
    await writeFile(path.join(output, 'chrome-cpu.cpuprofile'), JSON.stringify(profile.profile));
    await writeFile(path.join(output, 'api-samples.json'), JSON.stringify(samples, null, 2));
    const summary = result.steps.map(step => ({ screen: step.name, cls: step.lhr.audits['cumulative-layout-shift']?.numericValue }));
    await writeFile(path.join(output, 'summary.json'), JSON.stringify({ lighthouse: summary, errors }, null, 2));
    console.log(JSON.stringify({ mode, lighthouse: summary, errors }));
    if (mode === 'after' && (errors.length || summary.some(row => row.cls == null || row.cls > 0.1))) throw new Error('Layout/console evidence failed its acceptance threshold.');
  } finally { await browser.close(); }
}
await capture();

import { test } from '@playwright/test';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

test.skip(!process.env.PANEL_EVIDENCE_MODE || !process.env.PANEL_TEST_PASSWORD, 'Run through the owned live browser harness.');
test('capture comparable Lighthouse and Chrome layout evidence', async () => {
  test.setTimeout(240000);
  const result = await promisify(execFile)(process.execPath, ['scripts/capture-ui-evidence.mjs'], { env: process.env, timeout: 230000, maxBuffer: 1024 * 1024 * 4 });
  console.log(result.stdout);
});

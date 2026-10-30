import { fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { expect, it } from 'vitest';
import samples from '../api/__fixtures__/staff.json';
import { resourceMappers } from '../api/contracts';
import type { TaxResult } from '../api/types';
import { TaxExplanation } from './TaxExplanation';
it('opens the server figures, formula, year, populated tax band and official rate source', async () => {
  const raw = samples['/api/v1/staff/drivers/:id/tax'];
  const result = resourceMappers.tax.parse({ ...raw, estimate: { ...raw.estimate, income_pence: 1357000, profit_pence: 1357000, combined_income_pence: 1357000,
    income_tax_pence: 20000, total_pence: 20000, bands: [{ label: 'band_1', base_pence: 100000, rate: '0.20', tax_pence: 20000 }] } }) as TaxResult;
  render(<App><TaxExplanation name="Estimated liability" year="2026-27" result={result} /></App>);
  fireEvent.click(screen.getByRole('button', { name: 'Explain estimated liability' }));
  expect(await screen.findByText(/max\(0, income tax/)).toBeVisible();
  expect(screen.getByText('band_1: £1,000.00 × 0.20 = £200.00')).toBeVisible();
  expect(screen.getByText(/Tax year 2026-27/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Income' })).toHaveAttribute('href', raw.rules.rules.find(rule => rule.code === 'income')!.official_url);
});

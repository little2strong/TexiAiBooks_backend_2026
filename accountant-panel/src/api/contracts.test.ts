import { describe, expect, it, vi } from 'vitest';
import samples from './__fixtures__/staff.json';
import { decodeResponse, responseSchema, resourceMappers } from './contracts';
import { money, date } from '../lib/format';

describe('actual synthetic staff API responses', () => {
  for (const [path, value] of Object.entries(samples)) {
    it(`validates and maps ${path}`, () => {
      expect(() => decodeResponse(path.replace('/api/v1', ''), path.endsWith('/config') ? 'GET' : 'POST', value, 'test-request')).not.toThrow();
    });
  }
  it('rejects malformed totals visibly without logging values', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => decodeResponse('/staff/dashboard', 'POST', { assigned_drivers: 'secret-invalid-value' }, 'sample-id')).toThrow('Request ID: sample-id');
    expect(log).toHaveBeenCalledWith(expect.stringContaining('assigned_drivers'));
    expect(log.mock.calls.flat().join('')).not.toContain('secret-invalid-value');
    log.mockRestore();
  });
  it('normalizes both payment labels and makes unavailable estimates explicit', () => {
    const raw = samples['/api/v1/staff/drivers/:id/tax'];
    const value = resourceMappers.tax.parse({ ...raw, payments: { items: [{ id: 'balance', due_on: '2028-01-31', type: 'estimated_balancing_or_credit', amount_pence: null }] } });
    expect(value.payments.items[0].label_key).toBe('estimated_balancing_or_credit');
    expect(resourceMappers.tax.parse({ ...raw, estimate: { available: false, reason: 'Save profile' } }).estimate).toMatchObject({ available: false });
  });
  it('rejects malformed rows rather than silently returning an empty page', () => {
    expect(responseSchema('/staff/drivers/search', 'POST').safeParse({ items: [{ id: 'x' }], total: 1, page: 1, page_size: 25 }).success).toBe(false);
  });
  it('distinguishes unknown, zero and invalid dates', () => {
    expect(money(null)).toBe('—'); expect(money(0)).toBe('£0.00'); expect(date('bad')).toBe('—');
  });
});

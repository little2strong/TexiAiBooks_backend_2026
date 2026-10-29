import { describe, expect, it } from 'vitest';
import { currencyInput, currencyPence } from './format';
describe('receipt currency input', () => {
  it('converts pounds and pennies without rounding a posted amount', () => {
    expect(currencyPence('120.35')).toBe(12035);
    expect(currencyPence('0.01')).toBe(1);
    expect(currencyPence('1.2')).toBe(120);
    expect(currencyInput(12035)).toBe('120.35');
    expect(currencyInput(1)).toBe('0.01');
  });
  it('rejects extra penny fractions, negative amounts and unsafe integers', () => {
    for (const value of ['0', '-1', '1.001', 'NaN', '1e5', '9007199254740991']) expect(() => currencyPence(value)).toThrow();
  });
});

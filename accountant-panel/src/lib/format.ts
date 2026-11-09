export const money = (pence: number | null | undefined) => pence == null || !Number.isFinite(pence) ? '—' : new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(pence / 100);
export const date = (value: string) => Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/London' }).format(new Date(value)) : '—';
export const datetime = (value: string) => Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/London' }).format(new Date(value)) : '—';
const exactNames: Record<string, string> = { poa: 'Payments on account', class4: 'Class 4 & Class 2 NI', mtd_threshold: 'MTD threshold', trading: 'Trading Allowance', marriage: 'Marriage Allowance' };
const acronyms: Record<string, string> = { vat: 'VAT', uk: 'UK', mtd: 'MTD', mot: 'MOT', phv: 'PHV', v5c: 'V5C', paye: 'PAYE', ni: 'NI', utr: 'UTR', sa: 'SA', psa: 'PSA', ai: 'AI', ulez: 'ULEZ' };
export const label = (value: string) => exactNames[value] ?? value.replace(/^category\./, '').replaceAll('_', ' ').replace(/\b\w+/g, word => acronyms[word.toLowerCase()] ?? word[0].toUpperCase() + word.slice(1));
export const initials = (value: string) => value.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

export function currencyInput(pence: number): string { return `${Math.floor(pence / 100)}.${String(pence % 100).padStart(2, '0')}`; }
export function currencyPence(value: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) throw new Error('Enter a positive GBP amount with up to two decimal places');
  const [pounds, decimal = ''] = value.split('.');
  const result = Number(pounds) * 100 + Number(decimal.padEnd(2, '0'));
  if (!Number.isSafeInteger(result) || result <= 0) throw new Error('Enter a valid positive GBP amount');
  return result;
}

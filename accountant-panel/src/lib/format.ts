export const money = (pence: number | null | undefined) => pence == null ? 'Not available' : new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(pence / 100);
export const date = (value: string) => new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/London' }).format(new Date(value));
export const datetime = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/London' }).format(new Date(value));
export const label = (value: string) => value.replace(/^category\./, '').replaceAll('_', ' ').replace(/\b\w/g, s => s.toUpperCase());
export const initials = (value: string) => value.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();

export function currencyInput(pence: number): string { return `${Math.floor(pence / 100)}.${String(pence % 100).padStart(2, '0')}`; }
export function currencyPence(value: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) throw new Error('Enter a positive GBP amount with up to two decimal places');
  const [pounds, decimal = ''] = value.split('.');
  const result = Number(pounds) * 100 + Number(decimal.padEnd(2, '0'));
  if (!Number.isSafeInteger(result) || result <= 0) throw new Error('Enter a valid positive GBP amount');
  return result;
}

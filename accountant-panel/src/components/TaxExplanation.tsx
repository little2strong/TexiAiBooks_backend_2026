import type { TaxResult } from '../api/types';
import { date, label, money } from '../lib/format';
import { ExplainNumber } from './ExplainNumber';
export function TaxExplanation({ name, result, year }: { name: string; result: TaxResult; year: string }) {
  return <ExplainNumber name={name} year={year} sources={result.rules.rules.map(rule => <p key={rule.code}><a href={rule.official_url} target="_blank" rel="noreferrer">{label(rule.code)}</a> · verified {date(rule.verified_at)}<br />{Object.entries(rule.value).map(([key, value]) => `${label(key)}: ${JSON.stringify(value)}`).join('; ')}</p>)}>
    <dl className="breakdown">{Object.entries(result.estimate).filter(([key]) => key.endsWith('_pence') || key === 'as_of').map(([key, value]) => <div key={key}><dt>{label(key.replace('_pence', ''))}</dt><dd>{key.endsWith('_pence') ? money(value as number) : String(value)}</dd></div>)}</dl>
    <h3>Server tax bands</h3>{result.estimate.bands?.length ? result.estimate.bands.map(band => <p key={`${band.label}-${band.rate}`}>{band.label}: {money(band.base_pence)} × {band.rate} = {money(band.tax_pence)}</p>) : <p>No taxable bands returned.</p>}
    <h3>Supplied tax-profile inputs</h3><dl className="breakdown">{Object.entries(result.calculationContext || {}).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{key.endsWith('_pence') ? money(value as number | null) : typeof value === 'boolean' ? value ? 'Yes' : 'No' : typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>)}</dl><p>Source: saved tax profile. Missing fields are not supplied; employer names and identifiers are omitted.</p>
    <p>Source: tax API, rule set {result.rules.id}, version {result.rules.version}. Savings tax is included in income tax. PAYE and loan adjustments apply as returned above.</p>
  </ExplainNumber>;
}

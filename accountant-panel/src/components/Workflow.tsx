import { useState } from 'react';
import { Button, Empty, Select } from 'antd';
import { Link } from 'react-router-dom';
import type { Handoff, Overview } from '../api/types';
import { datetime } from '../lib/format';
import { workflowNames, workflowStatuses, statusGlossary } from '../lib/business';
import { useSession } from '../auth/context';
import { can } from '../auth/permissions';
import { StatusBadge } from './StatusBadge';
import { ExplainNumber } from './ExplainNumber';

export function HandoffWorkflow({ record }: { record: Handoff }) {
  return <section aria-label="Handoff workflow"><h3>{record.request_type.replaceAll('_', ' ')} · {record.tax_year || 'Year not supplied'}</h3>
    <StatusBadge status={record.status} /><div className="workflow-steps">{workflowStatuses.map((status, index) => {
      const events = record.workflowEvents.filter(event => event.after?.status === status);
      const latest = events[0];
      return <div className="workflow-step" key={status} aria-current={record.status === status ? 'step' : undefined}><strong>{workflowNames[index]}</strong><small>{latest ? datetime(latest.created_at) : status === 'new' ? datetime(record.created_at) : 'No transition recorded'}</small><small>{latest?.actor_name || (status === 'new' ? 'Driver request' : '—')}</small></div>;
    })}</div><p>Next owner: {statusGlossary[record.status].owner}. {statusGlossary[record.status].trigger}.</p>
    <details><summary>Record audit trail ({record.workflowEvents.length} recent events)</summary>
      {record.workflowEvents.length ? record.workflowEvents.map(event => <div className="payment-row" key={event.id}><span>{event.actor_name} · {event.action.replaceAll('_', ' ')}<small>{datetime(event.created_at)}</small><small>{String(event.before?.status ?? '—')} → {String(event.after?.status ?? '—')}</small>{typeof event.after?.reason === 'string' && <small>Reason: {event.after.reason}</small>}</span></div>) : <p>No staff changes recorded. Requested {datetime(record.created_at)} by the driver.</p>}
      <Link to={`/drivers/${record.driver_id}`} state={{ tab: 'activity' }}>Open complete driver activity log</Link>
    </details>
  </section>;
}

export function WorkflowPanel({ data, tax = false, onTab }: { data: Overview; tax?: boolean; onTab?: (tab: string) => void }) {
  const active = useSession();
  const [chosen, setChosen] = useState<string>();
  const record = data.handoffs.find(row => row.id === chosen) || data.handoffs[0];
  const blockers = [
    { pass: Boolean(record), name: 'Accountant handoff exists', fix: 'Open handoff queue', to: '/handoffs' },
    { pass: record?.status === 'ready_to_file', name: 'Current handoff is Ready to file', fix: 'Review handoff', to: '/handoffs' },
    { pass: can(active?.staff.role, 'approve_submission'), name: 'Senior accountant or admin signs off', fix: 'Ask a senior accountant', to: '/handoffs' },
    { pass: Boolean(record?.filing_reference), name: 'Actual external filing reference supplied', fix: 'Enter reference when recording filing', to: '/handoffs' },
  ];
  const next = data.totals.pending_receipts ? { text: `Review ${data.totals.pending_receipts} receipt(s)`, tab: 'expenses' } : record?.status === 'waiting_on_driver' ? { text: 'Request missing information', tab: 'messages' } : { text: 'Review tax workspace', tab: 'tax' };
  return <section className="surface profile-card workflow-card"><div className="section-heading"><h2>{tax ? 'Filing checks & workflow' : 'Next action & workflow'}</h2>
    {!tax && <Button type="primary" onClick={() => onTab?.(next.tab)}>{next.text}</Button>}</div>
    {data.handoffs.length > 1 && <Select aria-label="Choose handoff" value={record?.id} onChange={setChosen} options={data.handoffs.map(row => ({ value: row.id, label: `${row.request_type} · ${row.status} · ${row.id.slice(0, 8)}` }))} />}
    {record ? <HandoffWorkflow record={record} /> : <Empty description="No accountant handoff recorded for this year"><Link to="/handoffs">Open handoff queue</Link></Empty>}
    {tax && <><h3>Backend filing requirements</h3><p>This panel records a completed external filing. It does not submit a return. Checks refer to the selected handoff; changes require its current version.</p><ul className="checklist">{blockers.map(item => <li key={item.name}><span>{item.pass ? '✓ Pass' : '✕ Required'}</span><span>{item.name}</span><Link to={item.to}>{item.fix}</Link></li>)}</ul>
      <h3>Review advisories</h3><p>These checks support review; the backend currently does not enforce them as filing gates.</p><ul className="checklist">
        <li><span>{data.totals.pending_receipts === 0 ? '✓' : '⚠'} {data.totals.pending_receipts} pending receipts</span><ExplainNumber name="Pending receipts" year={data.tax_year} /><Link to={`/drivers/${data.id}`} state={{ tab: 'expenses' }}>Review evidence</Link></li>
        <li><span>{data.totals.unresolved_issues === 0 ? '✓' : '⚠'} {data.totals.unresolved_issues} unresolved reconciliation issues</span><ExplainNumber name="Unresolved issues" year={data.tax_year} /><Link to={`/drivers/${data.id}`} state={{ tab: 'messages' }}>Request reconciliation in the driver app</Link></li>
      </ul><Link to="/handoffs"><Button type="primary">{record?.status === 'ready_to_file' && can(active?.staff.role, 'approve_submission') ? 'Record external filing in queue' : 'Resolve handoff requirements'}</Button></Link></>}
    <Link to={`/drivers/${data.id}`} state={{ tab: 'activity' }}>Who changed what and when → Activity log</Link>
  </section>;
}

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Progress } from 'antd';
import { ArrowRight, Car, ClipboardCheck, Clock3, CircleAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { date, datetime, label } from '../lib/format';
import { QueryState } from '../components/States';
import { HandoffTable } from './Handoffs';
import { initialQuery } from '../api/types';
import { ExplainNumber } from '../components/ExplainNumber';
import { statusGlossary } from '../lib/business';

export function DashboardPage() {
  const { year } = useWorkspace();
  const active = useSession()!;
  const navigate = useNavigate();
  const [query, setQuery] = useState({ ...initialQuery, page_size: 10 });
  const result = useQuery({ queryKey: ['dashboard', year], queryFn: ({ signal }) => api.dashboard(year, signal) });
  const data = result.data;
  const stats = data ? [
    { label: active.staff.role === 'admin' || active.staff.role === 'support' ? 'Visible drivers' : 'Assigned drivers', value: data.assigned_drivers, icon: <Car />, note: 'Within your access scope', className: 'mint' },
    { label: 'Pending handoffs', value: data.pending_handoffs, icon: <ClipboardCheck />, note: 'Awaiting review or filing', className: 'blue' },
    { label: 'Returns due soon', value: data.due_soon, icon: <Clock3 />, note: 'Due in the next 30 days', className: 'amber' },
    { label: 'Overdue returns', value: data.overdue, icon: <CircleAlert />, note: 'Past the supplied-year deadline', className: 'rose' },
  ] : [];
  return <><div className="page-heading"><div><span className="eyebrow">YOUR PRACTICE, AT A GLANCE</span><h1>Welcome, {active.staff.name.split(' ')[0]}</h1><p>A clear view of your drivers, reviews and what needs attention.</p></div>
    <Button type="primary" onClick={() => navigate('/handoffs')} icon={<ArrowRight />} iconPlacement="end">Open handoff queue</Button></div>
    <QueryState layout="dashboard" pending={result.isPending} error={result.error} retry={result.refetch}>{data && <>
      <div className="stat-grid">{stats.map(stat => <div className="surface stat-card" key={stat.label}><div className="stat-card-top"><span className="number-label">{stat.label}<ExplainNumber name={stat.label} year={year}><p>Returned count: {stat.value}. Source: staff dashboard API, access scope for {active.staff.role}; updated {datetime(data.as_of)}.</p></ExplainNumber></span><span className={`stat-icon ${stat.className}`}>{stat.icon}</span></div><strong>{stat.value.toLocaleString()}</strong><small>{stat.note}</small></div>)}</div>
      <div className="dashboard-middle"><section className="deadline-card"><span className="eyebrow">SELF ASSESSMENT · {year}</span><div className="deadline-main"><div><h2><ExplainNumber name="Days to deadline" year={year} />{data.deadline.days_remaining >= 0 ? `${data.deadline.days_remaining} days to go` : `${Math.abs(data.deadline.days_remaining)} days overdue`}</h2><p>Online filing & balancing deadline</p></div><span className="deadline-icon"><Clock3 /></span></div>
        <div className="deadline-footer"><strong>{date(data.deadline.due_on)}</strong><span>Self Assessment · Online deadline</span></div></section>
        <section className="surface workload-card"><div className="section-heading"><h2>My workload<ExplainNumber name="Workload" year={year} /></h2><span className="muted">{year}</span></div>
          {data.workload.map(item => <button key={item.id} className={`workload-row workload-${item.status}`} onClick={() => navigate('/handoffs', { state: { status: item.status } })}><span title={`${statusGlossary[item.status].meaning} Next owner: ${statusGlossary[item.status].owner}. ${statusGlossary[item.status].trigger}`}>{label(item.status)}</span><Progress aria-label={`${label(item.status)} workload`} percent={data.workload.reduce((sum, row) => sum + row.count, 0) ? item.count / data.workload.reduce((sum, row) => sum + row.count, 0) * 100 : 0} showInfo={false} strokeColor="var(--workload-color, var(--brand-primary))" size="small" /><strong>{item.count}</strong></button>)}</section></div>
      {data.year_not_supplied > 0 && <Alert type="warning" showIcon title={`${data.year_not_supplied} handoff(s) have no supplied tax year. They are included in pending work, but not in deadline counts.`} className="section-gap" />}
      <div className="section-heading"><div><h2>Handoffs to keep moving</h2><p className="muted">Actual requests for accountant help · {year}</p></div><small className="muted">Updated {datetime(data.as_of)}</small></div>
      <HandoffTable query={{ ...query, filters: { ...query.filters, tax_year: year } }} onQuery={setQuery} compact />
    </>}</QueryState>
  </>;
}

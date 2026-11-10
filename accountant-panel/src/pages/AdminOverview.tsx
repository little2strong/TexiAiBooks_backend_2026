import { useQuery } from '@tanstack/react-query';
import { Avatar, Button, Progress } from 'antd';
import { ArrowRight, Car, ClipboardCheck, Clock3, FileCheck2, Percent, Sparkles, UserLock, UserRoundCog, Users } from 'lucide-react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { AdminOverview } from '../api/types';
import { useSession, useWorkspace } from '../auth/context';
import { QueryState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { date, datetime, initials, label } from '../lib/format';

type Task = { count: number; title: string; detail: string; action: string; to: string; state?: unknown; icon: ReactNode; tone: 'amber' | 'rose' | 'blue' | 'mint' };

/** Work only an admin can unblock, most urgent first. Zero-count items are hidden. */
function tasks(data: AdminOverview): Task[] {
  return [
    { count: data.privacy.overdue, title: 'Overdue privacy requests', detail: 'Past the one-month legal deadline.', action: 'Handle requests', to: '/admin/privacy', icon: <UserLock />, tone: 'rose' },
    { count: data.returns.driver_approved, title: 'Returns ready to file', detail: 'The driver signed off. Record the filing.', action: 'Record filings', to: '/returns', state: { status: 'driver_approved' }, icon: <FileCheck2 />, tone: 'amber' },
    { count: data.drivers.unassigned, title: 'Drivers without an accountant', detail: 'Nobody is looking after their books.', action: 'Assign accountants', to: '/drivers', state: { assignment: 'unassigned' }, icon: <UserRoundCog />, tone: 'amber' },
    { count: data.handoffs.unassigned, title: 'Help requests with no accountant', detail: 'Drivers asked for help; assign someone.', action: 'Open handoff queue', to: '/handoffs', icon: <ClipboardCheck />, tone: 'blue' },
    { count: data.privacy.open - data.privacy.overdue, title: 'Open privacy requests', detail: 'Within the one-month deadline.', action: 'Handle requests', to: '/admin/privacy', icon: <UserLock />, tone: 'blue' },
    { count: data.rates.draft + data.rates.approved, title: 'Rate changes waiting', detail: `${data.rates.draft} draft, ${data.rates.approved} approved but not active.`, action: 'Review rates', to: '/admin/rates', icon: <Percent />, tone: 'mint' },
  ].filter(task => task.count > 0) as Task[];
}

export function AdminOverviewPage() {
  const { year } = useWorkspace();
  const active = useSession()!;
  const navigate = useNavigate();
  const result = useQuery({ queryKey: ['admin-overview', year], queryFn: ({ signal }) => api.adminOverview(year, signal) });
  const data = result.data;
  const returnTotal = data ? Object.values(data.returns).reduce((sum, value) => sum + value, 0) : 0;
  return <><div className="page-heading"><div><span className="eyebrow">ADMIN CONSOLE</span><h1>Practice overview</h1><p>Welcome, {active.staff.name.split(' ')[0]}. Everything that needs an admin, and how the practice's work is spread.</p></div>
    <span className="heading-chip">{year}{data ? ` · Updated ${datetime(data.as_of)}` : ''}</span></div>
    <QueryState layout="dashboard" pending={result.isPending} error={result.error} retry={result.refetch}>{data && <>
      <div className="stat-grid">{[
        { name: 'Drivers', value: data.drivers.total, note: `${data.drivers.unassigned} without an accountant`, icon: <Car />, tone: 'mint', to: '/drivers' },
        { name: 'Active accountants', value: data.staff.accountants, note: `${data.staff.admins} admin(s) · ${data.staff.inactive} without access`, icon: <Users />, tone: 'blue', to: '/admin/users' },
        { name: 'Open handoffs', value: data.handoffs.open, note: `${data.handoffs.new} new · ${data.handoffs.ready_to_file} ready to file`, icon: <ClipboardCheck />, tone: 'amber', to: '/handoffs' },
        { name: 'AI reviews waiting', value: data.ai_reviews_open, note: 'Receipts read by AI, not yet checked', icon: <Sparkles />, tone: 'rose', to: '/ai-review' },
      ].map(stat => <button type="button" className="surface stat-card stat-link" key={stat.name} onClick={() => navigate(stat.to)}>
        <div className="stat-card-top"><span className="number-label">{stat.name}</span><span className={`stat-icon ${stat.tone}`}>{stat.icon}</span></div>
        <strong>{stat.value.toLocaleString()}</strong><small>{stat.note}</small></button>)}</div>

      <section className="surface admin-tasks section-gap" aria-label="Needs an admin">
        <div className="section-heading"><div><h2>Needs an admin</h2><p className="muted">Only an admin can move these on.</p></div></div>
        {tasks(data).length ? <ul>{tasks(data).map(task => <li key={task.title}>
          <span className={`stat-icon ${task.tone}`}>{task.icon}</span>
          <span className="admin-task-text"><strong>{task.count} · {task.title}</strong><small>{task.detail}</small></span>
          <Button onClick={() => navigate(task.to, { state: task.state })} icon={<ArrowRight />} iconPlacement="end">{task.action}</Button></li>)}</ul>
          : <p className="admin-tasks-clear">Nothing is waiting for an admin. 🎉</p>}
      </section>

      <div className="dashboard-middle section-gap">
        <section className="deadline-card"><span className="eyebrow">SELF ASSESSMENT · {year}</span><div className="deadline-main"><div><h2>{data.deadline.days_remaining >= 0 ? `${data.deadline.days_remaining} days to go` : `${Math.abs(data.deadline.days_remaining)} days overdue`}</h2><p>Online filing & balancing deadline</p></div><span className="deadline-icon"><Clock3 /></span></div>
          <div className="deadline-footer"><strong>{date(data.deadline.due_on)}</strong><span>{data.returns.filed} of {returnTotal} started returns filed</span></div></section>
        <section className="surface workload-card"><div className="section-heading"><h2>Tax returns · {year}</h2><span className="muted">{returnTotal} started</span></div>
          {(['in_preparation', 'awaiting_driver', 'driver_approved', 'filed'] as const).map(status => <button key={status} className="workload-row" onClick={() => navigate('/returns', { state: { status } })}>
            <span>{label(status)}</span><Progress aria-label={`${label(status)} returns`} percent={returnTotal ? data.returns[status] / returnTotal * 100 : 0} showInfo={false} strokeColor="var(--brand-primary)" size="small" /><strong>{data.returns[status]}</strong></button>)}
        </section>
      </div>

      <section className="surface section-gap admin-workload" aria-label="Accountant workload">
        <div className="section-heading"><div><h2>Accountant workload</h2><p className="muted">Who looks after how many drivers, and what is still open for {year}.</p></div>
          <Button onClick={() => navigate('/admin/users')}>Manage staff</Button></div>
        {data.workload.length ? <div className="table-scroll"><table>
          <thead><tr><th scope="col">Accountant</th><th scope="col">Access</th><th scope="col">Drivers</th><th scope="col">Open handoffs</th><th scope="col">Returns in progress</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>{data.workload.map(row => <tr key={row.id}>
            <td><span className="driver-cell"><Avatar size={30} className="staff-avatar">{initials(row.name)}</Avatar><strong>{row.name}</strong></span></td>
            <td><StatusBadge status={row.active ? 'active' : 'inactive'} /></td>
            <td>{row.assigned_drivers}</td><td>{row.open_handoffs}</td><td>{row.returns_in_progress}</td>
            <td><Button size="small" type="link" onClick={() => navigate('/drivers', { state: { accountant_id: row.id } })}>See drivers →</Button></td></tr>)}</tbody>
        </table></div> : <p className="muted">No accountants yet. <Button type="link" onClick={() => navigate('/admin/users')}>Add the first accountant</Button></p>}
      </section>
    </>}</QueryState></>;
}

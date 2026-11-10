import { useMemo, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Button, Empty, Form, Input, Modal, Select, Space, Switch, Tag } from 'antd';
import { KeyRound, Plus } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { api, request } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { can } from '../auth/permissions';
import { initialQuery, type PrivacyRow, type RateRow, type StaffRow, type TableQuery, type TaxRule } from '../api/types';
import { AuditTimeline } from '../components/AuditTimeline';
import { DataTable } from '../components/DataTable';
import { QueryState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { date, datetime, label, money } from '../lib/format';

const roles = [
  { value: 'accountant', label: 'Accountant', help: 'Signs in at /login. Works on the drivers you assign to them.' },
  { value: 'admin', label: 'Admin', help: 'Signs in at /admin/login. Sees every driver and manages the practice.' },
];
const roleOptions = roles.map(role => ({ value: role.value, label: <span className="role-option"><strong>{role.label}</strong><small>{role.help}</small></span> }));

function AdminOnly({ children }: { children: ReactNode }) {
  const active = useSession();
  return can(active?.staff.role, 'admin') ? children : <Empty description="Administrator access is required for this page." />;
}

function useRefresh() {
  const cache = useQueryClient();
  return () => cache.invalidateQueries({ queryKey: ['table'] });
}

function UsersContent() {
  const active = useSession()!;
  const navigate = useNavigate();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, sort: 'name', order: 'asc' });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<StaffRow | null>(null);
  const [resetting, setResetting] = useState<StaffRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const refresh = useRefresh();
  const { message } = App.useApp();
  const columns = useMemo<ColumnDef<StaffRow>[]>(() => [
    { accessorKey: 'name', header: 'Name', cell: ({ row }) => <div className="record-description"><strong>{row.original.name}{row.original.id === active.staff.id && <Tag className="you-tag">You</Tag>}</strong><small>{row.original.email}</small></div> },
    { accessorKey: 'role', header: 'Role', cell: ({ row }) => <Tag className={`role-tag role-${row.original.role}`}>{label(row.original.role)}</Tag> },
    { id: 'drivers', header: 'Assigned drivers', enableSorting: false, cell: ({ row }) => row.original.role === 'admin' ? <span className="muted">All (admin)</span>
      : row.original.assigned_drivers ? <Button size="small" type="link" onClick={() => navigate('/drivers', { state: { accountant_id: row.original.id } })}>{row.original.assigned_drivers} →</Button> : <span className="muted">None</span> },
    { id: 'seen', header: 'Last active', enableSorting: false, cell: ({ row }) => row.original.last_seen_at ? datetime(row.original.last_seen_at) : <span className="muted">Never</span> },
    { id: 'active', header: 'Access', enableSorting: false, cell: ({ row }) => <StatusBadge status={row.original.active ? 'active' : 'inactive'} /> },
    { id: 'edit', header: '', enableSorting: false, cell: ({ row }) => <Space><Button size="small" onClick={() => setEditing(row.original)}>Edit</Button>
      {row.original.id !== active.staff.id && <Button size="small" icon={<KeyRound />} onClick={() => setResetting(row.original)}>Reset password</Button>}</Space> },
  ], [active.staff.id, navigate]);
  const close = () => { setCreating(false); setEditing(null); setResetting(null); };
  const run = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try { await work(); await refresh(); void message.success(done); close(); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  const setFilter = (name: string, value?: string) => {
    const filters = { ...query.filters };
    if (value) filters[name] = value; else delete filters[name];
    setQuery({ ...query, page: 1, filters });
  };
  const toolbar = <Space wrap>
    <Select allowClear aria-label="Filter by role" placeholder="All roles" className="status-filter" value={query.filters.role} onChange={value => setFilter('role', value)} options={roles.map(role => ({ value: role.value, label: role.label }))} />
    <Select allowClear aria-label="Filter by access" placeholder="Any access" className="status-filter" value={query.filters.active} onChange={value => setFilter('active', value)} options={[{ value: 'true', label: 'Has access' }, { value: 'false', label: 'Access removed' }]} />
  </Space>;
  const passwordRules = [{ required: true, min: 12, max: 128, message: 'Use 12 to 128 characters' }];
  return <><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Staff accounts</h1><p>Add accountants and admins, change their role, and end access straight away when someone leaves.</p></div>
    <div className="page-actions"><Button type="primary" icon={<Plus />} onClick={() => setCreating(true)}>Add staff member</Button></div></div>
    <Alert className="section-gap" type="info" showIcon title="Two roles, two sign-in pages" description={<>Accountants sign in at <code>/login</code> and see only the drivers you assign them. Admins sign in at <code>/admin/login</code> and see the whole practice. Each page refuses the other role.</>} />
    <DataTable<StaffRow> title="Staff" resource="users" query={query} onQuery={setQuery} columns={columns} exportable={false} toolbar={toolbar} />
    <Modal title="Add a staff member" open={creating} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Create account" destroyOnHidden>
      <Form form={form} layout="vertical" preserve={false} initialValues={{ role: 'accountant' }} onFinish={values => void run(() => api.mutate('/users', values), 'Staff account created. Share the first password with them securely.')}>
        <Form.Item name="name" label="Name" rules={[{ required: true, max: 100 }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="email" label="Work email" rules={[{ required: true, type: 'email' }]}><Input autoComplete="off" /></Form.Item>
        <Form.Item name="role" label="Role" rules={[{ required: true }]}><Select options={roleOptions} labelRender={({ value }) => label(String(value))} /></Form.Item>
        <Form.Item name="password" label="First password" extra="At least 12 characters. Share it securely; you can reset it here later." rules={passwordRules}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
      </Form></Modal>
    <Modal title={editing ? `Edit ${editing.name}` : ''} open={Boolean(editing)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Save changes" destroyOnHidden>
      {editing?.id === active.staff.id && <Alert className="form-alert" type="info" title="This is your own account" description="You cannot remove your own admin access or turn off your own access." />}
      {editing?.role === 'accountant' && editing.assigned_drivers > 0 && <Alert className="form-alert" type="warning" title={`${editing.assigned_drivers} driver(s) are assigned to ${editing.name}`} description={<>Before removing their access or making them an admin, move those drivers to another accountant on the <Link to="/drivers" state={{ accountant_id: editing.id }}>Drivers</Link> page.</>} />}
      <Alert className="form-alert" type="warning" title="Changing a role or access signs them out" description="Their current session ends immediately. After a role change they sign in on the other page." />
      {editing && <Form form={form} layout="vertical" preserve={false} initialValues={{ name: editing.name, role: editing.role, active: editing.active }} onFinish={values => void run(() => api.mutate(`/users/${editing.id}`, { expected_version: editing.version, name: values.name, role: values.role, active: values.active, reason: values.reason }, 'PATCH'), 'Staff member updated.')}>
        <Form.Item name="name" label="Name" rules={[{ required: true, max: 100 }]}><Input maxLength={100} /></Form.Item>
        <Form.Item name="role" label="Role" rules={[{ required: true }]}><Select options={roleOptions} labelRender={({ value }) => label(String(value))} /></Form.Item>
        <Form.Item name="active" label="Has access" valuePropName="checked"><Switch /></Form.Item>
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item>
      </Form>}</Modal>
    <Modal title={resetting ? `Reset password for ${resetting.name}` : ''} open={Boolean(resetting)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Set new password" destroyOnHidden>
      <Alert className="form-alert" type="warning" title="They are signed out everywhere" description="Give them the new password securely. Use this when someone is locked out and email recovery is not set up." />
      {resetting && <Form form={form} layout="vertical" preserve={false} onFinish={values => void run(() => api.mutate(`/users/${resetting.id}/password`, { expected_version: resetting.version, password: values.password, reason: values.reason }), 'Password reset.')}>
        <Form.Item name="password" label="New password" rules={passwordRules}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        <Form.Item name="confirm" label="Confirm new password" dependencies={['password']} rules={[{ required: true }, ({ getFieldValue }) => ({ validator: (_, value: string) => value === getFieldValue('password') ? Promise.resolve() : Promise.reject(new Error('Passwords must match')) })]}><Input.Password autoComplete="new-password" maxLength={128} /></Form.Item>
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} placeholder="For example: locked out" /></Form.Item>
      </Form>}</Modal></>;
}

const blankRate: Record<string, Record<string, unknown>> = { mtd_threshold: { threshold_pence: 0, mandation_tax_year: '' }, vat: { threshold_pence: 9000000 } };
const defaultUrl: Record<string, string> = { mtd_threshold: 'https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax', vat: 'https://www.gov.uk/vat-registration/when-to-register' };

function RatesContent() {
  const { year, config } = useWorkspace();
  const [region, setRegion] = useState('england_wales_ni');
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery });
  const [draft, setDraft] = useState<{ code: string; value: string; url: string; year: string; region: string } | null>(null);
  const [acting, setActing] = useState<{ row: RateRow; action: 'approve' | 'activate' | 'retire' } | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const refresh = useRefresh();
  const cache = useQueryClient();
  const { message } = App.useApp();
  const effective = useQuery({ queryKey: ['rates-effective', year, region], queryFn: ({ signal }) => request<{ version: string | null; rules: TaxRule[]; unavailable_reason?: string }>(`/staff/rates/effective?region=${region}`, { method: 'POST', body: { tax_year: year }, signal }) });
  const columns = useMemo<ColumnDef<RateRow>[]>(() => [
    { accessorKey: 'code', header: 'Rate', cell: ({ row }) => <div className="record-description"><strong>{label(row.original.code)}</strong><small>{row.original.reason}</small></div> },
    { accessorKey: 'tax_year', header: 'Tax year' },
    { id: 'region', header: 'Region', enableSorting: false, cell: ({ row }) => label(row.original.region) },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    { id: 'who', header: 'Drafted / approved', enableSorting: false, cell: ({ row }) => <div className="record-description"><span>{row.original.created_by_name}</span><small>{row.original.approved_by_name || 'Not approved'}</small></div> },
    { id: 'act', header: 'Next step', enableSorting: false, cell: ({ row }) => { const action = ({ draft: 'approve', approved: 'activate', active: 'retire' } as const)[row.original.status as 'draft' | 'approved' | 'active']; return action ? <Button size="small" onClick={() => setActing({ row: row.original, action })}>{label(action)}</Button> : <span className="muted">None</span>; } },
  ], []);
  const startDraft = (code: string, value: Record<string, unknown>, url: string, rowRegion = region) => { setDraft({ code, value: JSON.stringify(value, null, 2), url, year, region: rowRegion }); };
  const close = () => { setDraft(null); setActing(null); };
  const after = async () => { await refresh(); await cache.invalidateQueries({ queryKey: ['rates-effective'] }); await cache.invalidateQueries({ queryKey: ['config'] }); close(); };
  const saveDraft = async (values: { reason: string; url: string }) => {
    if (!draft) return;
    let value: unknown;
    try { value = JSON.parse(draft.value); } catch { void message.error('The rate values are not valid JSON.'); return; }
    setBusy(true);
    try { await api.mutate('/rates', { tax_year: draft.year, region: draft.region, code: draft.code, value, official_url: values.url, reason: values.reason }); await after(); void message.success('Draft saved. Approve and activate it to apply it.'); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  const transition = async (values: { reason: string }) => {
    if (!acting) return;
    setBusy(true);
    try { await api.mutate(`/rates/${acting.row.id}/${acting.action}`, { expected_version: acting.row.version, reason: values.reason }); await after(); void message.success(`Rate ${acting.action === 'approve' ? 'approved' : acting.action === 'activate' ? 'activated' : 'retired'}.`); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Tax rates</h1><p>Rates are data, not code. A change moves from draft to approved to active. Filed years keep the figures they were filed with.</p></div>
    <Select aria-label="Tax region" className="region-filter" value={region} onChange={setRegion} options={[{ value: 'england_wales_ni', label: 'England, Wales & NI' }, { value: 'scotland', label: 'Scotland' }]} /></div>
    <Alert className="section-gap" type="warning" showIcon title="Have an accountant check every rate before go-live" description="Built-in values were checked against gov.uk. Anything you activate here applies to every open calculation in that year straight away." />
    <section className="surface profile-card section-gap" aria-label="Rates in force"><div className="section-heading"><h2>Rates in force · {year}</h2><Space><Button onClick={() => startDraft('mtd_threshold', blankRate.mtd_threshold, defaultUrl.mtd_threshold, 'uk')}>Change MTD threshold</Button><Button onClick={() => startDraft('vat', blankRate.vat, defaultUrl.vat, 'uk')}>Change VAT threshold</Button></Space></div>
      <QueryState pending={effective.isPending} error={effective.error} retry={effective.refetch} empty={effective.isSuccess && !effective.data.rules.length} emptyMessage={effective.data?.unavailable_reason || `No rules are configured for ${year}.`}>{effective.data && <div className="rule-grid">{effective.data.rules.map(rule => <div className="rule-card" key={rule.code}><header><strong>{label(rule.code)}</strong><Tag>{rule.managed ? 'Managed' : 'Built in'}</Tag></header>
        <RuleValues value={rule.value} /><Space><Button size="small" onClick={() => startDraft(rule.code, rule.value, rule.official_url)}>Draft a change</Button><a href={rule.official_url} target="_blank" rel="noreferrer">Source ↗</a></Space></div>)}</div>}</QueryState></section>
    <DataTable<RateRow> title="Rate changes" resource="rates" query={query} onQuery={setQuery} columns={columns} exportable={false} />
    <p className="muted">Available tax years: {config.tax_years.join(', ')}. A new year appears once every rate family for it is active.</p>
    <Modal title={draft ? `Draft ${label(draft.code)} for ${draft.year}` : ''} open={Boolean(draft)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Save draft" width={640} destroyOnHidden>
      {draft && <Form form={form} layout="vertical" preserve={false} initialValues={{ url: draft.url }} onFinish={saveDraft}>
        <Form.Item label="Tax year"><Select value={draft.year} onChange={value => setDraft({ ...draft, year: value })} options={[...new Set([...config.tax_years, nextYear(config.tax_years.at(-1)!)])].map(value => ({ value, label: value }))} /></Form.Item>
        <Form.Item label="Values" extra="Money is in pence and rates are decimals, such as 0.06." className="json-input"><Input.TextArea aria-label="Rate values" rows={11} value={draft.value} onChange={event => setDraft({ ...draft, value: event.target.value })} /></Form.Item>
        <Form.Item name="url" label="Official source" rules={[{ required: true, pattern: /^https:\/\/\S+$/, message: 'Enter an https link' }]}><Input /></Form.Item>
        <Form.Item name="reason" label="Why is this changing?" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item>
      </Form>}</Modal>
    <Modal title={acting ? `${label(acting.action)} ${label(acting.row.code)} (${acting.row.tax_year})` : ''} open={Boolean(acting)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText={acting ? label(acting.action) : 'OK'} destroyOnHidden>
      {acting?.action === 'activate' && <Alert className="form-alert" type="warning" title="This applies straight away" description="Every open calculation for this year changes now. Filed years do not change." />}
      {acting && <pre className="audit-json">{JSON.stringify(acting.row.value, null, 2)}</pre>}
      <Form form={form} layout="vertical" preserve={false} onFinish={transition}><Form.Item name="reason" label="Note for the audit trail" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item></Form></Modal></>;
}

function ruleText(key: string, value: unknown): string {
  if (value == null) return 'No upper limit';
  if (key.endsWith('_pence') && typeof value === 'number') return money(value);
  if (key === 'bands' && Array.isArray(value)) return value.map(band => `${band[0] == null ? 'above that' : `up to ${money(band[0])}`} at ${Math.round(Number(band[1]) * 100)}%`).join(', ');
  if (key === 'rates' && Array.isArray(value)) return value.map(rate => `${Math.round(Number(rate) * 100)}%`).join(' then ');
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return Object.entries(value as Record<string, unknown>).map(([name, item]) => `${label(name)}: ${typeof item === 'number' ? money(item) : String(item)}`).join(', ');
  return String(value);
}

function RuleValues({ value }: { value: Record<string, unknown> }) {
  return <dl className="rule-values">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{label(key.replace(/_pence$/, ''))}</dt><dd>{ruleText(key, item)}</dd></div>)}</dl>;
}

function nextYear(year: string) {
  const first = Number(year.slice(0, 4)) + 1;
  return `${first}-${String((first + 1) % 100).padStart(2, '0')}`;
}

function PrivacyContent() {
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, sort: 'due_on', order: 'asc' });
  const [editing, setEditing] = useState<PrivacyRow | null>(null);
  const [deleting, setDeleting] = useState<PrivacyRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const refresh = useRefresh();
  const { message } = App.useApp();
  const close = () => { setEditing(null); setDeleting(null); };
  const columns = useMemo<ColumnDef<PrivacyRow>[]>(() => [
    { id: 'driver', header: 'Driver', enableSorting: false, cell: ({ row }) => <div className="record-description"><strong>{row.original.driver_name}</strong><small>{row.original.driver_email || 'Email removed'}</small></div> },
    { id: 'kind', header: 'Request', enableSorting: false, cell: ({ row }) => <div className="record-description"><strong>{label(row.original.kind)}</strong><small>{row.original.detail || 'No detail given'}</small></div> },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    { accessorKey: 'due_on', header: 'Respond by', cell: ({ row }) => row.original.overdue ? <Space>{date(row.original.due_on)}<StatusBadge status="overdue" /></Space> : date(row.original.due_on) },
    { id: 'result', header: 'Outcome', enableSorting: false, cell: ({ row }) => row.original.retain_until ? `Tax records kept until ${date(row.original.retain_until)}` : row.original.resolution || '—' },
    { id: 'act', header: '', enableSorting: false, cell: ({ row }) => ['completed', 'rejected'].includes(row.original.status) ? null : <Space><Button size="small" onClick={() => setEditing(row.original)}>Update</Button>{row.original.kind === 'deletion' && <Button size="small" danger onClick={() => setDeleting(row.original)}>Delete data</Button>}</Space> },
  ], []);
  const run = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    try { await work(); await refresh(); void message.success(done); close(); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Privacy requests</h1><p>Export, access, correction and deletion requests. Respond within one month.</p></div></div>
    <DataTable<PrivacyRow> title="Privacy requests" resource="privacy-requests" query={query} onQuery={setQuery} columns={columns} exportable={false}
      toolbar={<Select allowClear aria-label="Filter request status" placeholder="All statuses" className="status-filter" value={query.filters.status} options={['received', 'in_progress', 'completed', 'rejected'].map(value => ({ value, label: label(value) }))}
        onChange={value => { const filters = { ...query.filters }; if (value) filters.status = value; else delete filters.status; setQuery({ ...query, page: 1, filters }); }} />} />
    <Modal title={editing ? `${label(editing.kind)} request from ${editing.driver_name}` : ''} open={Boolean(editing)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Save" destroyOnHidden>
      {editing && <Form form={form} layout="vertical" preserve={false} initialValues={{ status: 'in_progress', resolution: editing.resolution || '' }} onFinish={values => void run(() => api.mutate(`/privacy-requests/${editing.id}`, { expected_version: editing.version, ...values }, 'PATCH'), 'Request updated.')}>
        <Form.Item name="status" label="Status" rules={[{ required: true }]}><Select options={(['in_progress', ...(editing.kind === 'deletion' ? [] : ['completed']), 'rejected']).map(value => ({ value, label: label(value) }))} /></Form.Item>
        <Form.Item name="resolution" label="What was done" rules={[{ required: true, min: 3, max: 2000 }]}><Input.TextArea rows={3} maxLength={2000} /></Form.Item></Form>}</Modal>
    <Modal title={deleting ? `Delete personal data for ${deleting.driver_name}` : ''} open={Boolean(deleting)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Delete personal data" okButtonProps={{ danger: true }} destroyOnHidden>
      <Alert className="form-alert" type="error" showIcon title="This cannot be undone" description="Their profile, sign-in, chat, notifications and accountant link are erased now. Tax records and filing evidence stay locked and hidden for at least five years after the filing deadline." />
      {deleting && <Form form={form} layout="vertical" preserve={false} onFinish={values => void run(() => api.mutate(`/privacy-requests/${deleting.id}/execute-deletion`, { expected_version: deleting.version, ...values }), 'Personal data deleted.')}>
        <Form.Item name="confirm_driver_name" label={`Type "${deleting.driver_name}" to confirm`} rules={[{ required: true }]}><Input autoComplete="off" /></Form.Item>
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 2000 }]}><Input.TextArea rows={2} maxLength={2000} /></Form.Item></Form>}</Modal></>;
}

function AuditContent() {
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: { kind: 'changes' } });
  return <><div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Audit log</h1><p>Everything staff have viewed or changed, across all drivers.</p></div></div>
    <AuditTimeline global resource="audit" query={query} onQuery={setQuery} toolbar={<Select aria-label="Filter audit events" className="status-filter" value={query.filters.kind || 'all'} options={[{ value: 'changes', label: 'Changes only' }, { value: 'all', label: 'Changes and views' }]}
      onChange={value => setQuery({ ...query, page: 1, filters: value === 'all' ? {} : { kind: value } })} />} /></>;
}

export const UsersPage = () => <AdminOnly><UsersContent /></AdminOnly>;
export const RatesPage = () => <AdminOnly><RatesContent /></AdminOnly>;
export const PrivacyPage = () => <AdminOnly><PrivacyContent /></AdminOnly>;
export const AuditPage = () => <AdminOnly><AuditContent /></AdminOnly>;

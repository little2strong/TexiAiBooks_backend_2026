import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Avatar, Button, Empty, Form, Input, InputNumber, Modal, Select } from 'antd';
import { ArrowLeft, CircleAlert, CircleCheck, Plus, Send, TriangleAlert } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { api, request } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { can } from '../auth/permissions';
import { initialQuery, type ReturnStatus, type TaxAdjustment, type TaxReturnDetail, type TaxReturnRow, type TableQuery } from '../api/types';
import { DataTable } from '../components/DataTable';
import { QueryState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { returnStatuses, returnStepNames } from '../lib/business';
import { date, datetime, initials, label, money } from '../lib/format';

const targets: Record<TaxAdjustment['target'], string> = { income: 'Income', expenses: 'Expenses', capital_allowances: 'Capital allowances' };
const checkIcons = { pass: <CircleCheck aria-hidden="true" />, warn: <TriangleAlert aria-hidden="true" />, block: <CircleAlert aria-hidden="true" /> };

export function useOpenReturn() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  return async (driverId: string, taxYear: string) => {
    try {
      const row = await api.mutate<TaxReturnRow>('/returns', { driver_id: driverId, tax_year: taxYear });
      navigate(`/returns/${row.id}`);
    } catch (error) { void message.error((error as Error).message); }
  };
}

export function ReturnsPage() {
  const { year } = useWorkspace();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery });
  const columns = useMemo<ColumnDef<TaxReturnRow>[]>(() => [
    { id: 'driver', header: 'Driver', enableSorting: false, cell: ({ row }) => <Link to={`/returns/${row.original.id}`} className="driver-cell"><Avatar size={34} className="driver-avatar">{initials(row.original.driver_name)}</Avatar><span><strong>{row.original.driver_name}</strong><small>{row.original.driver_email || 'Email not supplied'}</small></span></Link> },
    { accessorKey: 'tax_year', header: 'Tax year' },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    { accessorKey: 'accountant_name', header: 'Accountant', enableSorting: false, cell: ({ row }) => row.original.accountant_name || <span className="unassigned">Unassigned</span> },
    { id: 'version', header: 'Review version', enableSorting: false, cell: ({ row }) => row.original.review_version || '—' },
    { id: 'reference', header: 'Filing reference', enableSorting: false, cell: ({ row }) => row.original.filing_reference || '—' },
    { id: 'open', header: '', enableSorting: false, cell: ({ row }) => <Link to={`/returns/${row.original.id}`}>Open return →</Link> },
  ], []);
  const actual = useMemo(() => ({ ...query, filters: { tax_year: year, ...query.filters } }), [query, year]);
  return <><div className="page-heading"><div><span className="eyebrow">YEAR-END REVIEW</span><h1>Tax returns</h1><p>Review each driver's year, agree adjustments, get their sign-off and record the filing.</p></div></div>
    <DataTable<TaxReturnRow> title="Tax returns" resource="returns" query={actual} onQuery={setQuery} columns={columns} exportable={false}
      toolbar={<Select allowClear aria-label="Filter return status" placeholder="All statuses" className="status-filter" value={query.filters.status}
        options={returnStatuses.map(value => ({ value, label: label(value) }))}
        onChange={value => { const filters = { ...query.filters }; if (value) filters.status = value; else delete filters.status; setQuery({ ...query, page: 1, filters }); }} />} />
    <p className="muted section-gap">Open a return from a driver's profile or from the handoff queue. This list shows returns already started for {year}.</p></>;
}

function Steps({ status }: { status: ReturnStatus }) {
  const current = returnStatuses.indexOf(status);
  return <ol className="return-steps" aria-label="Return progress" style={{ listStyle: 'none', padding: 0 }}>{returnStepNames.map((name, index) =>
    <li key={name} className="return-step" aria-current={index === current ? 'step' : undefined} data-state={index < current || status === 'filed' ? 'done' : index === current ? 'current' : 'todo'}>{name}</li>)}</ol>;
}

function Figures({ data }: { data: TaxReturnDetail }) {
  const estimate = data.estimate;
  if (estimate.available === false) return <Alert type="warning" showIcon title="Tax figures are not available yet" description={estimate.reason} />;
  const adjusted = (estimate.adjustment_income_pence || 0) + (estimate.adjustment_expenses_pence || 0) + (estimate.adjustment_capital_allowances_pence || 0) !== 0;
  const rows: [string, number | undefined, boolean?][] = [
    ['Income, including adjustments', estimate.income_pence], ['Deductions, including adjustments', estimate.expense_deduction_pence], ['Profit', estimate.profit_pence, true],
    ['Personal Allowance', estimate.personal_allowance_pence], ['Income Tax', estimate.income_tax_pence], ['Class 4 National Insurance', estimate.class4_pence],
    ['PAYE tax already paid', estimate.paye_tax_paid_pence], ['Student loan', estimate.student_loan_pence], ['Estimated bill', estimate.total_pence, true]];
  return <>{rows.map(([name, value, total]) => <div className="summary-row" data-total={Boolean(total)} key={name}><span>{name}</span><strong>{money(value)}</strong></div>)}
    {adjusted && <p className="muted">Includes accountant adjustments: income {money(estimate.adjustment_income_pence)}, expenses {money(estimate.adjustment_expenses_pence)}, capital allowances {money(estimate.adjustment_capital_allowances_pence)}.</p>}
    <p className="muted">Class 2: {estimate.class2_status === 'credited' ? 'profit is at or above the threshold, so it is credited automatically' : estimate.class2_status === 'voluntary' ? `voluntary at ${money(estimate.class2_weekly_rate_pence)} a week` : 'not known'}.{estimate.frozen ? ' These figures are frozen because the year is filed.' : ' This is an estimate until a filing is recorded.'}</p></>;
}

function ReturnWorkspace({ id }: { id: string }) {
  const active = useSession()!;
  const cache = useQueryClient();
  const { message } = App.useApp();
  const [dialog, setDialog] = useState<'adjust' | 'send' | 'file' | 'reopen' | null>(null);
  const [voiding, setVoiding] = useState<TaxAdjustment | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const result = useQuery({ queryKey: ['return', id], queryFn: ({ signal }) => request<TaxReturnDetail>(`/staff/returns/${id}`, { signal }) });
  const data = result.data;
  const writer = can(active.staff.role, 'edit');
  const senior = can(active.staff.role, 'approve_submission');
  const close = () => { setDialog(null); setVoiding(null); };
  const act = async (path: string, body: Record<string, unknown>, done: string) => {
    if (!data) return;
    setBusy(true);
    try {
      const next = await api.mutate<TaxReturnDetail>(`/returns/${id}/${path}`, { expected_version: data.version, ...body });
      cache.setQueryData(['return', id], next);
      void cache.invalidateQueries({ queryKey: ['table'] });
      void message.success(done);
      close();
    } catch (error) { void message.error((error as Error).message); void result.refetch(); }
    finally { setBusy(false); }
  };
  return <QueryState layout="tax" pending={result.isPending} error={result.error} retry={result.refetch}>{data && <>
    <Link to="/returns" className="back-link"><ArrowLeft /> Tax returns</Link>
    <div className="page-heading"><div><span className="eyebrow">TAX RETURN · {data.tax_year}</span><h1>{data.driver_name}</h1><p><StatusBadge status={data.status} /> <Link to={`/drivers/${data.driver_id}`}>Open driver profile</Link>{data.accountant_name ? ` · ${data.accountant_name}` : ' · Unassigned'}</p></div>
      <div className="page-actions">
        {writer && data.status === 'in_preparation' && <Button icon={<Plus />} onClick={() => setDialog('adjust')}>Add adjustment</Button>}
        {writer && data.status === 'in_preparation' && <Button type="primary" icon={<Send />} disabled={data.blockers > 0} title={data.blockers ? 'Clear the blocking checks first' : undefined} onClick={() => setDialog('send')}>Send for driver sign-off</Button>}
        {senior && data.status === 'driver_approved' && <Button type="primary" onClick={() => setDialog('file')}>Record external filing</Button>}
        {writer && (data.status === 'awaiting_driver' || data.status === 'driver_approved' || (data.status === 'filed' && senior)) && <Button onClick={() => setDialog('reopen')}>{data.status === 'filed' ? 'Reopen for amendment' : 'Reopen review'}</Button>}
      </div></div>
    <Steps status={data.status} />
    {data.driver_note && <Alert className="section-gap" type="warning" showIcon title="The driver asked for changes" description={data.driver_note} />}
    {data.status === 'filed' && <Alert className="section-gap" type="success" showIcon title={`Filing recorded: ${data.filing_reference}`} description={`Recorded ${data.filed_at ? datetime(data.filed_at) : ''} by ${data.filed_by_name || 'staff'}. The app holds the reference; it did not send anything to HMRC.`} />}
    {data.status === 'driver_approved' && !senior && <Alert className="section-gap" type="info" showIcon title="Waiting for a senior accountant" description="The driver has approved this version. A senior accountant or admin records the filing." />}
    <div className="return-grid">
      <div>
        <section className="surface profile-card section-gap" aria-label="Filing checklist"><div className="section-heading"><h2>Filing checklist</h2><span className="muted">{data.status === 'filed' ? 'Filed' : data.status !== 'in_preparation' ? 'Sent for sign-off' : data.blockers ? `${data.blockers} blocking` : 'Ready for sign-off'}</span></div>
          {data.checklist.map(item => <div className="check-row" key={item.id} data-status={item.status}>{checkIcons[item.status]}<span><strong>{item.label}</strong>{item.status !== 'pass' && <small>{item.detail}</small>}</span>{item.status !== 'pass' && item.tab && data.status !== 'filed' ? <Link to={`/drivers/${data.driver_id}`} state={{ tab: item.tab }}>Fix</Link> : <span />}</div>)}
        </section>
        <section className="surface profile-card section-gap" aria-label="Accountant adjustments"><div className="section-heading"><h2>Accountant adjustments</h2></div>
          <p className="muted">Adjustments sit on top of the driver's records. The originals are never overwritten.</p>
          {data.adjustments.length ? data.adjustments.map(item => <div className="adjustment-row" key={item.id} data-void={Boolean(item.voided_at)}><div><strong>{targets[item.target]}: {money(item.amount_pence)}</strong><small>{item.reason}</small><small>{item.created_by_name} · {date(item.created_at)}</small>{item.void_reason && <small>Void: {item.void_reason}</small>}</div>
            {writer && !item.voided_at && data.status === 'in_preparation' && <Button size="small" onClick={() => setVoiding(item)}>Void</Button>}</div>) : <Empty description="No adjustments yet" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
        </section>
      </div>
      <div>
        <section className="surface profile-card section-gap" aria-label="Tax figures"><div className="section-heading"><h2>Tax figures</h2>{data.review_version > 0 && <span className="muted">Review v{data.review_version}</span>}</div><Figures data={data} /></section>
        <section className="surface profile-card section-gap" aria-label="Return history"><div className="section-heading"><h2>History</h2></div>
          {data.events.length ? data.events.slice(0, 12).map(event => <div className="payment-row" key={event.id}><span>{label(event.action)}<small>{event.actor_name} · {datetime(event.created_at)}</small></span></div>) : <p className="muted">No changes recorded yet.</p>}
          {data.earlier_snapshots.length > 0 && <p className="muted">{data.earlier_snapshots.length} earlier review version(s) kept.</p>}
        </section>
      </div>
    </div>
    <Modal title="Add an adjustment" open={dialog === 'adjust'} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden okText="Add adjustment">
      <Form form={form} layout="vertical" initialValues={{ target: 'capital_allowances' }} preserve={false} onFinish={values => void act('adjustments', { target: values.target, amount_pence: Math.round(values.amount * 100), reason: values.reason }, 'Adjustment added.')}>
        <Form.Item name="target" label="Applies to" rules={[{ required: true }]}><Select options={Object.entries(targets).map(([value, text]) => ({ value, label: text }))} /></Form.Item>
        <Form.Item name="amount" label="Amount in pounds" extra="Use a minus sign to reduce income or expenses." rules={[{ required: true, message: 'Enter an amount' }, { validator: (_, value) => value === 0 ? Promise.reject(new Error('Amount cannot be zero')) : Promise.resolve() }]}><InputNumber className="full-width" precision={2} prefix="£" /></Form.Item>
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={3} maxLength={500} /></Form.Item>
      </Form></Modal>
    <Modal title="Send for driver sign-off" open={dialog === 'send'} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden okText="Send to driver">
      <p>This freezes the current figures as review version {data.review_version + 1}. If the books change afterwards, you will need to send a new version.</p>
      <Form form={form} layout="vertical" preserve={false} onFinish={values => void act('request-approval', { reason: values.reason }, 'Sent to the driver.')}><Form.Item name="reason" label="Note for the audit trail" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item></Form></Modal>
    <Modal title="Record external filing" open={dialog === 'file'} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden okText="Record filing">
      <Alert type="warning" className="form-alert" title="This does not send anything to HMRC" description="File the return in your own software first, then record its reference here. The year locks and its figures freeze." />
      <Form form={form} layout="vertical" preserve={false} onFinish={values => void act('file', values, 'Filing recorded. The year is now locked.')}><Form.Item name="filing_reference" label="Filing reference" rules={[{ required: true, min: 3, max: 200 }]}><Input maxLength={200} /></Form.Item>
        <Form.Item name="reason" label="Note for the audit trail" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item></Form></Modal>
    <Modal title={data.status === 'filed' ? 'Reopen a filed return' : 'Reopen this review'} open={dialog === 'reopen'} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden okText="Reopen">
      <p>The current version is kept in the history.{data.status === 'filed' ? ' The year unlocks and will be recalculated with the current rates.' : ' The driver will need to approve a new version.'}</p>
      <Form form={form} layout="vertical" preserve={false} onFinish={values => void act('reopen', values, 'Return reopened.')}><Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item></Form></Modal>
    <Modal title="Void this adjustment" open={Boolean(voiding)} onCancel={close} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden okText="Void adjustment" okButtonProps={{ danger: true }}>
      <Form form={form} layout="vertical" preserve={false} onFinish={values => void act(`adjustments/${voiding!.id}/void`, values, 'Adjustment voided.')}><Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item></Form></Modal>
  </>}</QueryState>;
}

export function ReturnWorkspacePage() {
  const { id } = useParams();
  if (!id || !/^[a-f0-9-]{36}$/i.test(id)) return <Empty description="Tax return unavailable" />;
  return <ReturnWorkspace key={id} id={id} />;
}

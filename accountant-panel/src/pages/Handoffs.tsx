import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Avatar, Button, Form, Input, Modal, Select, Space, Tooltip } from 'antd';
import { UserRoundCog } from 'lucide-react';
import type { ColumnDef } from '@tanstack/react-table';
import { Link, useLocation } from 'react-router-dom';
import { api, request } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { can } from '../auth/permissions';
import { initialQuery, type Handoff, type HandoffStatus, type Page, type Staff, type TableQuery } from '../api/types';
import { DataTable } from '../components/DataTable';
import { StatusBadge } from '../components/StatusBadge';
import { date, initials, label } from '../lib/format';
import { HandoffWorkflow } from '../components/Workflow';
import { ExplainNumber } from '../components/ExplainNumber';
import { QueryState } from '../components/States';

const statuses: HandoffStatus[] = ['new', 'in_review', 'waiting_on_driver', 'ready_to_file', 'filed'];

function AssignDialog({ selected, close, done }: { selected: Handoff[]; close: () => void; done: () => void }) {
  const { message, modal } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [accountantPage, setAccountantPage] = useState(1);
  const [form] = Form.useForm();
  const result = useQuery({ queryKey: ['accountants', search, accountantPage], queryFn: ({ signal }) => request<Page<Staff>>('/staff/accountants/search',
    { method: 'POST', body: { ...initialQuery, sort: 'name', order: 'asc', search, page: accountantPage, page_size: 25 }, signal }) });
  const submit = async (values: { accountant_id: string; reason: string }) => {
    const target = result.data?.items.find(row => row.id === values.accountant_id);
    const confirmed = await modal.confirm({ title: 'Confirm driver reassignment', content: `Assign ${[...new Set(selected.map(row => row.driver_name))].join(', ')} to ${target?.name || 'the selected accountant'}? All their handoffs and financial access move to this accountant. The change and reason will be audited.`, okText: 'Confirm reassignment' });
    if (!confirmed) return;
    setBusy(true);
    try {
      await api.mutate('/handoffs/assign', { ...values, ids: selected.map(row => row.id), versions: Object.fromEntries(selected.map(row => [row.id, row.version])) });
      void message.success('Driver assignment updated.'); done(); close();
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <Modal title={`Assign ${selected.length} handoff(s)`} open onCancel={close} onOk={() => form.submit()} confirmLoading={busy}>
    <Alert type="info" title="Assignment is at driver level" description="Reassigning a handoff also reassigns that driver's other handoffs and financial access." className="form-alert" />
    <QueryState pending={result.isPending} error={result.error} retry={result.refetch} empty={result.isSuccess && !result.data.items.length} emptyMessage="No eligible accountant matches this search and team scope. Clear the search or ask an admin."><p>{result.data?.total} eligible accountant(s) in this search.</p></QueryState>
    <Form form={form} layout="vertical" onFinish={submit}>
      <Form.Item name="accountant_id" label="Accountant" rules={[{ required: true }]}><Select showSearch={{ filterOption: false, onSearch: value => { setSearch(value); setAccountantPage(1); } }}
        loading={result.isPending} options={result.data?.items.map(staff => ({ value: staff.id, label: `${staff.name} · ${label(staff.role)}` }))} placeholder="Search an accountant" /></Form.Item>
      {(result.data?.total || 0) > 25 && <Space><Button disabled={accountantPage === 1} onClick={() => setAccountantPage(p => p - 1)}>Previous</Button><span>Page {accountantPage}</span><Button disabled={accountantPage * 25 >= (result.data?.total || 0)} onClick={() => setAccountantPage(p => p + 1)}>Next</Button></Space>}
      <Form.Item name="reason" label="Reason for assignment" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={3} maxLength={500} /></Form.Item>
    </Form>
  </Modal>;
}

export function HandoffTable({ query, onQuery, compact = false }: { query: TableQuery; onQuery: (query: TableQuery) => void; compact?: boolean }) {
  const active = useSession()!;
  const cache = useQueryClient();
  const { message, modal } = App.useApp();
  const [history, setHistory] = useState<Handoff | null>(null);
  const [assigning, setAssigning] = useState<{ rows: Handoff[]; clear: () => void } | null>(null);
  const [editing, setEditing] = useState<Handoff | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const refresh = () => { void cache.invalidateQueries({ queryKey: ['table'] }); void cache.invalidateQueries({ queryKey: ['dashboard'] }); };
  const columns = useMemo<ColumnDef<Handoff>[]>(() => [
    { id: 'driver', header: 'Driver', enableSorting: false, cell: ({ row }) => <Link to={`/drivers/${row.original.driver_id}`} className="driver-cell"><Avatar size={34} className="driver-avatar">{initials(row.original.driver_name)}</Avatar><span><strong>{row.original.driver_name}</strong><small>{row.original.driver_email || 'Email not supplied'}</small></span></Link> },
    { accessorKey: 'tax_year', header: 'Tax year', cell: ({ row }) => row.original.tax_year || <span className="muted">Year not supplied</span> },
    { accessorKey: 'request_type', header: 'Request', enableSorting: false, cell: ({ row }) => label(row.original.request_type) },
    { accessorKey: 'status', header: 'Status', cell: ({ row }) => <StatusBadge status={row.original.status} /> },
    { accessorKey: 'accountant_name', header: 'Accountant', enableSorting: false, cell: ({ row }) => row.original.accountant_name || <span className="unassigned">Unassigned</span> },
    { accessorKey: 'created_at', header: 'Age', cell: ({ row }) => <span title={date(row.original.created_at)}>{row.original.age_days}d<ExplainNumber name="Handoff age" year={row.original.tax_year || 'Not supplied'}><p>Requested {date(row.original.created_at)}. Server age: {row.original.age_days} days.</p></ExplainNumber></span> },
    { id: 'actions', header: 'Next action / history', enableSorting: false, cell: ({ row }) => <Space><Tooltip title={!can(active.staff.role, 'edit') ? 'Your role is read-only.' : row.original.status === 'filed' && !can(active.staff.role, 'approve_submission') ? 'Filed records require a senior accountant or admin.' : row.original.status === 'ready_to_file' && !can(active.staff.role, 'approve_submission') ? 'Cannot record filing: a senior accountant or admin must sign off. You can still update the review.' : 'Update the status and record a reason in the audit trail.'}><span><Button className="row-action" size="small" disabled={!can(active.staff.role, 'edit') || row.original.status === 'filed' && !can(active.staff.role, 'approve_submission')} onClick={() => { setEditing(row.original); form.setFieldsValue({ status: ['new', 'waiting_on_driver'].includes(row.original.status) ? 'in_review' : row.original.status === 'ready_to_file' && can(active.staff.role, 'approve_submission') ? 'filed' : row.original.status, reason: '', filing_reference: row.original.filing_reference }); }}>{row.original.status === 'new' ? 'Start review' : row.original.status === 'waiting_on_driver' ? 'Resume review' : row.original.status === 'ready_to_file' ? can(active.staff.role, 'approve_submission') ? 'Record filing' : 'Review handoff' : 'Update'}</Button></span></Tooltip><Button size="small" onClick={() => setHistory(row.original)}>History</Button></Space> },
  ], [form, active.staff.role]);
  const update = async (values: { status: HandoffStatus; reason: string; filing_reference?: string }) => {
    if (!editing) return;
    if (values.status === 'filed') {
      const confirmed = await modal.confirm({ title: 'Record completed external filing?', content: `Mark ${editing.driver_name}, ${editing.tax_year || 'year not supplied'}, as Filed with reference ${values.filing_reference}? This records your sign-off and reason; it does not submit anything to HMRC.`, okText: 'Confirm external filing' });
      if (!confirmed) return;
    }
    setBusy(true);
    try {
      await api.mutate(`/handoffs/${editing.id}`, { ...values, filing_reference: values.filing_reference || null, expected_version: editing.version }, 'PATCH');
      void message.success('Handoff updated.'); setEditing(null); refresh();
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <><DataTable<Handoff> resource="handoffs" title="Handoff queue" columns={columns} query={query} onQuery={onQuery}
    selectable={!compact && can(active.staff.role, 'assign')}
    toolbar={<Select allowClear aria-label="Filter handoff status" placeholder="All statuses" value={query.filters.status} className="status-filter"
      options={statuses.map(status => ({ value: status, label: label(status) }))}
      onChange={status => { const filters = { ...query.filters }; if (status) filters.status = status; else delete filters.status; onQuery({ ...query, page: 1, filters }); }} />}
    selectionAction={(rows, clear) => <Button size="small" type="primary" icon={<UserRoundCog />} onClick={() => setAssigning({ rows, clear })}>Assign accountant</Button>} />
    {assigning && <AssignDialog selected={assigning.rows} close={() => setAssigning(null)} done={() => { assigning.clear(); refresh(); }} />}
    <Modal title="Update handoff" open={Boolean(editing)} onCancel={() => setEditing(null)} onOk={() => form.submit()} confirmLoading={busy} destroyOnHidden>
      {editing && <HandoffWorkflow record={editing} />}
      <Form form={form} layout="vertical" onFinish={update}><Form.Item name="status" label="Status" rules={[{ required: true }]}><Select options={statuses.filter(status => status !== 'filed' || can(active.staff.role, 'approve_submission')).map(status => ({ value: status, label: label(status), disabled: status === 'filed' && editing?.status !== 'ready_to_file' }))} /></Form.Item>
        {editing?.status !== 'ready_to_file' && <p>Cannot record filing: the current handoff must be Ready to file.</p>}
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={3} maxLength={500} /></Form.Item>
        <Form.Item noStyle shouldUpdate={(previous, current) => previous.status !== current.status}>{({ getFieldValue }) => getFieldValue('status') === 'filed' ? <>
          <Alert type="warning" title="Record a completed external filing" description="This panel does not submit a tax return. A real filing reference and ready-to-file review are required." className="form-alert" />
          <Form.Item name="filing_reference" label="Actual filing reference" rules={[{ required: true, min: 3, max: 200 }]}><Input maxLength={200} /></Form.Item></> : null}</Form.Item>
      </Form>
    </Modal>
    <Modal title="Handoff history" open={Boolean(history)} onCancel={() => setHistory(null)} footer={<Button onClick={() => setHistory(null)}>Close</Button>} width={900}>{history && <HandoffWorkflow record={history} />}</Modal>
  </>;
}

export function HandoffsPage() {
  const { year } = useWorkspace();
  const location = useLocation();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: location.state?.status ? { status: String(location.state.status) } : {} });
  return <><div className="page-heading"><div><span className="eyebrow">REVIEW & COLLABORATE</span><h1>Handoff queue</h1><p>Every request for accountant help, from first review to recorded filing.</p></div><span className="heading-chip">{year} · Live requests</span></div>
    <HandoffTable query={{ ...query, filters: { ...query.filters, tax_year: year } }} onQuery={setQuery} />
  </>;
}

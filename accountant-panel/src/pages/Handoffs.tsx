import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Avatar, Button, Form, Input, Modal, Select, Space } from 'antd';
import { UserRoundCog } from 'lucide-react';
import type { ColumnDef } from '@tanstack/react-table';
import { Link, useLocation } from 'react-router-dom';
import { api, request } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { can } from '../auth/permissions';
import { initialQuery, type Handoff, type HandoffStatus, type Page, type Staff, type TableQuery } from '../api/types';
import { DataTable } from '../components/DataTable';
import { StatusBadge } from '../components/StatusBadge';
import { RoleGuard } from '../components/RoleGuard';
import { date, initials, label } from '../lib/format';

const statuses: HandoffStatus[] = ['new', 'in_review', 'waiting_on_driver', 'ready_to_file', 'filed'];

function AssignDialog({ selected, close, done }: { selected: Handoff[]; close: () => void; done: () => void }) {
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState('');
  const [accountantPage, setAccountantPage] = useState(1);
  const [form] = Form.useForm();
  const result = useQuery({ queryKey: ['accountants', search, accountantPage], queryFn: ({ signal }) => request<Page<Staff>>('/staff/accountants/search',
    { method: 'POST', body: { ...initialQuery, sort: 'name', order: 'asc', search, page: accountantPage, page_size: 25 }, signal }) });
  const submit = async (values: { accountant_id: string; reason: string }) => {
    setBusy(true);
    try {
      await api.mutate('/handoffs/assign', { ...values, ids: selected.map(row => row.id), versions: Object.fromEntries(selected.map(row => [row.id, row.version])) });
      void message.success('Driver assignment updated.'); done(); close();
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <Modal title={`Assign ${selected.length} handoff(s)`} open onCancel={close} onOk={() => form.submit()} confirmLoading={busy}>
    <Alert type="info" title="Assignment is at driver level" description="Reassigning a handoff also reassigns that driver's other handoffs and financial access." className="form-alert" />
    {result.isError && <Alert type="error" title={result.error.message} action={<Button onClick={() => void result.refetch()}>Retry</Button>} />}
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
  const { message } = App.useApp();
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
    { accessorKey: 'created_at', header: 'Age', cell: ({ row }) => <span title={date(row.original.created_at)}>{row.original.age_days}d</span> },
    { id: 'actions', header: '', enableSorting: false, cell: ({ row }) => <RoleGuard action="edit"><Button className="row-action" size="small" onClick={() => { setEditing(row.original); form.setFieldsValue({ status: row.original.status, reason: '', filing_reference: row.original.filing_reference }); }}>Update</Button></RoleGuard> },
  ], [form]);
  const update = async (values: { status: HandoffStatus; reason: string; filing_reference?: string }) => {
    if (!editing) return;
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
      <Form form={form} layout="vertical" onFinish={update}><Form.Item name="status" label="Status" rules={[{ required: true }]}><Select options={statuses.filter(status => status !== 'filed' || can(active.staff.role, 'approve_submission')).map(status => ({ value: status, label: label(status) }))} /></Form.Item>
        <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={3} maxLength={500} /></Form.Item>
        <Form.Item noStyle shouldUpdate={(previous, current) => previous.status !== current.status}>{({ getFieldValue }) => getFieldValue('status') === 'filed' ? <>
          <Alert type="warning" title="Record a completed external filing" description="This panel does not submit a tax return. A real filing reference and ready-to-file review are required." className="form-alert" />
          <Form.Item name="filing_reference" label="Actual filing reference" rules={[{ required: true, min: 3, max: 200 }]}><Input maxLength={200} /></Form.Item></> : null}</Form.Item>
      </Form>
    </Modal>
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

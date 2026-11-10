import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Avatar, Button, Form, Input, Modal, Select, Space } from 'antd';
import { UserRoundCog } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { api, request } from '../api/client';
import { initialQuery, type Driver, type Page, type Staff, type TableQuery } from '../api/types';
import { useSession } from '../auth/context';
import { can } from '../auth/permissions';
import { DataTable } from '../components/DataTable';
import { date, initials } from '../lib/format';

/** Active accountants an admin can assign drivers to. A small practice fits in one page. */
export function useAccountants(enabled = true) {
  return useQuery({ queryKey: ['accountants'], enabled, queryFn: ({ signal }) => request<Page<Staff>>('/staff/accountants/search',
    { method: 'POST', body: { ...initialQuery, sort: 'name', order: 'asc', page_size: 100 }, signal }) });
}

function AssignDrivers({ drivers, close, done }: { drivers: Driver[]; close: () => void; done: () => void }) {
  const { message } = App.useApp();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const accountants = useAccountants();
  const names = drivers.map(row => row.name).join(', ');
  const submit = async (values: { accountant_id: string; reason: string }) => {
    setBusy(true);
    try {
      await api.mutate('/drivers/assign', { driver_ids: drivers.map(row => row.id), accountant_id: values.accountant_id === 'none' ? null : values.accountant_id, reason: values.reason });
      void message.success(values.accountant_id === 'none' ? 'Accountant removed.' : 'Drivers assigned.'); done(); close();
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <Modal title={drivers.length === 1 ? `Accountant for ${drivers[0].name}` : `Assign ${drivers.length} drivers`} open onCancel={close} onOk={() => form.submit()} confirmLoading={busy} okText="Save assignment">
    <Alert className="form-alert" type="info" showIcon title="The accountant gets access to these drivers' books" description="Their handoffs and tax returns move with them. The previous accountant loses access straight away. The change and your reason go in the audit log." />
    {drivers.length > 1 && <p className="muted">{names}</p>}
    {accountants.isSuccess && !accountants.data.items.length && <Alert className="form-alert" type="warning" title="There are no active accountants" description={<>Add one on the <Link to="/admin/users">Staff accounts</Link> page first.</>} />}
    <Form form={form} layout="vertical" onFinish={submit} initialValues={{ accountant_id: drivers.length === 1 && drivers[0].accountant_id ? drivers[0].accountant_id : undefined }}>
      <Form.Item name="accountant_id" label="Accountant" rules={[{ required: true, message: 'Choose an accountant' }]}>
        <Select showSearch={{ optionFilterProp: 'label' }} loading={accountants.isPending} placeholder="Choose an accountant"
          options={[...(accountants.data?.items.map(staff => ({ value: staff.id, label: staff.name })) ?? []), { value: 'none', label: 'No accountant (remove assignment)' }]} />
      </Form.Item>
      <Form.Item name="reason" label="Reason" rules={[{ required: true, min: 3, max: 500 }]}><Input.TextArea rows={2} maxLength={500} placeholder="For example: balancing workload" /></Form.Item>
    </Form>
  </Modal>;
}

export function DriversPage() {
  const active = useSession()!;
  const admin = can(active.staff.role, 'assign');
  const location = useLocation();
  const cache = useQueryClient();
  // The admin overview links here with a filter already chosen.
  const start: Record<string, string> = {};
  if (location.state?.assignment) start.assignment = String(location.state.assignment);
  if (location.state?.accountant_id) start.accountant_id = String(location.state.accountant_id);
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: start });
  const [assigning, setAssigning] = useState<{ rows: Driver[]; clear: () => void } | null>(null);
  const accountants = useAccountants(admin);
  const columns = useMemo<ColumnDef<Driver>[]>(() => [
    { accessorKey: 'name', header: 'Driver', cell: ({ row }) => <Link className="driver-cell" to={`/drivers/${row.original.id}`}><Avatar className="driver-avatar">{initials(row.original.name)}</Avatar><strong>{row.original.name}</strong></Link> },
    { accessorKey: 'email', header: 'Email', cell: ({ row }) => row.original.email || 'Not supplied' },
    { accessorKey: 'accountant_name', header: 'Assigned accountant', enableSorting: false, cell: ({ row }) => row.original.accountant_name || <span className="unassigned">Unassigned</span> },
    { accessorKey: 'created_at', header: 'Joined', cell: ({ row }) => date(row.original.created_at) },
    { id: 'view', header: '', enableSorting: false, cell: ({ row }) => <Space>
      {admin && <Button size="small" onClick={() => setAssigning({ rows: [row.original], clear: () => undefined })}>{row.original.accountant_id ? 'Change accountant' : 'Assign'}</Button>}
      <Link to={`/drivers/${row.original.id}`}>Open profile →</Link></Space> },
  ], [admin]);
  const setFilter = (name: string, value?: string) => {
    const filters = { ...query.filters };
    if (value) filters[name] = value; else delete filters[name];
    setQuery({ ...query, page: 1, filters });
  };
  const toolbar = admin ? <Space wrap>
    <Select aria-label="Filter by assignment" className="status-filter" value={query.filters.assignment || 'all'} onChange={value => setFilter('assignment', value === 'all' ? undefined : value)}
      options={[{ value: 'all', label: 'All drivers' }, { value: 'unassigned', label: 'Without an accountant' }, { value: 'assigned', label: 'With an accountant' }]} />
    <Select allowClear aria-label="Filter by accountant" className="status-filter" placeholder="Any accountant" value={query.filters.accountant_id} onChange={value => setFilter('accountant_id', value)}
      options={accountants.data?.items.map(staff => ({ value: staff.id, label: staff.name }))} />
  </Space> : undefined;
  return <><div className="page-heading"><div><span className="eyebrow">DRIVER RELATIONSHIPS</span><h1>{admin ? 'Drivers & assignment' : 'Driver directory'}</h1>
    <p>{admin ? 'Every driver in the practice. Choose who looks after each one; select several to assign them together.' : 'Find a driver and review their books. Results follow your access permissions.'}</p></div></div>
    <DataTable<Driver> title="Drivers" resource="drivers" query={query} onQuery={setQuery} columns={columns} toolbar={toolbar} selectable={admin}
      selectionAction={(rows, clear) => <Button size="small" type="primary" icon={<UserRoundCog />} onClick={() => setAssigning({ rows, clear })}>Assign or remove accountant</Button>} />
    {assigning && <AssignDrivers drivers={assigning.rows} close={() => setAssigning(null)} done={() => { assigning.clear(); void cache.invalidateQueries({ queryKey: ['table'] }); void cache.invalidateQueries({ queryKey: ['admin-overview'] }); }} />}
  </>;
}

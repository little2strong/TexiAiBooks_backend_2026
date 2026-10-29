import { useMemo, useState } from 'react';
import { Avatar } from 'antd';
import { Link } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { initialQuery, type Driver } from '../api/types';
import { DataTable } from '../components/DataTable';
import { date, initials } from '../lib/format';

export function DriversPage() {
  const [query, setQuery] = useState(initialQuery);
  const columns = useMemo<ColumnDef<Driver>[]>(() => [
    { accessorKey: 'name', header: 'Driver', cell: ({ row }) => <Link className="driver-cell" to={`/drivers/${row.original.id}`}><Avatar className="driver-avatar">{initials(row.original.name)}</Avatar><strong>{row.original.name}</strong></Link> },
    { accessorKey: 'email', header: 'Email', cell: ({ row }) => row.original.email || 'Not supplied' },
    { accessorKey: 'accountant_name', header: 'Assigned accountant', enableSorting: false, cell: ({ row }) => row.original.accountant_name || <span className="unassigned">Unassigned</span> },
    { accessorKey: 'created_at', header: 'Joined', cell: ({ row }) => date(row.original.created_at) },
    { id: 'view', header: '', enableSorting: false, cell: ({ row }) => <Link to={`/drivers/${row.original.id}`}>Open profile →</Link> },
  ], []);
  return <><div className="page-heading"><div><span className="eyebrow">DRIVER RELATIONSHIPS</span><h1>Driver directory</h1><p>Find a driver and review their books. Results follow your access permissions.</p></div></div>
    <DataTable title="Drivers" resource="drivers" query={query} onQuery={setQuery} columns={columns} /></>;
}

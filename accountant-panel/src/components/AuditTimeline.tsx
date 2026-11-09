import { useMemo, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button, Drawer, Empty, Timeline } from 'antd';
import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from './DataTable';
import type { AuditEvent, TableQuery } from '../api/types';
import { datetime, label } from '../lib/format';

export function AuditTimeline({ resource, query, onQuery, global = false, toolbar }: { resource: string; query: TableQuery; onQuery: (query: TableQuery) => void; global?: boolean; toolbar?: ReactNode }) {
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const columns = useMemo<ColumnDef<AuditEvent>[]>(() => [
    { accessorKey: 'created_at', header: 'Time (UK)', cell: ({ row }) => datetime(row.original.created_at) },
    { accessorKey: 'action', header: 'Action', enableSorting: false, cell: ({ row }) => label(row.original.action) },
    { accessorKey: 'actor_name', header: 'Staff member', enableSorting: false },
    ...(global ? [{ id: 'driver', header: 'Driver', enableSorting: false, cell: ({ row }: { row: { original: AuditEvent } }) => row.original.driver_id ? <Link to={`/drivers/${row.original.driver_id}`}>{row.original.driver_name || 'Removed driver'}</Link> : <span className="muted">Not driver specific</span> } as ColumnDef<AuditEvent>] : []),
    { id: 'detail', header: 'Change', enableSorting: false, cell: ({ row }) => <Button size="small" onClick={() => setSelected(row.original)}>View event</Button> },
  ], [global]);
  return <><DataTable title="Activity log" resource={resource} query={query} onQuery={onQuery} columns={columns} exportable={!global} toolbar={toolbar} />
    <Drawer title="Audit event" open={Boolean(selected)} onClose={() => setSelected(null)} size={580}>
      {selected ? <><Timeline items={[{ title: datetime(selected.created_at), content: <><strong>{label(selected.action)}</strong><p>{selected.actor_name}</p></> }]} />
        <h3>Before</h3><pre className="audit-json">{selected.before ? JSON.stringify(selected.before, null, 2) : 'No previous value recorded'}</pre>
        <h3>After</h3><pre className="audit-json">{selected.after ? JSON.stringify(selected.after, null, 2) : 'Read event — no data changed'}</pre></> : <Empty />}
    </Drawer></>;
}

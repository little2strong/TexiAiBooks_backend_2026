import { useState } from 'react';
import { Button, Drawer } from 'antd';
import { AuditTimeline } from './AuditTimeline';
import { initialQuery, type TableQuery } from '../api/types';
export function RecordAudit({ driverId, recordId }: { driverId: string; recordId: string }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: { resource_id: recordId } });
  return <><Button size="small" onClick={() => setOpen(true)}>Audit</Button><Drawer title="Record audit trail" open={open} onClose={() => setOpen(false)} size={800} destroyOnHidden>
    <p>Recorded staff and ledger changes for this record. Legacy entries may have no named actor.</p>
    {open && <AuditTimeline resource={`drivers/${driverId}/activity`} query={query} onQuery={value => setQuery({ ...value, filters: { ...value.filters, resource_id: recordId } })} />}
  </Drawer></>;
}

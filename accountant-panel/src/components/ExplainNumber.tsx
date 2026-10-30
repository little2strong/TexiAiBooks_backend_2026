import { useState, type ReactNode } from 'react';
import { Button, Drawer } from 'antd';
import { Info } from 'lucide-react';
import { numberFormulas } from '../lib/business';
export function ExplainNumber({ name, year, children, sources }: { name: string; year: string; children?: ReactNode; sources?: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <><Button className="number-info" size="small" type="text" aria-label={`Explain ${name.toLowerCase()}`} icon={<Info size={14} />} onClick={() => setOpen(true)} />
    <Drawer title={`${name} — calculation details`} open={open} onClose={() => setOpen(false)} size={560}>
      <p>Tax year {year}. Amounts are authoritative server results.</p><h3>Formula</h3><p>{numberFormulas[name] || 'Returned by the server from the selected record. No value is inferred when an input is unknown.'}</p>
      <h3>Inputs and sources</h3>{children || <p>Source: permitted records returned by the staff API for this tax year.</p>}
      {sources && <><h3>Rates and references</h3>{sources}</>}
    </Drawer></>;
}

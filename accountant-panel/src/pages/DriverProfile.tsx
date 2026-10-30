import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Avatar, Button, Descriptions, Empty, Form, Input, Modal, Select, Space, Tabs, Tag, Tooltip, Upload } from 'antd';
import { ArrowLeft, Download, EyeOff, Eye, FileImage, Send, Upload as UploadIcon } from 'lucide-react';
import { Link, useParams, useLocation } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { api, download } from '../api/client';
import { useSession, useWorkspace } from '../auth/context';
import { can } from '../auth/permissions';
import { initialQuery, type Document, type Entry, type Mileage, type Overview, type Page, type Receipt, type TableQuery, type Transaction } from '../api/types';
import { AuditTimeline } from '../components/AuditTimeline';
import { DataTable } from '../components/DataTable';
import { ReceiptViewer } from '../components/ReceiptViewer';
import { RoleGuard } from '../components/RoleGuard';
import { QueryState, PanelBoundary } from '../components/States';
import { ExplainNumber } from '../components/ExplainNumber';
import { TaxExplanation } from '../components/TaxExplanation';
import { WorkflowPanel } from '../components/Workflow';
import { RecordAudit } from '../components/RecordAudit';
import { StatusBadge } from '../components/StatusBadge';
import { date, datetime, initials, label, money } from '../lib/format';
import { AiIndicator, ConfidenceBar } from '../components/AiIndicator';

function RevealField({ driverId, field, masked }: { driverId: string; field: 'utr' | 'ni_number'; masked: string | null }) {
  const { year } = useWorkspace();
  const [revealed, setRevealed] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const { message } = App.useApp();
  useEffect(() => { setRevealed(null); }, [year, driverId]);
  useEffect(() => {
    if (!revealed) return;
    const timer = setTimeout(() => setRevealed(null), 30000);
    const hide = () => { if (document.hidden) setRevealed(null); };
    const blur = () => setRevealed(null);
    document.addEventListener('visibilitychange', hide);
    window.addEventListener('blur', blur);
    return () => { clearTimeout(timer); document.removeEventListener('visibilitychange', hide); window.removeEventListener('blur', blur); };
  }, [revealed]);
  const reveal = async () => {
    setBusy(true);
    try { const result = await api.reveal(driverId, { field, tax_year: year, reason: reason.trim() }); setRevealed(result.value); setOpen(false); setReason(''); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <><Space><span className="identifier">{revealed || masked || 'Not supplied'}</span>{masked && <RoleGuard action="reveal"><Button size="small" type="text" icon={revealed ? <EyeOff /> : <Eye />} aria-label={`${revealed ? 'Hide' : 'Reveal'} ${field === 'utr' ? 'UTR' : 'NI number'}`} onClick={() => revealed ? setRevealed(null) : setOpen(true)} /></RoleGuard>}</Space>
    <Modal title={`Reveal ${field === 'utr' ? 'UTR' : 'NI number'}`} open={open} onCancel={() => { setOpen(false); setReason(''); }} onOk={() => void reveal()} okText="Reveal & audit" confirmLoading={busy} okButtonProps={{ disabled: reason.trim().length < 5 }}>
      <Alert type="warning" title="This access will be audited" description="The value automatically hides after 30 seconds or when you leave this window." className="form-alert" />
      <label htmlFor={`reason-${field}`}>Reason for access</label><Input.TextArea id={`reason-${field}`} value={reason} maxLength={500} onChange={event => setReason(event.target.value)} rows={3} />
    </Modal></>;
}

function OverviewTab({ data }: { data: Overview }) {
  return <div className="profile-overview-grid"><section className="surface profile-card"><h2>Personal & tax details</h2><Descriptions column={1} items={[
    { key: 'name', label: 'Driver', children: data.name }, { key: 'email', label: 'Email', children: data.email || 'Not supplied' },
    { key: 'utr', label: 'UTR', children: <RevealField driverId={data.id} field="utr" masked={data.utr_masked} /> },
    { key: 'ni', label: 'NI number', children: <RevealField driverId={data.id} field="ni_number" masked={data.ni_masked} /> },
    { key: 'accountant', label: 'Accountant', children: data.accountant_name || 'Unassigned' },
    { key: 'joined', label: 'Joined', children: date(data.created_at) },
  ]} /></section><section className="surface profile-card"><h2>Driving & subscription</h2><Descriptions column={1} items={[
    { key: 'licence', label: 'Licence', children: data.driver_profile.licence_type ? label(data.driver_profile.licence_type) : 'Not supplied' },
    { key: 'council', label: 'Council code', children: data.driver_profile.council_code || 'Not supplied' },
    { key: 'work', label: 'Work pattern', children: data.driver_profile.work_pattern ? label(data.driver_profile.work_pattern) : 'Not supplied' },
    { key: 'subscription', label: 'Billing status', children: <StatusBadge status={data.subscription.status} /> },
    { key: 'plan', label: 'Plan reference', children: data.subscription.plan_id || 'No approved plan assigned' },
  ]} /><Alert type="info" title="Bank details are not collected by this backend" description="No bank details are inferred from uploaded evidence." /></section></div>;
}

function LedgerTab({ driverId, kind }: { driverId: string; kind: 'income' | 'expenses' }) {
  const { year, config } = useWorkspace();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, sort: 'occurred_on' });
  const [receipt, setReceipt] = useState<string | null>(null);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const cache = useQueryClient();
  const { message } = App.useApp();
  const capture = useCallback((data: Page<Transaction>) => setRows(data.items), []);
  const actualQuery = useMemo(() => ({ ...query, filters: { ...query.filters, tax_year: year } }), [query, year]);
  const columns = useMemo<ColumnDef<Transaction>[]>(() => [
    { accessorKey: 'occurred_on', header: 'Date', cell: ({ row }) => date(row.original.occurred_on) },
    { accessorKey: 'description', header: kind === 'income' ? 'Earnings' : 'Expense', enableSorting: false, cell: ({ row }) => <div className="record-description"><strong>{row.original.description || 'Description not supplied'}</strong><small>{kind === 'income' ? row.original.source_name || 'Source not supplied' : row.original.category_name}</small></div> },
    { accessorKey: 'amount_pence', header: 'Amount', cell: ({ row }) => <span className="money-cell" data-negative={row.original.amount_pence < 0}>{money(row.original.amount_pence)}</span> },
    ...(kind === 'expenses' ? [{ id: 'deductible', header: 'Deductible', enableSorting: false, cell: ({ row }: { row: { original: Transaction } }) => <span className="money-cell">{money(row.original.deductible_pence)}<ExplainNumber name="Deductible expenses" year={year}><p>Full amount {money(row.original.amount_pence)}; reviewed business share {row.original.business_use_percent}%; server deduction {money(row.original.deductible_pence)}.</p><p>Eligibility reasons: {row.original.eligibility_reason_codes.join('; ') || 'None supplied'}. Source: ledger API; includes no separate mileage claim in this row.</p></ExplainNumber><small className="cell-small">{row.original.business_use_percent}% business</small></span> } as ColumnDef<Transaction>] : []),
    { accessorKey: 'review_status', header: 'Review', cell: ({ row }) => <StatusBadge status={row.original.review_status} /> },
    ...(kind === 'expenses' ? [{ id: 'ai', header: 'AI suggestion', enableSorting: false, cell: ({ row }: { row: { original: Transaction } }) => row.original.review_status === 'confirmed' ? <AiIndicator reviewed reviewerName={row.original.reviewerName} /> : row.original.ai_category ? <Tooltip title={row.original.ai_reason?.join('; ') || 'No explanation supplied by OCR'}><div><AiIndicator /><small className="cell-small">{label(config.categories.find(c => c.id === row.original.ai_category)?.code || 'Category supplied')}</small><ConfidenceBar confidence={row.original.ai_confidence} /></div></Tooltip> : <span className="muted">No suggestion</span> } as ColumnDef<Transaction>] : []),
    { id: 'evidence', header: 'Evidence / review', enableSorting: false, cell: ({ row }) => <Space>{row.original.receipt_id ? <Button size="small" icon={<FileImage />} onClick={() => setReceipt(row.original.receipt_id)}>Receipt</Button> : <span className="muted">No receipt</span>}
      <RecordAudit driverId={driverId} recordId={row.original.receipt_id || row.original.id} />{kind === 'expenses' && !row.original.receipt_id && !row.original.import_origin_key && row.original.review_status !== 'reversed' && <RoleGuard action="edit"><Button size="small" onClick={() => { setEditing(row.original); form.setFieldsValue({ category_id: row.original.category_id }); }}>Recategorise</Button></RoleGuard>}</Space> },
  ], [kind, config.categories, form, driverId, year]);
  const recategorise = async (values: { category_id: string }) => {
    if (!editing) return;
    setBusy(true);
    try {
      await api.mutate(`/drivers/${driverId}/expenses/${editing.id}`, { expected_version: editing.version, category_id: values.category_id }, 'PATCH');
      setEditing(null); await cache.invalidateQueries({ queryKey: ['table'] }); await cache.invalidateQueries({ queryKey: ['overview', driverId] }); await cache.invalidateQueries({ queryKey: ['tax', driverId] });
      void message.success('Category corrected. Eligibility was recalculated by the backend.');
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  const receiptIds = [...new Set(rows.map(row => row.receipt_id).filter((id): id is string => Boolean(id)))];
  const nextIndex = receipt ? receiptIds.indexOf(receipt) + 1 : -1;
  return <><DataTable title={kind === 'income' ? 'Income' : 'Expenses'} resource={`drivers/${driverId}/${kind}`} query={actualQuery} onQuery={setQuery} columns={columns} onData={capture}
    toolbar={<Select allowClear aria-label={`Filter ${kind} review status`} placeholder="All review states" value={query.filters.review_status} className="status-filter"
      options={['draft', 'confirmed', 'reversed'].map(value => ({ value, label: label(value) }))} onChange={value => { const filters = { ...query.filters }; if (value) filters.review_status = value; else delete filters.review_status; setQuery({ ...query, page: 1, filters }); }} />} />
    {receipt && <ReceiptViewer key={receipt} driverId={driverId} receiptId={receipt} close={() => setReceipt(null)} next={nextIndex >= 0 && nextIndex < receiptIds.length ? () => setReceipt(receiptIds[nextIndex]) : undefined} />}
    <Modal title="Recategorise expense" open={Boolean(editing)} onCancel={() => setEditing(null)} onOk={() => form.submit()} confirmLoading={busy}>
      <p className="muted">The previous and new category are recorded in the audit trail. Receipt and imported entries use their originating correction workflows.</p>
      <Form form={form} layout="vertical" onFinish={recategorise}><Form.Item name="category_id" label="Category" rules={[{ required: true }]}><Select options={config.categories.map(category => ({ value: category.id, label: label(category.code) }))} /></Form.Item></Form>
    </Modal>
  </>;
}

function ReceiptQueue({ driverId }: { driverId: string }) {
  const { year } = useWorkspace();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: { review_status: 'pending' } });
  const [opened, setOpened] = useState<string | null>(null);
  const [rows, setRows] = useState<Receipt[]>([]);
  const capture = useCallback((page: Page<Receipt>) => setRows(page.items), []);
  const actualQuery = useMemo(() => ({ ...query, filters: { ...query.filters, tax_year: year } }), [query, year]);
  const columns = useMemo<ColumnDef<Receipt>[]>(() => [
    { accessorKey: 'created_at', header: 'Uploaded', cell: ({ row }) => datetime(row.original.created_at) },
    { accessorKey: 'merchant', header: 'Merchant', enableSorting: false, cell: ({ row }) => row.original.merchant || 'Needs manual review' },
    { accessorKey: 'amount_pence', header: 'Full bill', enableSorting: false, cell: ({ row }) => <span className="money-cell" data-negative={(row.original.amount_pence || 0) < 0}>{money(row.original.amount_pence)}</span> },
    { accessorKey: 'review_status', header: 'Review', cell: ({ row }) => <StatusBadge status={row.original.review_status} /> },
    { id: 'open', header: '', enableSorting: false, cell: ({ row }) => <Button size="small" onClick={() => setOpened(row.original.id)}>Review receipt</Button> },
  ], []);
  const nextIndex = rows.findIndex(row => row.id === opened) + 1;
  return <><Alert type="info" title="Evidence awaiting a decision" description="Undated receipts stay visible until their date and amount have been reviewed. Confirmed receipts create canonical ledger postings." className="section-gap" />
    <DataTable title="Receipts" resource={`drivers/${driverId}/receipts`} query={actualQuery} onQuery={setQuery} columns={columns} onData={capture} toolbar={<Select aria-label="Filter receipt status" className="status-filter" value={query.filters.review_status || ''}
      options={[{ value: '', label: 'All receipt states' }, ...['pending', 'confirmed', 'reversed'].map(value => ({ value, label: label(value) }))]}
      onChange={value => setQuery({ ...query, page: 1, filters: value ? { review_status: value } : {} })} />} />
    {opened && <ReceiptViewer key={opened} driverId={driverId} receiptId={opened} close={() => setOpened(null)} next={nextIndex > 0 && nextIndex < rows.length ? () => setOpened(rows[nextIndex].id) : undefined} />}
  </>;
}

function ExpenseTabs({ driverId }: { driverId: string }) {
  return <Tabs destroyOnHidden items={[{ key: 'ledger', label: 'Expense ledger', children: <LedgerTab driverId={driverId} kind="expenses" /> },
    { key: 'receipts', label: 'Receipt review queue', children: <ReceiptQueue driverId={driverId} /> }]} />;
}

export function TaxTab({ driverId, mileageOnly = false }: { driverId: string; mileageOnly?: boolean }) {
  const { year } = useWorkspace();
  const result = useQuery({ queryKey: ['tax', driverId, year], queryFn: ({ signal }) => api.tax(driverId, year, signal) });
  const overview = useQuery({ queryKey: ['overview', driverId, year], queryFn: ({ signal }) => api.overview(driverId, year, signal), enabled: !mileageOnly });
  return <QueryState layout={mileageOnly ? 'panel' : 'tax'} pending={result.isPending} error={result.error} retry={result.refetch} empty={mileageOnly && result.isSuccess && !result.data.rules.rules.some(rule => rule.code === 'mileage')} emptyMessage="No mileage rates were supplied for this tax year. Refresh or ask an administrator.">{result.data && <>
    {mileageOnly ? <section className="surface profile-card section-gap"><h2>Verified mileage rules · {year}</h2>{result.data.rules.rules.filter(rule => rule.code === 'mileage').map(rule => <div key={rule.code}>
      <Descriptions column={{ xs: 1, md: 3 }} items={Object.entries(rule.value).map(([key, value]) => ({ key, label: label(key), children: String(value) }))} />
      <a href={rule.official_url} target="_blank" rel="noreferrer">HMRC source ↗</a><small className="muted"> · Verified {date(rule.verified_at)} · Per-vehicle eligibility is enforced by the backend.</small></div>)}</section> : <>
      <Alert type="info" showIcon title="Estimate for review — not an assessed bill or completed tax return" description="Figures follow the selected tax-year rules. Review missing inputs and unsupported tax circumstances before relying on this estimate." className="section-gap" />
      {result.data.estimate.available === false ? <Alert type="warning" title="Tax estimate unavailable" description={result.data.estimate.reason} className="section-gap" /> :
        <div className="stat-grid section-gap">{[['Estimated liability', result.data.estimate.total_pence], ['Income tax', result.data.estimate.income_tax_pence], ['Class 4 NI', result.data.estimate.class4_pence], ['Personal allowance', result.data.estimate.personal_allowance_pence]].map(([name, value]) => <div className="surface stat-card" key={String(name)}><span className="number-label">{name}<TaxExplanation name={String(name)} year={year} result={result.data!} /></span><strong>{money(value as number | undefined)}</strong></div>)}</div>}

      <QueryState pending={overview.isPending} error={overview.error} retry={overview.refetch}>{overview.data && <WorkflowPanel data={overview.data} tax />}</QueryState>
      <div className="profile-overview-grid"><section className="surface profile-card"><h2>Payment timeline</h2>{result.data.payments.items.length ? result.data.payments.items.map(item => <div className="payment-row" key={item.id}><span>{date(item.due_on)}<small>{label(item.label_key.replace(/^deadline\./, ''))}</small></span><strong>{item.amount_pence == null ? 'Amount not assessed' : money(item.amount_pence)}<ExplainNumber name="Payment amount" year={year} sources={result.data!.rules.rules.filter(rule => rule.code === 'poa').map(rule => <p key={rule.code}><a href={rule.official_url} target="_blank" rel="noreferrer">Payment rules source</a> ? {JSON.stringify(rule.value)}</p>)}><dl className="breakdown">{Object.entries(result.data!.payments).filter(([key]) => key.endsWith('_pence')).map(([key, value]) => <div key={key}><dt>{label(key.replace('_pence', ''))}</dt><dd>{money(value as number | null)}</dd></div>)}</dl><p>Source: payment timeline API, supplied prior assessment and current-pace projection; due {date(item.due_on)}.</p></ExplainNumber></strong></div>) : <Empty description="No payment dates supplied" />}
        {(result.data.payments.warnings || []).map(warning => <Alert key={warning} type="warning" title={warning} className="form-alert" />)}</section>
        <section className="surface profile-card"><h2>Assumptions & limitations</h2><ul className="assumption-list">{[...new Set([...(result.data.estimate.warnings || []), ...(result.data.estimate.assumptions || [])])].map(text => <li key={text}>{text.replaceAll('_', ' ')}</li>)}</ul><p className="muted">Rule set {result.data.rules.version}</p>
          <Space wrap>{result.data.rules.rules.map(rule => <a key={rule.code} href={rule.official_url} target="_blank" rel="noreferrer">{label(rule.code)} ↗</a>)}</Space></section></div>
    </>}
  </>}</QueryState>;
}

function MileageTab({ driverId }: { driverId: string }) {
  const { year } = useWorkspace();
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, sort: 'occurred_on' });
  const [summary, setSummary] = useState<{ business_miles: string; deduction_pence: number } | null>(null);
  const actualQuery = useMemo(() => ({ ...query, filters: { tax_year: year } }), [query, year]);
  const capture = useCallback((data: Page<Mileage> & Record<string, unknown>) => setSummary(data.summary as { business_miles: string; deduction_pence: number }), []);
  const columns = useMemo<ColumnDef<Mileage>[]>(() => [
    { accessorKey: 'occurred_on', header: 'Date', cell: ({ row }) => date(row.original.occurred_on) },
    { accessorKey: 'purpose', header: 'Journey purpose', enableSorting: false },
    { accessorKey: 'business_miles', header: 'Business miles' },
    { accessorKey: 'private_miles', header: 'Private miles', enableSorting: false },
    { id: 'audit', header: 'History', enableSorting: false, cell: ({ row }) => <RecordAudit driverId={driverId} recordId={row.original.id} /> },
    { id: 'odometer', header: 'Odometer evidence', enableSorting: false, cell: ({ row }) => row.original.start_odometer && row.original.end_odometer ? `${row.original.start_odometer} → ${row.original.end_odometer}` : 'Not supplied' },
  ], []);
  return <><div className="inline-stats section-gap"><span><strong>{summary?.business_miles ?? '—'}</strong> recorded business miles<ExplainNumber name="Business miles" year={year} /></span><span><strong>{money(summary?.deduction_pence)}</strong> eligible mileage deduction<ExplainNumber name="Mileage deduction" year={year}><p>{summary?.business_miles ?? '—'} recorded miles; deduction {money(summary?.deduction_pence)}. Source: mileage summary API. Per-vehicle logs and effective elections determine eligibility; the summary is not filtered by table search.</p><p>Rates and official references for this year are displayed in Verified mileage rules below.</p></ExplainNumber></span></div>
    <TaxTab driverId={driverId} mileageOnly /><DataTable title="Mileage logs" resource={`drivers/${driverId}/mileage`} query={actualQuery} onQuery={setQuery} columns={columns} onData={capture} />
  </>;
}

function DocumentsTab({ driverId }: { driverId: string }) {
  const { config } = useWorkspace();
  const [query, setQuery] = useState(initialQuery);
  const [busy, setBusy] = useState(false);
  const { message } = App.useApp();
  const cache = useQueryClient();
  const openDocument = async (document: Document) => {
    try { download(await api.blob(`/drivers/${driverId}/documents/${document.id}/content`), `evidence.${document.mime_type === 'application/pdf' ? 'pdf' : document.mime_type === 'image/png' ? 'png' : 'jpg'}`); }
    catch (error) { void message.error((error as Error).message); }
  };
  const columns = useMemo<ColumnDef<Document>[]>(() => [
    { accessorKey: 'created_at', header: 'Uploaded', cell: ({ row }) => datetime(row.original.created_at) },
    { accessorKey: 'mime_type', header: 'Type', enableSorting: false },
    { accessorKey: 'size_bytes', header: 'Size', cell: ({ row }) => `${(row.original.size_bytes / 1024).toFixed(1)} KB` },
    { accessorKey: 'scan_status', header: 'Safety check', enableSorting: false, cell: ({ row }) => <StatusBadge status={row.original.scan_status} /> },
    { id: 'download', header: '', enableSorting: false, cell: ({ row }) => <Space><Tooltip title={['clean', 'generated'].includes(row.original.scan_status) ? 'Download private evidence' : 'Download unavailable until scanning succeeds. Ask the driver for replacement evidence if scanning fails.'}><span><Button size="small" icon={<Download />} disabled={!['clean', 'generated'].includes(row.original.scan_status)} onClick={() => void openDocument(row.original)}>Download</Button></span></Tooltip><RecordAudit driverId={driverId} recordId={row.original.id} /></Space> },
  ], [driverId]);
  return <><Alert type="info" title="Private evidence store" description="Uploads are quarantined until the configured scanner approves them. Documents are never publicly accessible." className="section-gap" />
    <DataTable title="Documents" resource={`drivers/${driverId}/documents`} query={query} onQuery={setQuery} columns={columns} toolbar={<RoleGuard action="edit"><Upload accept="image/png,image/jpeg,application/pdf" showUploadList={false} disabled={busy}
      beforeUpload={async file => {
        if (file.size > config.upload_max_bytes) { void message.error('File exceeds the server upload limit.'); return false; }
        const body = new FormData(); body.append('file', file);
        setBusy(true);
        try { await api.mutate(`/drivers/${driverId}/documents`, body); await cache.invalidateQueries({ queryKey: ['table'] }); void message.success('Evidence uploaded for private scanning.'); }
        catch (error) { void message.error((error as Error).message); }
        finally { setBusy(false); }
        return false;
      }}><Button loading={busy} icon={<UploadIcon />}>Upload document</Button></Upload></RoleGuard>} />
  </>;
}

function CommunicationTab({ driverId, kind }: { driverId: string; kind: 'messages' | 'notes' }) {
  const [query, setQuery] = useState<TableQuery>(initialQuery);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();
  const cache = useQueryClient();
  const columns = useMemo<ColumnDef<Entry>[]>(() => [
    { accessorKey: 'created_at', header: 'Time (UK)', cell: ({ row }) => datetime(row.original.created_at) },
    { accessorKey: 'author', header: 'From', enableSorting: false },
    { id: 'audit', header: 'History', enableSorting: false, cell: ({ row }) => <RecordAudit driverId={driverId} recordId={row.original.id} /> },
    { accessorKey: 'body', header: kind === 'messages' ? 'Message' : 'Internal note / ticket', enableSorting: false, cell: ({ row }) => <div className="message-body">{row.original.kind === 'ticket' && <Tag>Ticket</Tag>}{row.original.body}</div> },
  ], [kind]);
  const submit = async (values: { body: string; kind?: string }) => {
    if (!values.body.trim()) return;
    setBusy(true);
    try { await api.mutate(`/drivers/${driverId}/${kind}`, { body: values.body.trim(), kind: values.kind || 'note' }); form.resetFields(); await cache.invalidateQueries({ queryKey: ['table'] }); void message.success(kind === 'messages' ? 'Message saved to the driver’s human accountant thread.' : 'Internal note saved.'); }
    catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  return <><Alert type="info" title={kind === 'messages' ? 'Human accountant conversation' : 'Internal notes & support tickets'}
    description={kind === 'messages' ? 'Messages are stored in the human thread. Push/email delivery and a Flutter chat screen are separate integrations.' : 'These entries stay inside the staff panel and are not shown to the driver.'} className="section-gap" />
    <DataTable title={kind === 'messages' ? 'Messages' : 'Notes'} resource={`drivers/${driverId}/${kind}`} query={query} onQuery={setQuery} columns={columns} />
    <RoleGuard action={kind === 'messages' ? 'message' : 'note'}><section className="surface profile-card composer"><h2>{kind === 'messages' ? 'Message the driver' : 'Add an internal entry'}</h2>
      <Form layout="vertical" form={form} onFinish={submit} initialValues={{ kind: 'note' }}><Form.Item name="body" label={kind === 'messages' ? 'Your message' : 'Note or ticket'} rules={[{ required: true, whitespace: true, max: 8000 }]}><Input.TextArea rows={3} maxLength={8000} /></Form.Item>
        <Space>{kind === 'notes' && <Form.Item name="kind" noStyle><Select aria-label="Entry type" options={[{ value: 'note', label: 'Internal note' }, { value: 'ticket', label: 'Support ticket' }]} /></Form.Item>}<Button type="primary" htmlType="submit" loading={busy} icon={<Send />}>{kind === 'messages' ? 'Send message' : 'Save entry'}</Button></Space>
      </Form></section></RoleGuard>
  </>;
}

function DriverProfileContent({ driverId }: { driverId: string }) {
  const { year } = useWorkspace();
  const location = useLocation();
  const [tab, setTab] = useState(location.state?.tab || 'overview');
  useEffect(() => { if (location.state?.tab) setTab(location.state.tab); }, [location.key, location.state]);
  const [auditQuery, setAuditQuery] = useState(initialQuery);
  const result = useQuery({ queryKey: ['overview', driverId, year], queryFn: ({ signal }) => api.overview(driverId, year, signal) });
  const data = result.data;
  return <><Link to="/drivers" className="back-link"><ArrowLeft /> Driver directory</Link>
    <QueryState layout="profile" pending={result.isPending} error={result.error} retry={result.refetch}>{data && <>
      <div className="page-heading profile-heading"><div className="driver-cell"><Avatar size={56} className="driver-avatar">{initials(data.name)}</Avatar><div><span className="eyebrow">DRIVER 360</span><h1>{data.name}</h1><p>{data.email || 'Email not supplied'} <span className="text-divider">·</span> {data.accountant_name ? `Assigned to ${data.accountant_name}` : 'Awaiting assignment'}</p><div className="profile-plan"><StatusBadge status={data.subscription.status} />{data.subscription.plan_id && <span className="muted">{data.subscription.plan_id}</span>}<span className="muted">Tax year {year}</span></div></div></div></div>
      <div className="stat-grid profile-stats">{[['Income', data.totals.income_pence], ['Deductible expenses', data.totals.deductible_expenses_pence], ['Profit', data.totals.profit_pence], ['Estimated tax', data.totals.estimated_tax_pence]].map(([title, value]) => <div className="surface stat-card" key={String(title)}><span className="number-label">{title}<ExplainNumber name={String(title)} year={year}><p>Income {money(data.totals.income_pence)}; deductible expenses {money(data.totals.deductible_expenses_pence)}; included mileage deduction {money(data.totals.mileage_deduction_pence)}; profit {money(data.totals.profit_pence)}.</p><p>Source: overview API, confirmed ledger through {data.totals.as_of ? datetime(data.totals.as_of) : 'server as-of date'}. Tax rates, bands and PAYE/loan adjustments are available in the Tax tab.</p><Button onClick={() => setTab('tax')}>Open tax breakdown and rates</Button></ExplainNumber></span><strong>{money(value as number | null)}</strong></div>)}</div>
      <Tabs activeKey={tab} onChange={setTab} destroyOnHidden className="profile-tabs" items={[
        { key: 'overview', label: 'Overview', children: <PanelBoundary resetKey={`${driverId}-${year}`}><WorkflowPanel data={data} onTab={setTab} /><OverviewTab data={data} /></PanelBoundary> },
        ...(['income', 'expenses', 'mileage', 'tax', 'documents', 'messages', 'notes', 'activity'] as const).map(key => ({ key,
          label: key === 'activity' ? 'Activity log' : key === 'notes' ? 'Internal notes' : label(key),
          children: <PanelBoundary resetKey={`${key}-${year}`}>{key === 'income' ? <LedgerTab key={`${key}-${year}`} driverId={driverId} kind={key} /> : key === 'expenses' ? <ExpenseTabs key={year} driverId={driverId} /> :
            key === 'mileage' ? <MileageTab key={year} driverId={driverId} /> : key === 'tax' ? <TaxTab driverId={driverId} /> :
              key === 'documents' ? <DocumentsTab driverId={driverId} /> : key === 'messages' || key === 'notes' ? <CommunicationTab driverId={driverId} kind={key} /> :
                <AuditTimeline resource={`drivers/${driverId}/activity`} query={auditQuery} onQuery={setAuditQuery} />}</PanelBoundary>,
        })),
      ]} />
    </>}</QueryState>
  </>;
}

export function DriverProfilePage() {
  const { id } = useParams();
  const active = useSession();
  if (!id || !/^[a-f0-9-]{36}$/i.test(id) || !can(active?.staff.role, 'read')) return <Empty description="Driver unavailable" />;
  return <DriverProfileContent key={id} driverId={id} />;
}

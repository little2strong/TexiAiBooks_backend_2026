import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, App, Button, Form, Input, Modal, Radio, Select } from 'antd';
import { Link } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { api, request } from '../api/client';
import { initialQuery, type AiReviewRow, type AiSummary, type TableQuery } from '../api/types';
import { ConfidenceBar } from '../components/AiIndicator';
import { DataTable } from '../components/DataTable';
import { RoleGuard } from '../components/RoleGuard';
import { QueryState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { date, label, money } from '../lib/format';

const fields = ['merchant', 'amount', 'date', 'vat', 'category'];

export function AiReviewPage() {
  const [query, setQuery] = useState<TableQuery>({ ...initialQuery, filters: { feedback: 'open' } });
  const [opened, setOpened] = useState<AiReviewRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const verdict = Form.useWatch('verdict', form);
  const cache = useQueryClient();
  const { message } = App.useApp();
  const summary = useQuery({ queryKey: ['ai-summary'], queryFn: ({ signal }) => request<AiSummary>('/staff/ai-reviews/summary', { method: 'POST', signal }) });
  const columns = useMemo<ColumnDef<AiReviewRow>[]>(() => [
    { accessorKey: 'created_at', header: 'Uploaded', cell: ({ row }) => date(row.original.created_at) },
    { id: 'driver', header: 'Driver', enableSorting: false, cell: ({ row }) => <Link to={`/drivers/${row.original.driver_id}`} state={{ tab: 'expenses' }}>{row.original.driver_name}</Link> },
    { id: 'merchant', header: 'AI read', enableSorting: false, cell: ({ row }) => <div className="record-description"><strong>{row.original.merchant || 'No merchant read'}</strong><small>{row.original.occurred_on ? date(row.original.occurred_on) : 'No date read'}</small></div> },
    { id: 'amount_pence', header: 'Amount', enableSorting: false, cell: ({ row }) => <span className="money-cell">{money(row.original.amount_pence)}</span> },
    { id: 'category', header: 'Suggested category', enableSorting: false, cell: ({ row }) => row.original.suggested_category ? label(row.original.suggested_category) : <span className="muted">None</span> },
    { id: 'confidence', header: 'Confidence', enableSorting: false, cell: ({ row }) => <ConfidenceBar confidence={row.original.confidence ?? null} /> },
    { accessorKey: 'review_status', header: 'Receipt', cell: ({ row }) => <StatusBadge status={row.original.review_status} /> },
    { id: 'feedback', header: 'Feedback', enableSorting: false, cell: ({ row }) => row.original.feedback_verdict ? <StatusBadge status={row.original.feedback_verdict} /> : <RoleGuard action="edit" fallback={<span className="muted">Not reviewed</span>}><Button size="small" onClick={() => setOpened(row.original)}>Give feedback</Button></RoleGuard> },
  ], []);
  const submit = async (values: { verdict: string; fields?: string[]; correction?: string; reason?: string }) => {
    if (!opened) return;
    setBusy(true);
    try {
      const corrections = values.verdict === 'corrected' ? Object.fromEntries((values.fields || []).map(field => [field, values.correction || ''])) : {};
      await api.mutate(`/ai-reviews/${opened.id}/feedback`, { verdict: values.verdict, corrections, reason: values.reason || null });
      setOpened(null);
      await cache.invalidateQueries({ queryKey: ['table'] });
      await cache.invalidateQueries({ queryKey: ['ai-summary'] });
      void message.success('Feedback saved.');
    } catch (error) { void message.error((error as Error).message); }
    finally { setBusy(false); }
  };
  const data = summary.data;
  return <><div className="page-heading"><div><span className="eyebrow">AI QUALITY</span><h1>AI review</h1><p>Check what the AI read from receipts and record where it went wrong. Feedback never changes a driver's books.</p></div></div>
    <QueryState layout="stats" pending={summary.isPending} error={summary.error} retry={summary.refetch}>{data && <div className="stat-grid profile-stats section-gap">{[['Waiting for review', data.open], ['Accepted as read', data.accepted], ['Corrected', data.corrected], ['Acceptance rate', data.acceptance_percent == null ? '—' : `${data.acceptance_percent}%`]].map(([name, value]) => <div className="surface stat-card" key={String(name)}><span>{name}</span><strong>{value}</strong></div>)}</div>}</QueryState>
    {data && data.extractions === 0 && <Alert className="section-gap" type="info" showIcon title="No AI extractions yet" description="Receipts appear here once an OCR provider is configured and has processed them. Until then, drivers and accountants enter receipt details by hand." />}
    <DataTable<AiReviewRow> title="AI extractions" resource="ai-reviews" query={query} onQuery={setQuery} columns={columns} exportable={false}
      toolbar={<Select aria-label="Filter feedback" className="status-filter" value={query.filters.feedback || 'all'} options={[{ value: 'open', label: 'Waiting for review' }, { value: 'done', label: 'Already reviewed' }, { value: 'all', label: 'All extractions' }]}
        onChange={value => { const filters = { ...query.filters }; if (value === 'all') delete filters.feedback; else filters.feedback = value; setQuery({ ...query, page: 1, filters }); }} />} />
    <Modal title="Feedback on this AI read" open={Boolean(opened)} onCancel={() => setOpened(null)} onOk={() => form.submit()} confirmLoading={busy} okText="Save feedback" destroyOnHidden>
      {opened && <p className="muted">{opened.merchant || 'No merchant read'} · {money(opened.amount_pence)} · {opened.suggested_category ? label(opened.suggested_category) : 'No category'}{opened.warnings.length ? ` · ${opened.warnings.map(label).join(', ')}` : ''}</p>}
      <Form form={form} layout="vertical" preserve={false} onFinish={submit} initialValues={{ verdict: 'accepted' }}>
        <Form.Item name="verdict" label="How was the AI read?" rules={[{ required: true }]}><Radio.Group optionType="button" options={[{ value: 'accepted', label: 'Correct' }, { value: 'corrected', label: 'Needed correcting' }, { value: 'rejected', label: 'Unusable' }]} /></Form.Item>
        {verdict === 'corrected' && <><Form.Item name="fields" label="Which fields were wrong?" rules={[{ required: true, message: 'Choose at least one field' }]}><Select mode="multiple" options={fields.map(value => ({ value, label: label(value) }))} /></Form.Item>
          <Form.Item name="correction" label="Correct value" rules={[{ required: true, max: 200 }]}><Input maxLength={200} /></Form.Item></>}
        <Form.Item name="reason" label="Reason" rules={[{ required: verdict !== 'accepted', message: 'Give a reason', max: 500 }]}><Input.TextArea rows={2} maxLength={500} /></Form.Item>
      </Form></Modal></>;
}

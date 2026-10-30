import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { DataTable } from './DataTable';
import { initialQuery } from '../api/types';
import { api, request } from '../api/client';
vi.mock('../api/client', () => ({ request: vi.fn(), api: { views: vi.fn() }, download: vi.fn() }));
vi.mock('./RoleGuard', () => ({ RoleGuard: () => null }));

function setup(resource: string, outcome: 'pending' | 'empty' | 'error' | 'data') {
  vi.mocked(api.views).mockResolvedValue({ items: [] });
  const rows = { items: outcome === 'empty' ? [] : [{ id: 'one', name: 'Visible record' }], total: outcome === 'empty' ? 0 : 1, page: 1, page_size: 25 };
  vi.mocked(request).mockImplementation(() => outcome === 'pending' ? new Promise(() => {}) : outcome === 'error' ? Promise.reject(new Error('Request ID: table-500')) : Promise.resolve(rows) as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onQuery = vi.fn();
  const child = (query = initialQuery) => <QueryClientProvider client={client}><App><DataTable resource={resource} title="Records" query={query} onQuery={onQuery} columns={[{ accessorKey: 'name', header: 'Name' }]} selectable /></App></QueryClientProvider>;
  return { ...render(child()), child, onQuery };
}
for (const resource of ['drivers', 'handoffs', 'drivers/12345678-1234-1234-1234-123456789012/expenses', 'drivers/12345678-1234-1234-1234-123456789012/activity']) describe(`${resource} panel states`, () => {
  it('shows a dimensioned loading state', () => { const { container } = setup(resource, 'pending'); expect(screen.getByRole('status')).toBeVisible(); expect(container.querySelector('.query-table')).toBeInTheDocument(); });
  it('shows access-scoped empty state and next action', async () => { setup(resource, 'empty'); expect(await screen.findByText(/No records match this view within your access scope/)).toBeVisible(); expect(screen.getByRole('button', { name: 'Clear filters / refresh' })).toBeEnabled(); });
  it('shows request ID and Retry on failure', async () => { setup(resource, 'error'); expect(await screen.findByText('Request ID: table-500')).toBeVisible(); expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled(); });
  it('renders data and preserves selection for an equivalent query', async () => {
    const view = setup(resource, 'data'); await screen.findByText('Visible record');
    fireEvent.click(screen.getByLabelText('Select row 1'));
    expect(screen.getByText('1 selected')).toBeVisible(); view.rerender(view.child({ ...initialQuery, filters: {} }));
    await waitFor(() => expect(screen.getByLabelText('Select row 1')).toBeChecked());
    expect(screen.getByText('1 selected')).toBeVisible();
  });
});
it('treats reordered filter keys as the same view', async () => {
  const view = setup('handoffs', 'data');
  view.rerender(view.child({ ...initialQuery, filters: { tax_year: '2026-27', status: 'new' } }));
  await screen.findByText('Visible record'); fireEvent.click(screen.getByLabelText('Select row 1'));
  view.rerender(view.child({ ...initialQuery, filters: { status: 'new', tax_year: '2026-27' } }));
  await waitFor(() => expect(screen.getByLabelText('Select row 1')).toBeChecked());
});

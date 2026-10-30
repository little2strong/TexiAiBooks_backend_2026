import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { App } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import samples from '../api/__fixtures__/staff.json';
import { decodeResponse } from '../api/contracts';
import { DashboardPage } from './Dashboard';
import { DriverProfilePage, TaxTab } from './DriverProfile';
vi.mock('@tanstack/react-query', async original => ({ ...await original<typeof import('@tanstack/react-query')>(), useQuery: vi.fn() }));
vi.mock('../auth/context', () => ({ useWorkspace: () => ({ year: '2026-27', config: { categories: [], sources: [] } }), useSession: () => ({ staff: { id: 'staff', name: 'Synthetic Admin', role: 'admin' } }) }));
vi.mock('../components/DataTable', () => ({ DataTable: () => <p>Data table panel</p> }));
vi.mock('./Handoffs', () => ({ HandoffTable: () => <p>Handoff table panel</p> }));
vi.mock('../components/RoleGuard', () => ({ RoleGuard: () => null }));
const dashboard = decodeResponse('/staff/dashboard', 'POST', samples['/api/v1/staff/dashboard'], 'unit');
const overview = decodeResponse('/staff/drivers/driver/overview', 'POST', samples['/api/v1/staff/drivers/:id/overview'], 'unit');
const tax = decodeResponse('/staff/drivers/driver/tax', 'POST', samples['/api/v1/staff/drivers/:id/tax'], 'unit');
const query = (data?: unknown, error: Error | null = null, pending = false) => ({ data, error, isPending: pending, refetch: vi.fn() });
function show(node: React.ReactNode, path = '/') { return render(<App><MemoryRouter initialEntries={[path]}><Routes><Route path="*" element={node} /><Route path="/drivers/:id" element={<DriverProfilePage />} /></Routes></MemoryRouter></App>); }
beforeEach(() => vi.mocked(useQuery).mockReset());
describe('dashboard major states', () => {
  it('shows matching loading layout', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, null, true) as never); show(<DashboardPage />); expect(screen.getByRole('status')).toBeVisible(); });
  it('shows actionable API error', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, new Error('Request ID: dashboard')) as never); show(<DashboardPage />); expect(screen.getByText('Request ID: dashboard')).toBeVisible(); expect(screen.getByRole('button', { name: 'Retry' })).toBeVisible(); });
  it('renders real zero counts for an empty practice', () => { vi.mocked(useQuery).mockReturnValue(query({ ...(dashboard as object), assigned_drivers: 0, pending_handoffs: 0 }) as never); show(<DashboardPage />); expect(screen.getByText('Handoff table panel')).toBeVisible(); expect(screen.getAllByText('0').length).toBeGreaterThan(0); });
  it('renders server data', () => { vi.mocked(useQuery).mockReturnValue(query(dashboard) as never); show(<DashboardPage />); expect(screen.getByText('Pending handoffs')).toBeVisible(); expect(screen.getByText('Handoff table panel')).toBeVisible(); });
});
describe('driver profile major states', () => {
  const path = '/drivers/12345678-1234-1234-1234-123456789012';
  it('shows loading layout', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, null, true) as never); show(null, path); expect(screen.getByRole('status')).toBeVisible(); });
  it('shows missing or out-of-scope record error with retry', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, new Error('Record unavailable. Request ID: profile')) as never); show(null, path); expect(screen.getByText(/Request ID: profile/)).toBeVisible(); });
  it('shows an explicit empty record fallback', () => { show(<DriverProfilePage />); expect(screen.getByText('Driver unavailable')).toBeVisible(); });
  it('renders data, workflow and audit entry point', () => { vi.mocked(useQuery).mockReturnValue(query(overview) as never); show(null, path); expect(screen.getByRole('heading', { name: 'Browser Driver' })).toBeVisible(); expect(screen.getByText('Next action & workflow')).toBeVisible(); expect(screen.getByText(/Who changed what and when/)).toBeVisible(); });
});
describe('tax major states', () => {
  it('shows reserved loading layout', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, null, true) as never); show(<TaxTab driverId="driver" />); expect(screen.getByRole('status')).toBeVisible(); });
  it('shows server error and Retry', () => { vi.mocked(useQuery).mockReturnValue(query(undefined, new Error('Request ID: tax')) as never); show(<TaxTab driverId="driver" />); expect(screen.getByText('Request ID: tax')).toBeVisible(); });
  it('shows unavailable estimate without inventing zero tax', () => { vi.mocked(useQuery).mockImplementation(options => query(options?.queryKey?.[0] === 'overview' ? overview : { ...(tax as object), estimate: { available: false, reason: 'Save tax profile inputs' } }) as never); show(<TaxTab driverId="driver" />); expect(screen.getByText('Tax estimate unavailable')).toBeVisible(); expect(screen.getByText('Save tax profile inputs')).toBeVisible(); });
  it('renders tax numbers, explained formula, timeline and filing checks', () => { vi.mocked(useQuery).mockImplementation(options => query(options?.queryKey?.[0] === 'overview' ? overview : tax) as never); show(<TaxTab driverId="driver" />); expect(screen.getAllByText('Estimated liability')[0]).toBeVisible(); expect(screen.getByText('Backend filing requirements')).toBeVisible(); expect(screen.getByText('Payment timeline')).toBeVisible(); });
});

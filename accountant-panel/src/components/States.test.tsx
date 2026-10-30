import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PanelBoundary, QueryState, type StateLayout } from './States';

for (const layout of ['dashboard', 'profile', 'tax', 'table', 'panel'] as StateLayout[]) describe(`${layout} shared query frame`, () => {
  it('renders loading, empty with action, error with retry, and data', () => {
    const retry = vi.fn();
    const { rerender, container } = render(<QueryState layout={layout} pending error={null} retry={retry}><p>Data</p></QueryState>);
    expect(screen.getByRole('status')).toHaveAccessibleName('Loading content');
    expect(container.querySelector(`.query-${layout}`)).toBeInTheDocument();
    rerender(<QueryState layout={layout} pending={false} empty error={null} retry={retry}><p>Data</p></QueryState>);
    fireEvent.click(screen.getByRole('button', { name: 'Refresh records' })); expect(retry).toHaveBeenCalledTimes(1);
    rerender(<QueryState layout={layout} pending={false} error={new Error('Request ID: unit-42')} retry={retry}><p>Data</p></QueryState>);
    expect(screen.getByText('Request ID: unit-42')).toBeVisible(); fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledTimes(2);
    rerender(<QueryState layout={layout} pending={false} error={null} retry={retry}><p>Data</p></QueryState>);
    expect(screen.getByText('Data')).toBeVisible();
  });
});
it('isolates a failing widget and resets on navigation', () => {
  const log = vi.spyOn(console, 'error').mockImplementation(() => {});
  function Broken(): never { throw new Error('bad render'); }
  const { rerender } = render(<><p>Other panel</p><PanelBoundary resetKey="one"><Broken /></PanelBoundary></>);
  expect(screen.getByText('Other panel')).toBeVisible(); expect(screen.getByRole('alert')).toBeVisible();
  rerender(<PanelBoundary resetKey="two"><p>Recovered</p></PanelBoundary>);
  expect(screen.getByText('Recovered')).toBeVisible(); log.mockRestore();
});
it('renders zero as real data instead of an empty result', () => {
  render(<QueryState pending={false} error={null} retry={() => {}}>{0}</QueryState>);
  expect(screen.getByText('0')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Refresh records' })).toBeNull();
});

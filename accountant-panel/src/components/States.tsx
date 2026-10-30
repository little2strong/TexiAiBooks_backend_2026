import { Alert, Button, Skeleton } from 'antd';
import { Component, Profiler, type ReactNode } from 'react';
declare global { interface Window { __panelRenders?: { name: string; phase: string; duration: number }[] } }

export type StateLayout = 'panel' | 'dashboard' | 'profile' | 'tax' | 'table';
export function LoadingLayout({ layout }: { layout: StateLayout }) {
  if (layout === 'dashboard' || layout === 'profile' || layout === 'tax') return <>
    {layout === 'profile' && <div className="surface profile-heading loading-profile"><Skeleton active avatar paragraph={{ rows: 2 }} /></div>}
    {layout === 'tax' && <div className="surface state-padding loading-tax-notice section-gap"><Skeleton active paragraph={{ rows: 1 }} /></div>}
    <div className="stat-grid section-gap">{['one', 'two', 'three', 'four'].map(key => <div key={key} className="surface stat-card"><Skeleton active paragraph={{ rows: 2 }} /></div>)}</div>
    {(layout === 'profile' || layout === 'tax') && <div className={`surface state-padding section-gap loading-workflow ${layout === 'tax' ? 'loading-filing' : ''}`}><Skeleton active paragraph={{ rows: layout === 'tax' ? 14 : 7 }} /></div>}
    <div className={layout === 'dashboard' ? 'dashboard-middle' : 'profile-overview-grid'}><div className="surface state-padding loading-detail"><Skeleton active paragraph={{ rows: 5 }} /></div><div className="surface state-padding loading-detail"><Skeleton active paragraph={{ rows: 5 }} /></div></div>
  </>;
  return <div className="state-padding"><Skeleton active paragraph={{ rows: layout === 'table' ? 6 : 4 }} /></div>;
}
export function QueryState({ pending, error, retry, empty = false, emptyMessage = 'No data is available in this view.', emptyAction, layout = 'panel', children }: {
  pending: boolean; error: Error | null; retry: () => unknown; empty?: boolean; emptyMessage?: string; emptyAction?: ReactNode; layout?: StateLayout; children: ReactNode;
}) {
  const content = <div className={`query-state query-${layout}`} aria-busy={pending}>
    {pending ? <div role="status" aria-label="Loading content"><LoadingLayout layout={layout} /></div> : error ?
      <div className="state-padding"><Alert type="error" showIcon title="Unable to load this view" description={error.message} action={<Button onClick={() => retry()}>Retry</Button>} /></div> :
      empty || children == null || typeof children === 'boolean' || children === '' ? <div className="empty-state"><p>{emptyMessage}</p>{emptyAction || <Button onClick={() => retry()}>Refresh records</Button>}</div> : children}
  </div>;
  return <PanelBoundary>{import.meta.env.DEV && import.meta.env.VITE_UI_DIAGNOSTICS === 'true' ? <Profiler id={`QueryState:${layout}`} onRender={(name, phase, duration) => { window.__panelRenders = [...(window.__panelRenders || []).slice(-199), { name, phase, duration }]; }}>{content}</Profiler> : content}</PanelBoundary>;
}
export class PanelBoundary extends Component<{ children: ReactNode; resetKey?: string }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { console.error(`Panel render failed: ${error.name}`); }
  componentDidUpdate(previous: Readonly<{ children: ReactNode; resetKey?: string }>) {
    if (previous.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }
  render() { return this.state.failed ? <div className="surface state-padding" role="alert"><h2>This panel could not be displayed</h2><p>Other panels remain available. Retry this panel or refresh its data.</p><Button onClick={() => this.setState({ failed: false })}>Retry panel</Button></div> : this.props.children; }
}

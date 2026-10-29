import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Result, Spin } from 'antd';
import { Navigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Config } from '../api/types';
import { session } from './session';

export function useSession() { return useSyncExternalStore(session.subscribe, session.get); }
const WorkspaceContext = createContext<{ config: Config; year: string; setYear: (year: string) => void } | null>(null);
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error('Workspace configuration is required');
  return value;
}

export function ProtectedWorkspace({ children }: { children: ReactNode }) {
  const active = useSession();
  const config = useQuery({ queryKey: ['config'], queryFn: api.config, enabled: Boolean(active) });
  const [year, setYear] = useState('');
  useEffect(() => {
    if (!active || !config.data) return;
    let lastActive = Date.now();
    let lastHeartbeat = 0;
    const touch = () => {
      if (Date.now() - lastActive >= config.data!.idle_timeout_seconds * 1000) { session.end(); return; }
      lastActive = Date.now();
      if (Date.now() - lastHeartbeat > 60000) {
        lastHeartbeat = Date.now();
        void api.me().catch(() => undefined);
      }
    };
    const interval = setInterval(() => {
      if (Date.now() - lastActive >= config.data!.idle_timeout_seconds * 1000) session.end();
    }, 1000);
    const events = ['pointerdown', 'keydown', 'scroll'] as const;
    events.forEach(event => window.addEventListener(event, touch, { passive: true }));
    const visibility = () => { if (document.hidden) return; if (Date.now() - lastActive >= config.data!.idle_timeout_seconds * 1000) session.end(); };
    document.addEventListener('visibilitychange', visibility);
    return () => {
      clearInterval(interval);
      events.forEach(event => window.removeEventListener(event, touch));
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [active, config.data]);
  if (!active) return <Navigate to="/login" replace />;
  if (config.isPending) return <div className="center-state"><Spin size="large" description="Opening secure workspace" /></div>;
  if (config.isError) return <Result status="error" title="The staff workspace could not load" subTitle={config.error.message}
    extra={<><Button onClick={() => void config.refetch()}>Retry</Button><Button onClick={() => session.end()}>Sign out</Button></>} />;
  if (!config.data.tax_years.length) return <Alert type="error" title="No verified tax years are configured" />;
  const selected = year || (config.data.tax_years.includes(config.data.current_tax_year) ? config.data.current_tax_year : config.data.tax_years.at(-1)!);
  return <WorkspaceContext.Provider value={{ config: config.data, year: selected, setYear }}>{children}</WorkspaceContext.Provider>;
}

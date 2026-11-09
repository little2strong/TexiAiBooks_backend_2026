import { useEffect, useMemo, useRef, useState } from 'react';
import { Avatar, Button, Dropdown, Input, Modal, Select } from 'antd';
import { LayoutDashboard, Sparkles, Car, ClipboardCheck, ChevronDown, FileCheck2, History, LogOut, PanelLeftClose, PanelLeftOpen, Percent, Search, Users, ShieldCheck, UserLock } from 'lucide-react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { useSession, useWorkspace } from '../auth/context';
import { api } from '../api/client';
import { session } from '../auth/session';
import { can } from '../auth/permissions';
import type { Driver } from '../api/types';
import { initialQuery } from '../api/types';
import { initials, label } from '../lib/format';
import { DataTable } from './DataTable';
import { ThemeToggle } from './ThemeToggle';
import type { InputRef } from 'antd';

const sections: [string, string][] = [['/returns', 'Tax returns'], ['/ai-review', 'AI review'], ['/handoffs', 'Handoff queue'], ['/drivers', 'Driver directory'],
  ['/admin/users', 'Users & roles'], ['/admin/rates', 'Tax rates'], ['/admin/privacy', 'Privacy requests'], ['/admin/audit', 'Audit log']];

export function WorkspaceLayout() {
  const active = useSession()!;
  const { year, setYear, config } = useWorkspace();
  const [collapsed, setCollapsed] = useState(false);
  const [global, setGlobal] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const navigate = useNavigate();
  const location = useLocation();
  const searchInput = useRef<InputRef>(null);
  const place = sections.find(([path]) => location.pathname.startsWith(path))?.[1] || 'Dashboard';
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchInput.current?.focus(); }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);
  const columns = useMemo<ColumnDef<Driver>[]>(() => [
    { accessorKey: 'name', header: 'Driver', cell: ({ row }) => <Button type="link" onClick={() => { setSearchOpen(false); setGlobal(''); navigate(`/drivers/${row.original.id}`); }}>{row.original.name}</Button> },
    { accessorKey: 'email', header: 'Email' },
    { accessorKey: 'accountant_name', header: 'Accountant', enableSorting: false },
  ], [navigate]);
  const signOut = async () => { try { await api.logout(); } catch { /* Local credentials must clear even if the network is unavailable. */ } finally { session.end(); } };
  return <div className={`workspace ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar" aria-label="Primary navigation">
      <NavLink to="/" className="brand" aria-label="TaxiAiBooks home"><span className="brand-mark">t<span>.</span></span><span className="brand-text">TaxiAiBooks<small>ACCOUNTANT WORKSPACE</small></span></NavLink>
      <div className="practice-label">YOUR WORKSPACE</div>
      <nav><NavLink to="/" end aria-label="Dashboard"><LayoutDashboard aria-hidden="true" /><span>Dashboard</span></NavLink>
        <NavLink to="/handoffs" aria-label="Handoff queue"><ClipboardCheck aria-hidden="true" /><span>Handoff queue</span></NavLink>
        <NavLink to="/returns" aria-label="Tax returns"><FileCheck2 aria-hidden="true" /><span>Tax returns</span></NavLink>
        <NavLink to="/ai-review" aria-label="AI review"><Sparkles aria-hidden="true" /><span>AI review</span></NavLink>
        <NavLink to="/drivers" aria-label="Driver directory"><Car aria-hidden="true" /><span>Driver directory</span></NavLink></nav>
      {can(active.staff.role, 'admin') && <><div className="practice-label workspace-nav-label">ADMINISTRATION</div>
        <nav aria-label="Administration"><NavLink to="/admin/users" aria-label="Users and roles"><Users aria-hidden="true" /><span>Users & roles</span></NavLink>
          <NavLink to="/admin/rates" aria-label="Tax rates"><Percent aria-hidden="true" /><span>Tax rates</span></NavLink>
          <NavLink to="/admin/privacy" aria-label="Privacy requests"><UserLock aria-hidden="true" /><span>Privacy requests</span></NavLink>
          <NavLink to="/admin/audit" aria-label="Audit log"><History aria-hidden="true" /><span>Audit log</span></NavLink></nav></>}
      <div className="sidebar-bottom"><div className="security-card"><ShieldCheck /><strong>Secure workspace</strong><span>Access is scoped. Actions are audited.</span></div>
        <Dropdown menu={{ items: [{ key: 'logout', label: 'Sign out', icon: <LogOut />, onClick: () => void signOut() }] }} trigger={['click']}>
          <button className="staff-menu" aria-label={`${active.staff.name}, account menu`}><Avatar className="staff-avatar">{initials(active.staff.name)}</Avatar><span><strong>{active.staff.name}</strong><small>{label(active.staff.role)}</small></span><ChevronDown /></button>
        </Dropdown></div>
    </aside>
    <div className="workspace-body"><header className="topbar">
      <Button type="text" icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={() => setCollapsed(!collapsed)} />
      <span className="topbar-context">Accountant panel <span>/</span> <strong>{place}</strong></span>
      <Input.Search ref={searchInput} prefix={<Search />} suffix={<kbd>⌘ / Ctrl K</kbd>} aria-label="Global driver search" placeholder="Search drivers…" value={global} maxLength={254}
        onChange={event => setGlobal(event.target.value)} onSearch={value => { if (value.trim()) { setSearchQuery({ ...initialQuery, search: value.trim() }); setSearchOpen(true); setGlobal(''); } }} className="global-search" />
      <Select aria-label="Workspace tax year" className="year-select" value={year} onChange={setYear} options={config.tax_years.map(value => ({ value, label: `Tax year ${value}` }))} />
      <ThemeToggle />
      <Dropdown menu={{ items: [{ key: 'logout', label: 'Sign out', icon: <LogOut />, onClick: () => void signOut() }] }} trigger={['click']}>
        <Button type="text" className="topbar-user" aria-label="User menu" icon={<Avatar size="small" className="driver-avatar">{initials(active.staff.name)}</Avatar>}><span>{active.staff.name.split(' ')[0]}</span><ChevronDown /></Button>
      </Dropdown>
    </header>
    <main id="main-content" className="main-content" tabIndex={-1}><Outlet /></main>
    <footer className="workspace-footer"><span>Drive. Snap. Done.</span><span><ShieldCheck /> Financial data is private · UK dates & GBP</span></footer>
    </div>
    <Modal title="Find a driver" open={searchOpen} onCancel={() => { setSearchOpen(false); setSearchQuery(initialQuery); }} footer={null} width={1000} destroyOnHidden>
      <p className="muted">Results follow your assigned-driver permissions. UTR searches require an exact ten-digit value.</p>
      <DataTable resource="drivers" title="Driver search" query={searchQuery} onQuery={setSearchQuery} columns={columns} />
    </Modal>
  </div>;
}

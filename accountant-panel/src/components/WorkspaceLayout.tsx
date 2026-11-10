import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Avatar, Button, Dropdown, Input, Modal, Select } from 'antd';
import { LayoutDashboard, Sparkles, Car, ClipboardCheck, ChevronDown, FileCheck2, Gauge, History, LogOut, PanelLeftClose, PanelLeftOpen, Percent, Search, Users, ShieldCheck, UserLock } from 'lucide-react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import type { ColumnDef } from '@tanstack/react-table';
import { useSession, useWorkspace } from '../auth/context';
import { api } from '../api/client';
import { homeFor } from '../api/providers';
import { session } from '../auth/session';
import type { Driver } from '../api/types';
import { initialQuery } from '../api/types';
import { initials, label } from '../lib/format';
import { DataTable } from './DataTable';
import { ThemeToggle } from './ThemeToggle';
import type { InputRef } from 'antd';

type Link = { to: string; text: string; icon: ReactNode; end?: boolean };

// Each role sees only its own menu. The backend enforces the same split.
const accountantLinks: Link[] = [
  { to: '/', text: 'Dashboard', icon: <LayoutDashboard aria-hidden="true" />, end: true },
  { to: '/handoffs', text: 'Handoff queue', icon: <ClipboardCheck aria-hidden="true" /> },
  { to: '/returns', text: 'Tax returns', icon: <FileCheck2 aria-hidden="true" /> },
  { to: '/ai-review', text: 'AI review', icon: <Sparkles aria-hidden="true" /> },
  { to: '/drivers', text: 'Driver directory', icon: <Car aria-hidden="true" /> },
];
const adminWorkLinks: Link[] = [
  { to: '/admin', text: 'Overview', icon: <Gauge aria-hidden="true" />, end: true },
  { to: '/drivers', text: 'Drivers & assignment', icon: <Car aria-hidden="true" /> },
  { to: '/handoffs', text: 'Handoff queue', icon: <ClipboardCheck aria-hidden="true" /> },
  { to: '/returns', text: 'Tax returns', icon: <FileCheck2 aria-hidden="true" /> },
  { to: '/ai-review', text: 'AI review', icon: <Sparkles aria-hidden="true" /> },
];
const adminSettingsLinks: Link[] = [
  { to: '/admin/users', text: 'Staff accounts', icon: <Users aria-hidden="true" /> },
  { to: '/admin/rates', text: 'Tax rates', icon: <Percent aria-hidden="true" /> },
  { to: '/admin/privacy', text: 'Privacy requests', icon: <UserLock aria-hidden="true" /> },
  { to: '/admin/audit', text: 'Audit log', icon: <History aria-hidden="true" /> },
];

function Nav({ links, label: name }: { links: Link[]; label: string }) {
  return <nav aria-label={name}>{links.map(link => <NavLink key={link.to} to={link.to} end={link.end} aria-label={link.text}>{link.icon}<span>{link.text}</span></NavLink>)}</nav>;
}

export function WorkspaceLayout() {
  const active = useSession()!;
  const admin = active.staff.role === 'admin';
  const { year, setYear, config } = useWorkspace();
  const [collapsed, setCollapsed] = useState(false);
  const [global, setGlobal] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const navigate = useNavigate();
  const location = useLocation();
  const searchInput = useRef<InputRef>(null);
  const links = admin ? [...adminSettingsLinks, ...adminWorkLinks] : accountantLinks;
  // Longest match first, so /admin/users is not reported as /admin.
  const place = [...links].sort((a, b) => b.to.length - a.to.length).find(link => link.end ? location.pathname === link.to : location.pathname.startsWith(link.to))?.text
    || (location.pathname.startsWith('/drivers/') ? 'Driver profile' : admin ? 'Overview' : 'Dashboard');
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
  const edition = admin ? 'Admin console' : 'Accountant panel';
  return <div className={`workspace ${admin ? 'admin-console' : ''} ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar" aria-label="Primary navigation">
      <NavLink to={homeFor(active.staff.role)} className="brand" aria-label="TaxiAiBooks home"><span className="brand-mark">t<span>.</span></span><span className="brand-text">TaxiAiBooks<small>{admin ? 'ADMIN CONSOLE' : 'ACCOUNTANT WORKSPACE'}</small></span></NavLink>
      {admin ? <>
        <div className="practice-label">PRACTICE</div>
        <Nav links={adminWorkLinks} label="Practice" />
        <div className="practice-label workspace-nav-label">ADMINISTRATION</div>
        <Nav links={adminSettingsLinks} label="Administration" />
      </> : <>
        <div className="practice-label">YOUR WORKSPACE</div>
        <Nav links={accountantLinks} label="Workspace" />
      </>}
      <div className="sidebar-bottom"><div className="security-card"><ShieldCheck /><strong>{admin ? 'Administrator access' : 'Secure workspace'}</strong><span>{admin ? 'Every change you make is audited.' : 'Access is scoped. Actions are audited.'}</span></div>
        <Dropdown menu={{ items: [{ key: 'logout', label: 'Sign out', icon: <LogOut />, onClick: () => void signOut() }] }} trigger={['click']}>
          <button className="staff-menu" aria-label={`${active.staff.name}, account menu`}><Avatar className="staff-avatar">{initials(active.staff.name)}</Avatar><span><strong>{active.staff.name}</strong><small>{label(active.staff.role)}</small></span><ChevronDown /></button>
        </Dropdown></div>
    </aside>
    <div className="workspace-body"><header className="topbar">
      <Button type="text" icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={() => setCollapsed(!collapsed)} />
      <span className="topbar-context">{edition} <span>/</span> <strong>{place}</strong></span>
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
      <p className="muted">{admin ? 'Searches every driver in the practice.' : 'Results follow your assigned-driver permissions.'} UTR searches require an exact ten-digit value.</p>
      <DataTable resource="drivers" title="Driver search" query={searchQuery} onQuery={setSearchQuery} columns={columns} />
    </Modal>
  </div>;
}

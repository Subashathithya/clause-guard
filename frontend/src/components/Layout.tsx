import { useCallback, useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Bell,
  Building2,
  FilePlus2,
  FileText,
  Home,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  Scale,
  Settings as SettingsIcon,
  Shield,
  User as UserIcon,
  X,
  FileSearch,
} from 'lucide-react';
import { useAuth } from '../auth/context';
import { useAsync } from '../hooks';
import { api } from '../api';
import { MenuAction, Popover, useToast } from './ui/overlays';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
}

const MAIN_NAV: Array<NavItem | { section: string }> = [
  { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={17} />, end: true },
  { to: '/analyze', label: 'Analyze Contract', icon: <FilePlus2 size={17} /> },
  { to: '/contracts', label: 'My Contracts', icon: <FileText size={17} /> },
  { to: '/compare', label: 'Compare', icon: <Layers size={17} /> },
  { to: '/terms-checker', label: 'T&C Checker', icon: <Scale size={17} /> },
  { to: '/insights', label: 'Insights', icon: <FileSearch size={17} /> },
];

const FOOTER_NAV: NavItem[] = [
  { to: '/notifications', label: 'Notifications', icon: <Bell size={17} /> },
  { to: '/settings', label: 'Settings', icon: <SettingsIcon size={17} /> },
];

function isSection(item: NavItem | { section: string }): item is { section: string } {
  return 'section' in item;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase();
}

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, loggedIn } = useAuth();
  return (
    <>
      <div className="sidebar-brand">
        <span className="brand-shield">
          <Shield size={18} />
        </span>
        <h1>
          ClauseGuard
          <span style={{ display: 'block', fontSize: 11, fontWeight: 400, color: '#94a3b8' }}>
            Contract clarity, in plain English
          </span>
        </h1>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        {MAIN_NAV.map((item) =>
          isSection(item) ? null : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => ['side-link', isActive ? 'active' : ''].filter(Boolean).join(' ')}
              onClick={onNavigate}
            >
              <span className="nav-ic">{item.icon}</span>
              {item.label}
            </NavLink>
          )
        )}

        <div className="side-section-label">Account</div>
        {FOOTER_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => ['side-link', isActive ? 'active' : ''].filter(Boolean).join(' ')}
            onClick={onNavigate}
          >
            <span className="nav-ic">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        {loggedIn && user ? (
          <div className="quota-box">
            <div className="quota-row">
              <span>Free analyses</span>
              <strong style={{ color: '#e2e8f0' }}>
                {user.quota.remaining} of {user.quota.monthly_limit} left
              </strong>
            </div>
            <div className="quota-row" style={{ marginTop: 4 }}>
              <span>Renews monthly</span>
              <span style={{ color: '#94a3b8' }}>{user.email}</span>
            </div>
          </div>
        ) : (
          <div className="quota-box">
            <div className="quota-row">
              <span>Guest mode</span>
              <strong style={{ color: '#e2e8f0' }}>5 analyses / month</strong>
            </div>
            <NavLink
              to="/signup"
              onClick={onNavigate}
              style={{ display: 'block', marginTop: 8, fontSize: 13, fontWeight: 600 }}
            >
              Create a free account →
            </NavLink>
          </div>
        )}
      </div>
    </>
  );
}

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);
  const { user, loggedIn, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const closeNav = useCallback(() => setNavOpen(false), []);
  useEffect(() => closeNav(), [location.pathname, closeNav]);

  return (
    <div className="shell">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`} aria-label="Sidebar">
        <SidebarContent onNavigate={closeNav} />
      </aside>
      {navOpen && (
        <button
          type="button"
          className="sidebar-scrim"
          onClick={closeNav}
          aria-label="Close navigation"
          style={{ border: 'none', cursor: 'pointer' }}
        />
      )}

      <div className="shell-main">
        <header className="topbar">
          <button
            type="button"
            className="gc-burger"
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={navOpen}
          >
            {navOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <NavLink
            to="/dashboard"
            className="gc-burger hide-sm"
            aria-label="Dashboard"
            style={{ color: 'var(--text-mid)' }}
          >
            <Home size={20} />
          </NavLink>

          <div className="topbar-spacer" />

          <div className="topbar-group">
            <button
              type="button"
              className="icon-btn"
              onClick={() => navigate('/notifications')}
              aria-label="Notifications"
            >
              <Bell size={20} />
            </button>

            <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate('/analyze')}>
              <FilePlus2 size={15} /> <span className="hide-sm">New analysis</span>
            </button>

            {loggedIn && user ? (
              <Popover
                label="Account menu"
                align="right"
                trigger={
                  <span className="avatar" style={{ cursor: 'pointer' }} aria-label="Account menu">
                    {initials(user.full_name || user.email)}
                  </span>
                }
              >
                {(close) => (
                  <>
                    <div style={{ padding: '4px 10px 8px' }}>
                      <strong className="text-sm">{user.full_name || 'ClauseGuard user'}</strong>
                      <div className="text-xs faint" style={{ wordBreak: 'break-all' }}>
                        {user.email}
                      </div>
                    </div>
                    <div className="popover-divider" />
                    <MenuAction onSelect={() => { close(); navigate('/settings'); }}>
                      <UserIcon size={15} /> Profile &amp; settings
                    </MenuAction>
                    <MenuAction
                      danger
                      onSelect={() => {
                        close();
                        logout();
                        toast.push('You have been signed out.', 'info');
                        navigate('/');
                      }}
                    >
                      <LogOut size={15} /> Sign out
                    </MenuAction>
                  </>
                )}
              </Popover>
            ) : (
              <div className="topbar-group">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/login')}>
                  Sign in
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/signup')}>
                  <Building2 size={15} /> Sign up
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="shell-workspace">
          <Outlet />
          <footer className="mt-5 text-sm faint" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 16, marginTop: 40 }}>
            ClauseGuard provides AI-assisted contract understanding and is not legal advice. For anything
            important, please review with a qualified professional.
          </footer>
        </main>
      </div>
    </div>
  );
}

export function useAuthGate() {
  const { booting, loggedIn } = useAuth();
  const { value: health, loading } = useAsync(async () => api.health(), []);
  const requiresAuth = health?.auth_required === true;
  const blocked = !booting && !loading && requiresAuth && !loggedIn;
  return { booting: booting || loading, blocked };
}
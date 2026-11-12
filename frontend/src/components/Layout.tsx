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
import { useI18n } from '../i18n/I18nProvider';
import InstallCard from '../pwa/InstallCard';
import { MenuAction, Popover, useToast } from './ui/overlays';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
}

const MAIN_NAV: Array<NavItem | { section: string }> = [
  { to: '/dashboard', label: 'nav.dashboard', icon: <LayoutDashboard size={17} />, end: true },
  { to: '/analyze', label: 'nav.analyze', icon: <FilePlus2 size={17} /> },
  { to: '/contracts', label: 'nav.contracts', icon: <FileText size={17} /> },
  { to: '/compare', label: 'nav.compare', icon: <Layers size={17} /> },
  { to: '/terms-checker', label: 'nav.termsChecker', icon: <Scale size={17} /> },
  { to: '/insights', label: 'nav.insights', icon: <FileSearch size={17} /> },
];

const FOOTER_NAV: NavItem[] = [
  { to: '/notifications', label: 'nav.notifications', icon: <Bell size={17} /> },
  { to: '/settings', label: 'nav.settings', icon: <SettingsIcon size={17} /> },
];

const BOTTOM_NAV: Array<NavItem & { primary?: boolean }> = [
  { to: '/dashboard', label: 'nav.home', icon: <LayoutDashboard size={20} />, end: true },
  { to: '/contracts', label: 'nav.contracts', icon: <FileText size={20} /> },
  { to: '/analyze', label: 'nav.analyze', icon: <FilePlus2 size={20} />, primary: true },
  { to: '/compare', label: 'nav.compare', icon: <Layers size={20} /> },
  { to: '/insights', label: 'nav.insights', icon: <FileSearch size={20} /> },
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
  const { t } = useI18n();
  return (
    <>
      <div className="sidebar-brand">
        <div className="sidebar-brand-main">
          <span className="brand-shield">
            <Shield size={18} />
          </span>
          <div className="sidebar-brand-title">
            ClauseGuard
            <span className="sidebar-brand-sub">{t('nav.brandSubtitle')}</span>
          </div>
        </div>
        {onNavigate && (
          <button
            type="button"
            className="sidebar-close"
            onClick={onNavigate}
            aria-label={t('nav.closeNav')}
          >
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="sidebar-nav" aria-label={t('nav.mainNav')}>
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
              {t(item.label)}
            </NavLink>
          )
        )}

        <div className="side-section-label">{t('nav.account')}</div>
        {FOOTER_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => ['side-link', isActive ? 'active' : ''].filter(Boolean).join(' ')}
            onClick={onNavigate}
          >
            <span className="nav-ic">{item.icon}</span>
            {t(item.label)}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        {loggedIn && user ? (
          <div className="quota-box">
            <div className="quota-row">
              <span>{t('nav.freeAnalyses')}</span>
              <strong style={{ color: '#e2e8f0' }}>
                {user.quota.remaining} of {user.quota.monthly_limit} left
              </strong>
            </div>
            <div className="quota-row" style={{ marginTop: 4 }}>
              <span>{t('nav.renewsMonthly')}</span>
              <span style={{ color: '#94a3b8' }}>{user.email}</span>
            </div>
          </div>
        ) : (
          <div className="quota-box">
            <div className="quota-row">
              <span>{t('nav.guestMode')}</span>
              <strong style={{ color: '#e2e8f0' }}>{t('nav.guestQuota')}</strong>
            </div>
            <NavLink
              to="/signup"
              onClick={onNavigate}
              style={{ display: 'block', marginTop: 8, fontSize: 13, fontWeight: 600 }}
            >
              {t('nav.createFreeAccount')}
            </NavLink>
            <NavLink
              to="/login"
              onClick={onNavigate}
              style={{ display: 'block', marginTop: 6, fontSize: 13, color: '#cbd5e1' }}
            >
              {t('nav.signIn')}
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
  const { t } = useI18n();

  const closeNav = useCallback(() => setNavOpen(false), []);
  useEffect(() => closeNav(), [location.pathname, closeNav]);

  // Close the mobile drawer with Escape and prevent the page behind it from
  // scrolling while it is open.
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeNav();
    };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [navOpen, closeNav]);

  return (
    <div className="shell">
      <a href="#main-content" className="skip-link">
        {t('nav.skipToContent')}
      </a>

      <aside id="app-sidebar" className={`sidebar ${navOpen ? 'open' : ''}`} aria-label={t('nav.sidebar')}>
        <SidebarContent onNavigate={closeNav} />
      </aside>
      {navOpen && (
        <button
          type="button"
          className="sidebar-scrim"
          onClick={closeNav}
          aria-label={t('nav.closeNav')}
        />
      )}

      <div className="shell-main">
        <header className="topbar">
          <button
            type="button"
            className="gc-burger"
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? t('nav.closeNav') : t('nav.openNav')}
            aria-expanded={navOpen}
            aria-controls="app-sidebar"
          >
            {navOpen ? <X size={20} /> : <Menu size={20} />}
          </button>

          <NavLink
            to="/dashboard"
            className="gc-burger hide-sm"
            aria-label={t('nav.dashboard')}
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
              aria-label={t('nav.notifications')}
            >
              <Bell size={20} />
            </button>

            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => navigate('/analyze')}
              aria-label={t('nav.newAnalysis')}
            >
              <FilePlus2 size={15} /> <span className="hide-sm">{t('nav.newAnalysis')}</span>
            </button>

            {loggedIn && user ? (
              <Popover
                label={t('nav.accountMenu')}
                align="right"
                trigger={
                  <span className="avatar" style={{ cursor: 'pointer' }} aria-label={t('nav.accountMenu')}>
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
                      <UserIcon size={15} /> {t('nav.profileSettings')}
                    </MenuAction>
                    <MenuAction
                      danger
                      onSelect={() => {
                        close();
                        logout();
                        toast.push(t('auth.signedOut'), 'info');
                        navigate('/');
                      }}
                    >
                      <LogOut size={15} /> {t('nav.signOut')}
                    </MenuAction>
                  </>
                )}
              </Popover>
            ) : (
              <div className="topbar-group">
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/login')}>
                  {t('nav.signIn')}
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/signup')}>
                  <Building2 size={15} /> {t('nav.signUp')}
                </button>
              </div>
            )}
          </div>
        </header>

        <main id="main-content" className="shell-workspace" tabIndex={-1}>
          <InstallCard />
          <Outlet />
          <footer className="app-footer">
            {t('footer.disclaimer')}
          </footer>
        </main>
      </div>

      <nav className="bottom-nav" aria-label={t('nav.quickNav')}>
        {BOTTOM_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              ['bn-item', item.primary ? 'bn-item-primary' : '', isActive ? 'active' : '']
                .filter(Boolean)
                .join(' ')
            }
          >
            <span className="bn-ic" aria-hidden="true">{item.icon}</span>
            {t(item.label)}
          </NavLink>
        ))}
      </nav>
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
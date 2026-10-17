import { useEffect, useState } from 'react';
import { KeyRound, LogOut, Shield, User as UserIcon, Bell, Palette } from 'lucide-react';
import { useAuth } from '../auth/context';
import { Card, PageHeader } from '../components/ui/data';
import { useToast, MenuAction, Popover } from '../components/ui/overlays';
import { Badge, Field, Input } from '../components/ui/primitives';
import { formatDate } from '../lib/format';

function SettingsCard({ icon, title, children, actions }: { icon: React.ReactNode; title: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <Card>
      <div className="card-header">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="qc-ic">{icon}</span>
          <h3 className="card-title" style={{ margin: 0 }}>{title}</h3>
        </div>
        {actions}
      </div>
      {children}
    </Card>
  );
}

function TogglePref({ label, helper, checked, onChange }: { label: string; helper: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="row-spread" style={{ padding: 'var(--s3) 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong className="text-sm">{label}</strong>
        <p className="text-xs faint mb-0">{helper}</p>
      </div>
      <input
        type="checkbox"
        role="switch"
        aria-checked={checked}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        aria-label={label}
      />
    </div>
  );
}

export default function SettingsPage() {
  const { user, loggedIn, logout } = useAuth();
  const toast = useToast();
  const [calmMode, setCalmMode] = useState<boolean>(() => localStorage.getItem('cg_calm_mode') === '1');

  useEffect(() => {
    localStorage.setItem('cg_calm_mode', calmMode ? '1' : '0');
    document.documentElement.classList.toggle('calm-mode', calmMode);
  }, [calmMode]);

  return (
    <div>
      <PageHeader title="Settings" lead="Your account and preferences." />

      {loggedIn && user ? (
        <div className="stack">
          <SettingsCard icon={<UserIcon size={18} />} title="Profile">
            <div className="grid grid-2">
              <Field label="Full name" htmlFor="st-name">
                <Input id="st-name" value={user.full_name} readOnly aria-readonly />
                <span className="field-helper">Editing your name isn’t available yet.</span>
              </Field>
              <Field label="Email" htmlFor="st-email">
                <Input id="st-email" value={user.email} readOnly aria-readonly />
                <span className="field-helper">This is your sign-in email.</span>
              </Field>
            </div>
            <p className="text-xs faint">Member since {formatDate(user.created_at)}.</p>
          </SettingsCard>

          <SettingsCard icon={<Shield size={18} />} title="Plan">
            <div className="row-spread">
              <div>
                <Badge tone="info">Free plan</Badge>
                <p className="text-sm muted mt-2 mb-0">
                  You can analyse {user.quota.monthly_limit} contracts per month. You’ve used{' '}
                  {user.quota.used} this month — {user.quota.remaining} remaining.
                </p>
              </div>
            </div>
          </SettingsCard>

          <SettingsCard
            icon={<KeyRound size={18} />}
            title="Security"
            actions={
              <Popover
                label="Account actions"
                trigger={<button type="button" className="btn btn-secondary btn-sm"><LogOut size={15} /> Sign out</button>}
              >
                {(close) => (
                  <MenuAction danger onSelect={() => { close(); logout(); toast.push('You have been signed out.', 'info'); }}>
                    Sign out of this device
                  </MenuAction>
                )}
              </Popover>
            }
          >
            <p className="text-sm muted">
              Passwords on ClauseGuard are stored securely, and your contracts are only visible to you.
              Self-service password changes aren’t available yet — please contact support.
            </p>
          </SettingsCard>

          <SettingsCard icon={<Palette size={18} />} title="Appearance" >
            <TogglePref
              label="Calmer interface"
              helper="Reduce moving animation throughout the app. Saved on this device."
              checked={calmMode}
              onChange={setCalmMode}
            />
            <div className="mt-3 row" style={{ gap: 8 }}>
              <Bell size={15} className="faint" aria-hidden="true" />
              <span className="text-xs faint">Notification preferences will appear here once notifications are available.</span>
            </div>
          </SettingsCard>
        </div>
      ) : (
        <div className="stack">
          <SettingsCard icon={<UserIcon size={18} />} title="You're in guest mode">
            <p className="text-sm muted">
              You can analyse up to 5 contracts a month without an account, but nothing is saved between
              visits. Create a free account to keep all your analyses in one place, on any device.
            </p>
            <div className="row" style={{ gap: 10 }}>
              <button type="button" className="btn btn-primary" onClick={() => (window.location.href = '/signup')}>
                Create a free account
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => (window.location.href = '/login')}>
                Sign in
              </button>
            </div>
          </SettingsCard>
          <SettingsCard icon={<Palette size={18} />} title="Appearance">
            <TogglePref
              label="Calmer interface"
              helper="Reduce moving animation throughout the app. Saved on this device."
              checked={calmMode}
              onChange={setCalmMode}
            />
          </SettingsCard>
        </div>
      )}
    </div>
  );
}
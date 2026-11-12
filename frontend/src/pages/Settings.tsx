import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, LogOut, Shield, User as UserIcon, Bell, Palette, Download, Share, Smartphone, HardDriveDownload } from 'lucide-react';
import { useAuth } from '../auth/context';
import { Card, PageHeader } from '../components/ui/data';
import { useToast, MenuAction, Popover } from '../components/ui/overlays';
import { Badge, Button, Field, Input, Switch } from '../components/ui/primitives';
import { formatDate } from '../lib/format';
import { useInstallPrompt } from '../pwa/useInstallPrompt';
import {
  disableAppLock,
  enableAppLock,
  isAppLockEnabled,
  isAppLockSupported,
} from '../pwa/appLock';
import { useI18n } from '../i18n/I18nProvider';
import { LOCALES, LOCALE_INFO, type Locale } from '../i18n/locales';

function SettingsCard({ icon, title, children, actions }: { icon: React.ReactNode; title: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <Card>
      <div className="card-header">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span className="qc-ic">{icon}</span>
          <h2 className="card-title" style={{ margin: 0 }}>{title}</h2>
        </div>
        {actions}
      </div>
      {children}
    </Card>
  );
}

function TogglePref({ label, helper, checked, onChange }: { label: string; helper: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="pref-row">
      <div className="pref-copy">
        <strong>{label}</strong>
        <p>{helper}</p>
      </div>
      <Switch checked={checked} onChange={onChange} label={label} />
    </div>
  );
}

export default function SettingsPage() {
  const { user, loggedIn, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [calmMode, setCalmMode] = useState<boolean>(() => localStorage.getItem('cg_calm_mode') === '1');
  const installPrompt = useInstallPrompt();
  const { t, locale, setLocale } = useI18n();
  const [lockEnabled, setLockEnabled] = useState<boolean>(() => isAppLockEnabled());
  const lockSupported = isAppLockSupported();

  const toggleLock = async (next: boolean) => {
    try {
      if (next) {
        await enableAppLock();
        setLockEnabled(true);
        toast.push(t('settings.lockOn'), 'success');
      } else {
        disableAppLock();
        setLockEnabled(false);
        toast.push(t('settings.lockOff'), 'info');
      }
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('settings.lockUnavailable'), 'error');
    }
  };

  useEffect(() => {
    localStorage.setItem('cg_calm_mode', calmMode ? '1' : '0');
    document.documentElement.classList.toggle('calm-mode', calmMode);
  }, [calmMode]);

  return (
    <div>
      <PageHeader title={t('settings.title')} lead={t('settings.lead')} />

      {loggedIn && user ? (
        <div className="stack">
          <SettingsCard icon={<UserIcon size={18} />} title={t('settings.profile')}>
            <div className="grid grid-2">
              <Field label={t('settings.fullName')} htmlFor="st-name">
                <Input id="st-name" value={user.full_name} readOnly aria-readonly />
                <span className="field-helper">{t('settings.nameNotEditable')}</span>
              </Field>
              <Field label={t('settings.email')} htmlFor="st-email">
                <Input id="st-email" value={user.email} readOnly aria-readonly />
                <span className="field-helper">{t('settings.signInEmail')}</span>
              </Field>
            </div>
            <p className="text-xs faint">{t('settings.memberSince', { date: formatDate(user.created_at) })}</p>
          </SettingsCard>

          <SettingsCard icon={<Shield size={18} />} title={t('settings.plan')}>
            <div className="row-spread">
              <div>
                <Badge tone="info">{t('settings.freePlan')}</Badge>
                <p className="text-sm muted mt-2 mb-0">
                  {t('settings.planBody', {
                    limit: user.quota.monthly_limit,
                    used: user.quota.used,
                    remaining: user.quota.remaining,
                  })}
                </p>
              </div>
            </div>
          </SettingsCard>

          <SettingsCard
            icon={<KeyRound size={18} />}
            title={t('settings.security')}
            actions={
              <Popover
                label={t('settings.accountActions')}
                trigger={<button type="button" className="btn btn-secondary btn-sm"><LogOut size={15} /> {t('settings.signOut')}</button>}
              >
                {(close) => (
                  <MenuAction danger onSelect={() => { close(); logout(); toast.push('You have been signed out.', 'info'); }}>
                    {t('settings.signOutDevice')}
                  </MenuAction>
                )}
              </Popover>
            }
          >
            <p className="text-sm muted">{t('settings.securityBody')}</p>
          </SettingsCard>

          <SettingsCard icon={<Palette size={18} />} title={t('settings.appearance')} >
            <TogglePref
              label={t('settings.calmer')}
              helper={t('settings.calmerHelper')}
              checked={calmMode}
              onChange={setCalmMode}
            />
            <div className="mt-3 row" style={{ gap: 8 }}>
              <Bell size={15} className="faint" aria-hidden="true" />
              <span className="text-xs faint">{t('settings.notificationsNote')}</span>
            </div>
          </SettingsCard>
        </div>
      ) : (
        <div className="stack">
          <SettingsCard icon={<UserIcon size={18} />} title={t('settings.guestTitle')}>
            <p className="text-sm muted">{t('settings.guestBody')}</p>
            <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-primary" onClick={() => navigate('/signup')}>
                {t('settings.createFreeAccount')}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => navigate('/login')}>
                {t('settings.signIn')}
              </button>
            </div>
          </SettingsCard>
          <SettingsCard icon={<Palette size={18} />} title={t('settings.appearance')}>
            <TogglePref
              label={t('settings.calmer')}
              helper={t('settings.calmerHelper')}
              checked={calmMode}
              onChange={setCalmMode}
            />
          </SettingsCard>
        </div>
      )}

      <div className="stack mt-4">
        <SettingsCard icon={<Smartphone size={18} />} title={t('settings.thisDevice')}>
          <div className="pref-row">
            <div className="pref-copy">
              <strong>{t('settings.installApp')}</strong>
              <p>
                {installPrompt.installed
                  ? t('settings.installedBody')
                  : installPrompt.canInstall
                    ? t('settings.installHelpAvailable')
                    : installPrompt.needsManualSteps
                      ? t('settings.installHelpManual')
                      : t('settings.installHelp')}
              </p>
            </div>
            <div className="row" style={{ gap: 8 }}>
              {installPrompt.installed && <Badge tone="success">{t('settings.installed')}</Badge>}
              {installPrompt.canInstall && (
                <Button size="sm" onClick={() => void installPrompt.install()}>
                  <Download size={14} /> {t('settings.installApp')}
                </Button>
              )}
              {installPrompt.needsManualSteps && (
                <span className="text-xs faint row-inline" style={{ gap: 5 }}>
                  <Share size={13} aria-hidden="true" /> {t('settings.addToHomeScreen')}
                </span>
              )}
            </div>
          </div>

          <div className="pref-row">
            <div className="pref-copy">
              <strong>{t('settings.offline')}</strong>
              <p>{t('settings.offlineBody')}</p>
            </div>
            <HardDriveDownload size={18} className="faint" aria-hidden="true" />
          </div>
          <div className="pref-row">
            <div className="pref-copy">
              <strong>{t('settings.lock')}</strong>
              <p>{t('settings.lockHelper')}</p>
            </div>
            {lockSupported ? (
              <Switch checked={lockEnabled} onChange={(v) => void toggleLock(v)} label={t('settings.lock')} />
            ) : (
              <span className="text-xs faint">{t('settings.lockUnavailable')}</span>
            )}
          </div>

          <div className="pref-row">
            <div className="pref-copy">
              <strong>{t('settings.language')}</strong>
              <p>{t('settings.languageHelper')}</p>
            </div>
            <div className="lang-picker" role="group" aria-label={t('settings.language')}>
              {LOCALES.map((code: Locale) => (
                <button
                  key={code}
                  type="button"
                  className={['lang-chip', locale === code ? 'lang-chip-on' : ''].filter(Boolean).join(' ')}
                  onClick={() => setLocale(code)}
                  aria-pressed={locale === code}
                  lang={LOCALE_INFO[code].intlTag}
                >
                  {LOCALE_INFO[code].nativeName}
                </button>
              ))}
            </div>
          </div>
        </SettingsCard>
      </div>
    </div>
  );
}
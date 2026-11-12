import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Fingerprint, ShieldAlert } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider';
import { isAppLockEnabled, isUnlockedForSession, unlockApp } from './appLock';
import { Button } from '../components/ui/primitives';

/**
 * Keeps the app closed until the device confirms who is holding it.
 *
 * The lock is opt-in (Settings → This device) and stays on until the browser
 * session ends. It never sees contract data — the device does the check.
 */
export default function AppLockGate({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const locked = isAppLockEnabled() && !isUnlockedForSession();
  const [checking, setChecking] = useState(locked);
  const [failed, setFailed] = useState(false);

  const attempt = useCallback(async () => {
    setChecking(true);
    setFailed(false);
    const ok = await unlockApp();
    setFailed(!ok);
    setChecking(false);
  }, []);

  useEffect(() => {
    if (locked) void attempt();
  }, [locked, attempt]);

  if (!locked) return <>{children}</>;

  return (
    <div className="lock-screen">
      <div className="lock-card card card-pad">
        <span className="lock-ico" aria-hidden="true">
          {failed ? <ShieldAlert size={24} /> : <Fingerprint size={24} />}
        </span>
        <h1>{t('settings.lockUnlockTitle')}</h1>
        <p className="muted">{t('settings.lockUnlockBody')}</p>
        {failed && (
          <p className="text-sm" style={{ color: 'var(--danger-text)' }}>
            {t('settings.lockFailed')}
          </p>
        )}
        <Button onClick={() => void attempt()} loading={checking}>
          <Fingerprint size={16} /> {t('settings.lockUnlock')}
        </Button>
      </div>
    </div>
  );
}

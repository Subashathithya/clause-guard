import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { activateWaitingWorker, onUpdateReady } from './serviceWorker';
import { useI18n } from '../i18n/I18nProvider';

/**
 * Tells the user when a new version is ready instead of swapping it under
 * their feet. Nothing is lost: the refresh happens only when they choose it.
 */
export default function UpdateBanner() {
  const { t } = useI18n();
  const [ready, setReady] = useState(false);

  useEffect(() => onUpdateReady(() => setReady(true)), []);

  if (!ready) return null;

  return (
    <div className="pwa-banner" role="status" aria-live="polite">
      <span>{t('pwa.updateReady')}</span>
      <button type="button" className="btn btn-primary btn-sm" onClick={activateWaitingWorker}>
        <RefreshCw size={14} /> {t('common.refresh')}
      </button>
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={() => setReady(false)}
        aria-label={t('pwa.dismissUpdate')}
      >
        {t('common.later')}
      </button>
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import { Wifi, WifiOff } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider';

/**
 * Small, honest connection notice. The app itself keeps working for pages
 * that are already open, so the wording says exactly that.
 */
export default function ConnectionBanner() {
  const { t } = useI18n();
  const [offline, setOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false
  );
  const [backOnline, setBackOnline] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const goOffline = () => {
      setOffline(true);
      setBackOnline(false);
    };
    const goOnline = () => {
      setOffline(false);
      setBackOnline(true);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setBackOnline(false), 5000);
    };
    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  if (!offline && !backOnline) return null;

  return (
    <div className="pwa-banner pwa-banner-connection" role="status" aria-live="polite">
      {offline ? (
        <>
          <WifiOff size={15} aria-hidden="true" />
          <span>{t('pwa.offline')}</span>
        </>
      ) : (
        <>
          <Wifi size={15} aria-hidden="true" />
          <span>{t('pwa.backOnline')}</span>
        </>
      )}
    </div>
  );
}

import { Download, Smartphone } from 'lucide-react';
import { Button } from '../components/ui/primitives';
import { useInstallPrompt } from './useInstallPrompt';
import { useI18n } from '../i18n/I18nProvider';

/**
 * Offers "add to home screen" without hijacking the first visit: the card
 * only appears when the browser actually offers an install button (or, on
 * iOS, when the manual steps are needed) and it can be dismissed for good.
 */
export default function InstallCard({ placement = 'app' }: { placement?: 'app' | 'landing' }) {
  const { t } = useI18n();
  const { canInstall, needsManualSteps, installed, dismissed, install, dismiss } = useInstallPrompt();

  if (installed || dismissed) return null;
  if (!canInstall && !needsManualSteps) return null;

  return (
    <div className={`install-card install-card-${placement}`} role="region" aria-label={t('pwa.installRegion')}>
      <span className="install-ico" aria-hidden="true">
        <Smartphone size={18} />
      </span>
      <div className="install-body">
        <strong>{t('pwa.installTitle')}</strong>
        {canInstall ? (
          <p className="text-sm muted mb-0">
            {t('pwa.installBody')}
          </p>
        ) : (
          <p className="text-sm muted mb-0">
            {t('pwa.installManual')}
          </p>
        )}
      </div>
      <div className="install-actions">
        {canInstall && (
          <Button size="sm" onClick={() => void install()}>
            <Download size={14} /> {t('common.install')}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={dismiss}>
          {t('common.notNow')}
        </Button>
      </div>
    </div>
  );
}

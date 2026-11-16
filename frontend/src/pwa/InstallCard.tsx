import { Download, Share, Smartphone } from 'lucide-react';
import { Button } from '../components/ui/primitives';
import { useI18n } from '../i18n/I18nProvider';
import { useInstallPrompt } from './useInstallPrompt';

/**
 * Offers "add to home screen".
 *
 * Chrome and Edge can show their own install dialog, so the button triggers
 * it. Every other browser (and browsers where the install event never
 * arrives) gets the steps for that browser instead — the offer is never
 * silently missing.
 */
export default function InstallCard({ placement = 'app' }: { placement?: 'app' | 'landing' }) {
  const { t } = useI18n();
  const { canInstall, method, showSteps, installed, dismissed, install, toggleSteps, dismiss } =
    useInstallPrompt();

  if (installed || dismissed) return null;

  const stepsKey =
    method === 'ios'
      ? 'pwa.installStepsIos'
      : method === 'chrome'
        ? 'pwa.installStepsChrome'
        : 'pwa.installStepsOther';

  return (
    <div className={`install-card install-card-${placement}`} role="region" aria-label={t('pwa.installRegion')}>
      <span className="install-ico" aria-hidden="true">
        <Smartphone size={18} />
      </span>
      <div className="install-body">
        <strong>{t('pwa.installTitle')}</strong>
        {canInstall ? (
          <p className="text-sm muted mb-0">{t('pwa.installBody')}</p>
        ) : (
          <p className="text-sm muted mb-0">{t('pwa.installBodyNoPrompt')}</p>
        )}
        {showSteps && (
          <ol className="install-steps text-sm muted">
            <li>{t(stepsKey)}</li>
          </ol>
        )}
      </div>
      <div className="install-actions">
        {canInstall ? (
          <Button size="sm" onClick={() => void install()}>
            <Download size={14} /> {t('common.install')}
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={toggleSteps} aria-expanded={showSteps}>
            {method === 'ios' ? <Share size={14} /> : <Download size={14} />} {t('pwa.howToInstall')}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={dismiss}>
          {t('common.notNow')}
        </Button>
      </div>
    </div>
  );
}

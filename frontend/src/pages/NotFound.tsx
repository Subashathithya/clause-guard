import { Link } from 'react-router-dom';
import { Shield, ShieldAlert } from 'lucide-react';
import { useI18n } from '../i18n/I18nProvider';

export default function NotFound() {
  const { t } = useI18n();
  return (
    <div className="notfound-page">
      <div className="notfound-card">
        <span className="notfound-icon">
          <ShieldAlert size={30} />
        </span>
        <h1>{t('notFound.title')}</h1>
        <p>{t('notFound.body')}</p>
        <div className="notfound-actions">
          <Link to="/dashboard" className="btn btn-primary">{t('nav.dashboard')}</Link>
          <Link to="/" className="btn btn-secondary">{t('nav.home')}</Link>
        </div>
        <Link to="/" className="notfound-brand">
          <Shield size={16} /> ClauseGuard
        </Link>
      </div>
    </div>
  );
}

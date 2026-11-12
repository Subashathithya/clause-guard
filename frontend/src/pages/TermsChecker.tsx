import { FileText } from 'lucide-react';
import { AnalyzeExperience } from '../components/analyze/AnalyzeExperience';
import { PageHeader } from '../components/ui/data';
import { useI18n } from '../i18n/I18nProvider';

export default function TermsChecker() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader
        title={t('terms.title')}
        lead={t('terms.lead')}
      />

      <div className="card card-pad mb-4 tc-note">
        <div className="row" style={{ gap: 10 }}>
          <FileText size={20} className="faint" aria-hidden="true" />
          <p className="text-sm muted mb-0">
            {t('terms.examples')}
          </p>
        </div>
      </div>

      <AnalyzeExperience mode="terms" initialSource="paste" />
    </div>
  );
}
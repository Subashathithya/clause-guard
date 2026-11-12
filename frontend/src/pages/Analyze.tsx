import { useSearchParams } from 'react-router-dom';
import { AnalyzeExperience } from '../components/analyze/AnalyzeExperience';
import { useI18n } from '../i18n/I18nProvider';
import { PageHeader } from '../components/ui/data';

export default function AnalyzePage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const source = params.get('source') === 'upload' ? 'upload' : 'paste';

  return (
    <div>
      <PageHeader
        title={t('analyze.title')}
        lead={t('analyze.pageLead')}
      />
      <AnalyzeExperience mode="contract" initialSource={source} />
    </div>
  );
}
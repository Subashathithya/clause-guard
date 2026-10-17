import { useSearchParams } from 'react-router-dom';
import { AnalyzeExperience } from '../components/analyze/AnalyzeExperience';
import { PageHeader } from '../components/ui/data';

export default function AnalyzePage() {
  const [params] = useSearchParams();
  const source = params.get('source') === 'upload' ? 'upload' : 'paste';

  return (
    <div>
      <PageHeader
        title="Analyze a contract"
        lead="Add your document and we’ll break it down into clear plain-English sections — including the parts that may deserve your attention."
      />
      <AnalyzeExperience mode="contract" initialSource={source} />
    </div>
  );
}
import { FileText } from 'lucide-react';
import { AnalyzeExperience } from '../components/analyze/AnalyzeExperience';
import { PageHeader } from '../components/ui/data';

export default function TermsChecker() {
  return (
    <div>
      <PageHeader
        title="T&C Checker"
        lead="Paste any Terms & Conditions (or upload a document) and get a plain-English rundown of what you’re agreeing to — including the clauses that often go unnoticed."
      />

      <div className="card card-pad mb-4 tc-note">
        <div className="row" style={{ gap: 10 }}>
          <FileText size={20} className="faint" aria-hidden="true" />
          <p className="text-sm muted mb-0">
            Great candidates: app &amp; website terms, subscription plans, gym or course policies,
            warranty terms. The same careful, plain-English reading applies to all of them.
          </p>
        </div>
      </div>

      <AnalyzeExperience mode="terms" initialSource="paste" />
    </div>
  );
}
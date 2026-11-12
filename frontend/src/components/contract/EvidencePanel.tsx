import { BookOpen } from 'lucide-react';
import type { Clause } from '../../types';
import { Tag } from '../ui/primitives';
import { useI18n } from '../../i18n/I18nProvider';

/** Evidence panel: shows the reference the analysis compared a clause against.
 *  Presented as plain-language "what we compared this with" — no technical jargon. */
export function EvidencePanel({ clause }: { clause: Clause }) {
  const { t } = useI18n();
  const comparison = clause.comparison;
  const refText = comparison?.reference_clause;
  const sim = comparison?.similarity ?? 0;
  const matchLabel =
    comparison?.standard_match === 'match'
      ? t('clause.evidenceAligned')
      : comparison?.standard_match === 'worse'
        ? t('clause.differsFromPractice')
        : t('clause.noStrongReference');

  if (!refText) {
    return (
      <div className="evidence-panel">
        <div className="ep-head">
          <BookOpen size={16} aria-hidden="true" />
          <strong>{t('clause.referenceCheck')}</strong>
          <span className="ml-auto tag">{t('clause.noReference')}</span>
        </div>
        <p className="text-sm muted mt-2 mb-0">{t('clause.noReferenceBody')}</p>
      </div>
    );
  }

  return (
    <div className="evidence-panel">
      <div className="ep-head">
        <BookOpen size={16} aria-hidden="true" />
        <strong>{t('clause.referenceCheck')}</strong>
        <span className="ml-auto tag">
          {t('clause.closeToPractice', { percent: Math.round(sim * 100) })}
        </span>
      </div>
      <p className="ep-label">{matchLabel}</p>
      {comparison.reference_category && (
        <div className="row" style={{ gap: 8 }}>
          <Tag>{t('clause.referenceSection', { category: comparison.reference_category })}</Tag>
        </div>
      )}
      <blockquote className="ep-quote">{refText}</blockquote>
      {comparison.notes && <p className="text-xs faint mb-0">{comparison.notes}</p>}
    </div>
  );
}
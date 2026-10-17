import { BookOpen } from 'lucide-react';
import type { Clause } from '../../types';
import { Tag } from '../ui/primitives';

/** Evidence panel: shows the reference the analysis compared a clause against.
 *  Presented as plain-language "what we compared this with" — no technical jargon. */
export function EvidencePanel({ clause }: { clause: Clause }) {
  const comparison = clause.comparison;
  const refText = comparison?.reference_clause;
  const sim = comparison?.similarity ?? 0;
  const matchLabel =
    comparison?.standard_match === 'match'
      ? 'Closely aligned with common practice'
      : comparison?.standard_match === 'worse'
        ? 'Differs from common practice'
        : 'No strong reference';

  if (!refText) {
    return (
      <div className="evidence-panel">
        <div className="ep-head">
          <BookOpen size={16} aria-hidden="true" />
          <strong>Reference check</strong>
          <span className="ml-auto tag">No comparable reference found</span>
        </div>
        <p className="text-sm muted mt-2 mb-0">
          We couldn’t find a common-practice reference that closely matches this wording, so the
          explanation above is based on the clause itself.
        </p>
      </div>
    );
  }

  return (
    <div className="evidence-panel">
      <div className="ep-head">
        <BookOpen size={16} aria-hidden="true" />
        <strong>Reference check</strong>
        <span className="ml-auto tag">
          {Math.round(sim * 100)}% close to common practice
        </span>
      </div>
      <p className="ep-label">{matchLabel}</p>
      {comparison.reference_category && (
        <div className="row" style={{ gap: 8 }}>
          <Tag>Reference section: {comparison.reference_category}</Tag>
        </div>
      )}
      <blockquote className="ep-quote">{refText}</blockquote>
      {comparison.notes && <p className="text-xs faint mb-0">{comparison.notes}</p>}
    </div>
  );
}
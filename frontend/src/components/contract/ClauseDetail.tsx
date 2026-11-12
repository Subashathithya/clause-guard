import { useMemo, useState } from 'react';
import { Info, Link2, MessageSquareText } from 'lucide-react';
import type { Clause } from '../../types';
import { inr, whitespace } from '../../lib/format';
import { relatedClauses, type ClauseLink } from '../../lib/clauseRelations';
import { AttentionBadge } from './AttentionBadge';
import { EvidencePanel } from './EvidencePanel';
import { Tag } from '../ui/primitives';
import { useI18n } from '../../i18n/I18nProvider';

function SectionBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="cd-block">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

/** Related-clause chips that need the full clause list. */
function RelatedClauses({
  clause,
  allClauses,
  onJump,
}: {
  clause: Clause;
  allClauses: Clause[];
  onJump: (clauseId: string) => void;
}) {
  const { t } = useI18n();
  const links = useMemo<ClauseLink[]>(() => relatedClauses(clause, allClauses), [clause, allClauses]);
  if (links.length === 0) return null;
  return (
    <SectionBlock title={t('clause.relatedSections')}>
      <p className="text-sm muted">{t('clause.otherParts')}</p>
      <div className="row" style={{ gap: 8 }}>
        {links.map((l) => {
          const other = allClauses.find((c) => c.clause_id === l.clauseId);
          const box = clauseBox(l.clauseId, clause, allClauses);
          return (
            <button
              key={l.clauseId}
              type="button"
              className="rel-chip"
              title={l.reason}
              onClick={() => onJump(l.clauseId)}
            >
              <Link2 size={13} aria-hidden="true" />
              {box.label}
              <AttentionBadge level={other?.risk_level} size="sm" />
            </button>
          );
        })}
      </div>
      <p className="text-xs faint mt-2 mb-0">{t('clause.linkedByWording')}</p>
    </SectionBlock>
  );
}

function clauseBox(clauseId: string, current: Clause, all: Clause[]): { label: string } {
  const idx = all.findIndex((c) => c.clause_id === clauseId);
  const c = all.find((x) => x.clause_id === clauseId);
  const number = idx >= 0 ? idx + 1 : clauseId.slice(-4);
  return { label: c ? `#${number} · ${c.category}` : `#${clauseId.slice(-4)}` };
}

export function ClauseDetail({
  clause,
  allClauses,
  onJump,
}: {
  clause: Clause;
  allClauses: Clause[];
  onJump: (clauseId: string) => void;
}) {
  const [showCounter, setShowCounter] = useState(false);
  const { t } = useI18n();

  // Simple explanations derived from the analysis response fields.
  const whyItMatters = useMemo(() => {
    const base = whitespace(clause.explanation);
    if (base) return base;
    return t('clause.genericExplanation');
  }, [clause.explanation, t]);

  const reviewPoint = useMemo(() => {
    if (clause.risk_level !== 'green') {
      const impact = whitespace(clause.financial_impact);
      if (impact && impact.toLowerCase() !== 'none identified') {
        return `${t('clause.reviewPointFinancial')} ${impact}`;
      }
      return t('clause.reviewPointGeneric');
    }
    return t('clause.reviewPointFine');
  }, [clause, t]);

  const financialNote = useMemo(() => {
    const impact = whitespace(clause.financial_impact || '');
    if (!impact || impact.toLowerCase() === 'none identified') return null;
    const parts = [impact];
    if (clause.financial_impact_inr) parts.push(`(~${inr(clause.financial_impact_inr)})`);
    return parts.join(' ');
  }, [clause]);

  return (
    <article className="clause-detail">
      <header className="cd-head">
        <div className="row" style={{ gap: 10 }}>
          <AttentionBadge level={clause.risk_level} />
          <Tag>{clause.category}</Tag>
          {clause.negotiation_needed && <Tag>{t('clause.suggestedRevision')}</Tag>}
        </div>
      </header>

      <SectionBlock title={t('clause.originalWording')}>
        <blockquote className="cd-quote">{clause.text}</blockquote>
      </SectionBlock>

      <SectionBlock title={t('clause.inPlainEnglish')}>
        <p className="cd-plain">{whyItMatters}</p>
      </SectionBlock>

      <SectionBlock title={t('clause.whyItMatters')}>
        <p style={{ display: 'flex', gap: 8 }}>
          <Info size={17} className="faint" style={{ flex: 'none', marginTop: 3 }} aria-hidden="true" />
          <span>{reviewPoint}{financialNote ? ` ${financialNote}` : ''}</span>
        </p>
        {financialNote && (
          <p className="cd-money" style={{ marginTop: 8 }}>
            {t('clause.financialMention', { impact: financialNote || '—' })}
          </p>
        )}
      </SectionBlock>

      {clause.negotiation_needed && clause.suggested_counter_clause && (
        <SectionBlock title={t('clause.suggestedRevisionShort')}>
          <div className="cd-counter">
            {showCounter ? (
              <>
                <p>{clause.suggested_counter_clause}</p>
                {clause.talking_points && clause.talking_points.length > 0 && (
                  <ul className="cd-points">
                    {clause.talking_points.map((tp, i) => (
                      <li key={i}>{tp}</li>
                    ))}
                  </ul>
                )}
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCounter(false)}>
                  {t('clause.hide')}
                </button>
              </>
            ) : (
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowCounter(true)}>
                <MessageSquareText size={15} /> {t('clause.seeFairer')}
              </button>
            )}
          </div>
        </SectionBlock>
      )}

      <RelatedClauses clause={clause} allClauses={allClauses} onJump={onJump} />

      <SectionBlock title={t('clause.comparedWith')}>
        <EvidencePanel clause={clause} />
      </SectionBlock>
    </article>
  );
}
import { Link2 } from 'lucide-react';
import type { Clause } from '../../types';
import type { Relationship } from '../../lib/clauseRelations';
import { AttentionBadge } from './AttentionBadge';
import { Tag } from '../ui/primitives';
import { useI18n } from '../../i18n/I18nProvider';

export function RelationshipList({
  relationships,
  onSelect,
}: {
  relationships: Relationship[];
  onSelect: (relationship: Relationship) => void;
}) {
  const { t } = useI18n();

  if (relationships.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon" aria-hidden="true"><Link2 size={26} /></div>
        <h4>{t('clause.noConnections')}</h4>
        <p>{t('clause.noConnectionsBody')}</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {relationships.map((rel) => (
        <button
          key={rel.id}
          type="button"
          className={[
            'rel-card',
            'card',
            'card-pad',
            rel.kind === 'inconsistency' ? 'rel-card-inconsistency' : '',
          ]
            .filter(Boolean)
            .join(' ')}
          onClick={() => onSelect(rel)}
          style={{ textAlign: 'left', width: '100%', cursor: 'pointer' }}
        >
          <div className="rel-pair">
            <ClauseChip clause={rel.a} />
            <span className="rel-arrow" aria-hidden="true">↔</span>
            <ClauseChip clause={rel.b} />
          </div>
          <p className="text-sm muted mb-0">{rel.reason}</p>
          <Tag>
            {rel.kind === 'inconsistency'
              ? t('clause.inconsistency')
              : rel.kind === 'category'
                ? t('clause.relatedByTopic')
                : t('clause.matchingWording')}
          </Tag>
        </button>
      ))}
    </div>
  );
}

function ClauseChip({ clause }: { clause: Clause }) {
  return (
    <span className="rel-clause">
      <span>{clause.category}</span>
      <AttentionBadge level={clause.risk_level} size="sm" />
    </span>
  );
}
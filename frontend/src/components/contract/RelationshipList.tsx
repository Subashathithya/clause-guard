import { Link2 } from 'lucide-react';
import type { Clause } from '../../types';
import type { Relationship } from '../../lib/clauseRelations';
import { AttentionBadge } from './AttentionBadge';
import { Tag } from '../ui/primitives';

export function RelationshipList({
  relationships,
  onSelect,
}: {
  relationships: Relationship[];
  onSelect: (relationship: Relationship) => void;
}) {
  if (relationships.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon" aria-hidden="true"><Link2 size={26} /></div>
        <h4>No connected sections yet</h4>
        <p>As soon as a document has multiple sections that talk to each other, they’ll show up here.</p>
      </div>
    );
  }

  return (
    <div className="stack">
      {relationships.map((rel) => (
        <button
          key={rel.id}
          type="button"
          className="rel-card card card-pad"
          onClick={() => onSelect(rel)}
          style={{ textAlign: 'left', width: '100%', cursor: 'pointer' }}
        >
          <div className="rel-pair">
            <ClauseChip clause={rel.a} />
            <span className="rel-arrow" aria-hidden="true">↔</span>
            <ClauseChip clause={rel.b} />
          </div>
          <p className="text-sm muted mb-0">{rel.reason}</p>
          <Tag>{rel.kind === 'category' ? 'Related by topic' : 'Matching wording'}</Tag>
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
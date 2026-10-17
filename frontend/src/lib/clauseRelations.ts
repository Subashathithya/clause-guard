import type { Clause } from '../types';

export interface ClauseLink {
  clauseId: string;
  reason: string;
  kind: 'category' | 'wording';
}

export interface Relationship {
  id: string;
  a: Clause;
  b: Clause;
  reason: string;
  kind: 'category' | 'wording';
}

/** Topic pairings between contract categories. Explanations stay on the level
 *  of "these two topics often interact" — derived from the real clause data. */
const CATEGORY_PAIRS: Record<string, string> = {
  'Auto-Renewal|Payment': 'Renewal and payment terms often interact — you may need to know when renewal fees are charged and whether ending the contract affects money owed.',
  'Auto-Renewal|Dispute': 'This document connects cancellation and renewal with how disputes are handled — worth reading both together before you rely on leaving.',
  'Liability|Dispute': 'Liability and dispute sections work together — one limits how much the other side can be held responsible while the other decides where disagreements go.',
  'Liability|Warranty': 'Warranty promises and liability limits are usually linked — the width of the warranty often sets the ceiling of their responsibility.',
  'Liability|Data Privacy': 'Privacy obligations can carry real consequences — data promises and liability limits are connected here.',
  'Dispute|Payment': 'Payment and dispute terms interact — late fees, refunds and who pays for disagreements are usually covered across both sections.',
  'Payment|Warranty': 'Payments and warranty/support commitments are linked — support sometimes depends on being paid up.',
};

const TOPIC_KEYWORDS: Record<string, { words: string[]; label: string }> = {
  terminate: { words: ['terminat', 'cancel', 'end this agreement', 'cease'], label: 'ending the contract' },
  notice: { words: ['notice', 'notify', 'days prior', 'in writing', 'written notice'], label: 'notice periods' },
  renew: { words: ['renew', 'auto-renew', 'successive', 'roll over'], label: 'renewal' },
  pay: { words: ['pay', 'fee', 'charge', 'amount', 'invoice', 'deposit', 'rent'], label: 'payments and fees' },
  liability: { words: ['liab', 'indemn', 'hold harmless', 'responsible for', 'damages'], label: 'liability' },
  data: { words: ['data', 'privacy', 'personal information', 'confidential', 'gdpr'], label: 'privacy and data' },
  dispute: { words: ['dispute', 'arbitrat', 'jurisdiction', 'court', 'governing law', 'litigation'], label: 'disputes and legal process' },
  warranty: { words: ['warrant', 'guarantee', 'repair', 'replacement', 'defect'], label: 'warranty and support' },
};

function topicsOf(text: string): Set<string> {
  const t = text.toLowerCase();
  const found = new Set<string>();
  for (const [topic, { words }] of Object.entries(TOPIC_KEYWORDS)) {
    if (words.some((w) => t.includes(w))) found.add(topic);
  }
  return found;
}

/** Find other clauses in the same analysis whose actual wording overlaps in
 *  topic with the given clause. Uses only real clause text. */
export function relatedClauses(clause: Clause, all: Clause[]): ClauseLink[] {
  const mine = topicsOf(clause.text);
  if (mine.size === 0) return [];
  const links: ClauseLink[] = [];
  for (const other of all) {
    if (other.clause_id === clause.clause_id) continue;
    const theirs = topicsOf(other.text);
    for (const topic of Array.from(mine)) {
      if (theirs.has(topic)) {
        links.push({
          clauseId: other.clause_id,
          reason: `Both sections touch on ${TOPIC_KEYWORDS[topic].label}.`,
          kind: 'wording',
        });
        break;
      }
    }
  }
  return links.slice(0, 4);
}

/** Build the full relationship list for an analysis from category pairings and
 *  shared-wording matches. Every pair is made of real clauses. */
export function deriveRelationships(clauses: Clause[]): Relationship[] {
  const out: Relationship[] = [];
  const seen = new Set<string>();

  for (let i = 0; i < clauses.length; i++) {
    for (let j = i + 1; j < clauses.length; j++) {
      const a = clauses[i];
      const b = clauses[j];
      const key = [a.category, b.category].sort().join('|');
      const reason = CATEGORY_PAIRS[key];
      if (reason) {
        const pairKey = [a.clause_id, b.clause_id].sort().join('#');
        if (!seen.has(pairKey)) {
          seen.add(pairKey);
          out.push({ id: pairKey, a, b, reason, kind: 'category' });
        }
      }
    }
  }

  // wording-level links (only when not already covered above)
  for (const clause of clauses) {
    for (const link of relatedClauses(clause, clauses)) {
      const partner = clauses.find((c) => c.clause_id === link.clauseId);
      if (!partner) continue;
      const pairKey = [clause.clause_id, partner.clause_id].sort().join('#');
      if (seen.has(pairKey)) continue;
      seen.add(pairKey);
      out.push({ id: pairKey, a: clause, b: partner, reason: link.reason, kind: 'wording' });
    }
  }

  return out.sort((x, y) => x.a.category.localeCompare(y.a.category));
}
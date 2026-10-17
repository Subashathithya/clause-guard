import type { AttentionLevel, Clause, RiskLevel } from '../types';

export function inr(n?: number | null): string {
  if (!n || n <= 0) return '₹0';
  return `₹${n.toLocaleString('en-IN')}`;
}

export function compactInr(n?: number | null): string {
  if (!n || n <= 0) return '₹0';
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(1)} L`;
  if (n >= 1_000) return `₹${(n / 1_000).toFixed(1)}k`;
  return `₹${n}`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const diff = Date.now() - d.getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

/** Map the stored risk level to a consumer-facing review label. */
export function attentionOf(level: RiskLevel | string | undefined | null): AttentionLevel {
  if (level === 'red') return 'high';
  if (level === 'yellow') return 'moderate';
  if (level === 'green') return 'low';
  return 'unknown';
}

export function attentionLabel(level: AttentionLevel | string): string {
  switch (level) {
    case 'high':
      return 'Review carefully';
    case 'moderate':
      return 'Worth a look';
    case 'low':
      return 'Looks fine';
    default:
      return 'Awaiting review';
  }
}

export function attentionCss(level: AttentionLevel | string): string {
  switch (level) {
    case 'high':
      return 'att-high';
    case 'moderate':
      return 'att-mid';
    case 'low':
      return 'att-low';
    default:
      return 'att-unknown';
  }
}

export function sortNumbers(a: string, b: string): number {
  return a.localeCompare(b, undefined, { numeric: true });
}

export function categoryLabel(category: string): string {
  const map: Record<string, string> = {
    Payment: 'Payments & fees',
    'Auto-Renewal': 'Renewal & cancellation',
    Liability: 'Liability',
    'Data Privacy': 'Privacy & data',
    Dispute: 'Disputes & legal',
    Warranty: 'Warranty & support',
    Other: 'Other sections',
  };
  return map[category] || category || 'Other';
}

export function whitespace(content: string): string {
  return content.replace(/\s+/g, ' ').trim();
}

export function clauseSummary(clause?: Clause): string {
  if (!clause) return '';
  const fd = whitespace(clause.financial_impact);
  if (fd && fd.toLowerCase() !== 'none identified') return fd;
  return whitespace(clause.explanation || '');
}
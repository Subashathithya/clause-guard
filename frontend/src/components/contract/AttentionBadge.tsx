import type { AttentionLevel, RiskLevel } from '../../types';
import { attentionCss, attentionLabel } from '../../lib/format';
import { Badge } from '../ui/primitives';

export function AttentionBadge({
  level,
  size = 'md',
}: {
  level: RiskLevel | AttentionLevel | string | undefined | null;
  size?: 'sm' | 'md';
}) {
  const normalized: AttentionLevel =
    level === 'high' || level === 'moderate' || level === 'low' || level === 'unknown'
      ? level
      : level === 'red'
        ? 'high'
        : level === 'yellow'
          ? 'moderate'
          : level === 'green'
            ? 'low'
            : 'unknown';

  const label =
    normalized === 'unknown' ? 'Awaiting review' : size === 'sm' ? shortLabel(normalized) : attentionLabel(normalized);
  return (
    <Badge className={`${attentionCss(normalized)}`} title={attentionLabel(normalized)}>
      {label}
    </Badge>
  );
}

function shortLabel(level: AttentionLevel): string {
  switch (level) {
    case 'high':
      return 'Review';
    case 'moderate':
      return 'Check';
    case 'low':
      return 'OK';
    default:
      return '—';
  }
}
import { Link } from 'react-router-dom';
import { FileText, MoreHorizontal, Trash2 } from 'lucide-react';
import type { Contract } from '../../types';
import { Badge } from '../ui/primitives';
import { MenuAction, Popover } from '../ui/overlays';
import { useI18n } from '../../i18n/I18nProvider';

export function countBadges(c?: Contract): { red: number; yellow: number; green: number } {
  return {
    red: c?.red_count ?? 0,
    yellow: c?.yellow_count ?? 0,
    green: c?.green_count ?? 0,
  };
}

export function ContractCard({
  contract,
  onDelete,
  footer,
}: {
  contract: Contract;
  onDelete?: (id: string) => void;
  footer?: React.ReactNode;
}) {
  const counts = countBadges(contract);
  const { t, formatDateTime, timeAgo } = useI18n();
  return (
    <div className="contract-card card">
      <div className="cc-top">
        <span className="cc-icon" aria-hidden="true">
          <FileText size={19} />
        </span>
        <div className="cc-title-wrap">
          <Link to={`/contracts/${contract.document_id}`} className="cc-title">
            {contract.document_name}
          </Link>
          <span className="text-xs faint">{timeAgo(contract.created_at)} · {formatDateTime(contract.created_at)}</span>
        </div>
        {onDelete && (
          <Popover
            label={t('clause.contractOptions')}
            trigger={<button type="button" className="icon-btn" aria-label={t('clause.contractOptions')}><MoreHorizontal size={18} /></button>}
          >
            {(close) => (
              <MenuAction
                danger
                onSelect={() => {
                  close();
                  onDelete(contract.document_id);
                }}
              >
                <Trash2 size={15} /> {t('clause.removeContract')}
              </MenuAction>
            )}
          </Popover>
        )}
      </div>
      <div className="cc-meta">
        {contract.status === 'NO_CLAUSES' ? (
          <Badge tone="warning">{t('clause.noClausesFound')}</Badge>
        ) : (
          <>
            <span className="cc-count att-red" title={t('clause.sectionsCareful')}>{counts.red}</span>
            <span className="cc-count att-amber" title={t('clause.sectionsWorthLook')}>{counts.yellow}</span>
            <span className="cc-count att-green" title={t('clause.sectionsFine')}>{counts.green}</span>
          </>
        )}
        <span className="cc-chars faint text-xs">
          {t('contract.characters', { count: contract.char_count?.toLocaleString() ?? 0 })}
        </span>
        {contract.source && (
          <Badge tone="neutral">
            {contract.source === 'upload' ? t('contract.uploaded') : t('contract.pasted')}
          </Badge>
        )}
      </div>
      {footer}
    </div>
  );
}
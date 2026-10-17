import { Link } from 'react-router-dom';
import { FileText, MoreHorizontal, Trash2 } from 'lucide-react';
import type { Contract } from '../../types';
import { Badge } from '../ui/primitives';
import { MenuAction, Popover } from '../ui/overlays';
import { formatDateTime, timeAgo } from '../../lib/format';

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
            label="Contract options"
            trigger={<button type="button" className="icon-btn" aria-label="Contract options"><MoreHorizontal size={18} /></button>}
          >
            {(close) => (
              <MenuAction
                danger
                onSelect={() => {
                  close();
                  onDelete(contract.document_id);
                }}
              >
                <Trash2 size={15} /> Remove contract
              </MenuAction>
            )}
          </Popover>
        )}
      </div>
      <div className="cc-meta">
        {contract.status === 'NO_CLAUSES' ? (
          <Badge tone="warning">No clauses found</Badge>
        ) : (
          <>
            <span className="cc-count att-red" title="Sections to review carefully">{counts.red}</span>
            <span className="cc-count att-amber" title="Sections worth a look">{counts.yellow}</span>
            <span className="cc-count att-green" title="Sections that look fine">{counts.green}</span>
          </>
        )}
        <span className="cc-chars faint text-xs">{contract.char_count?.toLocaleString()} characters</span>
        {contract.source && (
          <Badge tone="neutral">
            {contract.source === 'upload' ? 'Uploaded' : 'Pasted text'}
          </Badge>
        )}
      </div>
      {footer}
    </div>
  );
}
import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { useAsync, useDebounced } from '../hooks';
import type { Contract } from '../types';
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui/data';
import { Select, SkeletonLines } from '../components/ui/primitives';
import { ContractCard } from '../components/contract/ContractCard';
import { useToast } from '../components/ui/overlays';
import { useI18n } from '../i18n/I18nProvider';

type AttentionFilter = 'all' | 'attention' | 'careful';
type SortKey = 'recent' | 'name' | 'sections';

const OPTIONS = {
  attention: [
    { value: 'all', key: 'contracts.allContracts' },
    { value: 'attention', key: 'contracts.hasSectionsToReview' },
    { value: 'careful', key: 'contracts.hasSectionsCareful' },
  ],
  sort: [
    { value: 'recent', key: 'contracts.newestFirst' },
    { value: 'name', key: 'contracts.nameAz' },
    { value: 'sections', key: 'contracts.mostSections' },
  ],
};

export default function ContractsPage() {
  const toast = useToast();
  const { t } = useI18n();
  const { value: contracts, loading, error, retry, setValue } = useAsync<Contract[]>(() => api.contracts(), []);
  const [search, setSearch] = useState('');
  const [attention, setAttention] = useState<AttentionFilter>('all');
  const [sort, setSort] = useState<SortKey>('recent');
  const debouncedSearch = useDebounced(search);

  const filtered = useMemo(() => {
    let rows = contracts || [];
    const q = debouncedSearch.trim().toLowerCase();
    if (q) rows = rows.filter((c) => c.document_name.toLowerCase().includes(q));
    if (attention === 'attention') rows = rows.filter((c) => (c.red_count ?? 0) + (c.yellow_count ?? 0) > 0);
    if (attention === 'careful') rows = rows.filter((c) => (c.red_count ?? 0) > 0);
    switch (sort) {
      case 'name':
        rows = [...rows].sort((a, b) => a.document_name.localeCompare(b.document_name));
        break;
      case 'sections':
        rows = [...rows].sort((a, b) => (b.total_clauses ?? 0) - (a.total_clauses ?? 0));
        break;
      default:
        rows = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at));
    }
    return rows;
  }, [contracts, debouncedSearch, attention, sort]);

  const handleDelete = async (id: string) => {
    try {
      await api.deleteContract(id);
      setValue((prev) => (prev || []).filter((c) => c.document_id !== id));
      toast.push(t('common.contractRemoved'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('common.couldNotRemove'), 'error');
    }
  };

  return (
    <div>
      <PageHeader
        title={t('contracts.title')}
        lead={t('contracts.lead')}
        actions={<Link to="/analyze" className="btn btn-primary">{t('contracts.analyzeNew')}</Link>}
      />

      {loading && !contracts ? (
        <Card pad><SkeletonLines lines={6} /></Card>
      ) : error && !contracts ? (
        <ErrorState message={error} onRetry={retry} />
      ) : !contracts || contracts.length === 0 ? (
        <Card>
          <EmptyState
            title={t('contracts.noContractsYet')}
            description={t('contracts.noContractsYetBody')}
            action={<Link to="/analyze" className="btn btn-primary">{t('contracts.analyzeFirst')}</Link>}
          />
        </Card>
      ) : (
        <>
          <div className="contract-filters card card-pad row-spread">
            <div className="search-wrap">
              <Search size={16} aria-hidden="true" />
              <input
                type="search"
                className="search-input"
                placeholder={t('contracts.searchPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label={t('contracts.searchLabel')}
              />
            </div>
            <div className="row" style={{ gap: 10 }}>
              <Select
                options={OPTIONS.attention.map((o) => ({ value: o.value, label: t(o.key) }))}
                value={attention}
                onChange={(e) => setAttention(e.target.value as AttentionFilter)}
                aria-label={t('contracts.filterLabel')}
              />
              <Select
                options={OPTIONS.sort.map((o) => ({ value: o.value, label: t(o.key) }))}
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                aria-label={t('contracts.sortLabel')}
              />
            </div>
          </div>

          <p className="text-sm faint mt-3">
            {filtered.length === 1
              ? t('contracts.countOne', { count: filtered.length })
              : t('contracts.countMany', { count: filtered.length })}
          </p>

          <div className="contract-grid mt-3">
            {filtered.length === 0 ? (
              <Card>
                <EmptyState title={t('contracts.noMatching')} description={t('contracts.tryDifferentSearch')} />
              </Card>
            ) : (
              filtered.map((c) => <ContractCard key={c.document_id} contract={c} onDelete={handleDelete} />)
            )}
          </div>
        </>
      )}
    </div>
  );
}
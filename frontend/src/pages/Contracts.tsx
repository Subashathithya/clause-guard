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

type AttentionFilter = 'all' | 'attention' | 'careful';
type SortKey = 'recent' | 'name' | 'sections';

const OPTIONS = {
  attention: [
    { value: 'all', label: 'All contracts' },
    { value: 'attention', label: 'Has sections to review' },
    { value: 'careful', label: 'Has sections to review carefully' },
  ],
  sort: [
    { value: 'recent', label: 'Newest first' },
    { value: 'name', label: 'Name A–Z' },
    { value: 'sections', label: 'Most sections' },
  ],
};

export default function ContractsPage() {
  const toast = useToast();
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
      toast.push('Contract removed from your workspace.', 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Could not remove that contract.', 'error');
    }
  };

  return (
    <div>
      <PageHeader
        title="My contracts"
        lead="Every document you’ve analysed, in one place."
        actions={<Link to="/analyze" className="btn btn-primary">Analyze new contract</Link>}
      />

      {loading && !contracts ? (
        <Card pad><SkeletonLines lines={6} /></Card>
      ) : error && !contracts ? (
        <ErrorState message={error} onRetry={retry} />
      ) : !contracts || contracts.length === 0 ? (
        <Card>
          <EmptyState
            title="No contracts yet"
            description="Once you analyse a contract it will appear here so you can reopen it anytime."
            action={<Link to="/analyze" className="btn btn-primary">Analyse your first contract</Link>}
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
                placeholder="Search contracts…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search contracts"
              />
            </div>
            <div className="row" style={{ gap: 10 }}>
              <Select
                options={OPTIONS.attention}
                value={attention}
                onChange={(e) => setAttention(e.target.value as AttentionFilter)}
                aria-label="Filter by attention level"
              />
              <Select
                options={OPTIONS.sort}
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                aria-label="Sort contracts"
              />
            </div>
          </div>

          <p className="text-sm faint mt-3">{filtered.length} contract{filtered.length === 1 ? '' : 's'}</p>

          <div className="contract-grid mt-3">
            {filtered.length === 0 ? (
              <Card>
                <EmptyState title="No matching contracts" description="Try a different search or clear the filters." />
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
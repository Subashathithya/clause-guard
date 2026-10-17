import { useMemo, useState } from 'react';
import { ArrowLeftRight, Layers } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { CompareResult, Contract, DriftResult } from '../types';
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui/data';
import { Alert, Button, Select, SkeletonLines } from '../components/ui/primitives';

export default function ComparePage() {
  const { value: contracts, loading, error, retry } = useAsync<Contract[]>(() => api.contracts(), []);
  const [aId, setAId] = useState('');
  const [bId, setBId] = useState('');
  const [busy, setBusy] = useState<null | 'compare' | 'drift'>(null);
  const [resultError, setResultError] = useState('');
  const [compare, setCompare] = useState<CompareResult | null>(null);
  const [drift, setDrift] = useState<DriftResult | null>(null);

  const options = useMemo(
    () => (contracts || []).map((c) => ({ value: c.document_id, label: c.document_name })),
    [contracts]
  );

  const selA = (contracts || []).find((c) => c.document_id === aId);
  const selB = (contracts || []).find((c) => c.document_id === bId);

  const run = async (kind: 'compare' | 'drift') => {
    setResultError('');
    if (!aId || !bId) {
      setResultError('Choose a first and second version to compare.');
      return;
    }
    if (aId === bId) {
      setResultError('The two versions must be different documents.');
      return;
    }
    setBusy(kind);
    setCompare(null);
    setDrift(null);
    try {
      if (kind === 'drift') {
        setDrift(await api.drift([aId, bId]));
      } else {
        setCompare(await api.compare([aId, bId]));
      }
    } catch (err) {
      setResultError(err instanceof Error ? err.message : 'Comparison failed. Please try again.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Compare versions"
        lead="Have an old version and a new version of the same contract? Pick them and see exactly what changed between them."
      />

      {loading && !contracts ? (
        <Card pad><SkeletonLines lines={5} /></Card>
      ) : error && !contracts ? (
        <ErrorState message={error} onRetry={retry} />
      ) : !contracts || contracts.length < 2 ? (
        <Card>
          <EmptyState
            icon={<Layers size={26} />}
            title={contracts && contracts.length === 1 ? 'Need at least two contracts' : 'No contracts to compare yet'}
            description="Analyse at least two contracts (for example, version 1 and version 2 of the same agreement) and come back here."
          />
        </Card>
      ) : (
        <>
          <div className="card card-pad">
            <div className="comp-selects">
              <div style={{ flex: 1 }}>
                <label className="field-label mb-2" htmlFor="cmp-a">First version (the one you already have)</label>
                <Select id="cmp-a" options={options} value={aId} onChange={(e) => setAId(e.target.value)} aria-label="First version" />
                {selA && <p className="text-xs faint mt-2">Analysed · {selA.created_at}</p>}
              </div>
              <span className="comp-arrow" aria-hidden="true">→</span>
              <div style={{ flex: 1 }}>
                <label className="field-label mb-2" htmlFor="cmp-b">Second version (the one you’re being asked to sign)</label>
                <Select id="cmp-b" options={options} value={bId} onChange={(e) => setBId(e.target.value)} aria-label="Second version" />
                {selB && <p className="text-xs faint mt-2">Analysed · {selB.created_at}</p>}
              </div>
            </div>

            <div className="row mt-4" style={{ gap: 10 }}>
              <Button onClick={() => run('compare')} loading={busy === 'compare'}>
                <Layers size={16} /> Compare side by side
              </Button>
              <Button variant="secondary" onClick={() => run('drift')} loading={busy === 'drift'}>
                <ArrowLeftRight size={16} /> See what changed
              </Button>
            </div>
            {resultError && (
              <div className="mt-3">
                <Alert tone="danger" title="Couldn't run that comparison">{resultError}</Alert>
              </div>
            )}
          </div>

          {compare && <CompareTable compare={compare} />}
          {drift && <DriftTable drift={drift} />}
        </>
      )}
    </div>
  );
}

function CompareTable({ compare }: { compare: CompareResult }) {
  return (
    <div className="card card-pad mt-4">
      <h3 className="card-title">Side-by-side overview</h3>
      <p className="text-sm muted">
        Average attention scores by topic — a lower score means the wording is closer to common practice.
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Topic</th>
              {compare.documents.map((d) => (
                <th key={d.document_id}>{d.document_name}</th>
              ))}
              <th>More even terms</th>
            </tr>
          </thead>
          <tbody>
            {compare.category_matrix.map((row) => (
              <tr key={row.category}>
                <td>{row.category}</td>
                {compare.documents.map((d) => {
                  const v = row.by_document[d.document_name];
                  return <td key={d.document_id}>{v !== undefined ? v : '—'}</td>;
                })}
                <td>{row.winner || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {compare.narrative && (
        <div className="alert alert-info mt-4">
          <div>
            <strong className="alert-title">What this means for you</strong>
            <div className="mt-2">{compare.narrative}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function DirectionBadge({ dir }: { dir: string }) {
  if (dir === 'improved') return <span className="cc-tag green">Improved</span>;
  if (dir === 'worsened') return <span className="cc-tag red">Warrants attention</span>;
  if (dir === 'stable') return <span className="cc-tag">Unchanged</span>;
  if (dir === 'added') return <span className="cc-tag amber">Added</span>;
  if (dir === 'removed') return <span className="cc-tag">Removed</span>;
  return <span className="cc-tag">{dir}</span>;
}

function DriftTable({ drift }: { drift: DriftResult }) {
  return (
    <div className="card card-pad mt-4">
      <div className="card-header">
        <div>
          <h3 className="card-title">
            What changed: {drift.old.document_name} → {drift.new.document_name}
          </h3>
          <p className="text-sm muted mb-0">
            Overall, the newer version{' '}
            {drift.overall_direction === 'improved'
              ? 'reads as fairer than the old one.'
              : drift.overall_direction === 'worsened'
                ? 'deserves more attention than the old one.'
                : 'is broadly in line with the old one.'}
            {drift.overall_delta !== 0 && (
              <> (total shift {drift.overall_delta > 0 ? '+' : ''}{drift.overall_delta} points)</>
            )}
          </p>
        </div>
        <DirectionBadge dir={drift.overall_direction} />
      </div>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Before</th>
              <th>After</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {drift.changes.map((c) => (
              <tr key={c.category}>
                <td>{c.category}</td>
                <td>{c.before ?? '—'}</td>
                <td>{c.after ?? '—'}</td>
                <td><DirectionBadge dir={c.direction} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs faint mt-4 mb-0">
        This comparison is based on the attention scores of each topic in the two analysed versions.
      </p>
    </div>
  );
}
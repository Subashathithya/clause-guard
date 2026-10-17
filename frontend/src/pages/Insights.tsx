import { useMemo } from 'react';
import { BarChart3, FolderOpen, Lightbulb } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { AnalysisResult } from '../types';
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui/data';
import { SkeletonLines } from '../components/ui/primitives';

function useInsightsData() {
  return useAsync(async () => {
    const [stats, contracts] = await Promise.all([api.stats(), api.contracts()]);
    let analyses: AnalysisResult[] = [];
    if (contracts.length > 0) {
      const results = await Promise.allSettled(
        contracts.slice(0, 12).map((c) => api.getAnalysis(c.document_id))
      );
      analyses = results
        .filter((r): r is PromiseFulfilledResult<AnalysisResult> => r.status === 'fulfilled')
        .map((r) => r.value);
    }
    return { stats, contracts, analyses };
  }, []);
}

function MiniBar({ value, max, tone }: { value: number; max: number; tone: string }) {
  return (
    <div className="mini-bar">
      <div
        className="mini-bar-fill"
        style={{ width: max > 0 ? `${Math.max(4, (value / max) * 100)}%` : '0%', background: tone }}
      />
    </div>
  );
}

export default function Insights() {
  const { value, loading, error, retry } = useInsightsData();

  const categoryFreq = useMemo(() => {
    const map: Record<string, number> = {};
    for (const a of value?.analyses || []) {
      for (const c of a.clauses || []) map[c.category] = (map[c.category] || 0) + 1;
    }
    return Object.entries(map).sort((a, b) => b[1] - a[1]);
  }, [value]);

  const perContract = useMemo(() => {
    return (value?.contracts || [])
      .map((c) => ({ c, attention: (c.red_count || 0) + (c.yellow_count || 0) }))
      .sort((a, b) => b.attention - a.attention)
      .slice(0, 8);
  }, [value]);

  const activity = useMemo(() => {
    const map: Record<string, number> = {};
    for (const c of value?.contracts || []) {
      const key = new Date(c.created_at).toLocaleString(undefined, { month: 'short', year: '2-digit' });
      map[key] = (map[key] || 0) + 1;
    }
    return Object.entries(map).sort((a, b) => a[0].localeCompare(b[0])).slice(-8);
  }, [value]);

  if (loading && !value) return <Card pad><SkeletonLines lines={8} /></Card>;
  if (error && !value) {
    return (
      <div>
        <PageHeader title="Insights" />
        <ErrorState message={error} onRetry={retry} />
      </div>
    );
  }
  if (!value) return null;

  const { stats, contracts } = value;

  return (
    <div>
      <PageHeader
        title="Insights"
        lead="A look across the documents in your workspace — built only from the analyses you’ve run."
      />

      {contracts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Lightbulb size={26} />}
            title="Nothing to show yet"
            description="Once you analyse a few contracts, this page will show which kinds of sections show up most often and where attention is commonly needed."
          />
        </Card>
      ) : (
        <div className="stack">
          <div className="grid grid-3">
            <Card title="Documents analysed" subtitle="In your workspace">
              <div className="ov-item"><span className="ov-num">{stats.total_contracts}</span></div>
            </Card>
            <Card title="Sections understood" subtitle="Across all documents">
              <div className="ov-item"><span className="ov-num">{stats.total_clauses}</span></div>
            </Card>
            <Card title="To review in total" subtitle="Sections flagged">
              <div className="ov-item">
                <span className="ov-num att-red">{stats.red_clauses}</span>
                <span className="text-sm faint"> carefully · </span>
                <span className="ov-num att-amber">{stats.yellow_clauses}</span>
                <span className="text-sm faint"> worth a look</span>
              </div>
            </Card>
          </div>

          {categoryFreq.length > 0 && (
            <Card
              title="Sections by topic"
              subtitle="Which kinds of clauses appear most across your documents"
            >
              <div className="insight-list">
                {categoryFreq.map(([cat, n]) => (
                  <div key={cat} className="insight-row">
                    <span className="text-sm" style={{ flex: 1 }}>{cat}</span>
                    <MiniBar value={n} max={categoryFreq[0][1]} tone="var(--brand-400)" />
                    <span className="insight-val">{n}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {perContract.length > 0 && (
            <Card
              title="Where attention adds up"
              subtitle="Documents with the most sections to review"
            >
              <div className="insight-list">
                {perContract.map(({ c, attention }) => (
                  <div key={c.document_id} className="insight-row">
                    <span className="text-sm" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {c.document_name}
                    </span>
                    <MiniBar value={attention} max={perContract[0].attention} tone={attention > 0 ? 'var(--warning-text)' : 'var(--success-text)'} />
                    <span className="insight-val">{attention}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {activity.length > 0 && (
            <Card title="Your activity" subtitle="Contracts analysed over the months">
              <div className="insight-list">
                {activity.map(([month, n]) => (
                  <div key={month} className="insight-row">
                    <span className="text-sm" style={{ flex: 1 }}>{month}</span>
                    <MiniBar value={n} max={Math.max(...activity.map((a) => a[1]))} tone="var(--brand-600)" />
                    <span className="insight-val">{n}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs faint mt-3 mb-0">
                <BarChart3 size={12} style={{ verticalAlign: -2 }} /> Averages are rounded from your real analysis data.
              </p>
            </Card>
          )}

          <Card
            title="How this is put together"
            subtitle=""
          >
            <p className="text-sm muted mb-0" style={{ display: 'flex', gap: 8 }}>
              <FolderOpen size={15} className="faint" style={{ flex: 'none', marginTop: 3 }} />
              Everything here comes straight from the analyses in your workspace. When you remove a
              contract, the numbers here update automatically.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
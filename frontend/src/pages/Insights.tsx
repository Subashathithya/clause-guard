import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { BarChart3, FolderOpen, Gauge, Lightbulb, ShieldCheck } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { AnalysisResult } from '../types';
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui/data';
import { SkeletonLines } from '../components/ui/primitives';
import { ActivityArea, CategoryBars, ChartCard, RiskDonut, RiskStackedBars } from '../components/charts/Charts';
import { categoryLabel } from '../lib/format';

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

function Stat({ icon, label, value, hint }: { icon: ReactNode; label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card card-pad stat-tile">
      <span className="stat-tile-icon">{icon}</span>
      <div>
        <div className="stat-tile-value">{value}</div>
        <div className="stat-tile-label">{label}</div>
        {hint && <div className="stat-tile-hint">{hint}</div>}
      </div>
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
    return Object.entries(map)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 7)
      .map(([cat, n]) => ({ name: categoryLabel(cat), value: n }));
  }, [value]);

  const activity = useMemo(() => {
    const map: Record<string, { label: string; count: number }> = {};
    for (const c of value?.contracts || []) {
      const d = new Date(c.created_at);
      if (Number.isNaN(d.getTime())) continue;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      map[key] = { label: d.toLocaleString(undefined, { month: 'short' }), count: (map[key]?.count || 0) + 1 };
    }
    return Object.entries(map)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-8)
      .map(([, v]) => v);
  }, [value]);

  const perContract = useMemo(
    () =>
      (value?.contracts || []).slice(0, 6).map((c) => ({
        name: c.document_name.length > 16 ? `${c.document_name.slice(0, 15)}…` : c.document_name,
        high: c.red_count || 0,
        moderate: c.yellow_count || 0,
        low: c.green_count || 0,
      })),
    [value]
  );

  const attentionRanking = useMemo(
    () =>
      (value?.contracts || [])
        .map((c) => ({ c, attention: (c.red_count || 0) + (c.yellow_count || 0) }))
        .sort((a, b) => b.attention - a.attention)
        .slice(0, 6),
    [value]
  );

  if (loading && !value) return <Card pad><SkeletonLines lines={10} /></Card>;
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
  const totalClauses = stats.red_clauses + stats.yellow_clauses + stats.green_clauses;
  const flaggedPct = totalClauses > 0 ? Math.round(((stats.red_clauses + stats.yellow_clauses) / totalClauses) * 100) : 0;
  const safetyPct = totalClauses > 0 ? 100 - flaggedPct : 0;

  return (
    <div>
      <PageHeader
        title="Insights"
        lead="An analytics view across the documents in your workspace — computed only from the analyses you’ve run."
      />

      {contracts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Lightbulb size={26} />}
            title="Nothing to show yet"
            description="Once you analyse a few contracts, this page will fill with risk breakdowns, clause categories and trends from your real data."
          />
        </Card>
      ) : (
        <div className="stack">
          <div className="stat-strip">
            <Stat icon={<FolderOpen size={18} />} label="Documents analysed" value={stats.total_contracts} hint="in your workspace" />
            <Stat icon={<BarChart3 size={18} />} label="Sections understood" value={stats.total_clauses} hint="across all documents" />
            <Stat
              icon={<ShieldCheck size={18} />}
              label="Sections flagged"
              value={
                <>
                  <span style={{ color: 'var(--danger-text)' }}>{stats.red_clauses}</span>
                  <span className="faint" style={{ fontSize: '0.62em' }}> high · </span>
                  <span style={{ color: 'var(--warning-text)' }}>{stats.yellow_clauses}</span>
                  <span className="faint" style={{ fontSize: '0.62em' }}> moderate</span>
                </>
              }
              hint="needs a closer look"
            />
            <Stat
              icon={<Gauge size={18} />}
              label="Clean clauses"
              value={`${safetyPct}%`}
              hint={`${stats.green_clauses} low-risk sections`}
            />
          </div>

          <div className="chart-grid">
            <ChartCard title="Risk composition" subtitle="Every clause in the workspace, grouped by severity">
              <RiskDonut red={stats.red_clauses} yellow={stats.yellow_clauses} green={stats.green_clauses} />
            </ChartCard>
            <ChartCard title="Analysis activity" subtitle="Contracts analysed per month">
              <ActivityArea data={activity} />
            </ChartCard>
          </div>

          <div className="chart-grid">
            <ChartCard title="Sections by topic" subtitle="Which kinds of clauses appear most often">
              <CategoryBars data={categoryFreq} />
            </ChartCard>
            <ChartCard title="Risk mix per contract" subtitle="Six most recent documents, stacked by severity">
              <RiskStackedBars data={perContract} />
            </ChartCard>
          </div>

          {attentionRanking.length > 0 && (
            <Card title="Where attention adds up" subtitle="Documents with the most sections to review">
              <div className="rank-list">
                {attentionRanking.map(({ c, attention }, i) => {
                  const max = attentionRanking[0].attention || 1;
                  return (
                    <div key={c.document_id} className="rank-row">
                      <span className="rank-index">{i + 1}</span>
                      <span className="rank-name">{c.document_name}</span>
                      <span className="rank-bar">
                        <span
                          className="rank-bar-fill"
                          style={{ width: `${Math.max(4, (attention / max) * 100)}%` }}
                        />
                      </span>
                      <span className="rank-value">{attention}</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}

          <Card title="How this is put together" subtitle="">
            <p className="text-sm muted mb-0" style={{ display: 'flex', gap: 8 }}>
              <FolderOpen size={15} className="faint" style={{ flex: 'none', marginTop: 3 }} />
              Everything here comes straight from the analyses in your workspace. When you remove a
              contract, the numbers and charts update automatically.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}

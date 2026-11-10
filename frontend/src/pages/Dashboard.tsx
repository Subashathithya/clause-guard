import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, FilePlus2, FolderOpen, Layers, MessageCircleQuestion } from 'lucide-react';
import { useAsync } from '../hooks';
import { useAuth } from '../auth/context';
import { api } from '../api';
import type { Contract, Stats } from '../types';
import { Card, EmptyState, PageHeader } from '../components/ui/data';
import { SkeletonLines } from '../components/ui/primitives';
import { ContractCard } from '../components/contract/ContractCard';
import { useToast } from '../components/ui/overlays';
import { ActivityArea, ChartCard, RiskDonut } from '../components/charts/Charts';

function Metric({ label, value, tone }: { label: string; value: string | number; tone?: 'red' | 'amber' | 'green' }) {
  const color =
    tone === 'red' ? 'var(--danger-text)' : tone === 'amber' ? 'var(--warning-text)' : tone === 'green' ? 'var(--success-text)' : 'var(--text-strong)';
  return (
    <div className="metric-card card card-pad">
      <div className="mc-label">{label}</div>
      <div className="mc-value" style={{ color }}>{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { user, loggedIn } = useAuth();
  const toast = useToast();
  const { value: stats, loading: statsLoading, error: statsError, retry: retryStats } = useAsync<Stats>(() => api.stats(), []);
  const { value: contracts, loading: contractsLoading, error: contractsError, retry: retryContracts, setValue: setContracts } = useAsync<Contract[]>(() => api.contracts(), []);

  const recent = (contracts || []).slice(0, 6);
  const attentionCount = (stats?.red_clauses ?? 0) + (stats?.yellow_clauses ?? 0);
  const remaining = loggedIn ? user?.quota.remaining : null;

  const activity = useMemo(() => {
    const map: Record<string, { label: string; count: number }> = {};
    for (const c of contracts || []) {
      const d = new Date(c.created_at);
      if (Number.isNaN(d.getTime())) continue;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      map[key] = { label: d.toLocaleString(undefined, { month: 'short' }), count: (map[key]?.count || 0) + 1 };
    }
    return Object.entries(map)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-8)
      .map(([, v]) => v);
  }, [contracts]);

  const handleDelete = async (id: string) => {
    try {
      await api.deleteContract(id);
      setContracts((prev) => (prev || []).filter((c) => c.document_id !== id));
      toast.push('Contract removed from your workspace.', 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : 'Could not remove that contract.', 'error');
    }
  };

  return (
    <div>
      <PageHeader
        title={`Welcome back${loggedIn && user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        lead={
          statsError && !statsLoading
            ? undefined
            : 'See how your contracts look at a glance, and start your next analysis.'
        }
        actions={
          <Link to="/analyze" className="btn btn-primary">
            <FilePlus2 size={16} /> Analyze a contract
          </Link>
        }
      />

      {statsLoading && !stats ? (
        <Card pad>
          <SkeletonLines lines={3} />
        </Card>
      ) : statsError && !stats ? (
        <Card pad>
          <p className="muted">{statsError}</p>
          <button className="btn btn-secondary btn-sm" onClick={retryStats}>Try again</button>
        </Card>
      ) : (
        <div className="metric-grid">
          <Metric label="Contracts analysed" value={stats?.total_contracts ?? 0} />
          <Metric label="Sections found across documents" value={stats?.total_clauses ?? 0} />
          <Metric label="Sections to review" value={attentionCount} tone={attentionCount > 0 ? 'red' : 'green'} />
          <Metric
            label={loggedIn && remaining !== null ? 'Analyses left this month' : 'Analyses this month'}
            value={loggedIn && remaining !== null ? (remaining ?? 0) : (stats?.contracts_this_month ?? 0)}
            tone="amber"
          />
        </div>
      )}

      {(stats?.total_clauses ?? 0) > 0 && (
        <div className="chart-grid mt-4">
          <ChartCard title="Risk composition" subtitle="How the clauses you've analysed break down by severity">
            <RiskDonut red={stats?.red_clauses ?? 0} yellow={stats?.yellow_clauses ?? 0} green={stats?.green_clauses ?? 0} />
          </ChartCard>
          <ChartCard title="Analysis activity" subtitle="Contracts analysed per month">
            <ActivityArea data={activity} />
          </ChartCard>
        </div>
      )}

      <div className="quick-row">
        <Link to="/analyze?source=paste" className="quick-card card card-pad">
          <span className="qc-ic"><FilePlus2 size={18} /></span>
          <div><strong>Analyze a contract</strong><p className="muted text-sm mb-0">Upload or paste a document and get a plain-English breakdown.</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <Link to="/compare" className="quick-card card card-pad">
          <span className="qc-ic"><Layers size={18} /></span>
          <div><strong>Compare versions</strong><p className="muted text-sm mb-0">See what changed between two versions of a contract.</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <Link to="/contracts" className="quick-card card card-pad">
          <span className="qc-ic"><MessageCircleQuestion size={18} /></span>
          <div><strong>Ask about a contract</strong><p className="muted text-sm mb-0">Open a document and ask questions about its wording.</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>

      <div className="row-spread mb-3 mt-5">
        <h3 style={{ margin: 0 }}>Recent contracts</h3>
        {contracts && contracts.length > 0 && (
          <Link to="/contracts" className="text-sm">View all <ArrowRight size={13} style={{ verticalAlign: -1 }} /></Link>
        )}
      </div>

      {contractsLoading && !contracts ? (
        <Card pad><SkeletonLines lines={4} /></Card>
      ) : contractsError && !contracts ? (
        <Card pad>
          <p className="muted">{contractsError}</p>
          <button className="btn btn-secondary btn-sm" onClick={retryContracts}>Try again</button>
        </Card>
      ) : !contracts || contracts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FolderOpen size={26} />}
            title="No contracts yet"
            description="Analyse your first contract to see its summary here. It takes less than a minute."
            action={
              <Link to="/analyze" className="btn btn-primary">Analyse your first contract</Link>
            }
          />
        </Card>
      ) : (
        <div className="contract-grid">
          {recent.map((c) => (
            <ContractCard key={c.document_id} contract={c} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
import { useMemo } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CalendarDays,
  FilePlus2,
  FileSearch,
  FolderOpen,
  Gauge,
  Layers,
  MessageCircleQuestion,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { useAsync } from '../hooks';
import { useAuth } from '../auth/context';
import { api } from '../api';
import type { Contract, Reminder, Stats } from '../types';
import { Card, EmptyState, PageHeader } from '../components/ui/data';
import { SkeletonLines } from '../components/ui/primitives';
import { ContractCard } from '../components/contract/ContractCard';
import { useToast } from '../components/ui/overlays';
import { ActivityArea, ChartCard, RiskDonut } from '../components/charts/Charts';
import { useI18n } from '../i18n/I18nProvider';

type MetricTone = 'danger' | 'warning' | 'success';

function Metric({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  tone?: MetricTone;
}) {
  return (
    <div className={['metric-card', tone ? `metric-${tone}` : ''].filter(Boolean).join(' ')}>
      <div className="mc-top">
        <div className="mc-label">{label}</div>
        <span className="mc-icon" aria-hidden="true">
          {icon}
        </span>
      </div>
      <div className="mc-value">{value}</div>
      {sub && <div className="mc-sub">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const { user, loggedIn } = useAuth();
  const toast = useToast();
  const { t, formatDate } = useI18n();
  const { value: stats, loading: statsLoading, error: statsError, retry: retryStats } = useAsync<Stats>(() => api.stats(), []);
  const { value: contracts, loading: contractsLoading, error: contractsError, retry: retryContracts, setValue: setContracts } = useAsync<Contract[]>(() => api.contracts(), []);
  const { value: reminders } = useAsync<Reminder[]>(() => api.reminders(60), []);

  const recent = (contracts || []).slice(0, 6);
  const upcoming = (reminders || []).slice(0, 3);
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
      toast.push(t('common.contractRemoved'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('common.couldNotRemove'), 'error');
    }
  };

  return (
    <div>
      <PageHeader
        title={`${t('dashboard.welcome')}${loggedIn && user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        lead={
          statsError && !statsLoading
            ? undefined
            : t('dashboard.lead')
        }
        actions={
          <Link to="/analyze" className="btn btn-primary">
            <FilePlus2 size={16} /> {t('dashboard.analyzeContract')}
          </Link>
        }
      />

      {!loggedIn && (
        <div className="guest-banner">
          <span className="qc-ic"><Sparkles size={18} /></span>
          <div>
            <strong>{t('dashboard.guestTitle')}</strong>
            <p>{t('dashboard.guestBody')}</p>
          </div>
          <div className="guest-banner-actions">
            <Link to="/signup" className="btn btn-primary btn-sm">{t('dashboard.createFreeAccount')}</Link>
            <Link to="/login" className="btn btn-ghost btn-sm">{t('dashboard.signIn')}</Link>
          </div>
        </div>
      )}

      {statsLoading && !stats ? (
        <Card pad>
          <SkeletonLines lines={3} />
        </Card>
      ) : statsError && !stats ? (
        <Card pad>
          <p className="muted">{statsError}</p>
          <button className="btn btn-secondary btn-sm" onClick={retryStats}>{t('common.tryAgain')}</button>
        </Card>
      ) : (
        <div className="metric-grid">
          <Metric
            icon={<FolderOpen size={18} />}
            label={t('dashboard.contractsAnalyzed')}
            value={stats?.total_contracts ?? 0}
            sub={t('dashboard.inWorkspace')}
          />
          <Metric
            icon={<FileSearch size={18} />}
            label={t('dashboard.sectionsUnderstood')}
            value={stats?.total_clauses ?? 0}
            sub={t('dashboard.explainedPlain')}
          />
          <Metric
            icon={<ShieldAlert size={18} />}
            label={t('dashboard.sectionsToReview')}
            value={attentionCount}
            sub={attentionCount > 0 ? t('dashboard.worthCloserLook') : t('dashboard.nothingFlagged')}
            tone={attentionCount > 0 ? 'danger' : 'success'}
          />
          <Metric
            icon={<Gauge size={18} />}
            label={loggedIn && remaining !== null ? t('dashboard.analysesLeft') : t('dashboard.analysesThisMonth')}
            value={loggedIn && remaining !== null ? (remaining ?? 0) : (stats?.contracts_this_month ?? 0)}
            sub={
              loggedIn && remaining !== null
                ? t('dashboard.ofFreePlan', { count: user?.quota.monthly_limit ?? 0 })
                : t('dashboard.startNewOne')
            }
            tone="warning"
          />
        </div>
      )}

      {(stats?.total_clauses ?? 0) > 0 && (
        <div className="chart-grid mt-4">
          <ChartCard title={t('dashboard.chartContractsTitle')} subtitle={t('dashboard.chartContractsSub')}>
            <RiskDonut red={stats?.red_clauses ?? 0} yellow={stats?.yellow_clauses ?? 0} green={stats?.green_clauses ?? 0} />
          </ChartCard>
          <ChartCard title={t('dashboard.chartActivityTitle')} subtitle={t('dashboard.chartActivitySub')}>
            <ActivityArea data={activity} />
          </ChartCard>
        </div>
      )}

      {upcoming.length > 0 && (
        <Card
          className="mt-4"
          title={t('dashboard.comingUp')}
          subtitle={t('dashboard.comingUpSub')}
          actions={<Link to="/notifications" className="text-sm">{t('dashboard.viewAll')} <ArrowRight size={13} style={{ verticalAlign: -1 }} /></Link>}
        >
          <ul className="dash-reminders">
            {upcoming.map((r) => (
              <li key={r.id}>
                <Link to={`/contracts/${r.contract_id}`} className="dash-reminder">
                  <span className={['reminder-ico', r.is_overdue ? 'reminder-ico-overdue' : ''].join(' ')} aria-hidden="true">
                    <CalendarDays size={17} />
                  </span>
                  <span className="dash-reminder-body">
                    <strong>{r.label}</strong>
                    <span className="text-sm muted">{r.contract_name}</span>
                  </span>
                  <span className={r.is_overdue ? 'date-overdue' : 'text-sm muted'}>
                    {r.is_overdue
                      ? t('tracking.overdueBy', { count: Math.abs(r.days_until) })
                      : r.days_until === 0
                        ? t('tracking.dueToday')
                        : `${formatDate(`${r.due_date}T00:00:00`)} · ${t('tracking.inDays', { count: r.days_until })}`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="quick-row">
        <Link to="/analyze?source=paste" className="quick-card card card-pad">
          <span className="qc-ic"><FilePlus2 size={18} /></span>
          <div><strong>{t('dashboard.quickAnalyzeTitle')}</strong><p>{t('dashboard.quickAnalyzeBody')}</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <Link to="/compare" className="quick-card card card-pad">
          <span className="qc-ic"><Layers size={18} /></span>
          <div><strong>{t('dashboard.quickCompareTitle')}</strong><p>{t('dashboard.quickCompareBody')}</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
        <Link to="/contracts" className="quick-card card card-pad">
          <span className="qc-ic"><MessageCircleQuestion size={18} /></span>
          <div><strong>{t('dashboard.quickAskTitle')}</strong><p>{t('dashboard.quickAskBody')}</p></div>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>

      <div className="row-spread mb-3 mt-5">
        <h2 style={{ margin: 0 }}>{t('dashboard.recentContracts')}</h2>
        {contracts && contracts.length > 0 && (
          <Link to="/contracts" className="text-sm">{t('dashboard.viewAll')} <ArrowRight size={13} style={{ verticalAlign: -1 }} /></Link>
        )}
      </div>

      {contractsLoading && !contracts ? (
        <Card pad><SkeletonLines lines={4} /></Card>
      ) : contractsError && !contracts ? (
        <Card pad>
          <p className="muted">{contractsError}</p>
          <button className="btn btn-secondary btn-sm" onClick={retryContracts}>{t('common.tryAgain')}</button>
        </Card>
      ) : !contracts || contracts.length === 0 ? (
        <Card>
          <EmptyState
            icon={<FolderOpen size={26} />}
            title={t('dashboard.noContractsYet')}
            description={t('dashboard.noContractsYetBody')}
            action={
              <Link to="/analyze" className="btn btn-primary">{t('dashboard.analyzeFirst')}</Link>
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
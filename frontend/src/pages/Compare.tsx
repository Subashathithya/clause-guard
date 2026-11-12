import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftRight, CheckCircle2, Layers } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { CompareResult, Contract, DriftResult, VersionChange } from '../types';
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui/data';
import { Alert, Button, Select, SkeletonLines } from '../components/ui/primitives';
import { attentionOf } from '../lib/format';
import { useI18n } from '../i18n/I18nProvider';

/**
 * Backend narratives are helpful when they are real prose, but a failed
 * generation can return a technical error string. Never show that to users.
 */
function consumerNarrative(text?: string | null): string {
  if (!text) return '';
  const value = text.trim();
  if (!value) return '';
  if (/\b(error|exception|traceback|stack trace|llm|semantic|similarity score|prompt)\b/i.test(value)) {
    return '';
  }
  return value;
}

export default function ComparePage() {
  const { t, formatDate } = useI18n();
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
      setResultError(t('compare.chooseTwo'));
      return;
    }
    if (aId === bId) {
      setResultError(t('compare.sameDocument'));
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
      setResultError(err instanceof Error ? err.message : t('compare.failed'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title={t('compare.title')}
        lead={t('compare.lead')}
      />

      {loading && !contracts ? (
        <Card pad><SkeletonLines lines={5} /></Card>
      ) : error && !contracts ? (
        <ErrorState message={error} onRetry={retry} />
      ) : !contracts || contracts.length < 2 ? (
        <Card>
          <EmptyState
            icon={<Layers size={26} />}
            title={
              contracts && contracts.length === 1
                ? t('compare.needTwo')
                : t('compare.noneYet')
            }
            description={t('compare.analyzeTwo')}
            action={<Link to="/analyze" className="btn btn-primary">{t('compare.analyzeContract')}</Link>}
          />
        </Card>
      ) : (
        <>
          <div className="card card-pad">
            <div className="comp-selects">
              <div style={{ flex: 1 }}>
                <label className="field-label mb-2" htmlFor="cmp-a">{t('compare.firstVersion')}</label>
                <Select id="cmp-a" options={options} value={aId} onChange={(e) => setAId(e.target.value)} aria-label={t('compare.firstVersionShort')} />
                {selA && <p className="comp-date">{t('compare.analyzedOn', { date: formatDate(selA.created_at) })}</p>}
              </div>
              <span className="comp-arrow" aria-hidden="true">→</span>
              <div style={{ flex: 1 }}>
                <label className="field-label mb-2" htmlFor="cmp-b">{t('compare.secondVersion')}</label>
                <Select id="cmp-b" options={options} value={bId} onChange={(e) => setBId(e.target.value)} aria-label={t('compare.secondVersionShort')} />
                {selB && <p className="comp-date">{t('compare.analyzedOn', { date: formatDate(selB.created_at) })}</p>}
              </div>
            </div>

            <div className="row mt-4" style={{ gap: 10, flexWrap: 'wrap' }}>
              <Button onClick={() => run('compare')} loading={busy === 'compare'}>
                <Layers size={16} /> {t('compare.compareSideBySide')}
              </Button>
              <Button variant="secondary" onClick={() => run('drift')} loading={busy === 'drift'}>
                <ArrowLeftRight size={16} /> {t('compare.seeWhatChanged')}
              </Button>
            </div>
            {resultError && (
              <div className="mt-3">
                <Alert tone="danger" title={t('compare.couldNotCompare')}>{resultError}</Alert>
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
  const { t, categoryLabel } = useI18n();
  const narrative = consumerNarrative(compare.narrative);
  return (
    <div className="card card-pad mt-4">
      <h2 className="card-title">{t('compare.overview')}</h2>
      <p className="text-sm muted">{t('compare.avgScores')}</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('compare.topic')}</th>
              {compare.documents.map((d) => (
                <th key={d.document_id}>{d.document_name}</th>
              ))}
              <th>{t('compare.moreEven')}</th>
            </tr>
          </thead>
          <tbody>
            {compare.category_matrix.map((row) => (
              <tr key={row.category}>
                <td>{categoryLabel(row.category)}</td>
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
      {narrative && (
        <div className="alert alert-info mt-4">
          <div>
            <strong className="alert-title">{t('compare.whatThisMeans')}</strong>
            <div className="mt-2">{narrative}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function DirectionBadge({ dir }: { dir: string }) {
  const { t } = useI18n();
  if (dir === 'improved') return <span className="cc-tag green">{t('compare.improved')}</span>;
  if (dir === 'worsened') return <span className="cc-tag red">{t('compare.warrantsAttention')}</span>;
  if (dir === 'stable') return <span className="cc-tag">{t('compare.unchanged')}</span>;
  if (dir === 'added') return <span className="cc-tag amber">{t('compare.added')}</span>;
  if (dir === 'removed') return <span className="cc-tag">{t('compare.removed')}</span>;
  return <span className="cc-tag">{dir}</span>;
}

function DriftTable({ drift }: { drift: DriftResult }) {
  const { t, categoryLabel } = useI18n();
  return (
    <div className="card card-pad mt-4">
      <div className="card-header">
        <div>
          <h2 className="card-title">
            {t('compare.whatChanged', {
              old: drift.old.document_name,
              new: drift.new.document_name,
            })}
          </h2>
          <p className="text-sm muted mb-0">
            Overall, the newer version{' '}
            {drift.overall_direction === 'improved'
              ? t('compare.readsFairer')
              : drift.overall_direction === 'worsened'
                ? t('compare.deservesMore')
                : t('compare.inLine')}
          </p>
        </div>
        <DirectionBadge dir={drift.overall_direction} />
      </div>

      <VersionChanges comparison={drift.version_comparison} />

      {(drift.changes || []).length > 0 && (
        <>
          <h3 className="change-heading mt-5">{t('compare.attentionList')}</h3>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('compare.topic')}</th>
                  <th>{t('compare.before')}</th>
                  <th>{t('compare.after')}</th>
                  <th>{t('compare.change')}</th>
                </tr>
              </thead>
              <tbody>
                {drift.changes.map((c) => (
                  <tr key={c.category}>
                    <td>{categoryLabel(c.category)}</td>
                    <td>{c.before ?? '—'}</td>
                    <td>{c.after ?? '—'}</td>
                    <td><DirectionBadge dir={c.direction} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs faint mt-4 mb-0">{t('compare.higherNumber')}</p>
        </>
      )}
    </div>
  );
}

const CHANGE_COPY: Record<string, { topic: string; note: string; tone: string }> = {
  modified: { topic: 'compare.changeModifiedTopic', note: 'compare.changeModifiedNote', tone: 'rep-watch' },
  added: { topic: 'compare.changeAddedTopic', note: 'compare.changeAddedNote', tone: 'rep-watch' },
  removed: { topic: 'compare.changeRemovedTopic', note: 'compare.changeRemovedNote', tone: 'rep-note' },
  ambiguous: { topic: 'compare.changeAmbiguousTopic', note: 'compare.changeAmbiguousNote', tone: 'rep-fix' },
};

function changeCopy(change: VersionChange, t: (key: string) => string) {
  const copy = CHANGE_COPY[change.change_type] || {
    topic: 'compare.changeDefaultTopic',
    note: 'compare.changeDefaultNote',
    tone: 'rep-watch',
  };
  return { topic: t(copy.topic), note: t(copy.note), tone: copy.tone };
}

function VersionChanges({ comparison }: { comparison?: DriftResult['version_comparison'] }) {
  const { t, categoryLabel, attentionLabel } = useI18n();
  if (!comparison) return null;

  const changes = (comparison.changes || []).filter((c) => c.change_type !== 'unchanged');
  const increased = (comparison.attention_evolution || []).filter(
    (a) => a.evolution === 'increased'
  );
  const decreased = (comparison.attention_evolution || []).filter(
    (a) => a.evolution === 'decreased'
  );

  return (
    <div className="change-section">
      <h3 className="change-heading">
        {t('compare.wordingChangedTitle')}
        {changes.length > 0 && (
          <>
            {' '}
            <span className="count-pill">
              {changes.length === 1
                ? t('compare.changeCountOne', { count: changes.length })
                : t('compare.changeCountMany', { count: changes.length })}
            </span>
          </>
        )}
      </h3>

      {comparison.clauses_a > 0 && comparison.clauses_b > 0 && (
        <p className="text-sm muted">
          {t('compare.compared', { a: comparison.clauses_a, b: comparison.clauses_b })}
        </p>
      )}

      {changes.length === 0 ? (
        <p className="change-empty">
          <CheckCircle2 size={15} style={{ verticalAlign: -2, marginRight: 6, color: 'var(--success-text)' }} />
          {t('compare.noChanges')}
        </p>
      ) : (
        <ul className="change-list">
          {changes.map((change) => {
            const copy = changeCopy(change, t);
            const hasValues = Boolean(change.previous_value || change.current_value);
            return (
              <li key={`${change.clause_id_a}-${change.clause_id_b}-${change.category}`} className="change-item">
                <span className={['report-badge', copy.tone].join(' ')}>{copy.topic}</span>
                <div className="change-main">
                  <span className="change-topic">{categoryLabel(change.category)}</span>
                  <p className="change-note">
                    {change.change_type === 'modified' && hasValues
                      ? t('compare.wordingChanged')
                      : copy.note}
                  </p>
                  {hasValues && (
                    <div className="change-values">
                      {change.previous_value && <span className="change-value">{change.previous_value}</span>}
                      {change.previous_value && change.current_value && <span className="change-arrow" aria-hidden="true">→</span>}
                      {change.current_value && <span className="change-value new">{change.current_value}</span>}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {increased.length > 0 && (
        <>
          <h3 className="change-heading mt-4">{t('compare.needsMoreAttention')}</h3>
          <ul className="change-list">
            {increased.map((item) => (
              <li key={`${item.clause_id}-${item.category}`} className="change-item">
                <span className="report-badge rep-watch">{t('compare.moreAttention')}</span>
                <div className="change-main">
                  <span className="change-topic">{categoryLabel(item.category)}</span>
                  <p className="change-note">
                    {t('compare.wasNow', {
                      before: attentionLabel(attentionOf(item.previous_attention)),
                      after: attentionLabel(attentionOf(item.current_attention)),
                    })}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {decreased.length > 0 && (
        <>
          <h3 className="change-heading mt-4">{t('compare.needsLessAttention')}</h3>
          <ul className="change-list">
            {decreased.map((item) => (
              <li key={`${item.clause_id}-${item.category}`} className="change-item">
                <span className="report-badge rep-fix">{t('compare.lessAttention')}</span>
                <div className="change-main">
                  <span className="change-topic">{categoryLabel(item.category)}</span>
                  <p className="change-note">
                    {t('compare.wasNow', {
                      before: attentionLabel(attentionOf(item.previous_attention)),
                      after: attentionLabel(attentionOf(item.current_attention)),
                    })}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

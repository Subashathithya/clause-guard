import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, MessageCircleQuestion, Search, Star } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { AnalysisResult, AttentionLevel, Bookmark, ChatMessage, Clause } from '../types';
import { downloadAnalysisReport } from '../lib/report';
import { Card, EmptyState, ErrorState, PageHeader, Tabs } from '../components/ui/data';
import { Badge, Select, SkeletonLines, Tag } from '../components/ui/primitives';
import { Modal } from '../components/ui/overlays';
import { AttentionBadge } from '../components/contract/AttentionBadge';
import { ClauseDetail } from '../components/contract/ClauseDetail';
import { RelationshipList } from '../components/contract/RelationshipList';
import {
  ChecklistTab,
  DatesTab,
  SectionBookmarkButton,
} from '../components/contract/Tracking';
import { ChatThread } from '../components/chat/ChatThread';
import { relationshipsFromAnalysis, type Relationship } from '../lib/clauseRelations';
import { attentionOf, compactInr, inr } from '../lib/format';
import { useI18n } from '../i18n/I18nProvider';

type WorkspaceTab =
  | 'overview'
  | 'sections'
  | 'attention'
  | 'connections'
  | 'dates'
  | 'checklist'
  | 'chat';

const CATEGORIES = [
  'Payment',
  'Auto-Renewal',
  'Liability',
  'Data Privacy',
  'Dispute',
  'Warranty',
  'Other',
];

export default function ContractWorkspace() {
  const { contractId } = useParams<{ contractId: string }>();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { value: analysis, loading, error, retry } = useAsync<AnalysisResult | null>(
    () => (contractId ? api.getAnalysis(contractId) : Promise.resolve(null)),
    [contractId]
  );

  const [tab, setTab] = useState<WorkspaceTab>('overview');
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [attentionFilter, setAttentionFilter] = useState('all');
  const [attentionLevel, setAttentionLevel] = useState<AttentionLevel | 'all'>('all');
  const [relationship, setRelationship] = useState<Relationship | null>(null);
  const [showRelB, setShowRelB] = useState(false);
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [bookmarkedOnly, setBookmarkedOnly] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);

  const clauses = useMemo(() => analysis?.clauses || [], [analysis]);

  // Bookmarks are a small side list; a failure here should never block reading
  // the analysis, so errors are intentionally swallowed.
  useEffect(() => {
    if (!contractId) return;
    let alive = true;
    api
      .bookmarks(contractId)
      .then((rows) => {
        if (alive) setBookmarks(rows);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [contractId]);

  const bookmarkFor = (clauseId: string) =>
    bookmarks.find((b) => b.clause_index === clauseId) || null;

  const reloadBookmarks = () => {
    if (!contractId) return;
    api
      .bookmarks(contractId)
      .then(setBookmarks)
      .catch(() => undefined);
  };

  const selectedClause = useMemo(
    () => clauses.find((c) => c.clause_id === selectedClauseId) || null,
    [clauses, selectedClauseId]
  );

  // Sections tab filtering
  const visibleClauses = useMemo(() => {
    let rows = clauses;
    const q = search.trim().toLowerCase();
    if (q) rows = rows.filter((c) => c.text.toLowerCase().includes(q) || c.category.toLowerCase().includes(q));
    if (category !== 'all') rows = rows.filter((c) => c.category === category);
    if (attentionFilter === 'attention') rows = rows.filter((c) => c.risk_level !== 'green');
    if (attentionFilter === 'careful') rows = rows.filter((c) => c.risk_level === 'red');
    if (bookmarkedOnly) {
      rows = rows.filter((c) => bookmarks.some((b) => b.clause_index === c.clause_id));
    }
    return rows;
  }, [clauses, search, category, attentionFilter, bookmarkedOnly, bookmarks]);

  const importantClauses = useMemo(() => {
    let rows = clauses.filter((c) => c.risk_level !== 'green');
    if (attentionLevel !== 'all') {
      rows = rows.filter((c) => attentionOf(c.risk_level) === attentionLevel);
    }
    return rows.sort((a, b) => a.risk_level === b.risk_level ? 0 : a.risk_level === 'red' ? -1 : 1);
  }, [clauses, attentionLevel]);

  if (loading && !analysis) {
    return (
      <div>
        <PageHeader title="Loading your analysis…" crumb={[{ label: 'Contracts', to: '/contracts' }, { label: '…' }]} />
        <Card pad><SkeletonLines lines={8} /></Card>
      </div>
    );
  }

  if (error && !analysis) {
    return (
      <div>
        <PageHeader title={t('workspace.couldNotOpen')} crumb={[{ label: t('nav.contracts'), to: '/contracts' }]} />
        <ErrorState message={error} onRetry={retry} />
      </div>
    );
  }

  if (!analysis) return null;

  const downloadReport = async () => {
    setReportBusy(true);
    const id = contractId || analysis.document_id;
    let extras = {};
    if (id) {
      try {
        const [dates, checklist] = await Promise.all([
          api.contractDates(id),
          api.checklist(id),
        ]);
        extras = { dates, checklist };
      } catch {
        // Tracking data is additive; the core report still downloads without it.
      }
    }
    try {
      await downloadAnalysisReport(analysis, extras);
    } finally {
      setReportBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={analysis.document_name}
        lead={
          analysis.source === 'upload'
            ? t('workspace.uploadedDoc')
            : t('workspace.pastedDoc')
        }
        crumb={[{ label: t('nav.contracts'), to: '/contracts' }, { label: analysis.document_name }]}
        actions={
          <div className="row-inline" style={{ gap: 8 }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => void downloadReport()}
              disabled={reportBusy}
            >
              <Download size={14} /> {reportBusy ? t('workspace.preparing') : t('workspace.downloadReport')}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/contracts')}>
              <ArrowLeft size={14} /> {t('workspace.backToContracts')}
            </button>
          </div>
        }
      />

      <Tabs
        value={tab}
        onChange={(t) => setTab(t as WorkspaceTab)}
        tabs={[
          { id: 'overview', label: t('workspace.overview') },
          { id: 'sections', label: t('workspace.sections', { count: clauses.length }) },
          { id: 'attention', label: t('workspace.reviewCarefully') },
          { id: 'connections', label: t('workspace.connections') },
          { id: 'dates', label: t('workspace.datesReminders') },
          { id: 'checklist', label: t('workspace.checklist') },
          { id: 'chat', label: t('workspace.askAboutThis') },
        ]}
      />

      {tab === 'overview' && <Overview analysis={analysis} onOpenSections={() => setTab('sections')} onOpenChat={() => setTab('chat')} />}
      {tab === 'sections' && (
        <SectionsExplorer
          clauses={visibleClauses}
          allClauses={clauses}
          search={search}
          onSearchChange={setSearch}
          category={category}
          onCategoryChange={setCategory}
          attentionFilter={attentionFilter}
          onAttentionFilterChange={setAttentionFilter}
          bookmarkedOnly={bookmarkedOnly}
          onBookmarkedOnlyChange={setBookmarkedOnly}
          bookmarkCount={bookmarks.length}
          total={clauses.length}
          selected={selectedClause}
          onSelect={setSelectedClauseId}
          contractId={contractId || analysis.document_id || ''}
          bookmarkFor={bookmarkFor}
          onBookmarkChanged={() => {
            reloadBookmarks();
            setBookmarkedOnly(false);
          }}
        />
      )}
      {tab === 'attention' && (
        <ImportantAreas clauses={importantClauses} allClauses={clauses} level={attentionLevel} onLevelChange={setAttentionLevel} onSelect={setSelectedClauseId} onOpenSections={() => setTab('sections')} />
      )}
      {tab === 'connections' && <Connections analysis={analysis} onPick={setRelationship} />}
      {tab === 'dates' && (
        <DatesTab
          contractId={contractId || analysis.document_id || ''}
          analysis={analysis}
        />
      )}
      {tab === 'checklist' && (
        <ChecklistTab
          contractId={contractId || analysis.document_id || ''}
          onOpenClause={setSelectedClauseId}
        />
      )}
      {tab === 'chat' && <WorkspaceChat analysis={analysis} />}

      <Modal
        open={!!selectedClause}
        onClose={() => setSelectedClauseId(null)}
        title={selectedClause ? t('clause.sectionOf', { category: selectedClause.category }) : ''}
        size="lg"
      >
        {selectedClause && (
          <div>
            <div className="row-inline mb-3" style={{ justifyContent: 'flex-end' }}>
              <SectionBookmarkButton
                contractId={contractId || analysis.document_id || ''}
                clauseIndex={selectedClause.clause_id}
                bookmark={bookmarkFor(selectedClause.clause_id)}
                onChanged={reloadBookmarks}
              />
            </div>
            <ClauseDetail clause={selectedClause} allClauses={clauses} onJump={setSelectedClauseId} />
          </div>
        )}
      </Modal>

      <Modal
        open={!!relationship}
        onClose={() => { setRelationship(null); setShowRelB(false); }}
        title={t('workspace.connectedSections')}
        size="lg"
      >
        {relationship && (
          <div>
            <div className="rel-pair mb-4" style={{ justifyContent: 'center' }}>
              <Tag>{showRelB ? relationship.b.category : relationship.a.category}</Tag>
              <span className="rel-arrow" aria-hidden="true">↔</span>
              <Tag>{showRelB ? relationship.a.category : relationship.b.category}</Tag>
            </div>
            <p className="text-sm muted" style={{ textAlign: 'center', marginTop: -8 }}>{relationship.reason}</p>
            <ClauseDetail
              clause={showRelB ? relationship.b : relationship.a}
              allClauses={clauses}
              onJump={(id) => {
                setRelationship(null);
                setShowRelB(false);
                setSelectedClauseId(id);
              }}
            />
            <div className="mt-3 row" style={{ justifyContent: 'center', gap: 10 }}>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowRelB((v) => !v)}>
                {t('workspace.viewInstead', {
                  category: showRelB ? relationship.a.category : relationship.b.category,
                })}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ================================================================ Overview */
function Overview({
  analysis,
  onOpenSections,
  onOpenChat,
}: {
  analysis: AnalysisResult;
  onOpenSections: () => void;
  onOpenChat: () => void;
}) {
  const { t } = useI18n();
  const clauses = analysis.clauses || [];
  const risk = analysis.risk_summary;
  const attention = clauses.filter((c) => c.risk_level !== 'green');
  const top = analysis.summary?.top_priorities || [];
  const crossIssues = analysis.cross_clause?.inconsistencies || [];
  const evidence = analysis.evidence;

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="card-header">
          <h2 className="card-title">{t('workspace.atAGlance')}</h2>
          <Badge tone="neutral">{t('workspace.readyToRead')}</Badge>
        </div>
        <div className="ov-grid">
          <div className="ov-item"><span className="ov-num">{clauses.length}</span><span className="ov-lab">{t('workspace.sectionsFound', { count: '' }).replace(/^\d+\s*/, '')}</span></div>
          <div className="ov-item"><span className="ov-num att-red">{risk.red_count}</span><span className="ov-lab">{t('workspace.levelHigh')}</span></div>
          <div className="ov-item"><span className="ov-num att-amber">{risk.yellow_count}</span><span className="ov-lab">{t('workspace.levelMid')}</span></div>
          <div className="ov-item"><span className="ov-num att-green">{risk.green_count}</span><span className="ov-lab">{t('workspace.levelLow')}</span></div>
          <div className="ov-item"><span className="ov-num ov-money">{compactInr(risk.total_financial_exposure_inr)}</span><span className="ov-lab">{t('workspace.mentionedInMoney', { amount: '' }).replace(/^\s*/, '')}</span></div>
        </div>
        {evidence && evidence.total > 0 && evidence.reference_backed > 0 && (
          <p className="text-sm muted mb-0 mt-3">
            {t('workspace.referenceCheckLine', {
              done: evidence.reference_backed,
              total: evidence.total,
            })}
          </p>
        )}
      </div>

      {crossIssues.length > 0 && (
        <div className="alert alert-warning">
          <div>
            <strong className="alert-title">
              {crossIssues.length === 1
                ? t('workspace.twoSectionsDisagree')
                : t('workspace.crossPairs', { count: crossIssues.length })}
            </strong>
            <div className="mt-2 stack" style={{ gap: 6 }}>
              {crossIssues.slice(0, 3).map((issue) => (
                <div key={`${issue.source_clause_id}-${issue.target_clause_id}-${issue.kind}`}>
                  {t('workspace.differentDetails', { kind: issue.kind || t('workspace.all') })}
                  {issue.value_a && issue.value_b ? `: ${issue.value_a} vs ${issue.value_b}` : ''}.{' '}
                  {t('workspace.worthReadingTogether')}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {analysis.summary?.recommendation && (
        <div className="card card-pad">
          <h2 className="card-title">{t('workspace.summary')}</h2>
          <p style={{ marginBottom: 0 }}>{analysis.summary.recommendation}</p>
          {top.length > 0 && (
            <>
              <h3 className="mt-4">{t('workspace.worthCheckingFirst')}</h3>
              <ol className="top-priorities">
                {top.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}

      {attention.length > 0 && (
        <div className="card card-pad">
          <div className="card-header">
            <h2 className="card-title">{t('workspace.areasAttention')}</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenSections}>{t('workspace.viewAllSections')}</button>
          </div>
          <div className="stack">
            {attention.slice(0, 4).map((c) => (
              <AttentionRow key={c.clause_id} clause={c} />
            ))}
          </div>
        </div>
      )}

      <div className="row" style={{ justifyContent: 'space-between', gap: 10 }}>
        <button type="button" className="btn btn-primary btn-lg" onClick={onOpenSections}>
          {t('workspace.readSections')}
        </button>
        <button type="button" className="btn btn-secondary btn-lg" onClick={onOpenChat}>
          <MessageCircleQuestion size={17} /> {t('workspace.askAboutDoc')}
        </button>
      </div>

      <div className="alert alert-info">
        <div>
          <strong className="alert-title">{t('workspace.noteOnAnalysis')}</strong>
          <div className="mt-2">{t('footer.disclaimer')}</div>
        </div>
      </div>
    </div>
  );
}

function AttentionRow({ clause }: { clause: Clause }) {
  return (
    <div className="att-row">
      <AttentionBadge level={clause.risk_level} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <strong className="text-sm">{clause.category}</strong>
        <p className="text-sm muted" style={{ margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {clause.text}
        </p>
      </div>
      {clause.financial_impact_inr ? (
        <Tag>{inr(clause.financial_impact_inr)}</Tag>
      ) : null}
    </div>
  );
}

/* ================================================================ Sections */
function SectionsExplorer({
  clauses,
  allClauses,
  search,
  onSearchChange,
  category,
  onCategoryChange,
  attentionFilter,
  onAttentionFilterChange,
  bookmarkedOnly,
  onBookmarkedOnlyChange,
  bookmarkCount,
  total,
  selected,
  onSelect,
  contractId,
  bookmarkFor,
  onBookmarkChanged,
}: {
  clauses: Clause[];
  allClauses: Clause[];
  search: string;
  onSearchChange: (v: string) => void;
  category: string;
  onCategoryChange: (v: string) => void;
  attentionFilter: string;
  onAttentionFilterChange: (v: string) => void;
  bookmarkedOnly: boolean;
  onBookmarkedOnlyChange: (v: boolean) => void;
  bookmarkCount: number;
  total: number;
  selected: Clause | null;
  onSelect: (id: string) => void;
  contractId: string;
  bookmarkFor: (clauseId: string) => Bookmark | null;
  onBookmarkChanged: () => void;
}) {
  const { t, categoryLabel } = useI18n();
  return (
    <div className="sections-layout">
      <aside className="sections-list card">
        <div className="search-wrap mb-3">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            className="search-input"
            placeholder={t('workspace.searchSections')}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label={t('workspace.searchSectionsLabel')}
          />
        </div>
        <div className="row" style={{ gap: 8 }} aria-label={t('workspace.sectionFilters')}>
          <Select
            options={[
              { value: 'all', label: t('workspace.allTopics') },
              ...CATEGORIES.map((c) => ({ value: c, label: categoryLabel(c) })),
            ]}
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            aria-label={t('workspace.filterByTopic')}
          />
          <Select
            options={[
              { value: 'all', label: t('workspace.allLevels') },
              { value: 'attention', label: t('workspace.toReview') },
              { value: 'careful', label: t('workspace.levelHigh') },
            ]}
            value={attentionFilter}
            onChange={(e) => onAttentionFilterChange(e.target.value)}
            aria-label={t('workspace.filterByLevel')}
          />
        </div>
        <p className="text-xs faint mt-3">{t('workspace.countShown', { shown: clauses.length, total })}</p>
        <button
          type="button"
          className={['btn btn-sm', bookmarkedOnly ? 'btn-primary' : 'btn-secondary'].join(' ')}
          style={{ width: '100%', marginBottom: 'var(--s3)' }}
          onClick={() => onBookmarkedOnlyChange(!bookmarkedOnly)}
          aria-pressed={bookmarkedOnly}
          disabled={bookmarkCount === 0 && !bookmarkedOnly}
        >
          <Star size={14} fill={bookmarkedOnly ? 'currentColor' : 'none'} />
          {t('workspace.savedSections', { count: bookmarkCount })}
        </button>
        <div className="sec-list">
          {clauses.map((c, i) => (
            <button
              key={c.clause_id}
              type="button"
              className={['sec-item', selected?.clause_id === c.clause_id ? 'sec-item-on' : ''].filter(Boolean).join(' ')}
              onClick={() => onSelect(c.clause_id)}
              aria-pressed={selected?.clause_id === c.clause_id}
            >
              <span className="sec-num">#{i + 1}</span>
              <span className="sec-body">
                <span className="sec-title">{c.category}</span>
                <span className="sec-preview">{c.text}</span>
              </span>
              {bookmarkFor(c.clause_id) && (
                <Star size={13} className="sec-star" fill="currentColor" aria-label={t('workspace.savedSection')} />
              )}
              <AttentionBadge level={c.risk_level} size="sm" />
            </button>
          ))}
          {clauses.length === 0 && (
            <p className="text-sm muted" style={{ padding: '0 var(--s4)' }}>
              {bookmarkedOnly ? t('workspace.noSavedYet') : t('workspace.noFilterMatch')}
            </p>
          )}
        </div>
      </aside>

      <div className="sections-detail">
        {selected ? (
          <div>
            <div className="row-inline mb-3" style={{ justifyContent: 'flex-end' }}>
              <SectionBookmarkButton
                contractId={contractId}
                clauseIndex={selected.clause_id}
                bookmark={bookmarkFor(selected.clause_id)}
                onChanged={onBookmarkChanged}
              />
            </div>
            <ClauseDetail clause={selected} allClauses={allClauses} onJump={onSelect} />
          </div>
        ) : (
          <Card>
            <EmptyState
              title={t('workspace.chooseSection')}
              description={t('workspace.chooseSectionBody')}
            />
          </Card>
        )}
      </div>
    </div>
  );
}

/* ================================================================ Important areas */
function ImportantAreas({
  clauses,
  allClauses,
  level,
  onLevelChange,
  onSelect,
  onOpenSections,
}: {
  clauses: Clause[];
  allClauses: Clause[];
  level: AttentionLevel | 'all';
  onLevelChange: (v: AttentionLevel | 'all') => void;
  onSelect: (id: string) => void;
  onOpenSections: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="stack">
      <div className="card card-pad row-spread">
        <p className="text-sm muted mb-0" style={{ maxWidth: 520 }}>
          {t('workspace.attentionGroups')}
        </p>
        <div className="row" style={{ gap: 8 }} aria-label={t('workspace.filterByReview')}>
          {(['all', 'high', 'moderate'] as const).map((lv) => (
            <button
              key={lv}
              type="button"
              className={['btn btn-sm', level === lv ? 'btn-primary' : 'btn-secondary'].join(' ')}
              onClick={() => onLevelChange(lv)}
              aria-pressed={level === lv}
            >
              {lv === 'all'
                ? t('workspace.all')
                : lv === 'high'
                  ? t('workspace.levelHigh')
                  : t('workspace.levelMid')}
            </button>
          ))}
        </div>
      </div>

      {clauses.length === 0 ? (
        <Card>
          <EmptyState
            title={level === 'all' ? t('workspace.nothingToFlag') : t('workspace.noSectionsAtLevel')}
            description={t('workspace.attentionEmpty')}
            action={<button type="button" className="btn btn-secondary" onClick={onOpenSections}>{t('workspace.browseAllSections')}</button>}
          />
        </Card>
      ) : (
        <div className="card">
          {clauses.map((c, i) => (
            <button
              key={c.clause_id}
              type="button"
              className="att-card"
              onClick={() => onSelect(c.clause_id)}
              style={{ width: '100%', textAlign: 'left', border: 'none', background: 'none', cursor: 'pointer' }}
            >
              <div className="att-card-top">
                <span className="sec-num">#{i + 1}</span>
                <strong>{c.category}</strong>
                <span className="ml-auto"><AttentionBadge level={c.risk_level} /></span>
              </div>
              <p className="text-sm muted mb-0">{c.explanation}</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ================================================================ Connections */
function Connections({
  analysis,
  onPick,
}: {
  analysis: AnalysisResult;
  onPick: (rel: Relationship) => void;
}) {
  const { t } = useI18n();
  const rels = useMemo(() => relationshipsFromAnalysis(analysis), [analysis]);
  const issues = rels.filter((rel) => rel.kind === 'inconsistency').length;
  return (
    <div>
      <Card pad className="mb-4">
        <h2 className="card-title">{t('workspace.howConnect')}</h2>
        <p className="text-sm muted mb-0">{t('workspace.connectionsBody')}</p>
        {issues > 0 && (
          <p className="text-sm mt-3 mb-0" style={{ color: 'var(--warning-text)' }}>
            {issues === 1
              ? t('workspace.onePairDiffers')
              : t('workspace.pairsDiffer', { count: issues })}
          </p>
        )}
      </Card>
      <RelationshipList relationships={rels} onSelect={onPick} />
    </div>
  );
}

/* ================================================================ Chat */
function WorkspaceChat({ analysis }: { analysis: AnalysisResult }) {
  const { t } = useI18n();
  const id = analysis.document_id;
  const getAnswer = (question: string, history: ChatMessage[]) =>
    api.chat(question, id ? [id] : [], history);
  return (
    <ChatThread getAnswer={getAnswer} contextLabel={t('workspace.chatContext')} />
  );
}
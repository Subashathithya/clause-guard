import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Download, MessageCircleQuestion, Search } from 'lucide-react';
import { api } from '../api';
import { useAsync } from '../hooks';
import type { AnalysisResult, AttentionLevel, ChatMessage, Clause } from '../types';
import { downloadAnalysisReport } from '../lib/report';
import { Card, EmptyState, ErrorState, PageHeader, Tabs } from '../components/ui/data';
import { Badge, Select, SkeletonLines, Tag } from '../components/ui/primitives';
import { Modal } from '../components/ui/overlays';
import { AttentionBadge } from '../components/contract/AttentionBadge';
import { ClauseDetail } from '../components/contract/ClauseDetail';
import { RelationshipList } from '../components/contract/RelationshipList';
import { ChatThread } from '../components/chat/ChatThread';
import { deriveRelationships, type Relationship } from '../lib/clauseRelations';
import { attentionOf, categoryLabel, compactInr, inr } from '../lib/format';

type WorkspaceTab = 'overview' | 'sections' | 'attention' | 'connections' | 'chat';

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

  const clauses = useMemo(() => analysis?.clauses || [], [analysis]);

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
    return rows;
  }, [clauses, search, category, attentionFilter]);

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
        <PageHeader title="Couldn't open this analysis" crumb={[{ label: 'Contracts', to: '/contracts' }]} />
        <ErrorState message={error} onRetry={retry} />
      </div>
    );
  }

  if (!analysis) return null;

  return (
    <div>
      <PageHeader
        title={analysis.document_name}
        lead={
          analysis.source === 'upload'
            ? 'Uploaded document · analysed with ClauseGuard'
            : 'Pasted text · analysed with ClauseGuard'
        }
        crumb={[{ label: 'Contracts', to: '/contracts' }, { label: analysis.document_name }]}
        actions={
          <div className="row-inline" style={{ gap: 8 }}>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => downloadAnalysisReport(analysis)}
            >
              <Download size={14} /> Download report
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate('/contracts')}>
              <ArrowLeft size={14} /> Back to contracts
            </button>
          </div>
        }
      />

      <Tabs
        value={tab}
        onChange={(t) => setTab(t as WorkspaceTab)}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'sections', label: `Sections (${clauses.length})` },
          { id: 'attention', label: 'Review carefully' },
          { id: 'connections', label: 'Connections' },
          { id: 'chat', label: 'Ask about this' },
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
          total={clauses.length}
          selected={selectedClause}
          onSelect={setSelectedClauseId}
        />
      )}
      {tab === 'attention' && (
        <ImportantAreas clauses={importantClauses} allClauses={clauses} level={attentionLevel} onLevelChange={setAttentionLevel} onSelect={setSelectedClauseId} onOpenSections={() => setTab('sections')} />
      )}
      {tab === 'connections' && <Connections analysis={analysis} onPick={setRelationship} />}
      {tab === 'chat' && <WorkspaceChat analysis={analysis} />}

      <Modal
        open={!!selectedClause}
        onClose={() => setSelectedClauseId(null)}
        title={selectedClause ? `Section ${selectedClause.category}` : ''}
        size="lg"
      >
        {selectedClause && (
          <ClauseDetail clause={selectedClause} allClauses={clauses} onJump={setSelectedClauseId} />
        )}
      </Modal>

      <Modal
        open={!!relationship}
        onClose={() => { setRelationship(null); setShowRelB(false); }}
        title="Connected sections"
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
                View {showRelB ? relationship.a.category : relationship.b.category} instead
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
  const clauses = analysis.clauses || [];
  const risk = analysis.risk_summary;
  const attention = clauses.filter((c) => c.risk_level !== 'green');
  const top = analysis.summary?.top_priorities || [];

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="card-header">
          <h3 className="card-title">At a glance</h3>
          <Badge tone="neutral">Ready to read</Badge>
        </div>
        <div className="ov-grid">
          <div className="ov-item"><span className="ov-num">{clauses.length}</span><span className="ov-lab">sections found</span></div>
          <div className="ov-item"><span className="ov-num att-red">{risk.red_count}</span><span className="ov-lab">review carefully</span></div>
          <div className="ov-item"><span className="ov-num att-amber">{risk.yellow_count}</span><span className="ov-lab">worth a look</span></div>
          <div className="ov-item"><span className="ov-num att-green">{risk.green_count}</span><span className="ov-lab">look fine</span></div>
          <div className="ov-item"><span className="ov-num ov-money">{compactInr(risk.total_financial_exposure_inr)}</span><span className="ov-lab">mentioned in money terms</span></div>
        </div>
      </div>

      {analysis.summary?.recommendation && (
        <div className="card card-pad">
          <h3 className="card-title">Summary</h3>
          <p style={{ marginBottom: 0 }}>{analysis.summary.recommendation}</p>
          {top.length > 0 && (
            <>
              <h4 className="mt-4">Things worth checking first</h4>
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
            <h3 className="card-title">Areas that may deserve attention</h3>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onOpenSections}>View all sections</button>
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
          Read the sections
        </button>
        <button type="button" className="btn btn-secondary btn-lg" onClick={onOpenChat}>
          <MessageCircleQuestion size={17} /> Ask about this document
        </button>
      </div>

      <div className="alert alert-info">
        <div>
          <strong className="alert-title">A note on this analysis</strong>
          <div className="mt-2">
            ClauseGuard provides AI-assisted contract understanding and is not legal advice. For anything
            important, please review with a qualified professional.
          </div>
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
  total,
  selected,
  onSelect,
}: {
  clauses: Clause[];
  allClauses: Clause[];
  search: string;
  onSearchChange: (v: string) => void;
  category: string;
  onCategoryChange: (v: string) => void;
  attentionFilter: string;
  onAttentionFilterChange: (v: string) => void;
  total: number;
  selected: Clause | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="sections-layout">
      <aside className="sections-list card">
        <div className="search-wrap mb-3">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            className="search-input"
            placeholder="Search sections…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search sections"
          />
        </div>
        <div className="row" style={{ gap: 8 }} aria-label="Section filters">
          <Select
            options={[{ value: 'all', label: 'All topics' }, ...CATEGORIES.map((c) => ({ value: c, label: categoryLabel(c) }))]}
            value={category}
            onChange={(e) => onCategoryChange(e.target.value)}
            aria-label="Filter by topic"
          />
          <Select
            options={[
              { value: 'all', label: 'All levels' },
              { value: 'attention', label: 'To review or check' },
              { value: 'careful', label: 'Review carefully' },
            ]}
            value={attentionFilter}
            onChange={(e) => onAttentionFilterChange(e.target.value)}
            aria-label="Filter by attention level"
          />
        </div>
        <p className="text-xs faint mt-3">{clauses.length} of {total} sections</p>
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
              <AttentionBadge level={c.risk_level} size="sm" />
            </button>
          ))}
          {clauses.length === 0 && (
            <p className="text-sm muted" style={{ padding: '0 var(--s4)' }}>
              No sections match those filters.
            </p>
          )}
        </div>
      </aside>

      <div className="sections-detail">
        {selected ? (
          <ClauseDetail clause={selected} allClauses={allClauses} onJump={onSelect} />
        ) : (
          <Card>
            <EmptyState
              title="Choose a section"
              description="Pick a section from the list to read its plain-English explanation."
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
  return (
    <div className="stack">
      <div className="card card-pad row-spread">
        <p className="text-sm muted mb-0" style={{ maxWidth: 520 }}>
          Sections that may deserve a closer look, grouped by how much attention they probably need.
        </p>
        <div className="row" style={{ gap: 8 }} aria-label="Filter by review level">
          {(['all', 'high', 'moderate'] as const).map((lv) => (
            <button
              key={lv}
              type="button"
              className={['btn btn-sm', level === lv ? 'btn-primary' : 'btn-secondary'].join(' ')}
              onClick={() => onLevelChange(lv)}
              aria-pressed={level === lv}
            >
              {lv === 'all' ? 'All' : lv === 'high' ? 'Review carefully' : 'Worth a look'}
            </button>
          ))}
        </div>
      </div>

      {clauses.length === 0 ? (
        <Card>
          <EmptyState
            title={level === 'all' ? 'Nothing to flag here' : `No sections at this level`}
            description="When a section needs attention it will show up here. You can always browse all sections below."
            action={<button type="button" className="btn btn-secondary" onClick={onOpenSections}>Browse all sections</button>}
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
  const rels = useMemo(() => deriveRelationships(analysis.clauses || []), [analysis]);
  return (
    <div>
      <Card pad className="mb-4">
        <h3 className="card-title">How sections connect</h3>
        <p className="text-sm muted mb-0">
          Some parts of a contract depend on each other — for example, how the deal can end usually affects
          what happens to payments. Connections are shown between actual sections of your document.
        </p>
      </Card>
      <RelationshipList relationships={rels} onSelect={onPick} />
    </div>
  );
}

/* ================================================================ Chat */
function WorkspaceChat({ analysis }: { analysis: AnalysisResult }) {
  const id = analysis.document_id;
  const getAnswer = (question: string, history: ChatMessage[]) =>
    api.chat(question, id ? [id] : [], history);
  return (
    <ChatThread getAnswer={getAnswer} contextLabel="the document you uploaded" />
  );
}
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  CalendarDays,
  Check,
  CircleAlert,
  ClipboardList,
  Pencil,
  Plus,
  Sparkles,
  Star,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../../api';
import type {
  AnalysisResult,
  Bookmark,
  ChecklistItem,
  ContractDate,
  DateKind,
  DateSuggestion,
} from '../../types';
import { Card, EmptyState } from '../ui/data';
import { Button, Tag } from '../ui/primitives';
import { useToast } from '../ui/overlays';
import { useI18n } from '../../i18n/I18nProvider';

const KIND_KEYS: Record<DateKind, string> = {
  payment: 'tracking.kindPayment',
  renewal: 'tracking.kindRenewal',
  notice: 'tracking.kindNotice',
  termination: 'tracking.kindTermination',
  other: 'tracking.kindOther',
};

const KIND_VALUES = Object.keys(KIND_KEYS) as DateKind[];



function relativeDays(days: number, t: (key: string, params?: Record<string, string | number>) => string): string {
  if (days < 0) return t('tracking.overdueBy', { count: Math.abs(days) });
  if (days === 0) return t('tracking.dueToday');
  return days === 1 ? t('tracking.inOneDay') : t('tracking.inDays', { count: days });
}

function reminderLine(
  row: ContractDate,
  t: (key: string, params?: Record<string, string | number>) => string,
  formatDate: (iso?: string | null) => string
): string {
  if (row.remind_days_before === 0) return t('tracking.reminderOn', { date: formatDate(row.due_date) });
  return t('tracking.reminderBefore', {
    date: formatDate(row.remind_on),
    count: row.remind_days_before,
  });
}

/* ============================================================ Dates & reminders */
export function DatesTab({
  contractId,
  analysis,
}: {
  contractId: string;
  analysis: AnalysisResult;
}) {
  const toast = useToast();
  const { t, formatDate } = useI18n();
  const [rows, setRows] = useState<ContractDate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [label, setLabel] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [kind, setKind] = useState<DateKind>('other');
  const [lead, setLead] = useState(7);
  const [notes, setNotes] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await api.contractDates(contractId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your dates.');
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  const resetForm = () => {
    setEditingId(null);
    setLabel('');
    setDueDate('');
    setKind('other');
    setLead(7);
    setNotes('');
  };

  const startEdit = (row: ContractDate) => {
    setEditingId(row.id);
    setLabel(row.label);
    setDueDate(row.due_date);
    setKind(row.kind);
    setLead(row.remind_days_before);
    setNotes(row.notes);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!label.trim() || !dueDate) {
      toast.push(t('tracking.whatIsIt'), 'error');
      return;
    }
    setSaving(true);
    try {
      const input = {
        label: label.trim(),
        due_date: dueDate,
        kind,
        notes: notes.trim(),
        remind_days_before: lead,
      };
      if (editingId) {
        const updated = await api.updateContractDate(contractId, editingId, input);
        setRows((prev) => sortDates(prev.map((r) => (r.id === editingId ? updated : r))));
        toast.push(t('tracking.dateUpdated'), 'success');
      } else {
        const created = await api.addContractDate(contractId, input);
        setRows((prev) => sortDates([...prev, created]));
        toast.push(t('tracking.dateSaved'), 'success');
      }
      resetForm();
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotSaveDate'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row: ContractDate) => {
    try {
      await api.deleteContractDate(contractId, row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      if (editingId === row.id) resetForm();
      toast.push(t('tracking.dateRemoved'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotRemoveDate'), 'error');
    }
  };

  const addSuggestion = async (suggestion: DateSuggestion) => {
    setSaving(true);
    try {
      const created = await api.addContractDate(contractId, {
        label: suggestion.kind === 'other' ? t('tracking.keyDate') : t(KIND_KEYS[suggestion.kind]),
        due_date: suggestion.date,
        kind: suggestion.kind,
        notes: suggestion.context ? t('tracking.fromContract', { text: suggestion.context.slice(0, 180) }) : '',
        remind_days_before: 7,
      });
      setRows((prev) => sortDates([...prev, created]));
      toast.push(t('tracking.addedFromContract'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotSaveDate'), 'error');
    } finally {
      setSaving(false);
    }
  };

  const suggestions = useMemo(
    () => (analysis.date_suggestions || []).filter(
      (s) => !rows.some((r) => r.due_date === s.date)
    ),
    [analysis.date_suggestions, rows]
  );

  return (
    <div className="stack">
      {suggestions.length > 0 && (
        <Card
          title={t('tracking.datesFound')}
          subtitle={t('tracking.datesFoundBody')}
        >
          <div className="stack">
            {suggestions.map((s) => (
              <div key={`${s.date}-${s.clause_index}-${s.label}`} className="suggest-row">
                <div className="suggest-date">
                  <CalendarDays size={15} aria-hidden="true" />
                  <span>{formatDate(s.date)}</span>
                </div>
                <div className="suggest-body">
                  <div className="row-inline" style={{ gap: 8 }}>
                    <Tag>{t(KIND_KEYS[s.kind])}</Tag>
                    {s.clause_index && <span className="text-xs faint">Section {s.clause_index}</span>}
                  </div>
                  {s.context && <p className="text-sm muted mb-0 mt-2">{s.context}</p>}
                </div>
                <Button size="sm" variant="secondary" onClick={() => void addSuggestion(s)} disabled={saving}>
                  <Plus size={14} /> {t('tracking.trackThisDate')}
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card
        title={editingId ? t('tracking.editDate') : t('tracking.addDateTitle')}
        subtitle={t('tracking.onlyDatesHere')}
      >
        <form onSubmit={save} className="date-form">
          <div className="field" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor="date-label">{t('tracking.whatIsIt')}</label>
            <input
              id="date-label"
              className="input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={t('tracking.datePlaceholder')}
              maxLength={120}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor="date-value">{t('tracking.date')}</label>
            <input
              id="date-value"
              className="input"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor="date-kind">{t('tracking.type')}</label>
            <select
              id="date-kind"
              className="select"
              value={kind}
              onChange={(e) => setKind(e.target.value as DateKind)}
            >
              {KIND_VALUES.map((value) => (
                <option key={value} value={value}>{t(KIND_KEYS[value])}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor="date-lead">{t('tracking.remindMe')}</label>
            <select
              id="date-lead"
              className="select"
              value={lead}
              onChange={(e) => setLead(Number(e.target.value))}
            >
              {[0, 1, 3, 7, 14, 30, 60].map((d) => (
                <option key={d} value={d}>
                  {d === 0
                    ? t('tracking.onTheDay')
                    : d === 1
                      ? t('tracking.dayBefore')
                      : t('tracking.daysBefore', { count: d })}
                </option>
              ))}
            </select>
          </div>
          <div className="field date-form-notes" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor="date-notes">{t('tracking.noteOptional')}</label>
            <input
              id="date-notes"
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('tracking.notePlaceholder')}
              maxLength={1000}
            />
          </div>
          <div className="date-form-actions">
            <Button type="submit" loading={saving}>
              {editingId ? t('common.saveChanges') : t('tracking.addDate')}
            </Button>
            {editingId && (
              <Button type="button" variant="ghost" onClick={resetForm}>
                <X size={14} /> {t('common.cancel')}
              </Button>
            )}
          </div>
        </form>
      </Card>

      <Card
        title={t('tracking.yourDates')}
        subtitle={rows.length > 0 ? t('tracking.savedCount', { count: rows.length }) : undefined}
      >
        {loading ? (
          <p className="text-sm muted mb-0">{t('tracking.loadingDates')}</p>
        ) : error ? (
          <div className="row-inline" style={{ gap: 10 }}>
            <span className="text-sm" style={{ color: 'var(--danger-text)' }}>{error}</span>
            <Button size="sm" variant="secondary" onClick={() => void load()}>{t('common.tryAgain')}</Button>
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<CalendarDays size={26} />}
            title={t('tracking.noDates')}
            description={t('tracking.noDatesBody')}
          />
        ) : (
          <ul className="date-list">
            {rows.map((row) => (
              <li key={row.id} className={['date-row', row.is_overdue ? 'date-row-overdue' : ''].join(' ')}>
                <div className="date-chip">
                  <span>{formatDate(row.due_date).split(',')[1]?.trim() || formatDate(row.due_date)}</span>
                  <strong>{row.days_until < 0 ? t('tracking.past') : relativeDays(row.days_until, t)}</strong>
                </div>
                <div className="date-body">
                  <div className="row-inline" style={{ gap: 8, flexWrap: 'wrap' }}>
                    <strong>{row.label}</strong>
                    <Tag>{t(KIND_KEYS[row.kind])}</Tag>
                    {row.is_overdue && (
                      <span className="date-overdue">
                        <CircleAlert size={13} aria-hidden="true" /> {t('tracking.overdue')}
                      </span>
                    )}
                  </div>
                  {row.notes && <p className="text-sm muted mb-0 mt-2">{row.notes}</p>}
                  <p className="text-xs faint mb-0 mt-2">{reminderLine(row, t, formatDate)}</p>
                </div>
                <div className="date-actions">
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => startEdit(row)}
                    aria-label={`${t('common.edit')} ${row.label}`}
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    type="button"
                    className="icon-btn icon-btn-danger"
                    onClick={() => void remove(row)}
                    aria-label={`${t('common.delete')} ${row.label}`}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function sortDates(rows: ContractDate[]): ContractDate[] {
  return [...rows].sort((a, b) => a.due_date.localeCompare(b.due_date));
}

/* ============================================================ Checklist */
export function ChecklistTab({
  contractId,
  onOpenClause,
}: {
  contractId: string;
  onOpenClause: (clauseId: string) => void;
}) {
  const toast = useToast();
  const { t } = useI18n();
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [text, setText] = useState('');
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.checklist(contractId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your checklist.');
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  const done = items.filter((i) => i.done).length;
  const percent = items.length > 0 ? Math.round((done / items.length) * 100) : 0;

  const generate = async () => {
    setGenerating(true);
    try {
      const result = await api.generateChecklist(contractId);
      setItems(result.items);
      if (result.added > 0) {
        toast.push(t('tracking.stepsAdded', { count: result.added }), 'success');
      } else {
        toast.push(t('tracking.alreadyOnList'), 'info');
      }
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotBuild'), 'error');
    } finally {
      setGenerating(false);
    }
  };

  const add = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setAdding(true);
    try {
      const created = await api.addChecklistItem(contractId, text.trim());
      setItems((prev) => [...prev, created]);
      setText('');
      toast.push(t('tracking.stepAdded'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotAddStep'), 'error');
    } finally {
      setAdding(false);
    }
  };

  const toggle = async (item: ChecklistItem) => {
    try {
      const updated = await api.updateChecklistItem(contractId, item.id, { done: !item.done });
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)));
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotUpdateStep'), 'error');
    }
  };

  const remove = async (item: ChecklistItem) => {
    try {
      await api.deleteChecklistItem(contractId, item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      toast.push(t('tracking.stepRemoved'), 'success');
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('tracking.couldNotRemoveStep'), 'error');
    }
  };

  return (
    <div className="stack">
      <Card
        title={t('tracking.beforeYouSign')}
        subtitle={t('tracking.checklistBody')}
        actions={
          <Button size="sm" variant="secondary" onClick={() => void generate()} loading={generating}>
            <Sparkles size={14} /> {t('tracking.buildFromAnalysis')}
          </Button>
        }
      >
        {items.length > 0 && (
          <div className="checklist-progress">
            <div className="row-spread">
              <span className="text-sm muted">{t('tracking.doneOf', { done, total: items.length })}</span>
              <span className="text-sm muted">{percent}%</span>
            </div>
            <div
              className="progress-track"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={t('tracking.checklistProgress')}
            >
              <span className="progress-fill" style={{ width: `${percent}%` }} />
            </div>
          </div>
        )}

        {loading ? (
          <p className="text-sm muted mb-0">{t('tracking.checklistLoading')}</p>
        ) : error ? (
          <div className="row-inline" style={{ gap: 10 }}>
            <span className="text-sm" style={{ color: 'var(--danger-text)' }}>{error}</span>
            <Button size="sm" variant="secondary" onClick={() => void load()}>{t('common.tryAgain')}</Button>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<ClipboardList size={26} />}
            title={t('tracking.nothingOnList')}
            description={t('tracking.nothingOnListBody')}
          />
        ) : (
          <ul className="check-list">
            {items.map((item) => (
              <li key={item.id} className={['check-row', item.done ? 'check-row-done' : ''].join(' ')}>
                <button
                  type="button"
                  className="check-box"
                  onClick={() => void toggle(item)}
                  role="checkbox"
                  aria-checked={item.done}
                  aria-label={item.text}
                >
                  {item.done && <Check size={14} aria-hidden="true" />}
                </button>
                <div className="check-body">
                  <span className="check-text">{item.text}</span>
                  {item.clause_index && (
                    <button
                      type="button"
                      className="check-source"
                      onClick={() => onOpenClause(item.clause_index!)}
                    >
                      {t('tracking.openSection')} <ArrowUpRight size={12} />
                    </button>
                  )}
                </div>
                <button
                  type="button"
                  className="icon-btn icon-btn-danger"
                  onClick={() => void remove(item)}
                  aria-label={`${t('common.remove')} ${item.text}`}
                >
                  <Trash2 size={15} />
                </button>
              </li>
            ))}
          </ul>
        )}

        <form className="check-add" onSubmit={add}>
          <input
            className="input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t('tracking.addYourOwnStep')}
            aria-label={t('tracking.addYourOwnStepLabel')}
            maxLength={500}
          />
          <Button type="submit" variant="secondary" loading={adding} disabled={!text.trim()}>
            <Plus size={14} /> {t('common.add')}
          </Button>
        </form>
      </Card>
    </div>
  );
}

/* ============================================================ Bookmark toggle */
export function SectionBookmarkButton({
  contractId,
  clauseIndex,
  bookmark,
  onChanged,
}: {
  contractId: string;
  clauseIndex: string;
  bookmark: Bookmark | null;
  onChanged: (saved: boolean) => void;
}) {
  const toast = useToast();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      if (bookmark) {
        await api.deleteBookmark(contractId, bookmark.id);
        onChanged(false);
        toast.push(t('workspace.sectionRemoved'), 'success');
      } else {
        await api.addBookmark(contractId, clauseIndex);
        onChanged(true);
        toast.push(t('workspace.sectionSaved'), 'success');
      }
    } catch (err) {
      toast.push(err instanceof Error ? err.message : t('workspace.couldNotSave'), 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      type="button"
      size="sm"
      variant={bookmark ? 'primary' : 'secondary'}
      onClick={() => void toggle()}
      loading={busy}
      aria-pressed={!!bookmark}
    >
      <Star size={14} fill={bookmark ? 'currentColor' : 'none'} />
      {bookmark ? t('workspace.saved') : t('workspace.saveSection')}
    </Button>
  );
}

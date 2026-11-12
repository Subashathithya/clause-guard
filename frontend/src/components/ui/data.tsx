import React, { useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CloudUpload, FileText, Lock } from 'lucide-react';
import { Alert } from './primitives';
import { useI18n } from '../../i18n/I18nProvider';

/* ================================================================ Card */
export function Card({
  title,
  subtitle,
  actions,
  children,
  pad = true,
  className,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  pad?: boolean;
  className?: string;
}) {
  return (
    <div className={['card', pad ? 'card-pad' : undefined, className || ''].filter(Boolean).join(' ')}>
      {(title || subtitle || actions) && (
        <div className="card-header">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p className="card-subtitle mt-2">{subtitle}</p>}
          </div>
          {actions && <div>{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

/* ================================================================ Breadcrumbs */
export function Breadcrumbs({ items }: { items: { label: string; to?: string }[] }) {
  const { t } = useI18n();
  return (
    <nav aria-label={t('common.breadcrumb')} className="crumbs">
      {items.map((it, i) => {
        const last = i === items.length - 1;
        return (
          <React.Fragment key={`${it.label}-${i}`}>
            {i > 0 && <span className="crumb-sep" aria-hidden="true">›</span>}
            {it.to && !last ? (
              <Link to={it.to}>{it.label}</Link>
            ) : (
              <span aria-current={last ? 'page' : undefined} className={last ? '' : 'muted'}>
                {it.label}
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

/* ================================================================ PageHeader */
export function PageHeader({
  title,
  lead,
  actions,
  crumb,
}: {
  title: React.ReactNode;
  lead?: React.ReactNode;
  actions?: React.ReactNode;
  crumb?: { label: string; to?: string }[];
}) {
  return (
    <header className="page-head">
      {crumb && <Breadcrumbs items={crumb} />}
      <h1>{title}</h1>
      {lead && <p className="page-lead">{lead}</p>}
      {actions && <div className="page-head-actions">{actions}</div>}
    </header>
  );
}

/* ================================================================ Tabs */
export function Tabs({
  tabs,
  value,
  onChange,
  label = 'Page sections',
}: {
  tabs: { id: string; label: React.ReactNode }[];
  value: string;
  onChange: (id: string) => void;
  label?: string;
}) {
  const baseId = useId();

  const move = (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const keys = ['ArrowRight', 'ArrowLeft', 'Home', 'End'];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    const list = Array.from(
      e.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]') || []
    );
    if (list.length === 0) return;
    let next = index;
    if (e.key === 'ArrowRight') next = (index + 1) % list.length;
    if (e.key === 'ArrowLeft') next = (index - 1 + list.length) % list.length;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = list.length - 1;
    list[next]?.focus();
    const tab = tabs[next];
    if (tab) onChange(tab.id);
  };

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, index) => (
        <button
          key={t.id}
          id={`${baseId}-${t.id}-tab`}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          tabIndex={value === t.id ? 0 : -1}
          className={['tab', value === t.id ? 'tab-active' : ''].filter(Boolean).join(' ')}
          onClick={() => onChange(t.id)}
          onKeyDown={(e) => move(e, index)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ================================================================ States */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">{icon || <FileText size={26} />}</div>
      <h4>{title}</h4>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  icon,
}: {
  message: string;
  onRetry?: () => void;
  icon?: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="error-state" role="alert">
      <div className="err-icon" aria-hidden="true">{icon || <span aria-hidden="true">!</span>}</div>
      <h4>{t('common.somethingWentWrong')}</h4>
      <p className="muted">{message}</p>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>
          {t('common.tryAgain')}
        </button>
      )}
    </div>
  );
}

/* ================================================================ FileUploader */
export const SUPPORTED_UPLOAD_EXT = ['.pdf', '.txt', '.md', '.docx'];
export const SUPPORTED_UPLOAD_MIME = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];
export const MAX_UPLOAD_MB = 10;

export function FileUploader({
  onFile,
  error: externalError,
  clearError,
  fileLabel,
}: {
  onFile: (file: File) => void;
  error?: string;
  clearError?: () => void;
  fileLabel?: React.ReactNode;
}) {
  const { t } = useI18n();
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = (file: File): string | null => {
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return t('analyze.fileTooLarge', { max: MAX_UPLOAD_MB });
    }
    const extOk = SUPPORTED_UPLOAD_EXT.some((e) => file.name.toLowerCase().endsWith(e));
    const mimeOk = SUPPORTED_UPLOAD_MIME.includes(file.type);
    if (!extOk && !mimeOk) {
      return t('analyze.unsupportedFile');
    }
    return null;
  };

  const handle = (file?: File) => {
    if (!file) return;
    const err = validate(file);
    if (err) {
      setError(err);
      clearError?.();
      return;
    }
    setError(null);
    clearError?.();
    onFile(file);
  };

  return (
    <div>
      <div
        className={`dropzone ${dragging ? 'drag' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handle(e.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label={t('analyze.uploadDocument')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <CloudUpload size={34} aria-hidden="true" style={{ color: 'var(--brand-500)' }} />
        <div className="mt-3">
          <span className="dropzone-label">{t('analyze.dragDrop')}</span>
        </div>
        <p className="dropzone-hint">PDF, TXT, Markdown or DOCX · up to {MAX_UPLOAD_MB} MB</p>
        {fileLabel}
        <input
          ref={inputRef}
          type="file"
          tabIndex={-1}
          accept={SUPPORTED_UPLOAD_EXT.join(',')}
          onChange={(e) => {
            handle(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
      </div>
      {(error || externalError) && (
        <div className="mt-3">
          <Alert tone="danger" title={t('analyze.couldNotUseFile')}>
            {error || externalError}
          </Alert>
        </div>
      )}
    </div>
  );
}

export function SecureNote() {
  const { t } = useI18n();
  return (
    <p className="text-sm faint" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <Lock size={14} aria-hidden="true" /> {t('analyze.documentPrivacy')}
    </p>
  );
}
import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { CloudUpload, FileText, Lock } from 'lucide-react';
import { Alert } from './primitives';

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
            {title && <h3 className="card-title">{title}</h3>}
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
  return (
    <nav aria-label="Breadcrumb" className="crumbs">
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
}: {
  tabs: { id: string; label: React.ReactNode }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="Page sections">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          className={['tab', value === t.id ? 'tab-active' : ''].filter(Boolean).join(' ')}
          onClick={() => onChange(t.id)}
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
  return (
    <div className="error-state" role="alert">
      <div className="err-icon" aria-hidden="true">{icon || <span aria-hidden="true">!</span>}</div>
      <h4>Something went wrong</h4>
      <p className="muted">{message}</p>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>
          Try again
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
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = (file: File): string | null => {
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      return `This file is too large. The maximum is ${MAX_UPLOAD_MB} MB.`;
    }
    const extOk = SUPPORTED_UPLOAD_EXT.some((e) => file.name.toLowerCase().endsWith(e));
    const mimeOk = SUPPORTED_UPLOAD_MIME.includes(file.type);
    if (!extOk && !mimeOk) {
      return `That file type isn't supported. Please upload a PDF, TXT, Markdown or DOCX file.`;
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
        aria-label="Upload a contract document"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <CloudUpload size={34} aria-hidden="true" style={{ color: 'var(--brand-500)' }} />
        <div className="mt-3">
          <span className="dropzone-label">Drag &amp; drop your contract, or click to browse</span>
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
          <Alert tone="danger" title="Couldn't use that file">
            {error || externalError}
          </Alert>
        </div>
      )}
    </div>
  );
}

export function SecureNote() {
  return (
    <p className="text-sm faint" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <Lock size={14} aria-hidden="true" /> Your document is only used for this analysis and stays in your workspace.
    </p>
  );
}
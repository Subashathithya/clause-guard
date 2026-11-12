import React, { createContext, useCallback, useContext, useEffect, useId, useRef } from 'react';
import { useI18n } from '../../i18n/I18nProvider';

/* ================================================================ Modal */
export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  labelledBy,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
  labelledBy?: string;
}) {
  const { t } = useI18n();
  const id = useId();
  const titleId = labelledBy || `${id}-title`;
  const ref = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    returnFocusRef.current = prev;
    document.body.style.overflow = 'hidden';

    const dialog = ref.current;
    const focusables = () =>
      dialog
        ? Array.from(
            dialog.querySelectorAll<HTMLElement>(
              'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
          )
        : [];

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey) {
        if (active === first || !dialog?.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else if (active === last || !dialog?.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKey);
    const focusTarget =
      focusables().find(
        (el) =>
          el.hasAttribute('data-autofocus') ||
          el.tagName === 'BUTTON' ||
          (el as HTMLInputElement).type === 'text'
      ) || focusables()[0];
    window.setTimeout(() => focusTarget?.focus(), 0);

    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      returnFocusRef.current?.focus?.();
      returnFocusRef.current = null;
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        ref={ref}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={size === 'lg' ? { maxWidth: 820 } : size === 'sm' ? { maxWidth: 400 } : undefined}
      >
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label={t('common.closeDialog')}>
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

/* ================================================================ Popover */
export function Popover({
  label,
  trigger,
  children,
  align = 'right',
}: {
  label: string;
  trigger: React.ReactNode;
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  align?: 'left' | 'right';
}) {
  const [open, setOpen] = React.useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // The wrapper must not duplicate interactive semantics when the trigger is
  // already a real button/link. Detect that so we only add role/tabIndex for
  // non-interactive triggers (e.g. the account avatar).
  const triggerIsInteractive =
    React.isValidElement(trigger) &&
    (() => {
      const t = trigger.type;
      if (typeof t === 'string') {
        return ['button', 'a', 'input', 'select', 'textarea'].includes(t);
      }
      const fwd = (t as { render?: { name?: string } }).render;
      return (fwd?.name || (t as { name?: string }).name) === 'Button';
    })();

  const toggle = () => setOpen((v) => !v);

  let triggerNode: React.ReactNode;
  if (triggerIsInteractive) {
    const interactive = trigger as React.ReactElement<{
      onClick?: React.MouseEventHandler;
      'aria-haspopup'?: string;
      'aria-expanded'?: boolean;
    }>;
    triggerNode = React.cloneElement(interactive, {
      onClick: (e: React.MouseEvent) => {
        interactive.props.onClick?.(e);
        if (!e.defaultPrevented) toggle();
      },
      'aria-haspopup': 'menu',
      'aria-expanded': open,
    });
  } else {
    triggerNode = (
      <span
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        }}
      >
        {trigger}
      </span>
    );
  }

  return (
    <div className="popover" ref={ref}>
      {triggerNode}
      {open && (
        <div className="popover-panel" role="menu" style={align === 'left' ? { right: 'auto', left: 0 } : undefined}>
          {typeof children === 'function' ? children(() => setOpen(false)) : children}
        </div>
      )}
    </div>
  );
}

export function MenuAction({ onSelect, children, danger }: { onSelect: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <button
      type="button"
      role="menuitem"
      className={['popover-item', danger ? 'danger' : ''].filter(Boolean).join(' ')}
      onClick={onSelect}
    >
      {children}
    </button>
  );
}

/* ================================================================ Toasts */
interface ToastItem {
  id: number;
  tone: 'success' | 'error' | 'info';
  message: string;
}
interface ToastApi {
  push: (message: string, tone?: ToastItem['tone']) => void;
}
const ToastContext = createContext<ToastApi | null>(null);

let toastSeq = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: ToastItem['tone'] = 'info') => {
      const id = ++toastSeq;
      setToasts((prev) => [...prev.slice(-4), { id, tone, message }]);
      window.setTimeout(() => remove(id), 5000);
    },
    [remove]
  );

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-region" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`}>
            <span aria-hidden="true">
              {toast.tone === 'success' ? '✓' : toast.tone === 'error' ? '✕' : 'ℹ'}
            </span>
            <span>{toast.message}</span>
            <button
              type="button"
              className="icon-btn"
              style={{ color: '#cbd5e1' }}
              onClick={() => remove(toast.id)}
              aria-label={t('common.dismiss')}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
}
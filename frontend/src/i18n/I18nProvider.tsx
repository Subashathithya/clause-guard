import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { MESSAGES, translate } from './index';
import {
  LOCALE_INFO,
  LOCALE_STORAGE_KEY,
  detectInitialLocale,
  setCurrentLocale,
  type Locale,
} from './locales';
import type { AttentionLevel } from '../types';

export interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  formatDate: (iso?: string | null) => string;
  formatDateTime: (iso?: string | null) => string;
  formatNumber: (n: number) => string;
  timeAgo: (iso?: string | null) => string;
  attentionLabel: (level: AttentionLevel) => string;
  categoryLabel: (category: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const CATEGORY_KEYS: Record<string, string> = {
  Payment: 'workspace.categoryPayment',
  'Auto-Renewal': 'workspace.categoryRenewal',
  Liability: 'workspace.categoryLiability',
  'Data Privacy': 'workspace.categoryPrivacy',
  Dispute: 'workspace.categoryDispute',
  Warranty: 'workspace.categoryWarranty',
  Other: 'workspace.categoryOther',
};

const ATTENTION_KEYS: Record<AttentionLevel, string> = {
  high: 'workspace.levelHigh',
  moderate: 'workspace.levelMid',
  low: 'workspace.levelLow',
  unknown: 'workspace.levelUnknown',
};

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => detectInitialLocale());

  useEffect(() => {
    document.documentElement.lang = locale;
    setCurrentLocale(locale);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch (err) {
      /* private browsing — the language still applies for this session */
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => setLocaleState(next), []);

  const value = useMemo<I18nContextValue>(() => {
    const tree = MESSAGES[locale];
    const intlTag = LOCALE_INFO[locale].intlTag;

    const t = (key: string, params?: Record<string, string | number>) =>
      translate(tree, key, params);

    const formatDate = (iso?: string | null) => {
      if (!iso) return '—';
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return '—';
      return d.toLocaleDateString(intlTag, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    };

    const formatDateTime = (iso?: string | null) => {
      if (!iso) return '—';
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return '—';
      return d.toLocaleString(intlTag, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    };

    const formatNumber = (n: number) => n.toLocaleString(intlTag);

    const timeAgo = (iso?: string | null) => {
      if (!iso) return '';
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return '';
      const diff = Date.now() - d.getTime();
      const mins = Math.round(diff / 60000);
      if (mins < 1) return t('common.justNow');
      if (mins < 60) return t('common.minutesAgo', { count: mins });
      const hrs = Math.round(mins / 60);
      if (hrs < 24) return t('common.hoursAgo', { count: hrs });
      const days = Math.round(hrs / 24);
      if (days < 30) return t('common.daysAgo', { count: days });
      return formatDate(iso);
    };

    const attentionLabel = (level: AttentionLevel) => t(ATTENTION_KEYS[level] || ATTENTION_KEYS.unknown);

    const categoryLabel = (category: string) => {
      const key = CATEGORY_KEYS[category];
      return key ? t(key) : category || t('workspace.categoryOther');
    };

    return {
      locale,
      setLocale,
      t,
      formatDate,
      formatDateTime,
      formatNumber,
      timeAgo,
      attentionLabel,
      categoryLabel,
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within <I18nProvider>');
  return ctx;
}

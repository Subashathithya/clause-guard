/**
 * Languages the app speaks.
 *
 * English is the source language; Hindi, Tamil and Telugu are the first
 * translations. Every locale is written in its own script, so the UI picks
 * the matching system font automatically.
 */
export type Locale = 'en' | 'hi' | 'ta' | 'te';

export const LOCALES: Locale[] = ['en', 'hi', 'ta', 'te'];

export const LOCALE_STORAGE_KEY = 'cg_locale';

export interface LocaleInfo {
  /** Name in English. */
  name: string;
  /** Name written in the language itself. */
  nativeName: string;
  /** BCP-47 tag used for dates and numbers. */
  intlTag: string;
  /** Short label for compact switchers. */
  short: string;
}

export const LOCALE_INFO: Record<Locale, LocaleInfo> = {
  en: { name: 'English', nativeName: 'English', intlTag: 'en-IN', short: 'EN' },
  hi: { name: 'Hindi', nativeName: 'हिन्दी', intlTag: 'hi-IN', short: 'हि' },
  ta: { name: 'Tamil', nativeName: 'தமிழ்', intlTag: 'ta-IN', short: 'தமி' },
  te: { name: 'Telugu', nativeName: 'తెలుగు', intlTag: 'te-IN', short: 'తె' },
};

/**
 * The locale in force right now. Kept outside React so non-component code
 * (for example the API client) can localise a message without a hook.
 */
let currentLocale: Locale = 'en';

export function setCurrentLocale(locale: Locale): void {
  currentLocale = locale;
}

export function getCurrentLocale(): Locale {
  return currentLocale;
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as string[]).includes(value);
}

/** The language the visitor's browser asks for, if we speak it. */
export function detectBrowserLocale(): Locale {
  if (typeof navigator === 'undefined') return 'en';
  const candidates = navigator.languages?.length
    ? navigator.languages
    : [navigator.language].filter(Boolean);
  for (const raw of candidates) {
    const tag = raw.toLowerCase();
    if (tag.startsWith('hi')) return 'hi';
    if (tag.startsWith('ta')) return 'ta';
    if (tag.startsWith('te')) return 'te';
  }
  return 'en';
}

/** Saved choice, else the browser language, else English. */
export function detectInitialLocale(): Locale {
  if (typeof localStorage !== 'undefined') {
    const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (isLocale(saved)) return saved;
  }
  return detectBrowserLocale();
}

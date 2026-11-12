import { en, type Messages } from './messages/en';
import { hi } from './messages/hi';
import { ta } from './messages/ta';
import { te } from './messages/te';
import { getCurrentLocale, type Locale } from './locales';

export const MESSAGES: Record<Locale, Messages> = { en, hi, ta, te };

/**
 * Look up a dotted key such as `workspace.overview` and fill in any
 * `{placeholders}`. A missing key returns the key itself, so a gap shows up
 * in the UI instead of a blank space.
 */
export function translate(
  tree: Messages,
  key: string,
  params?: Record<string, string | number>
): string {
  const value = key.split('.').reduce<unknown>((acc, part) => {
    if (acc && typeof acc === 'object') return (acc as Record<string, unknown>)[part];
    return undefined;
  }, tree);

  if (typeof value !== 'string') return key;
  if (!params) return value;
  return value.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match
  );
}

/** Translate a key with the locale that is currently in force. */
export function translateNow(
  key: string,
  params?: Record<string, string | number>
): string {
  return translate(MESSAGES[getCurrentLocale()], key, params);
}

export type { Messages };
export { en };

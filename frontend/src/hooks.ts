import { useCallback, useEffect, useRef, useState } from 'react';

/** Loads async data with loading/error/value states and a retry handle. */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]) {
  const [value, setValue] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fnRef.current()
      .then((v) => {
        if (alive) {
          setValue(v);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (alive) {
          setError(err instanceof Error ? err.message : String(err));
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  return { value, loading, error, retry: run, setValue };
}

/** Debounced string value for search inputs. */
export function useDebounced(value: string, delay = 250): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

/** Current time that advances each N ms while `active` is true (progress UI). */
export function useTicker(active: boolean, intervalMs = 1500): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setTick((v) => v + 1), intervalMs);
    return () => window.clearInterval(t);
  }, [active, intervalMs]);
  return tick;
}

export function useLib<T>(factory: () => T): T {
  const ref = useRef<T | undefined>(undefined);
  if (ref.current === undefined) ref.current = factory();
  return ref.current;
}
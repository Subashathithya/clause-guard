import { Capacitor } from '@capacitor/core';

/**
 * Service worker registration for the web build.
 *
 * The native Android build ships its own bundle, so it never registers a
 * service worker there. During development the worker is skipped as well:
 * a cached shell makes hot reloads confusing and hides real network errors.
 */
export const SERVICE_WORKER_URL = '/service-worker.js';

type UpdateListener = () => void;

const updateListeners = new Set<UpdateListener>();

/** Subscribe to "a new version is ready" updates. */
export function onUpdateReady(listener: UpdateListener): () => void {
  updateListeners.add(listener);
  return () => {
    updateListeners.delete(listener);
  };
}

function notifyUpdateReady(): void {
  updateListeners.forEach((listener) => {
    try {
      listener();
    } catch (err) {
      /* a broken listener must not break the update flow */
    }
  });
}

export function isServiceWorkerSupported(): boolean {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator;
}

export function shouldRegisterServiceWorker(): boolean {
  if (!isServiceWorkerSupported()) return false;
  if (Capacitor.isNativePlatform()) return false;
  return process.env.NODE_ENV === 'production';
}

/**
 * Register the worker and report when a newer version is waiting.
 *
 * The new version is not activated on its own: the user is asked first, so a
 * refresh never interrupts someone in the middle of reading a contract.
 */
export function registerServiceWorker(): void {
  if (!shouldRegisterServiceWorker()) return;

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(SERVICE_WORKER_URL)
      .then((registration) => {
        const track = (worker: ServiceWorker | null) => {
          if (!worker) return;
          worker.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) {
              notifyUpdateReady();
            }
          });
        };
        track(registration.waiting);
        registration.addEventListener('updatefound', () => track(registration.installing));
      })
      .catch(() => {
        /* An unavailable service worker must never break the app. */
      });
  });
}

/** Ask a waiting worker to take over, then reload into the new version. */
export function activateWaitingWorker(): void {
  if (!isServiceWorkerSupported()) {
    window.location.reload();
    return;
  }
  navigator.serviceWorker.getRegistration().then((registration) => {
    const waiting = registration?.waiting;
    if (!waiting) {
      window.location.reload();
      return;
    }
    const reload = () => window.location.reload();
    navigator.serviceWorker.addEventListener('controllerchange', reload);
    waiting.postMessage({ type: 'SKIP_WAITING' });
  });
}

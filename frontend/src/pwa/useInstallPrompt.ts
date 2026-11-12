import { useCallback, useEffect, useState } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'cg_install_dismissed';

/** True when the app is already running as an installed app. */
export function isRunningAsInstalledApp(): boolean {
  if (typeof window === 'undefined') return false;
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches;
  const iosStandalone = (window.navigator as { standalone?: boolean }).standalone === true;
  return Boolean(standalone || iosStandalone);
}

/** iOS Safari does not offer an install button, so we show instructions. */
export function isIosBrowser(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent;
  return /iPad|iPhone|iPod/i.test(ua) && !(window.navigator as { standalone?: boolean }).standalone;
}

export function isDismissed(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(DISMISS_KEY) === '1';
}

export function rememberDismissed(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(DISMISS_KEY, '1');
}

export interface InstallPromptState {
  /** The browser offered an install button we can trigger. */
  canInstall: boolean;
  /** iOS Safari: show the "Share → Add to Home Screen" steps instead. */
  needsManualSteps: boolean;
  installed: boolean;
  dismissed: boolean;
  install: () => Promise<void>;
  dismiss: () => void;
}

/**
 * Tracks the browser's install prompt so the app can offer "add to home
 * screen" at a sensible moment instead of hijacking the first visit.
 */
export function useInstallPrompt(): InstallPromptState {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState<boolean>(() => isRunningAsInstalledApp());
  const [dismissed, setDismissed] = useState<boolean>(() => isDismissed());

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setDeferred(null);
    };
    window.addEventListener('beforeinstallprompt', onBeforeInstall);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const install = useCallback(async () => {
    if (!deferred) return;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    if (choice.outcome === 'accepted') {
      setInstalled(true);
    }
    setDeferred(null);
  }, [deferred]);

  const dismiss = useCallback(() => {
    rememberDismissed();
    setDismissed(true);
  }, []);

  return {
    canInstall: Boolean(deferred),
    needsManualSteps: !deferred && isIosBrowser() && !installed,
    installed,
    dismissed,
    install,
    dismiss,
  };
}

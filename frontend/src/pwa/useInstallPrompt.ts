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

/**
 * How the user installs the app in *this* browser.
 *
 * Only Chrome and Edge fire an install event; Safari on iOS and every other
 * browser need a few manual steps instead. The instructions are chosen from
 * the browser actually in use, so the text is always actionable.
 */
export type InstallMethod = 'prompt' | 'ios' | 'chrome' | 'other';

export function detectInstallMethod(hasPrompt: boolean): InstallMethod {
  if (hasPrompt) return 'prompt';
  if (isIosBrowser()) return 'ios';
  if (typeof navigator === 'undefined') return 'other';
  const ua = navigator.userAgent;
  if (/Edg\//i.test(ua)) return 'chrome';
  if (/Chrome|Chromium/i.test(ua)) return 'chrome';
  return 'other';
}

export interface InstallPromptState {
  /** The browser offered an install button we can trigger. */
  canInstall: boolean;
  /** How this browser installs the app. */
  method: InstallMethod;
  /** True when the steps for this browser are expanded. */
  showSteps: boolean;
  installed: boolean;
  dismissed: boolean;
  install: () => Promise<void>;
  toggleSteps: () => void;
  dismiss: () => void;
}

/**
 * Tracks the browser's install prompt so the app can offer "add to home
 * screen" at a sensible moment instead of hijacking the first visit.
 *
 * The offer is always visible (unless the app is already installed or the
 * user dismissed it): browsers that cannot show a native prompt still get
 * the steps for their own browser.
 */
export function useInstallPrompt(): InstallPromptState {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = useState<boolean>(() => isRunningAsInstalledApp());
  const [dismissed, setDismissed] = useState<boolean>(() => isDismissed());
  const [showSteps, setShowSteps] = useState(false);

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

  const toggleSteps = useCallback(() => setShowSteps((v) => !v), []);

  const dismiss = useCallback(() => {
    rememberDismissed();
    setDismissed(true);
  }, []);

  return {
    canInstall: Boolean(deferred),
    method: detectInstallMethod(Boolean(deferred)),
    showSteps,
    installed,
    dismissed,
    install,
    toggleSteps,
    dismiss,
  };
}

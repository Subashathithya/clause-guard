/**
 * Optional app lock.
 *
 * The lock is entirely device-local: the browser's platform authenticator
 * (fingerprint, face or the device PIN) does the verification and the
 * credential never leaves the device — only its public id is kept in local
 * storage so the browser knows which credential to ask for.
 *
 * Nothing about the user's contracts is involved, and no server round trip is
 * needed to unlock. Clearing site data for the app also removes the lock.
 */
const CREDENTIAL_KEY = 'cg_app_lock_credential';

/** The last human-readable reason a lock attempt failed. */
let lastLockError = '';
const ENABLED_KEY = 'cg_app_lock_enabled';
const UNLOCKED_KEY = 'cg_app_lock_unlocked';

function b64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let out = '';
  bytes.forEach((b) => {
    out += String.fromCharCode(b);
  });
  return btoa(out).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromB64url(value: string): ArrayBuffer {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

/**
 * Turn a browser error into something a person can act on.
 *
 * The most common one is "invalid domain": WebAuthn only accepts
 * "localhost" (or the real web address of the deployed site) as the
 * relying-party id, so opening the app at 127.0.0.1 can never work.
 */
function friendlyLockError(err: unknown): string {
  const name = err instanceof Error ? err.name : '';
  const message = err instanceof Error ? err.message : String(err ?? '');
  if (/invalid domain/i.test(message) || name === 'SecurityError') {
    return (
      'Open ClauseGuard at localhost (or at the app\u2019s real web address) to use the ' +
      'fingerprint lock — a raw IP address is not accepted by the browser.'
    );
  }
  if (name === 'NotAllowedError') {
    return 'No fingerprint or face was detected. Try again, or use your device PIN.';
  }
  if (name === 'AbortError') {
    return 'The fingerprint check was cancelled.';
  }
  return 'This device could not set up the fingerprint lock.';
}

/** True when this browser can ask for a fingerprint, face or device PIN. */
export function isAppLockSupported(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    typeof window.PublicKeyCredential !== 'undefined' &&
    !!navigator.credentials &&
    typeof navigator.credentials.create === 'function' &&
    typeof navigator.credentials.get === 'function'
  );
}

/**
 * True when this *device* can actually verify the user.
 *
 * The WebAuthn API can exist on a machine with no fingerprint, face or PIN
 * enrolled — the browser then has no way to check who is holding it. The
 * platform authenticator check is the honest one, so the setting is only
 * offered where it can work.
 */
export async function hasPlatformAuthenticator(): Promise<boolean> {
  if (!isAppLockSupported()) return false;
  try {
    if (
      typeof window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable ===
      'function'
    ) {
      return await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    }
  } catch (err) {
    return false;
  }
  return false;
}

export function isAppLockEnabled(): boolean {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(ENABLED_KEY) === '1' && !!localStorage.getItem(CREDENTIAL_KEY);
}

/** Ask the device to register a credential for this app. */
export async function enableAppLock(): Promise<void> {
  if (!isAppLockSupported()) {
    throw new Error('This device cannot lock the app with a fingerprint or face.');
  }
  const credential = (await navigator.credentials.create({
    publicKey: {
      challenge: crypto.getRandomValues(new Uint8Array(32)),
      rp: { name: 'ClauseGuard' },
      user: {
        id: crypto.getRandomValues(new Uint8Array(16)),
        name: 'clauseguard-user',
        displayName: 'ClauseGuard',
      },
      pubKeyCredParams: [
        { type: 'public-key', alg: -7 },
        { type: 'public-key', alg: -257 },
      ],
      authenticatorSelection: {
        authenticatorAttachment: 'platform',
        userVerification: 'required',
        residentKey: 'preferred',
      },
      attestation: 'none',
      timeout: 60000,
    },
  })) as PublicKeyCredential | null;

  if (!credential) {
    throw new Error(friendlyLockError(new Error('no credential')));
  }
  localStorage.setItem(CREDENTIAL_KEY, b64url(credential.rawId));
  localStorage.setItem(ENABLED_KEY, '1');
}

export function disableAppLock(): void {
  localStorage.removeItem(CREDENTIAL_KEY);
  localStorage.removeItem(ENABLED_KEY);
  sessionStorage.removeItem(UNLOCKED_KEY);
}

/** Ask the device to verify the user. True when the user passed. */
export async function unlockApp(): Promise<boolean> {
  if (!isAppLockSupported()) return true;
  const stored = localStorage.getItem(CREDENTIAL_KEY);
  if (!stored) return true;
  try {
    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge: crypto.getRandomValues(new Uint8Array(32)),
        allowCredentials: [{ type: 'public-key', id: fromB64url(stored) }],
        userVerification: 'required',
        timeout: 60000,
      },
    });
    if (!assertion) return false;
    sessionStorage.setItem(UNLOCKED_KEY, '1');
    return true;
  } catch (err) {
    lastLockError = friendlyLockError(err);
    return false;
  }
}

/** True when the app was already unlocked in this browser session. */
export function isUnlockedForSession(): boolean {
  if (typeof sessionStorage === 'undefined') return false;
  return sessionStorage.getItem(UNLOCKED_KEY) === '1';
}

/** The last human-readable reason a lock attempt failed (empty if none). */
export function lockErrorMessage(): string {
  return lastLockError;
}

export function lockNow(): void {
  if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem(UNLOCKED_KEY);
}

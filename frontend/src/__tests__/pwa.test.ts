/**
 * PWA guard rails.
 *
 * These tests lock in the two promises that matter for a contract app:
 *   1. the app can be installed and opened offline (manifest + worker exist
 *      and point at real files), and
 *   2. the offline helper never stores contracts, analyses or account data.
 */
import fs from 'fs';
import path from 'path';

const PUBLIC_DIR = path.resolve(__dirname, '..', '..', 'public');

function readPublic(file: string): string {
  return fs.readFileSync(path.join(PUBLIC_DIR, file), 'utf8');
}

function manifest(): any {
  return JSON.parse(readPublic('manifest.json'));
}

describe('web app manifest', () => {
  it('describes an installable standalone app', () => {
    const m = manifest();
    expect(m.name).toContain('ClauseGuard');
    expect(m.short_name).toBeTruthy();
    expect(m.description).toBeTruthy();
    expect(m.display).toBe('standalone');
    expect(m.start_url).toBeTruthy();
    expect(m.scope).toBeTruthy();
    expect(m.theme_color).toBe('#4f46e5');
    expect(m.background_color).toBeTruthy();
  });

  it('ships the icon sizes browsers require for installation', () => {
    const m = manifest();
    const sizes = m.icons.map((i: { sizes: string }) => i.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
    expect(m.icons.some((i: { purpose?: string }) => i.purpose === 'maskable')).toBe(true);
  });

  it('points only at icons that exist in public/', () => {
    const m = manifest();
    for (const icon of m.icons) {
      expect(fs.existsSync(path.join(PUBLIC_DIR, icon.src))).toBe(true);
    }
    for (const shortcut of m.shortcuts || []) {
      for (const icon of shortcut.icons || []) {
        expect(fs.existsSync(path.join(PUBLIC_DIR, icon.src))).toBe(true);
      }
    }
  });
});

describe('offline helper (service worker)', () => {
  const worker = readPublic('service-worker.js');

  it('caches the app shell and the offline page', () => {
    expect(worker).toContain("'/offline.html'");
    expect(worker).toContain("'/index.html'");
    expect(worker).toContain('/manifest.json');
  });

  it('never caches API traffic', () => {
    // Every API path that can return contract, analysis or account data has to
    // be listed as excluded.
    for (const path of ['/contracts', '/analyze', '/upload', '/chat', '/compare', '/auth', '/reminders']) {
      expect(worker).toContain(`'${path}'`);
    }
    expect(worker).toContain('isApiPath');
  });

  it('never caches authenticated requests', () => {
    expect(worker).toContain("request.headers.has('authorization')");
  });

  it('only caches assets served from this origin', () => {
    expect(worker).toContain('url.origin !== self.location.origin');
  });

  it('does not skip waiting on its own, so an update never interrupts a read', () => {
    expect(worker).not.toContain('self.skipWaiting();\n  });');
    expect(worker).toContain('SKIP_WAITING');
  });
});

describe('offline page', () => {
  it('explains the situation in plain language', () => {
    const page = readPublic('offline.html');
    expect(page).toContain("You're offline");
    expect(page).toContain('Try again');
    expect(page).not.toMatch(/service worker|cache storage/i);
  });
});

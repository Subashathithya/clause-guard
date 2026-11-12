import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { AuthProvider } from '../auth/context';
import { ToastProvider } from '../components/ui/overlays';
import { I18nProvider } from '../i18n/I18nProvider';
import { MESSAGES } from '../i18n';
import { LOCALE_STORAGE_KEY, type Locale } from '../i18n/locales';

function mockHealth() {
  (global as any).fetch = jest.fn((url: string) => {
    if (url.includes('/health')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'API is running', auth_required: false }),
      });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'not found' }) });
  });
}

function renderApp(locale: Locale, initialPath = '/') {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  return render(
    <I18nProvider>
      <ToastProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[initialPath]}>
            <App />
          </MemoryRouter>
        </AuthProvider>
      </ToastProvider>
    </I18nProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockHealth();
});

describe('translations', () => {
  it('renders the landing page in English', async () => {
    renderApp('en');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'Confusing contracts,'
    );
    expect(screen.getByRole('link', { name: /Upload a contract/i })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
  });

  it('renders the landing page in Hindi', async () => {
    renderApp('hi');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'उलझन भरे अनुबंध,'
    );
    expect(screen.getByRole('link', { name: /अनुबंध अपलोड करें/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('hi');
  });

  it('renders the landing page in Tamil', async () => {
    renderApp('ta');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'சிக்கலான ஒப்பந்தங்கள்,'
    );
    expect(screen.getByRole('link', { name: /ஒப்பந்தத்தைப் பதிவேற்று/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('ta');
  });

  it('renders the landing page in Telugu', async () => {
    renderApp('te');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
      'గందరగోళంగా ఉన్న ఒప్పందులు,'
    );
    expect(screen.getByRole('link', { name: /ఒప్పందాన్ని అప్‌లోడ్ చేయండి/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('te');
  });

  it('translates the sign-in page too', async () => {
    renderApp('hi', '/login');
    expect(
      await screen.findByRole('heading', { name: /ClauseGuard में साइन इन करें/ })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /साइन इन/ })).toBeInTheDocument();
  });
});

describe('catalogues', () => {
  const flatten = (obj: Record<string, unknown>, prefix = ''): string[] =>
    Object.entries(obj).flatMap(([key, value]) =>
      typeof value === 'object' && value !== null
        ? flatten(value as Record<string, unknown>, `${prefix}${key}.`)
        : [`${prefix}${key}`]
    );

  it('every locale has exactly the same keys as English', () => {
    const en = flatten(MESSAGES.en as unknown as Record<string, unknown>).sort();
    for (const locale of ['hi', 'ta', 'te'] as const) {
      const other = flatten(MESSAGES[locale] as unknown as Record<string, unknown>).sort();
      expect(other).toEqual(en);
    }
  });

  it('has no empty translations', () => {
    for (const locale of ['en', 'hi', 'ta', 'te'] as const) {
      const tree = MESSAGES[locale] as unknown as Record<string, unknown>;
      for (const key of flatten(tree)) {
        const value = key
          .split('.')
          .reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], tree);
        expect(typeof value).toBe('string');
        expect((value as string).trim().length).toBeGreaterThan(0);
      }
    }
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { AuthProvider } from '../auth/context';
import { ToastProvider } from '../components/ui/overlays';

function renderApp(initialPath = '/') {
  return render(
    <ToastProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <App />
        </MemoryRouter>
      </AuthProvider>
    </ToastProvider>
  );
}

function mockHealth(authRequired = false) {
  (global as any).fetch = jest.fn((url: string) => {
    if (url.includes('/health')) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ status: 'API is running', auth_required: authRequired }),
      });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({ detail: 'not found' }) });
  });
}

describe('App routing', () => {
  beforeEach(() => {
    localStorage.clear();
    mockHealth(false);
  });

  it('shows the public landing page at /', async () => {
    renderApp('/');
    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading.textContent).toContain('Confusing contracts');
    expect(screen.getByText('Understand any contract in plain English')).toBeInTheDocument();
  });

  it('shows the analyse page when REQUIRE_AUTH is off', async () => {
    renderApp('/analyze');
    expect(await screen.findByRole('heading', { name: /Analyze a contract/i })).toBeInTheDocument();
  });

  it('renders a friendly 404 for unknown paths', () => {
    renderApp('/no-such-page');
    expect(screen.getByRole('heading', { name: /This page got lost in the fine print/i })).toBeInTheDocument();
  });

  it('redirects to /login when auth is required and the user is a guest', async () => {
    mockHealth(true);
    renderApp('/dashboard');
    expect(await screen.findByRole('heading', { name: /Sign in to ClauseGuard/i })).toBeInTheDocument();
  });

  it('lets a user navigate from the landing page to analyse', async () => {
    renderApp('/');
    await screen.findByRole('heading', { level: 1 });
    fireEvent.click(screen.getByRole('link', { name: /Analyze a contract/i }));
    expect(await screen.findByRole('heading', { name: /Analyze a contract/i })).toBeInTheDocument();
  });
});
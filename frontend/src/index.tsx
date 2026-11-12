import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import './styles/tokens.css';
import './styles/ui.css';
import './styles/layout.css';
import './styles/landing.css';
import './styles/pages.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { AuthProvider } from './auth/context';
import { ToastProvider } from './components/ui/overlays';
import { I18nProvider } from './i18n/I18nProvider';
import { registerServiceWorker } from './pwa/serviceWorker';

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <I18nProvider>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  </React.StrictMode>
);

reportWebVitals();

// Offline shell + install support (web build only).
registerServiceWorker();
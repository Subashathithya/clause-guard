import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell, useAuthGate } from './components/Layout';
import { Spinner } from './components/ui/primitives';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import AnalyzePage from './pages/Analyze';
import ContractsPage from './pages/Contracts';
import ContractWorkspace from './pages/ContractWorkspace';
import ComparePage from './pages/Compare';
import TermsChecker from './pages/TermsChecker';
import Insights from './pages/Insights';
import Notifications from './pages/Notifications';
import SettingsPage from './pages/Settings';
import NotFound from './pages/NotFound';

/** Guards the application section: redirects to /login when the backend
 *  requires authentication and the visitor is not signed in. In the default
 *  guest mode it lets everyone through. */
function ProtectedZone() {
  const { booting, blocked } = useAuthGate();
  if (booting) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 'var(--s10)' }}>
        <Spinner label="Loading ClauseGuard" />
      </div>
    );
  }
  if (blocked) return <Navigate to="/login" replace />;
  return <AppShell />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />

      <Route element={<ProtectedZone />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/contracts/:contractId" element={<ContractWorkspace />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/terms-checker" element={<TermsChecker />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/context';
import { useToast } from '../components/ui/overlays';
import { Button, Field, Input, PasswordInput } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from || '/dashboard';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    setEmailError('');
    setPasswordError('');
    let ok = true;
    if (!EMAIL_RE.test(email.trim())) {
      setEmailError('Enter a valid email address.');
      ok = false;
    }
    if (!password) {
      setPasswordError('Enter your password.');
      ok = false;
    }
    if (!ok) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      toast.push(`Welcome back! Your free analyses are loaded.`, 'success');
      navigate(from, { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Sign in failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Sign in to ClauseGuard" subtitle="Your contracts and explanations, all in one place.">
      <form onSubmit={submit} noValidate>
        <Field label="Email" htmlFor="login-email" error={emailError}>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            invalid={!!emailError}
          />
        </Field>
        <Field label="Password" htmlFor="login-password" error={passwordError}>
          <PasswordInput
            id="login-password"
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            invalid={!!passwordError}
          />
        </Field>
        <div className="row-spread text-sm" style={{ marginBottom: 'var(--s4)' }}>
          <span />
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        {formError && (
          <div className="alert alert-danger mb-3" role="alert">
            {formError}
          </div>
        )}
        <Button type="submit" block loading={submitting} disabled={submitting}>
          {submitting ? 'Signing you in…' : 'Sign in'}
        </Button>
      </form>
      <p className="text-center text-sm muted mt-4" style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
        New to ClauseGuard? <Link to="/signup">Create a free account</Link>
      </p>
    </AuthLayout>
  );
}
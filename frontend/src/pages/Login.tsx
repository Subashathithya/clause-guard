import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/context';
import { useToast } from '../components/ui/overlays';
import { Button, Field, Input, PasswordInput } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';
import { useI18n } from '../i18n/I18nProvider';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const { t } = useI18n();

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
      setEmailError(t('auth.invalidEmail'));
      ok = false;
    }
    if (!password) {
      setPasswordError(t('auth.passwordRequired'));
      ok = false;
    }
    if (!ok) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      toast.push(t('auth.welcomeTitle'), 'success');
      navigate(from, { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t('common.networkError'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title={t('auth.loginTitle')} subtitle={t('auth.loginLead')}>
      <form onSubmit={submit} noValidate>
        <Field label={t('auth.email')} htmlFor="login-email" error={emailError}>
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
        <Field label={t('auth.password')} htmlFor="login-password" error={passwordError}>
          <PasswordInput
            id="login-password"
            autoComplete="current-password"
            placeholder={t('auth.passwordPlaceholder')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            invalid={!!passwordError}
          />
        </Field>
        <div className="row-spread text-sm" style={{ marginBottom: 'var(--s4)' }}>
          <span />
          <Link to="/forgot-password">{t('auth.forgotPassword')}</Link>
        </div>
        {formError && (
          <div className="alert alert-danger mb-3" role="alert">
            {formError}
          </div>
        )}
        <Button type="submit" block loading={submitting} disabled={submitting}>
          {submitting ? t('auth.signingIn') : t('auth.signIn')}
        </Button>
      </form>
      <p className="text-center text-sm muted mt-4" style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
        {t('auth.newHere')} <Link to="/signup">{t('auth.createAccount')}</Link>
      </p>
    </AuthLayout>
  );
}
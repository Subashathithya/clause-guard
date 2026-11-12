import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/context';
import { useToast } from '../components/ui/overlays';
import { Button, Field, Input, PasswordInput } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';
import { useI18n } from '../i18n/I18nProvider';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const { t } = useI18n();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!fullName.trim()) next.fullName = t('auth.nameRequired');
    if (!EMAIL_RE.test(email.trim())) next.email = t('auth.invalidEmail');
    if (password.length < 8) next.password = t('auth.passwordTooShort');
    if (confirm !== password) next.confirm = t('auth.passwordsDoNotMatch');
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (!validate()) return;

    setSubmitting(true);
    try {
      await signup(email.trim(), password, fullName.trim());
      toast.push(t('auth.welcomeTitle'), 'success');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : t('common.networkError'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title={t('auth.signupTitle')} subtitle={t('auth.signupLead')}>
      <form onSubmit={submit} noValidate>
        <Field label={t('auth.fullName')} htmlFor="su-name" error={errors.fullName}>
          <Input
            id="su-name"
            autoComplete="name"
            placeholder="Aarav Sharma"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            invalid={!!errors.fullName}
          />
        </Field>
        <Field label={t('auth.email')} htmlFor="su-email" error={errors.email}>
          <Input
            id="su-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            invalid={!!errors.email}
          />
        </Field>
        <Field
          label={t('auth.password')}
          htmlFor="su-password"
          helper={t('auth.passwordHint')}
          error={errors.password}
        >
          <PasswordInput
            id="su-password"
            autoComplete="new-password"
            placeholder={t('auth.createPassword')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            invalid={!!errors.password}
          />
        </Field>
        <Field label={t('auth.confirmPassword')} htmlFor="su-confirm" error={errors.confirm}>
          <PasswordInput
            id="su-confirm"
            autoComplete="new-password"
            placeholder={t('auth.repeatPassword')}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            invalid={!!errors.confirm}
          />
        </Field>
        {formError && (
          <div className="alert alert-danger mb-3" role="alert">
            {formError}
          </div>
        )}
        <Button type="submit" block loading={submitting} disabled={submitting}>
          {submitting ? t('auth.signingIn') : t('auth.createAccountButton')}
        </Button>
      </form>
      <p className="text-center text-sm muted mt-4" style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
        {t('auth.haveAccount')} <Link to="/login">{t('nav.signIn')}</Link>
      </p>
    </AuthLayout>
  );
}
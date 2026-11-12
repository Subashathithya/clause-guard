import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Button, Field, Input } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';
import { useI18n } from '../i18n/I18nProvider';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function ForgotPassword() {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [sent, setSent] = useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError('');
    if (!EMAIL_RE.test(email.trim())) {
      setEmailError(t('auth.invalidEmail'));
      return;
    }
    // There is no password-reset endpoint yet — we do not fake a reset email.
    setSent(true);
  };

  return (
    <AuthLayout title={t('auth.forgotTitle')} subtitle={t('auth.forgotLead')}>
      {sent ? (
        <Alert tone="info" title={t('auth.forgotUnavailable')}>
          {t('auth.forgotUnavailableBefore')}{' '}
          <Link to="/login">{t('auth.forgotSignInAgain')}</Link>{' '}
          {t('auth.forgotUnavailableAfter', { email: email.trim() })}
        </Alert>
      ) : (
        <form onSubmit={submit} noValidate>
          <Field
            label={t('auth.email')}
            htmlFor="fp-email"
            helper={t('auth.forgotBody')}
            error={emailError}
          >
            <Input
              id="fp-email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              invalid={!!emailError}
            />
          </Field>
          <Button type="submit" block>
            {t('auth.continue')}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
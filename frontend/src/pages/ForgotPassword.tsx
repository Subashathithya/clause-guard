import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Button, Field, Input } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [sent, setSent] = useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError('');
    if (!EMAIL_RE.test(email.trim())) {
      setEmailError('Enter a valid email address.');
      return;
    }
    // There is no password-reset endpoint yet — we do not fake a reset email.
    setSent(true);
  };

  return (
    <AuthLayout title="Reset your password" subtitle="We’ll help you get back into your account.">
      {sent ? (
        <Alert tone="info" title="Password reset isn’t available yet">
          We don’t have a self-service reset built in at the moment. For now, please{' '}
          <Link to="/login">sign in again</Link> if you remember your password, or reach out to support
          and we’ll restore access for <strong>{email.trim()}</strong>.
        </Alert>
      ) : (
        <form onSubmit={submit} noValidate>
          <Field
            label="Email"
            htmlFor="fp-email"
            helper="Enter the email you registered with and we’ll look into it."
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
            Continue
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
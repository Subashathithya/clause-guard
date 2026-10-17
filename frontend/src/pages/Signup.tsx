import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/context';
import { useToast } from '../components/ui/overlays';
import { Button, Field, Input, PasswordInput } from '../components/ui/primitives';
import { AuthLayout } from './AuthLayout';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!fullName.trim()) next.fullName = 'Please enter your name.';
    if (!EMAIL_RE.test(email.trim())) next.email = 'Enter a valid email address.';
    if (password.length < 8) next.password = 'Use at least 8 characters.';
    if (confirm !== password) next.confirm = 'Passwords do not match.';
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
      toast.push('Account created — welcome to ClauseGuard!', 'success');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Sign up failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Create your free account" subtitle="Analyse up to 5 contracts a month, free forever.">
      <form onSubmit={submit} noValidate>
        <Field label="Full name" htmlFor="su-name" error={errors.fullName}>
          <Input
            id="su-name"
            autoComplete="name"
            placeholder="Aarav Sharma"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            invalid={!!errors.fullName}
          />
        </Field>
        <Field label="Email" htmlFor="su-email" error={errors.email}>
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
          label="Password"
          htmlFor="su-password"
          helper="At least 8 characters."
          error={errors.password}
        >
          <PasswordInput
            id="su-password"
            autoComplete="new-password"
            placeholder="Create a password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            invalid={!!errors.password}
          />
        </Field>
        <Field label="Confirm password" htmlFor="su-confirm" error={errors.confirm}>
          <PasswordInput
            id="su-confirm"
            autoComplete="new-password"
            placeholder="Repeat your password"
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
          {submitting ? 'Creating your account…' : 'Create account'}
        </Button>
      </form>
      <p className="text-center text-sm muted mt-4" style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </AuthLayout>
  );
}
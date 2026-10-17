import { Link } from 'react-router-dom';
import { Shield } from 'lucide-react';

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="auth-page">
      <div className="auth-card card card-pad">
        <Link to="/" className="auth-brand" aria-label="ClauseGuard home">
          <span className="brand-shield"><Shield size={18} /></span>
          <span className="auth-brand-name">ClauseGuard</span>
        </Link>
        <div className="auth-head">
          <h1>{title}</h1>
          <p className="muted">{subtitle}</p>
        </div>
        {children}
      </div>
      <p className="text-xs faint text-center auth-foot">
        <Link to="/">← Back to home</Link>
      </p>
    </div>
  );
}
import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export default function NotFound() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--s6)' }}>
      <div className="text-center" style={{ maxWidth: 440 }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 64, height: 64, borderRadius: '50%', background: 'var(--brand-50)', color: 'var(--brand-600)', marginBottom: 'var(--s4)' }}>
          <ShieldAlert size={30} />
        </div>
        <h1>This page got lost in the fine print</h1>
        <p className="muted">We couldn’t find the page you were looking for.</p>
        <div className="row-spread" style={{ justifyContent: 'center', gap: 12 }}>
          <Link to="/dashboard" className="btn btn-primary">Go to Dashboard</Link>
          <Link to="/" className="btn btn-secondary">Back to home</Link>
        </div>
      </div>
    </div>
  );
}
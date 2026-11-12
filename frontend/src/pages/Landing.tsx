import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileQuestion,
  FileSearch,
  FileUp,
  Lock,
  Menu,
  MessageCircleQuestion,
  Shield,
  Sparkles,
  TrendingDown,
  Users,
  X,
} from 'lucide-react';
import InstallCard from '../pwa/InstallCard';
import { useI18n } from '../i18n/I18nProvider';

const NAV_LINKS = [
  { href: '#how', key: 'landing.navHow' },
  { href: '#features', key: 'landing.navFeatures' },
  { href: '#privacy', key: 'landing.navPrivacy' },
  { href: '#faq', key: 'landing.navFaq' },
];

function FaqQ({ q, a }: { q: string; a: string }) {
  return (
    <details className="faq">
      <summary>
        {q}
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <p>{a}</p>
    </details>
  );
}

export default function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { t } = useI18n();

  return (
    <div className="landing">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      {/* ------------------------------------------------ top bar */}
      <header className="lnd-top">
        <Link to="/" className="lnd-logo" aria-label="ClauseGuard home">
          <span className="brand-shield"><Shield size={18} /></span>
          <span>ClauseGuard</span>
        </Link>
        <nav className="lnd-nav" aria-label="Landing navigation">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href}>{t(link.key)}</a>
          ))}
        </nav>
        <div className="lnd-actions">
          <Link to="/login" className="btn btn-ghost btn-sm">{t('nav.signIn')}</Link>
          <Link to="/signup" className="btn btn-primary btn-sm">{t('auth.createAccount')}</Link>
        </div>
        <button
          type="button"
          className="lnd-mobile-toggle"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-controls="landing-mobile-menu"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {menuOpen && (
        <nav id="landing-mobile-menu" className="lnd-mobile-panel" aria-label="Landing navigation">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={() => setMenuOpen(false)}>
              {t(link.key)}
            </a>
          ))}
          <div className="lnd-mobile-auth">
            <Link to="/login" className="btn btn-secondary" onClick={() => setMenuOpen(false)}>{t('nav.signIn')}</Link>
            <Link to="/signup" className="btn btn-primary" onClick={() => setMenuOpen(false)}>{t('nav.createFreeAccount')}</Link>
          </div>
        </nav>
      )}

      <main id="main-content">
        {/* ------------------------------------------------ hero */}
        <section className="lnd-hero">
        <div className="lnd-hero-inner">
          <span className="lnd-eyebrow"><Sparkles size={14} /> {t('landing.eyebrow')}</span>
          <h1 className="lnd-title">
            {t('landing.titleLine1')}
            <br />
            <span className="lnd-accent">{t('landing.titleLine2')}</span>
          </h1>
          <p className="lnd-lead">{t('landing.lead')}</p>
          <div className="lnd-cta-row">
            <Link to="/analyze" className="btn btn-primary btn-lg">
              <FileUp size={18} /> {t('landing.ctaUpload')}
            </Link>
            <Link to="/analyze" className="btn btn-secondary btn-lg">
              <ClipboardList size={18} /> {t('landing.ctaPaste')}
            </Link>
          </div>
          <ul className="lnd-trust" aria-label="Why people use ClauseGuard">
            <li><CheckCircle2 size={15} /> {t('landing.trustFree')}</li>
            <li><CheckCircle2 size={15} /> {t('landing.trustNoAccount')}</li>
            <li><CheckCircle2 size={15} /> {t('landing.trustPlain')}</li>
          </ul>
          <InstallCard placement="landing" />
        </div>

        <div className="lnd-hero-visual" aria-hidden="true">
          <div className="hero-card">
            <div className="hero-card-title">{t('landing.heroDoc')}</div>
            <div className="hero-clause">
              <span className="hero-dot dot-mid" />
              <div>
                <strong>{t('landing.heroSectionDeposit')}</strong>
                <p>{t('landing.heroDepositQuote')}</p>
              </div>
              <span className="hd-att">{t('landing.heroWorthALook')}</span>
            </div>
            <div className="hero-msg">
              <span className="hero-msg-ic"><Sparkles size={14} /></span>
              <p>{t('landing.heroExplain')}</p>
            </div>
            <div className="hero-clause">
              <span className="hero-dot dot-low" />
              <div>
                <strong>{t('landing.heroSectionRent')}</strong>
                <p>{t('landing.heroRentQuote')}</p>
              </div>
              <span className="hd-att att-low2">{t('landing.heroLooksFine')}</span>
            </div>
          </div>
          <div className="hero-note">
            <span className="hero-note-ic"><MessageCircleQuestion size={18} /></span>
            <div>
              <strong>{t('landing.heroAskTitle')}</strong>
              <p>{t('landing.heroAskBody')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ how it works */}
      <section className="lnd-section" id="how">
        <div className="lnd-section-head">
          <h2>{t('landing.howTitle')}</h2>
          <p>{t('landing.howLead')}</p>
        </div>
        <div className="lnd-steps">
          <div className="step">
            <span className="step-num">1</span>
            <h3>{t('landing.step1Title')}</h3>
            <p>{t('landing.step1Body')}</p>
          </div>
          <div className="step">
            <span className="step-num">2</span>
            <h3>{t('landing.step2Title')}</h3>
            <p>{t('landing.step2Body')}</p>
          </div>
          <div className="step">
            <span className="step-num">3</span>
            <h3>{t('landing.step3Title')}</h3>
            <p>{t('landing.step3Body')}</p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ features */}
      <section className="lnd-section lnd-alt" id="features">
        <div className="lnd-section-head">
          <h2>{t('landing.featuresTitle')}</h2>
          <p>{t('landing.featuresLead')}</p>
        </div>
        <div className="lnd-features">
          <div className="feature-card">
            <span className="fc-ic"><FileSearch size={20} /></span>
            <h3>{t('landing.feature1Title')}</h3>
            <p>{t('landing.feature1Body')}</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><MessageCircleQuestion size={20} /></span>
            <h3>{t('landing.feature2Title')}</h3>
            <p>{t('landing.feature2Body')}</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><TrendingDown size={20} /></span>
            <h3>{t('landing.feature3Title')}</h3>
            <p>{t('landing.feature3Body')}</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><Users size={20} /></span>
            <h3>{t('landing.feature4Title')}</h3>
            <p>{t('landing.feature4Body')}</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><Lock size={20} /></span>
            <h3>{t('landing.feature5Title')}</h3>
            <p>{t('landing.feature5Body')}</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><FileQuestion size={20} /></span>
            <h3>{t('landing.feature6Title')}</h3>
            <p>{t('landing.feature6Body')}</p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ example */}
      <section className="lnd-section">
        <div className="lnd-section-head">
          <h2>{t('landing.exampleTitle')}</h2>
          <p>{t('landing.exampleLead')}</p>
        </div>
        <div className="lnd-example">
          <div className="example-orig">
            <span className="tag">{t('landing.exampleOriginal')}</span>
            <p className="quote">{t('landing.exampleQuote')}</p>
          </div>
          <div className="example-plain">
            <span className="tag">{t('landing.examplePlain')}</span>
            <p>{t('landing.examplePlainBody')}</p>
            <span className="att-high badge">{t('landing.exampleReview')}</span>{' '}
            <span className="badge badge-neutral">{t('landing.exampleAutoRenewal')}</span>
          </div>
        </div>
        <p className="text-sm faint text-center" style={{ maxWidth: 560, margin: '0 auto' }}>
          {t('landing.exampleFootnote')}
        </p>
      </section>

      {/* ------------------------------------------------ privacy */}
      <section className="lnd-section lnd-alt" id="privacy">
        <div className="lnd-section-head">
          <h2>{t('landing.privacyTitle')}</h2>
          <p>{t('landing.privacyLead')}</p>
        </div>
        <div className="lnd-privacy">
          <div><strong>{t('landing.privacy1Title')}</strong><p>{t('landing.privacy1Body')}</p></div>
          <div><strong>{t('landing.privacy2Title')}</strong><p>{t('landing.privacy2Body')}</p></div>
          <div><strong>{t('landing.privacy3Title')}</strong><p>{t('landing.privacy3Body')}</p></div>
        </div>
      </section>

      {/* ------------------------------------------------ FAQ */}
      <section className="lnd-section" id="faq">
        <div className="lnd-section-head">
          <h2>{t('landing.faqTitle')}</h2>
        </div>
        <div className="lnd-faq">
          <FaqQ
            q={t('landing.faq1Q')}
            a={t('landing.faq1A')}
          />
          <FaqQ
            q={t('landing.faq2Q')}
            a={t('landing.faq2A')}
          />
          <FaqQ
            q={t('landing.faq3Q')}
            a={t('landing.faq3A')}
          />
          <FaqQ
            q={t('landing.faq4Q')}
            a={t('landing.faq4A')}
          />
          <FaqQ
            q={t('landing.faq5Q')}
            a={t('landing.faq5A')}
          />
        </div>
      </section>

      {/* ------------------------------------------------ final CTA */}
      <section className="lnd-final">
        <h2>{t('landing.finalTitle')}</h2>
        <p>{t('landing.finalLead')}</p>
        <div className="lnd-cta-row">
          <Link to="/analyze" className="btn btn-primary btn-lg">{t('landing.finalCta')}</Link>
        </div>
      </section>
      </main>

      {/* ------------------------------------------------ footer */}
      <footer className="lnd-footer">
        <div className="lnd-footer-inner">
          <div>
            <div className="lnd-logo" style={{ color: '#e2e8f0' }}>
              <span className="brand-shield"><Shield size={18} /></span>
              <span>ClauseGuard</span>
            </div>
            <p className="text-xs faint" style={{ maxWidth: 300 }}>{t('footer.disclaimer')}</p>
          </div>
          <div className="lnd-footer-links">
            <div>
              <strong>{t('landing.footerProduct')}</strong>
              <Link to="/analyze">{t('dashboard.analyzeContract')}</Link>
              <Link to="/dashboard">{t('nav.dashboard')}</Link>
              <Link to="/terms-checker">{t('nav.termsChecker')}</Link>
            </div>
            <div>
              <strong>{t('landing.footerCompany')}</strong>
              <a href="#privacy">{t('landing.footerPrivacy')}</a>
              <a href="#faq">{t('landing.footerFaq')}</a>
            </div>
          </div>
        </div>
        <div className="lnd-copy">
          {new Date().getFullYear()} {t('landing.footerCopy')}
        </div>
      </footer>
    </div>
  );
}
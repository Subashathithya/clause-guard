import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  FileQuestion,
  FileSearch,
  FileUp,
  Lock,
  MessageCircleQuestion,
  Shield,
  Sparkles,
  TrendingDown,
  Users,
} from 'lucide-react';

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
  return (
    <div className="landing">
      {/* ------------------------------------------------ top bar */}
      <header className="lnd-top">
        <Link to="/" className="lnd-logo" aria-label="ClauseGuard home">
          <span className="brand-shield"><Shield size={18} /></span>
          <span>ClauseGuard</span>
        </Link>
        <nav className="lnd-nav" aria-label="Landing navigation">
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#privacy">Privacy</a>
          <a href="#faq">FAQ</a>
        </nav>
        <div className="lnd-actions">
          <Link to="/login" className="btn btn-ghost btn-sm">Sign in</Link>
          <Link to="/signup" className="btn btn-primary btn-sm">Create account</Link>
        </div>
      </header>

      {/* ------------------------------------------------ hero */}
      <section className="lnd-hero">
        <div className="lnd-hero-inner">
          <span className="lnd-eyebrow"><Sparkles size={14} /> Understand any contract in plain English</span>
          <h1 className="lnd-title">
            Confusing contracts,
            <br />
            <span className="lnd-accent">clear answers.</span>
          </h1>
          <p className="lnd-lead">
            Rent agreements, gym memberships, phone plans, job offers, terms &amp; conditions — ClauseGuard
            reads your document, finds the important parts, and explains them the way a friend would.
            In minutes, not days.
          </p>
          <div className="lnd-cta-row">
            <Link to="/analyze" className="btn btn-primary btn-lg">
              <FileUp size={18} /> Upload a contract
            </Link>
            <Link to="/analyze" className="btn btn-secondary btn-lg">
              <ClipboardList size={18} /> Paste a contract
            </Link>
          </div>
          <ul className="lnd-trust" aria-label="Why people use ClauseGuard">
            <li><CheckCircle2 size={15} /> Free to start</li>
            <li><CheckCircle2 size={15} /> No account needed</li>
            <li><CheckCircle2 size={15} /> Plain-language explanations</li>
          </ul>
        </div>

        <div className="lnd-hero-visual" aria-hidden="true">
          <div className="hero-card">
            <div className="hero-card-title">Rent agreement · April 2026</div>
            <div className="hero-clause">
              <span className="hero-dot dot-mid" />
              <div>
                <strong>Section 9 — Security deposit</strong>
                <p>“The deposit shall be withheld until the premises are handed back in original condition…”</p>
              </div>
              <span className="hd-att">Worth a look</span>
            </div>
            <div className="hero-msg">
              <span className="hero-msg-ic"><Sparkles size={14} /></span>
              <p>
                Your deposit can be kept for repairs beyond normal wear and tear. Consider asking what
                “original condition” means before signing.
              </p>
            </div>
            <div className="hero-clause">
              <span className="hero-dot dot-low" />
              <div>
                <strong>Section 3 — Rent payment</strong>
                <p>“Rent is due on the first of every month by bank transfer.”</p>
              </div>
              <span className="hd-att att-low2">Looks fine</span>
            </div>
          </div>
          <div className="hero-note">
            <span className="hero-note-ic"><MessageCircleQuestion size={18} /></span>
            <div>
              <strong>Ask questions about your document</strong>
              <p>“Can I leave early without penalty?” — answered using your contract’s own wording.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ how it works */}
      <section className="lnd-section" id="how">
        <div className="lnd-section-head">
          <h2>How it works</h2>
          <p>Three simple steps. You stay in control the whole time.</p>
        </div>
        <div className="lnd-steps">
          <div className="step">
            <span className="step-num">1</span>
            <h3>Add your contract</h3>
            <p>Upload a PDF, Word, or text file — or just paste the text. There’s no sign-up required.</p>
          </div>
          <div className="step">
            <span className="step-num">2</span>
            <h3>We read it and explain it</h3>
            <p>We identify the important sections, summarise what each one means, and flag the parts that may deserve attention.</p>
          </div>
          <div className="step">
            <span className="step-num">3</span>
            <h3>Ask follow-up questions</h3>
            <p>Not sure about something? Ask questions about your document and get answers grounded in the text you uploaded.</p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ features */}
      <section className="lnd-section lnd-alt" id="features">
        <div className="lnd-section-head">
          <h2>Everything you need to feel confident</h2>
          <p>Built for real people, not legal professionals.</p>
        </div>
        <div className="lnd-features">
          <div className="feature-card">
            <span className="fc-ic"><FileSearch size={20} /></span>
            <h3>Find important clauses</h3>
            <p>We pull out renewals, cancellations, fees, and liability terms so you don’t have to hunt through pages of fine print.</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><MessageCircleQuestion size={20} /></span>
            <h3>Plain-English explanations</h3>
            <p>Every section is translated into everyday language, with a clear note on what to pay attention to.</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><TrendingDown size={20} /></span>
            <h3>See areas that may deserve attention</h3>
            <p>Some clauses are routine, others are worth a second read. We show you which is which — no scare tactics.</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><Users size={20} /></span>
            <h3>Compare two versions</h3>
            <p>Before you sign a new version of a contract you already have, see exactly what changed between them.</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><Lock size={20} /></span>
            <h3>Your documents stay yours</h3>
            <p>Contracts are only used to answer your questions and stay in your private workspace.</p>
          </div>
          <div className="feature-card">
            <span className="fc-ic"><FileQuestion size={20} /></span>
            <h3>Check terms &amp; conditions</h3>
            <p>Paste any terms and conditions and get a readable breakdown of what you’re agreeing to.</p>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------ example */}
      <section className="lnd-section">
        <div className="lnd-section-head">
          <h2>What the explanation looks like</h2>
          <p>A quick example of how we break a clause down.</p>
        </div>
        <div className="lnd-example">
          <div className="example-orig">
            <span className="tag">Original wording</span>
            <p className="quote">
              “This agreement shall automatically renew for successive one-year terms unless either party
              provides written notice of non-renewal at least sixty (60) days prior to expiration.”
            </p>
          </div>
          <div className="example-plain">
            <span className="tag">Plain English</span>
            <p>
              This contract keeps going for another year automatically. If you want it to end, you must
              email or write to them at least 60 days before the year is up.
            </p>
            <span className="att-high badge">Review carefully</span>{' '}
            <span className="badge badge-neutral">Auto-renewal section</span>
          </div>
        </div>
        <p className="text-sm faint text-center" style={{ maxWidth: 560, margin: '0 auto' }}>
          * Example shown for illustration. Results vary by document and are for understanding, not legal advice.
        </p>
      </section>

      {/* ------------------------------------------------ privacy */}
      <section className="lnd-section lnd-alt" id="privacy">
        <div className="lnd-section-head">
          <h2>Your privacy matters</h2>
          <p>Reading a contract is personal. Here’s how we treat yours.</p>
        </div>
        <div className="lnd-privacy">
          <div><strong>Stored in your workspace</strong><p>Uploaded contracts stay in your private workspace and are only used to answer your questions.</p></div>
          <div><strong>No selling your data</strong><p>We don’t sell or share your contracts or personal information with advertisers.</p></div>
          <div><strong>Delete anytime</strong><p>Remove a contract from your workspace whenever you like — it’s a single click.</p></div>
        </div>
      </section>

      {/* ------------------------------------------------ FAQ */}
      <section className="lnd-section" id="faq">
        <div className="lnd-section-head">
          <h2>Frequently asked questions</h2>
        </div>
        <div className="lnd-faq">
          <FaqQ
            q="Is ClauseGuard a legal service?"
            a="No. ClauseGuard is a tool for understanding contracts. It provides AI-assisted explanations and reminders, but it is not legal advice and does not replace a lawyer or qualified professional."
          />
          <FaqQ
            q="Do I need an account to try it?"
            a="No. You can paste or upload a contract and get an analysis without signing up. Creating a free account lets you keep all your contracts in one workspace across visits."
          />
          <FaqQ
            q="What file types can I upload?"
            a="You can upload PDF, Word (.docx), plain text (.txt), and Markdown (.md) files, up to 10 MB each. You can also paste contract text directly."
          />
          <FaqQ
            q="How long does an analysis take?"
            a="Usually under a minute. Larger documents take a little longer because every section is read individually."
          />
          <FaqQ
            q="Can I ask questions after the analysis?"
            a="Yes. Every analysed contract opens a chat where you can ask follow-up questions. Answers are based on the wording in the document you uploaded."
          />
        </div>
      </section>

      {/* ------------------------------------------------ final CTA */}
      <section className="lnd-final">
        <h2>Stop guessing what your contract says</h2>
        <p>Get a clear, plain-English breakdown in minutes.</p>
        <div className="lnd-cta-row">
          <Link to="/analyze" className="btn btn-primary btn-lg">Start now — it’s free</Link>
        </div>
      </section>

      {/* ------------------------------------------------ footer */}
      <footer className="lnd-footer">
        <div className="lnd-footer-inner">
          <div>
            <div className="lnd-logo" style={{ color: '#e2e8f0' }}>
              <span className="brand-shield"><Shield size={18} /></span>
              <span>ClauseGuard</span>
            </div>
            <p className="text-xs faint" style={{ maxWidth: 300 }}>
              ClauseGuard provides AI-assisted contract understanding and is not legal advice. For anything
              important, please review with a qualified professional.
            </p>
          </div>
          <div className="lnd-footer-links">
            <div>
              <strong>Product</strong>
              <Link to="/analyze">Analyze a contract</Link>
              <Link to="/dashboard">Dashboard</Link>
              <Link to="/terms-checker">T&amp;C Checker</Link>
            </div>
            <div>
              <strong>Company</strong>
              <a href="#privacy">Privacy</a>
              <a href="#faq">FAQ</a>
            </div>
          </div>
        </div>
        <div className="lnd-copy">
          {new Date().getFullYear()} ClauseGuard. Made for people who sign things.
          <ArrowRight size={13} style={{ verticalAlign: -2 }} />
        </div>
      </footer>
    </div>
  );
}
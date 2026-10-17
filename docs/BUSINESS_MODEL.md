# Business Model & Roadmap

## Freemium model

| | Free | Premium |
|---|---|---|
| Price | ₹0 | **₹500 / month** |
| Analyses | 5 / month | Unlimited |
| Clause risk analysis | ✅ basic | ✅ full (risk score + ₹ impact) |
| Negotiation packs | ❌ | ✅ counter-clause, talking points, success % |
| Compare contracts | ❌ | ✅ risk matrix (2–5 docs) |
| Policy drift detection | ❌ | ✅ old vs new versions |
| RAG chat | limited | ✅ unlimited, multi-doc |
| File upload (PDF/TXT/DOCX) | ❌ | ✅ |
| Contract history cloud | ❌ | ✅ (Neon Postgres + Firebase storage) |

Set limits via `FREE_TIER_ANALYSES_PER_MONTH` and `PREMIUM_PRICE_INR` in
backend env. Usage counters belong in Postgres:
```sql
CREATE TABLE IF NOT EXISTS usage_counters (
  user_id   TEXT PRIMARY KEY,
  month     TEXT NOT NULL,
  analyses_used INT DEFAULT 0
);
```

## Monetisation roadmap
1. **MVP (done here)** — freemium gates, unlimited premium.
2. **Payments** — Razorpay/Stripe checkout; `premium` flag on user record.
3. **PLG** — free tier is the acquisition engine; conversion driver is "you have
   2 red clauses — unlock the negotiation pack for ₹500/mo".
4. **B2B2B** — API access for consumer-protection orgs, banks, fintech apps
   (white-label risk scoring). Pricier per-analysis tier.
5. **Legal-tech partnerships** — referrals to human lawyers for the "complex
   yellow/red" cases; affiliate revenue.

## KPIs
- Activation: % of analyses that reach "Ask AI" · Con/trigger: red clauses per doc
- Conversion: free→premium rate · Retention: monthly premium churn
- Impact: ₹ saved / user (self-reported), counter-clauses accepted

## Roadmap (prioritised)
1. **User accounts** — Firebase Auth + Neon storage of contracts/history.
2. **Payments** — Razorpay subscription, premium unlock.
3. **Qdrant** for remote vector search (scale-out).
4. **OCR** for image/scanned contracts (tesseract + layout analysis).
5. **Multi-language** (Hindi, Tamil, etc.) explanations via the same prompt
   pipeline — big Indian-market lever.
6. **30–50 real-contract evaluation + regression CI gate** (see EVALUATION.md).
7. **Public dataset release + research paper**.
8. **Reports/export** (PDF analysis summary) for premium.

## Legal note
ClauseGuard is an educational tool, not legal advice. Display a disclaimer in the
UI and docs. Terms-of-service + privacy policy are required before public launch.
"""Phase 1 — hermetic Synthetic evaluation dataset builder.

SYNTHETIC by construction. This is NOT a corpus of real-world legal
contracts and we make no claim that it is representative of real contracts.
Ground truth is explicit per case (``truth.label`` + literal values for
``modified`` pairs) and every case is written deterministically (no seed, no
random, no LLM) so reruns reproduce the exact same dataset.jsonl.

Coverage (each family appears at least once; the 30→60 termination case is
the canonical golden seam and appears first):
* modified — termination-notice duration (30→60 golden), other durations,
  monetary ($), percentage (%), dates, obligations, conditions, exceptions,
  scope/party definitions;
* unchanged — identical text, formatting-only (whitespace/punctuation drift);
* added / removed — clause present in only one version;
* unrelated — category/identity differs so no deterministic pair forms;
* cross-clause variant — two clauses, one relationship (Termination 30→60
  + unchanged Confidentiality neighbour).
"""

from __future__ import annotations

_CONFIDENTIAL_A = "Confidential data must be returned within 30 days of termination."
_CONFIDENTIAL_B = "Confidential data must be returned within 30 days of termination."


def _clause(cid: str, category: str, text: str) -> dict:
    return {"clause_id": cid, "category": category, "text": text,
            "confidence": 0.9}


def _pair(truth_label: str, category: str,
          text_a: str, text_b: str,
          previous: str = "", current: str = "",
          *, id_a: str = "a1", id_b: str = "b1",
          ctx_a: str = "", ctx_b: str = "",
          name: str | None = None) -> dict:
    return {
        "id": name or f"{truth_label}-{category}-{id_a}{id_b}".lower(),
        "old": [_clause(id_a, category, text_a)]
               + ([_clause("a2", "Confidentiality", ctx_a)] if ctx_a else []),
        "new": [_clause(id_b, category, text_b)]
               + ([_clause("b2", "Confidentiality", ctx_b)] if ctx_b else []),
        "truth": {"label": truth_label, "previous_value": previous,
                  "current_value": current},
    }


def _modified(category: str, a: str, b: str, prev: str, cur: str,
              *, ctx_a: str = "", ctx_b: str = "", name: str | None = None) -> dict:
    return _pair("modified", category, a, b, prev, cur,
                 ctx_a=ctx_a, ctx_b=ctx_b, name=name)


def build_cases() -> list[dict]:
    cases: list[dict] = []
    cv_a = "Either party may terminate with 30 days written notice."
    cv_b = "Either party may terminate with 60 days written notice."

    # ── canonical golden — 30 days -> 60 days (single modified) ─────────────
    cases.append(_modified("Termination", cv_a, cv_b, "30 days", "60 days",
                           ctx_a=_CONFIDENTIAL_A, ctx_b=_CONFIDENTIAL_B,
                           name="golden-30-to-60"))

    # ── modified — other durations ──────────────────────────────────────────
    cases.append(_modified("Termination",
        "Either party may terminate with 45 days written notice.",
        "Either party may terminate with 90 days written notice.",
        "45 days", "90 days", ctx_a=_CONFIDENTIAL_A, ctx_b=_CONFIDENTIAL_B))
    cases.append(_modified("Termination",
        "Either party may terminate with 15 business days prior written notice.",
        "Either party may terminate with 30 business days prior written notice.",
        "15 business days", "30 business days"))
    cases.append(_modified("Dispute",
        "Either party must respond to a claim within 10 business days.",
        "Either party must respond to a claim within 20 business days.",
        "10 business days", "20 business days"))

    # ── modified — monetary ─────────────────────────────────────────────────
    cases.append(_modified("Payment",
        "The license fee is $25,000 per calendar year.",
        "The license fee is $90,000 per calendar year.",
        "$25,000", "$90,000"))
    cases.append(_modified("Payment",
        "Renewal increases the fee to $120,000.",
        "Renewal increases the fee to $150,000.",
        "$120,000", "$150,000"))
    cases.append(_modified("Insurance",
        "The policy limit is $1,000,000 per occurrence.",
        "The policy limit is $2,500,000 per occurrence.",
        "$1,000,000", "$2,500,000"))
    cases.append(_modified("Payment",
        "A late fee of $500 applies to overdue invoices.",
        "A late fee of $750 applies to overdue invoices.",
        "$500", "$750"))

    # ── modified — percentage ───────────────────────────────────────────────
    cases.append(_modified("Payment",
        "Service credits accrue at 5% of the monthly fee.",
        "Service credits accrue at 7.5% of the monthly fee.",
        "5%", "7.5%"))
    cases.append(_modified("Payment",
        "Royalties are 8% of net revenue.",
        "Royalties are 12% of net revenue.",
        "8%", "12%"))
    cases.append(_modified("DataProtection",
        "At most 20% of data may be stored outside the region.",
        "At most 10% of data may be stored outside the region.",
        "20%", "10%"))
    cases.append(_modified("Fee",
        "SLA credits return 2% of the fee for each hour of downtime.",
        "SLA credits return 3% of the fee for each hour of downtime.",
        "2%", "3%"))

    # ── modified — dates ────────────────────────────────────────────────────
    cases.append(_modified("Compliance",
        "Audit reports are due on January 15, 2026.",
        "Audit reports are due on February 1, 2027.",
        "January 15, 2026", "February 1, 2027"))
    cases.append(_modified("Delivery",
        "The service go-live date is June 1, 2027.",
        "The service go-live date is September 15, 2027.",
        "June 1, 2027", "September 15, 2027"))

    # ── modified — obligations / conditions / exceptions / scope ────────────
    cases.append(_modified("Obligation",
        "Vendor must return Confidential Data within 45 days of termination.",
        "Vendor must return Confidential Data within 30 days of termination.",
        "45 days", "30 days"))
    cases.append(_modified("Condition",
        "Payment is due 30 days after invoice, provided delivery is accepted.",
        "Payment is due 15 days after invoice, provided delivery is accepted.",
        "30 days", "15 days"))
    cases.append(_modified("Assignability",
        "Either party may assign its rights with written consent.",
        "Neither party may assign its rights without prior written consent.",
        "may assign", "may not assign"))
    cases.append(_modified("Scope",
        "This agreement applies to all Covered Entities of the purchaser.",
        "This agreement applies to all Covered Affiliates of the purchaser.",
        "Covered Entities", "Covered Affiliates"))

    # ── unchanged / formatting-only ────────────────────────────────────────
    cases.append(_pair("unchanged", "Termination",
        "Either party may terminate with 60 days written notice.",
        "  Either party may terminate with 60 days written notice. ",
        id_a="a1", id_b="b1"))
    cases.append(_pair("unchanged", "Confidentiality",
        "Confidential data must be returned within 30 days of termination.",
        "Confidential  data must be   returned within 30 days of termination.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("unchanged", "GoverningLaw",
        "This agreement is governed by the law of Delaware.",
        "This agreement is governed by the law of Delaware.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("unchanged", "Notice",
        "Notices must be sent to the registered address of each party.",
        "Notices must be sent to the registered address of each party.",
        id_a="a1", id_b="b1"))

    # ── added / removed ────────────────────────────────────────────────────
    cases.append(_pair("added", "Indemnification",
        "The warranties section is unchanged.",
        "The warranties section is unchanged. Either party indemnifies the "
        "other against third-party IP claims.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("added", "Renewal",
        "The term is 12 months.",
        "The term is 12 months and renews automatically unless cancelled 90 "
        "days before expiry.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("removed", "Noncompete",
        "The vendor must not compete for 12 months. The vendor may provide "
        "services to third parties without restriction.",
        "The vendor must not compete for 12 months.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("removed", "Confidentiality",
        "All confidential data must be destroyed on termination. "
        "Retention for tax purposes is permitted for 7 years.",
        "All confidential data must be destroyed on termination.",
        id_a="a1", id_b="b1"))
    cases.append(_pair("removed", "Payment",
        "Invoices are due net 30 days. Interest accrues at 1.5% monthly.",
        "Invoices are due net 30 days.",
        id_a="a1", id_b="b1"))

    # ── unrelated — category differs → no deterministic pair ───────────────
    cases.append(_pair("removed", "GoverningLaw",
        "Governing law is Delaware.",
        "Governing law is Delaware.",  # identical, so the golden seam
        id_a="a1", id_b="b1"))
    cases.append(_pair("added", "Miscellaneous",
        "This is a miscellaneous unrelated clause A.",
        "This is a miscellaneous unrelated clause B entirely different.",
        id_a="x1", id_b="y1"))

    return cases

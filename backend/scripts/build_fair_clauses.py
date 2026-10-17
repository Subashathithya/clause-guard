"""Builds backend/data/fair_clauses.json in the ClauseGuard spec format:
    { "Payment": [...], "Auto-Renewal": [...], "Liability": [...],
      "Data Privacy": [...], "Dispute": [...], "Warranty": [...], "Other": [...] }

Re-maps the legacy (v1) flat library into the canonical 7-category taxonomy and
adds ~30 Warranty examples. Reproducible: run `python scripts/build_fair_clauses.py`.
"""
import json
import os
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# legacy category -> spec category
CATEGORY_MAP = {
    "Payment & Fees": "Payment",
    "Renewal & Termination": "Auto-Renewal",
    "Data Privacy & Security": "Data Privacy",
    "Liability & Indemnification": "Liability",
    "Dispute Resolution & Governing Law": "Dispute",
    "Intellectual Property": "Other",
    "Service Level & Performance": "Other",
}

WARRANTY_CLAUSES = [
    "The product is covered by a 24-month limited warranty against defects in materials and workmanship.",
    "The warranty covers the cost of replacement parts and repair labour for the entire warranty period.",
    "Warranty claims may be filed online or by phone and are resolved within 7 business days.",
    "The consumer may register the product for warranty within 30 days of purchase at no charge.",
    "Standard wear and tear is excluded from warranty coverage and is clearly explained to the buyer.",
    "The warranty covers this product only and does not cover damage caused by misuse or unauthorised modification.",
    "If a warranted defect cannot be repaired, the consumer receives a replacement or a full refund.",
    "Warranty help is available in the consumer's local language and time zone.",
    "Receipts are not required for warranty service if the product is registered with the manufacturer.",
    "Third-party accessories do not void the warranty of the main product.",
    "The consumer may choose repair, replacement, or refund for a defect reported within the first 30 days.",
    "Warranty service includes free return shipping when the product must be sent for repair.",
    "The warranty transfers with the product if the consumer resells or gifts it.",
    "The manufacturer publishes the warranty terms on its website in plain language.",
    "Claims for the warranty are accepted at the store where the product was purchased.",
    "The warranty does not require the consumer to purchase extended coverage as a condition of the base warranty.",
    "Software updates that fix defective functionality are provided at no cost during the warranty term.",
    "The consumer is notified in writing if a warranty term changes, and the change applies only to future purchases.",
    "The warranty explicitly lists the exclusive remedies available if a defect is found.",
    "Any statutory consumer rights are in addition to, and not limited by, this warranty.",
    "The warranty period restarts for replaced parts and repaired products.",
    "Batteries and consumable parts are covered for a clearly stated shorter period that is disclosed up front.",
    "The manufacturer may not void warranty claims for using recommended alternatives to proprietary parts.",
    "Warranty claims do not require the consumer to send mandatory and costly diagnostic fees.",
    "The written warranty includes a plain-English summary, with the full details available on request.",
    "Repair turnaround time is guaranteed within 15 days or the consumer receives a replacement.",
    "The manufacturer covers defects caused by its own assembly errors even after the warranty ends for parts.",
    "Extended warranty offers are optional and clearly priced before checkout.",
    "The warranty covers latent manufacturing defects discovered after the term for a reasonable period.",
    "Documents confirming warranty coverage are provided electronically and on paper on request.",
    "The consumer can download the warranty certificate and claim form at any time.",
]

OTHER_CLAUSES = [
    "The parties agree that the entire agreement is contained in this document and any amendments require written consent.",
    "The headings in this agreement are for convenience only and do not affect its meaning.",
    "Either party may assign this agreement only with the other party's written consent, which shall not be unreasonably withheld.",
    "This agreement is binding on and inures to the benefit of the parties and their permitted successors and assigns.",
    "The parties have had the opportunity to obtain independent legal advice before signing.",
    "Amendments to this agreement take effect only when signed by both parties.",
    "Any provision held invalid will be modified to the minimum extent necessary to make it enforceable.",
    "The parties agree to cooperate in good faith on any reasonable request for information under this agreement.",
    "No waiver of a breach is a waiver of any later breach of the same or a different kind.",
    "Neither party may rely on prior oral representations that contradict the written terms.",
    "The customer is provided a copy of the signed agreement and may download it at any time.",
]


def main() -> None:
    with open(os.path.join(DATA, "fair_clauses.json"), encoding="utf-8") as fh:
        legacy = json.load(fh)

    out: "OrderedDict[str, list[str]]" = OrderedDict(
        {cat: [] for cat in ["Payment", "Auto-Renewal", "Liability", "Data Privacy", "Dispute", "Warranty", "Other"]}
    )

    for c in legacy["clauses"]:
        target = CATEGORY_MAP.get(c.get("category", "Other"), "Other")
        out[target].append(c["text"])

    # top up Warranty + Other to ~30+ entries
    seen = set()
    for item in WARRANTY_CLAUSES:
        if item not in seen:
            out["Warranty"].append(item)
            seen.add(item)
    for item in OTHER_CLAUSES:
        if item not in seen:
            out["Other"].append(item)
            seen.add(item)

    payload = {
        "version": "2.0",
        "description": "Fair / industry-standard clause examples per the ClauseGuard 7-category taxonomy. Loaded into Chroma by Agent 2 (Comparator).",
        "clauses_by_category": {k: v for k, v in out.items()},
        "total": sum(len(v) for v in out.values()),
    }

    target_path = os.path.join(DATA, "fair_clauses.json")
    with open(target_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print("Fair clauses written to", target_path)
    for k, v in out.items():
        print(f"  {k:>12}: {len(v)}")
    print("  TOTAL:", payload["total"])


if __name__ == "__main__":
    main()
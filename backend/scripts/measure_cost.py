"""Measure what one analysis actually costs in LLM calls and characters."""
import json
import time

from app.agents.orchestrator import run_orchestrator
from app.observability import observability

TEXT = """RESIDENTIAL LEASE AGREEMENT

1. Rent. Rent is Rs 42,000 per month, due on the 1st. Late payment attracts Rs 1,000 per day.
2. Deposit. An interest-free security deposit of Rs 2,52,000 is refundable within 60 days of vacating, subject to deductions.
3. Repairs. The landlord is responsible for structural repairs; the tenant bears all other repairs regardless of cause.
4. Termination. The landlord may terminate with 30 days' notice for any reason.
5. Notice. The current term ends on 31 March 2027. Either party may end this agreement with 60 days' written notice.
6. Disputes. Courts in Bengaluru have exclusive jurisdiction.
"""

observability.reset()
start = time.perf_counter()
result = run_orchestrator(TEXT, "Lease")
elapsed = time.perf_counter() - start
snapshot = observability.snapshot()

print("clauses:", len(result.clauses))
print("status:", result.status)
print(f"wall clock: {elapsed:.1f}s")
print()
print(json.dumps(snapshot, indent=2)[:2600])

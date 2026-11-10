import os
import pathlib

B = pathlib.Path(r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\backend")

print("=== backend/.env present? key + model mask ===")
env = B / ".env"
if env.exists():
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key in ("GROQ_API_KEY", "PRIMARY_MODEL", "FAST_MODEL"):
            show = val[:6] + "…(" + str(len(val)) + " chars)" if key == "GROQ_API_KEY" else val
            print(f"  {key} = {show}")
else:
    print("  (no .env)")

print()
print("=== load settings through the app's own config ===")
os.chdir(B)
import sys
sys.path.insert(0, str(B))
try:
    from app.settings import settings
    print("  PRIMARY_MODEL =", settings.PRIMARY_MODEL)
    print("  FAST_MODEL    =", settings.FAST_MODEL)
    print("  key set       =", bool(settings.GROQ_API_KEY))
except Exception as e:
    print("  settings import failed:", e)

print()
print("=== call the extractor on realistic contract text to get the REAL cause ===")
from app.agents.extract_agent import ExtractAgent

text = (
    "This Agreement is entered into effective January 1 2026 between the Company and the Customer. "
    "1. Term. This Agreement shall commence on the Effective Date and continue for an initial term "
    "of twelve (12) months. Thereafter this Agreement shall auto-renew unless either party provides "
    "written notice thirty (30) days prior. 2. Payment. Customer shall pay $12,000 per year payable "
    "in advance. Late payments accrue interest at 1.5% per month. 3. Termination. Either party may "
    "terminate upon thirty (30) days written notice. 4. Liability. Neither party shall be liable for "
    "any indirect damages. Total liability shall not exceed the price paid."
)
out = ExtractAgent().extract(text)
print("  total_clauses =", out.total_clauses)
print("  clauses       =", len(out.clauses))
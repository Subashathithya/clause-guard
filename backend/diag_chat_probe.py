import os
import pathlib
import sys

B = pathlib.Path(r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\backend")
os.chdir(B)
sys.path.insert(0, str(B))

from app import llm
from app.settings import settings

print("calling llm.chat(json_mode=True) with", settings.PRIMARY_MODEL)
try:
    raw = llm.chat(
        [{"role": "user", "content": 'Reply with JSON: {"ok": true}'}],
        model=settings.PRIMARY_MODEL,
        json_mode=True,
        max_tokens=64,
    )
    print("chat() OK ->", repr(raw[:120]))
except BaseException as e:
    import traceback
    traceback.print_exc()
    print("=== chat() raised:", type(e).__name__, e)

print()
print("calling llm.chat_json_validated (the extractor path, compact sample)")
try:
    validated, parsed = llm.chat_json_validated(
        [{"role": "system", "content": "You are an extractor."},
         {"role": "user", "content": "Split into clauses: 1. Term 12 months. 2. Pay $100."}],
        model=settings.PRIMARY_MODEL,
        schema=type("S", (), {}),  # placeholder; won't reach validation if transport fails
        stage="extract",
        max_tokens=256,
    )
    print("validated =", validated, "| parsed =", parsed)
except BaseException as e:
    import traceback
    traceback.print_exc()
    print("=== validated raised:", type(e).__name__, e)
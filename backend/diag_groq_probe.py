import os
import pathlib
import sys

B = pathlib.Path(r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\backend")
os.chdir(B)
sys.path.insert(0, str(B))

from app.settings import settings

print("PRIMARY_MODEL =", settings.PRIMARY_MODEL)
print("FAST_MODEL    =", settings.FAST_MODEL)
print("key set       =", bool(settings.GROQ_API_KEY))

import groq

print()
print("=== groq client version ===", end=" ")
try:
    import importlib.metadata
    print(importlib.metadata.version("groq"))
except Exception:
    print("?")

client = groq.Groq(api_key=settings.GROQ_API_KEY)

print("\n=== what models does this key actually offer? ===")
try:
    resp = client.models.list()
    names = sorted(m.id for m in resp.data)
    print("count:", len(names))
    print(*names, sep="\n")
except Exception as e:
    print("list failed:", type(e).__name__, e)

print("\n=== try a REAL chat with the configured model ===")
try:
    c = client.chat.completions.create(
        model=settings.PRIMARY_MODEL,
        messages=[{"role": "user", "content": 'Say hi as JSON: {"ok": true}'}],
        temperature=0.2,
        max_tokens=32,
    )
    print("SUCCESS:", c.choices[0].message.content[:120])
except Exception as e:
    print("FAILED:", type(e).__name__)
    print(e)
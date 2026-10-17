import os
import pathlib
import sys

B = pathlib.Path(r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\backend")
os.chdir(B)
sys.path.insert(0, str(B))

from app.settings import settings
import groq

client = groq.Groq(api_key=settings.GROQ_API_KEY)

js = {"type": "json_object"}
msg = [
    {"role": "system", "content": "Reply only with a JSON object. Use exactly the keys given."},
    {"role": "user", "content": 'Return a JSON object with a single key "ok" set to true. JSON:'},
]
probe = "Probe: " + msg[-1]["content"][:60]

candidates = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "meta-llama/llama-3.3-70b-versatile",
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama-3.1-8b-instant",
    "llama-3.2-3b-preview",
]
for m in candidates:
    try:
        c = client.chat.completions.create(model=m, messages=msg, response_format=js, max_tokens=64, temperature=0.2)
        content = (c.choices[0].message.content or "").strip()
        print(f"OK   {m:<28} -> {content[:70]!r}")
    except Exception as e:
        print(f"FAIL {m:<28} -> {str(e)[:110]}")
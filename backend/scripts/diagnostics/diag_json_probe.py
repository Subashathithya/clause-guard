import os
import pathlib
import sys

B = pathlib.Path(r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\backend")
os.chdir(B)
sys.path.insert(0, str(B))

from app.settings import settings
import groq

client = groq.Groq(api_key=settings.GROQ_API_KEY)

tests = {
    "json_object + system says JSON": (
        [{"role": "system", "content": "You return JSON output only."},
         {"role": "user", "content": 'Return JSON: {"ok": true}'}],
        {"type": "json_object"},
    ),
    "no system, user json only": (
        [{"role": "user", "content": 'Reply only with JSON: {"ok": true}'}],
        {"type": "json_object"},
    ),
    "raw text (no response_format)": (
        [{"role": "user", "content": 'Reply with a JSON object like {"ok": true}'}],
        None,
    ),
}

for name, (msgs, fmt) in tests.items():
    print(f"--- {name} ---")
    for attempts in range(1):
        try:
            kw = {"model": "openai/gpt-oss-120b", "messages": msgs, "max_tokens": 120, "temperature": 0.2}
            if fmt:
                kw["response_format"] = fmt
            c = client.chat.completions.create(**kw)
            print("  content:", repr((c.choices[0].message.content or "")[:140]))
        except Exception as e:
            print("  EXC:", str(e)[:180])
    print()
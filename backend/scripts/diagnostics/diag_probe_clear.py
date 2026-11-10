import re
import urllib.request

FRONT = r"C:\Users\ASUS\OneDrive\Desktop\clasueguard - Copy\frontend"

print("=== live listeners (health probe on :3000 :8000 :8001 :8011) ===")
for port in (3000, 8000, 8001, 8011):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            body = r.read(120).decode("utf-8", "replace")
            print(f"  :{port:<5} -> HTTP {r.status} | {body[:88]}")
    except Exception as e:
        print(f"  :{port:<5} -> DOWN / not answering ({type(e).__name__})")

print("=== frontend/.env.local REACT_APP_API_URL (the line that decides the fetch base) ===")
try:
    with open(FRONT + r"\.env.local", encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    m = re.search(r"(?m)^\s*REACT_APP_API_URL\s*=\s*([^\r\n]+)", content)
    if m:
        url = m.group(1).strip()
        print(f"  -> {url}")
    else:
        print("  (no REACT_APP_API_URL line present)")
        matched = re.findall(r"(?m)^(REACT_[A-Z0-9_]+)\s*=", content)
        print("  env keys present:", matched or "(none)")
except FileNotFoundError:
    print("  .env.local NOT FOUND")

print("=== actual fetch a failing browser does: GET from :8000 WITH Origin header ===")
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/health",
        headers={"Origin": "http://localhost:3000"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        acao = r.headers.get("Access-Control-Allow-Origin")
        print(f"  -> HTTP {r.status} | ACAO={acao!r}")
except Exception as e:
    print(f"  -> FAIL {type(e).__name__}: {e}")

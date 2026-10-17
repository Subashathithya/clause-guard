import urllib.request

print("=== UI :3000 (root index.html) ===")
try:
    req = urllib.request.Request("http://127.0.0.1:3000/", headers={"Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=8) as r:
        body = r.read(2000).decode("utf-8", "replace")
        head = body[:400].replace("\n", " ")
        print(f"  HTTP {r.status} | {head}")
except Exception as e:
    print(f"  FAIL {type(e).__name__}: {e}")

print("=== API :8000 /health (from Origin :3000, like the browser) ===")
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/health",
        headers={"Origin": "http://localhost:3000"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        print(f"  HTTP {r.status} | ACAO={r.headers.get('Access-Control-Allow-Origin')!r} | {r.read(90).decode()}")
except Exception as e:
    print(f"  FAIL {type(e).__name__}: {e}")

print("=== fetch base as compiled into the bundle ===")
import urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:3000/static/js/main.js", timeout=10) as r:
        js = r.read(50_000).decode("utf-8", "replace")
except Exception:
    js = ""
print("  '127.0.0.1:8000' in main.js:", ("127.0.0.1:8000" in js))
print("  'localhost:8011'   in main.js:", ("localhost:8011" in js))